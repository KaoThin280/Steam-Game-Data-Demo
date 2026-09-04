"""Thin RPC-style HTTP transport for the transport-neutral agent harness."""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_harness.mcp import HTTPMCPGateway
from app.agent_harness.provider import OpenRouterProvider
from app.agent_harness.runtime import AgentRuntime
from app.agent_harness.store import PostgresRunStore
from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import AsyncSessionLocal, get_db
from app.models.agent import AgentEvent, AgentRun, AgentSession
from app.models.user import AppUser
from app.services.error_notification_service import error_notification_service

router = APIRouter(prefix="/agent-rpc", tags=["Agent Harness RPC"])
_tasks: dict[str, asyncio.Task] = {}
logger = logging.getLogger(__name__)


class CreateSessionRequest(BaseModel):
    title: str | None = Field(None, max_length=200)


class RenameSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Session title cannot be blank")
        return value


class SendTaskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


async def _owned_session(db: AsyncSession, session_id: uuid.UUID, user_id: int) -> AgentSession:
    row = await db.scalar(select(AgentSession).where(AgentSession.id == session_id, AgentSession.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return row


async def _owned_run(db: AsyncSession, run_id: uuid.UUID, user_id: int) -> AgentRun:
    row = await db.scalar(select(AgentRun).join(AgentSession).where(AgentRun.id == run_id, AgentSession.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return row


async def _execute(run_id: str, session_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        owner_id = await db.scalar(select(AgentSession.user_id).where(AgentSession.id == session_id))
        if owner_id is None:
            return
        recent = (await db.scalars(
            select(AgentRun)
            .where(
                AgentRun.session_id == session_id,
                AgentRun.status == "completed",
            )
            .order_by(AgentRun.created_at.desc())
            .limit(settings.AGENT_HISTORY_RUNS)
        )).all()
        runs = list(reversed(recent))
        current = await db.scalar(select(AgentRun).where(AgentRun.id == uuid.UUID(run_id)))
        if current is not None:
            runs.append(current)
        history = []
        for run in runs:
            history.append({"role": "user", "content": run.input_text})
            if run.output_text:
                history.append({"role": "assistant", "content": run.output_text})
    runtime = AgentRuntime(
        OpenRouterProvider(),
        HTTPMCPGateway(
            settings.MCP_SERVER_URL,
            settings.MCP_SHARED_SECRET,
            settings.AGENT_TOOL_TIMEOUT,
            agent_context={"user_id": owner_id, "session_id": str(session_id), "run_id": run_id},
        ),
        PostgresRunStore(),
        max_steps=settings.AGENT_MAX_STEPS,
        tool_timeout=settings.AGENT_TOOL_TIMEOUT,
    )
    try:
        await runtime.execute(run_id, history)
        try:
            async with AsyncSessionLocal() as status_db:
                failed_run = await status_db.scalar(
                    select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
                )
                if failed_run is not None and failed_run.status == "failed":
                    error_notification_service.schedule(
                        component="agent.run",
                        error=failed_run.error_message or failed_run.error_code or "Agent run failed",
                        context={
                            "run_id": run_id,
                            "session_id": str(session_id),
                            "error_code": failed_run.error_code or "UNKNOWN",
                        },
                    )
        except Exception as notification_lookup_error:
            logger.warning("Could not inspect failed run for notification: %s", notification_lookup_error)
    finally:
        _tasks.pop(run_id, None)


def _schedule_run(run_id: str, session_id: uuid.UUID) -> None:
    existing = _tasks.get(run_id)
    if existing and not existing.done():
        return
    _tasks[run_id] = asyncio.create_task(
        _execute(run_id, session_id), name=f"agent-run-{run_id}"
    )


async def recover_orphaned_runs() -> int:
    """Requeue read-only agent runs orphaned by a process/VPS restart."""
    store = PostgresRunStore()
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(
            select(AgentRun)
            .where(AgentRun.status.in_(("queued", "running")))
            .order_by(AgentRun.created_at)
        )).all()
        recoverable = []
        for run in rows:
            if run.cancel_requested:
                run.status = "cancelled"
                run.completed_at = datetime.now(timezone.utc)
            else:
                run.status = "queued"
                run.error_code = None
                run.error_message = None
                recoverable.append((str(run.id), run.session_id))
        await db.commit()
    for run_id, session_id in recoverable:
        await store.append_event(run_id, "run.recovered", {"reason": "backend_restart"})
        _schedule_run(run_id, session_id)
    return len(recoverable)


async def interrupt_live_runs_for_shutdown() -> None:
    """Let runtimes persist `queued` before database pools are disposed."""
    tasks = [task for task in _tasks.values() if not task.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(payload: CreateSessionRequest, user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    row = AgentSession(user_id=user.id, title=payload.title, status="active")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"session_id": str(row.id), "status": row.status, "created_at": row.created_at}


@router.get("/sessions")
async def list_sessions(user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(AgentSession).where(AgentSession.user_id == user.id).order_by(AgentSession.updated_at.desc()).limit(50))).all()
    return [{"session_id": str(x.id), "title": x.title, "status": x.status, "updated_at": x.updated_at} for x in rows]


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID, user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    session = await _owned_session(db, session_id, user.id)
    runs = (await db.scalars(
        select(AgentRun)
        .where(AgentRun.session_id == session_id)
        .order_by(AgentRun.created_at)
        .limit(200)
    )).all()
    return {
        "session_id": str(session.id),
        "title": session.title,
        "status": session.status,
        "runs": [
            {
                "run_id": str(run.id),
                "input": run.input_text,
                "output": run.output_text,
                "status": run.status,
                "created_at": run.created_at,
            }
            for run in runs
        ],
    }


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: uuid.UUID,
    payload: RenameSessionRequest,
    user: AppUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename an owned persistent agent session."""
    session = await _owned_session(db, session_id, user.id)
    session.title = payload.title
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return {
        "session_id": str(session.id),
        "title": session.title,
        "status": session.status,
        "updated_at": session.updated_at,
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    user: AppUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an owned session and its runs/events through DB cascades."""
    session = await _owned_session(db, session_id, user.id)
    active = await db.scalar(
        select(AgentRun.id).where(
            AgentRun.session_id == session_id,
            AgentRun.status.in_(("queued", "running")),
        ).limit(1)
    )
    if active is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancel the active run before deleting this session",
        )
    await db.delete(session)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/tasks", status_code=status.HTTP_202_ACCEPTED)
async def send_task(session_id: uuid.UUID, payload: SendTaskRequest, request: Request, user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await rate_limit(request, limit=settings.RATE_LIMIT_AI_PER_MINUTE, window=60, bucket="agent-rpc")
    await _owned_session(db, session_id, user.id)
    active = await db.scalar(
        select(AgentRun.id).where(
            AgentRun.session_id == session_id,
            AgentRun.status.in_(("queued", "running")),
        ).limit(1)
    )
    if active is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session already has active run {active}",
        )
    run = AgentRun(session_id=session_id, input_text=payload.message, status="queued", max_steps=settings.AGENT_MAX_STEPS)
    db.add(run)
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await db.commit()
    await db.refresh(run)
    run_id = str(run.id)
    _schedule_run(run_id, session_id)
    return {"run_id": run_id, "session_id": str(session_id), "status": "queued"}


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    run = await _owned_run(db, run_id, user.id)
    return {"run_id": str(run.id), "session_id": str(run.session_id), "status": run.status, "current_step": run.current_step, "max_steps": run.max_steps, "output": run.output_text, "error": {"code": run.error_code, "message": run.error_message} if run.error_code else None, "cancel_requested": run.cancel_requested}


@router.get("/runs/{run_id}/events")
async def get_events(run_id: uuid.UUID, after: int = Query(0, ge=0), user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await _owned_run(db, run_id, user.id)
    rows = (await db.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id, AgentEvent.sequence > after).order_by(AgentEvent.sequence).limit(500))).all()
    return [{"sequence": x.sequence, "type": x.event_type, "payload": x.payload, "created_at": x.created_at} for x in rows]


@router.get("/runs/{run_id}/stream")
async def stream_events(run_id: uuid.UUID, request: Request, user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await _owned_run(db, run_id, user.id)
    async def generate():
        try:
            cursor = max(0, int(request.headers.get("last-event-id", "0")))
        except ValueError:
            cursor = 0
        while True:
            async with AsyncSessionLocal() as session:
                rows = (await session.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id, AgentEvent.sequence > cursor).order_by(AgentEvent.sequence))).all()
                run_status = await session.scalar(select(AgentRun.status).where(AgentRun.id == run_id))
            for event in rows:
                cursor = event.sequence
                yield f"id: {cursor}\nevent: {event.event_type}\ndata: {json.dumps(event.payload, default=str)}\n\n"
            if run_status in ("completed", "failed", "cancelled") and not rows:
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.75)
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_run(run_id: uuid.UUID, user: AppUser = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    run = await _owned_run(db, run_id, user.id)
    if run.status in ("completed", "failed", "cancelled"):
        return {"run_id": str(run_id), "status": run.status}
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AgentRun)
        .where(
            AgentRun.id == run_id,
            AgentRun.status.in_(("queued", "running")),
        )
        .values(
            cancel_requested=True,
            status="cancelled",
            completed_at=now,
            updated_at=now,
        )
    )
    await db.commit()
    await PostgresRunStore().append_event(
        str(run_id), "cancellation.requested", {"source": "rpc"}
    )
    task = _tasks.get(str(run_id))
    if task:
        task.cancel()
    return {"run_id": str(run_id), "status": "cancelled"}
