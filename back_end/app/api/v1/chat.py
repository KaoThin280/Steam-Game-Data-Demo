"""
Data-Analyst chat API.

POST /api/v1/chat          - run full agentic workflow
POST /api/v1/chat/stream   - simple streaming text
GET  /api/v1/chat/sessions - list previous sessions
GET  /api/v1/chat/files    - list generated artifacts in temp_data/

The workflow:
  - reads the SQL tables (games / reviews / users) only via the read-only gateway
  - lets the LLM run Python in the E2B sandbox for charts / aggregations
  - up to 4 retries on code execution failure
"""
import os
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import AppUser, ChatHistory
from app.services.agentic_workflow import AgenticWorkflow

router = APIRouter(prefix="/chat", tags=["Data Analyst Chat"])


# ---------------- Schemas ----------------
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """User-facing response for the E2B / Python agent.

    Only contains the final natural-language reply, the session id, the
    produced artifact filenames, and the status flag. Internal details
    (raw Python ``code``, execution ``logs``, ``events`` tool-call trace,
    ``error_message`` traceback, ``retries_used`` counter) are kept on the
    server for logging only and are NOT exposed here.
    """

    status: str
    user_response: str
    new_files: List[str] = []
    session_id: str


class SessionItem(BaseModel):
    session_id: str
    last_active: Optional[str] = None
    turn_count: int = 0


# ---------------- Dependency ----------------
async def get_workflow(
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_user),
) -> AgenticWorkflow:
    return AgenticWorkflow(db=db, user_id=current_user.id)


# ---------------- Endpoints ----------------
@router.post(
    "",
    response_model=ChatResponse,
    summary="Run the agentic data-analyst workflow.",
)
async def chat(
    request: Request,
    payload: ChatRequest,
    workflow: AgenticWorkflow = Depends(get_workflow),
):
    """Ask the AI agent a question. The agent may query the SQL gateway and/or
    run Python in E2B (with up to 3 retries on failure). The endpoint returns
    ONLY the final natural-language answer - tool/code/error details are
    kept server-side for logging."""
    await rate_limit(request, limit=10, window=60, bucket="ai-chat-agent")
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    session_id = payload.session_id or f"session_{workflow.user_id}_{int(time.time())}"
    result = await workflow.run(payload.message, session_id=session_id)
    return ChatResponse(
        status=result.get("status", "success"),
        user_response=result.get("user_response", ""),
        new_files=result.get("new_files", []),
        session_id=session_id,
    )


@router.post(
    "/stream",
    summary="Streaming text chat (no tool use, faster).",
)
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    workflow: AgenticWorkflow = Depends(get_workflow),
):
    await rate_limit(request, limit=15, window=60, bucket="ai-chat-stream")
    session_id = payload.session_id or f"session_{workflow.user_id}_{int(time.time())}"

    async def _gen():
        try:
            async for chunk in workflow.stream_chat(payload.message, session_id=session_id):
                safe = chunk.replace("\n", "\\n")
                yield f"data: {safe}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e).replace(chr(10), ' ')}\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/sessions",
    response_model=List[SessionItem],
    summary="List my chat sessions.",
)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: AppUser = Depends(get_current_active_user),
):
    # group by session_id, take the most recent chat per session
    stmt = (
        select(
            ChatHistory.session_id,
            func.max(ChatHistory.created_at).label("last_active"),
            func.count(ChatHistory.id).label("turn_count"),
        )
        .where(ChatHistory.user_id == current_user.id)
        .group_by(ChatHistory.session_id)
        .order_by(func.max(ChatHistory.created_at).desc())
        .limit(50)
    )
    rows = (await db.execute(stmt)).all()
    return [
        SessionItem(
            session_id=r.session_id,
            last_active=r.last_active.isoformat() if r.last_active else None,
            turn_count=r.turn_count,
        )
        for r in rows
    ]


@router.get(
    "/files",
    summary="List artifacts generated by the AI agent (in temp_data/).",
)
async def list_files(
    _user: AppUser = Depends(get_current_active_user),
):
    temp_dir = Path(settings.TEMP_DATA_DIR)
    if not temp_dir.exists():
        return {"files": []}
    files = []
    for f in sorted(temp_dir.iterdir()):
        if f.is_file() and f.stat().st_size > 0:
            files.append(
                {
                    "name": f.name,
                    "size": f.stat().st_size,
                    "url": f"/api/v1/chat/files/{f.name}",
                    "modified": f.stat().st_mtime,
                }
            )
    return {"files": files}
