"""Transport-neutral types for the agent loop."""
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


RunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ModelTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class ModelProvider(Protocol):
    async def next_turn(
        self, messages: list[dict[str, Any]], tools: list[ToolDefinition]
    ) -> ModelTurn: ...


class ToolGateway(Protocol):
    async def list_tools(self) -> list[ToolDefinition]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class RunStore(Protocol):
    async def set_status(self, run_id: str, status: RunStatus, **fields: Any) -> None: ...
    async def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int: ...
    async def is_cancel_requested(self, run_id: str) -> bool: ...
