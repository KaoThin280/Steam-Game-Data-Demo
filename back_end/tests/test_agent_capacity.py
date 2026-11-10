import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.api.v1 import agent_rpc
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_only_configured_number_of_runs_load_history_and_execute(monkeypatch):
    monkeypatch.setattr(agent_rpc, "_run_slots", asyncio.Semaphore(2))
    release = asyncio.Event()
    started = []
    async def execute(run_id, session_id):
        started.append(run_id)
        await release.wait()
    monkeypatch.setattr(agent_rpc, "_execute", execute)
    tasks = [asyncio.create_task(agent_rpc._execute_with_slot(str(i), uuid.uuid4())) for i in range(3)]
    await asyncio.sleep(0)
    assert len(started) == 2
    release.set()
    await asyncio.gather(*tasks)
    assert len(started) == 3


@pytest.mark.asyncio
async def test_shutdown_waiting_local_run_is_cancelled(monkeypatch):
    monkeypatch.setattr(agent_rpc, "_run_slots", asyncio.Semaphore(0))
    monkeypatch.setattr(agent_rpc.settings, "AGENT_RECOVERY_ENABLED", False)
    statuses = []
    class Store:
        async def set_status(self, run, status, **fields):
            statuses.append((status, fields))
        async def append_event(self, *args):
            pass
    monkeypatch.setattr(agent_rpc, "PostgresRunStore", Store)
    task = asyncio.create_task(agent_rpc._execute_with_slot("waiting", uuid.uuid4()))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert statuses == [("cancelled", {"cancel_requested": True})]


@pytest.mark.asyncio
async def test_full_pending_queue_rejects_before_inserting_run(monkeypatch):
    monkeypatch.setattr(agent_rpc, "_submission_lock", asyncio.Lock())
    monkeypatch.setattr(agent_rpc.settings, "AGENT_MAX_PENDING_RUNS", 1)
    monkeypatch.setattr(agent_rpc, "_tasks", {"busy": SimpleNamespace(done=lambda: False)})
    async def noop(*args, **kwargs):
        pass
    monkeypatch.setattr(agent_rpc, "rate_limit", noop)
    monkeypatch.setattr(agent_rpc, "_owned_session", noop)
    with pytest.raises(HTTPException) as error:
        await agent_rpc.send_task(uuid.uuid4(), agent_rpc.SendTaskRequest(message="test"), None, SimpleNamespace(id=1), None)
    assert error.value.status_code == 503
    assert error.value.headers["Retry-After"] == "10"
