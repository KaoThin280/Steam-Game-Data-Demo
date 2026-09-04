"""PostgreSQL persistence adapter for inspectable/resumable runs."""
from datetime import datetime, timezone
from typing import Any
import uuid
import json

from sqlalchemy import select, text, update

from app.agent_harness.types import RunStatus
from app.db.session import AsyncSessionLocal
from app.models.agent import AgentEvent, AgentRun
from app.core.config import settings


class PostgresRunStore:
    async def set_status(self, run_id: str, status: RunStatus, **fields: Any) -> None:
        run_uuid = uuid.UUID(str(run_id))
        values = {"status": status, "updated_at": datetime.now(timezone.utc), **fields}
        if status in ("completed", "failed", "cancelled"):
            values["completed_at"] = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            await db.execute(update(AgentRun).where(AgentRun.id == run_uuid).values(**values))
            await db.commit()

    async def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int:
        run_uuid = uuid.UUID(str(run_id))
        encoded = json.dumps(payload, default=str).encode("utf-8")
        if len(encoded) > settings.AGENT_EVENT_MAX_BYTES:
            payload = {
                "truncated": True,
                "original_bytes": len(encoded),
                "preview": encoded[: settings.AGENT_EVENT_MAX_BYTES].decode(
                    "utf-8", errors="replace"
                ),
            }
        async with AsyncSessionLocal() as db:
            # Serializes runtime and cancellation writers for the same run so
            # (run_id, sequence) remains deterministic under concurrency.
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:run_id))"),
                {"run_id": str(run_uuid)},
            )
            last = await db.scalar(select(AgentEvent.sequence).where(AgentEvent.run_id == run_uuid).order_by(AgentEvent.sequence.desc()).limit(1))
            event = AgentEvent(run_id=run_uuid, sequence=(last or 0) + 1, event_type=event_type, payload=payload)
            db.add(event)
            await db.commit()
            return event.sequence

    async def is_cancel_requested(self, run_id: str) -> bool:
        run_uuid = uuid.UUID(str(run_id))
        async with AsyncSessionLocal() as db:
            value = await db.scalar(select(AgentRun.cancel_requested).where(AgentRun.id == run_uuid))
            return bool(value)
