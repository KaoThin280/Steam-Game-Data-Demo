import asyncio

import pytest

from app.agent_harness.runtime import AgentRuntime, _response_language
from app.agent_harness.types import ModelTurn, ToolCall, ToolDefinition


class FakeStore:
    def __init__(self, cancel=False):
        self.status = "queued"
        self.events = []
        self.cancel = cancel

    async def set_status(self, _run_id, status, **fields):
        self.status = status
        self.fields = fields

    async def append_event(self, _run_id, event_type, payload):
        self.events.append((event_type, payload))
        return len(self.events)

    async def is_cancel_requested(self, _run_id):
        return self.cancel


class FakeTools:
    async def list_tools(self):
        return [ToolDefinition("lookup", "lookup", {"type": "object"})]

    async def call_tool(self, name, arguments):
        if name != "lookup":
            return {"ok": False, "error": {"code": "TOOL_NOT_FOUND"}}
        return {"ok": True, "content": {"value": arguments["value"]}}


class ScriptedProvider:
    def __init__(self, turns):
        self.turns = iter(turns)
        self.messages = []

    async def next_turn(self, messages, _tools):
        self.messages = messages
        return next(self.turns)


@pytest.mark.asyncio
async def test_multi_step_tool_result_is_fed_back():
    provider = ScriptedProvider([
        ModelTurn(tool_calls=[ToolCall("call-1", "lookup", {"value": 42})]),
        ModelTurn(text="The answer is 42."),
    ])
    store = FakeStore()
    await AgentRuntime(provider, FakeTools(), store).execute("run-1", [{"role": "user", "content": "answer"}])
    assert store.status == "completed"
    assert store.fields["output_text"] == "The answer is 42."
    assert any(message["role"] == "tool" and '"value": 42' in message["content"] for message in provider.messages)
    assert [event for event, _ in store.events].count("tool.finished") == 1


@pytest.mark.asyncio
async def test_cancel_before_first_model_call():
    store = FakeStore(cancel=True)
    provider = ScriptedProvider([])
    await AgentRuntime(provider, FakeTools(), store).execute("run-1", [{"role": "user", "content": "stop"}])
    assert store.status == "cancelled"
    assert "run.cancelled" in [event for event, _ in store.events]


@pytest.mark.asyncio
async def test_max_steps_stops_infinite_tool_loop():
    provider = ScriptedProvider([ModelTurn(tool_calls=[ToolCall(str(i), "lookup", {"value": i})]) for i in range(3)])
    store = FakeStore()
    await AgentRuntime(provider, FakeTools(), store, max_steps=3).execute("run-1", [{"role": "user", "content": "loop"}])
    assert store.status == "failed"
    assert store.fields["error_code"] == "MAX_STEPS"


@pytest.mark.asyncio
async def test_tool_failure_is_visible_to_next_model_turn():
    provider = ScriptedProvider([
        ModelTurn(tool_calls=[ToolCall("bad", "missing", {})]),
        ModelTurn(text="I could not use that unavailable tool."),
    ])
    store = FakeStore()
    await AgentRuntime(provider, FakeTools(), store).execute("run-1", [{"role": "user", "content": "fail"}])
    assert store.status == "completed"
    assert any("TOOL_NOT_FOUND" in (message.get("content") or "") for message in provider.messages)


@pytest.mark.asyncio
async def test_runtime_task_can_be_cancelled_cleanly():
    class SlowProvider:
        async def next_turn(self, *_args):
            await asyncio.sleep(10)

    store = FakeStore()
    task = asyncio.create_task(AgentRuntime(SlowProvider(), FakeTools(), store).execute("run-1", []))
    await asyncio.sleep(0)
    store.cancel = True
    task.cancel()
    await task
    assert store.status == "cancelled"


@pytest.mark.asyncio
async def test_process_interruption_requeues_run_for_startup_recovery():
    class SlowProvider:
        async def next_turn(self, *_args):
            await asyncio.sleep(10)

    store = FakeStore(cancel=False)
    task = asyncio.create_task(AgentRuntime(SlowProvider(), FakeTools(), store).execute("run-1", []))
    await asyncio.sleep(0)
    task.cancel()
    await task
    assert store.status == "queued"
    assert "run.interrupted" in [event for event, _ in store.events]


def test_response_language_uses_current_turn_not_old_history():
    history = [
        {"role": "user", "content": "Bạn là ai?"},
        {"role": "assistant", "content": "Tôi là trợ lý."},
        {"role": "user", "content": "Who are you?"},
    ]
    assert _response_language(history) == "English"
    history[-1] = {"role": "user", "content": "Bạn là ai?"}
    assert _response_language(history) == "Vietnamese"


@pytest.mark.asyncio
async def test_identical_tool_call_is_not_executed_twice():
    class CountingTools(FakeTools):
        def __init__(self):
            self.calls = 0

        async def call_tool(self, name, arguments):
            self.calls += 1
            return await super().call_tool(name, arguments)

    tools = CountingTools()
    provider = ScriptedProvider([
        ModelTurn(tool_calls=[ToolCall("call-1", "lookup", {"value": 42})]),
        ModelTurn(tool_calls=[ToolCall("call-2", "lookup", {"value": 42})]),
        ModelTurn(text="Done."),
    ])
    store = FakeStore()
    await AgentRuntime(provider, tools, store).execute("run-1", [{"role": "user", "content": "answer"}])
    assert tools.calls == 1
    assert any("DUPLICATE_TOOL_CALL" in (message.get("content") or "") for message in provider.messages)
