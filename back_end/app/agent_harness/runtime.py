"""Bounded, framework-free multi-step agent loop."""
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from app.agent_harness.types import ModelProvider, RunStore, ToolGateway
from app.core.config import settings


SYSTEM_PROMPT = """You are the Steam Game Data system's bounded data analyst agent.

Data model: games(steam_appid PK, name, is_free, required_age, release_date, publishers, developers, price_text, created_at); users(steamid PK, personaname, num_games_owned, created_at); reviews(recommendationid PK, steam_appid FK games, steamid FK users, language, review_text, timestamps, refund/free/early-access/deck flags, playtime fields); dimensions genres/categories/languages(id,name); junctions game_genres/game_categories/game_languages link steam_appid to the corresponding dimension id. Application auth, RBAC, tokens, and agent trace tables are deliberately unavailable.

Act as a careful data analyst: clarify the metric and time range from the current request, inspect a table with describe_steam_table when schema or distributions are uncertain, use aggregate SQL for factual answers, and use analyze_with_python for transformations/statistics/charts that benefit from Python. The Python tool receives a bounded DataFrame inside E2B; raw rows stay out of your context and you receive only its compact result. Never request or expose an entire dataset, secrets, auth data, or row dumps. Select only necessary columns, filter/aggregate early, and treat samples as examples rather than representative facts.

For charts, honor the user's requested chart type. First call search_saved_charts when cached results are acceptable; use get_saved_chart for a suitable match, otherwise use create_chart or a specialized chart tool. The UI renders the structured chart automatically. Do not fabricate chart URLs, duplicate the chart as a long Markdown table, or claim a filter unless the tool result confirms it. Never invent database values. If a tool fails, inspect its structured error and recover with a corrected call or explain the limitation. When asked who you are, explain this role and approved capabilities. Reply strictly in {language}; do not switch languages because of older messages."""


def _response_language(history: list[dict[str, Any]]) -> str:
    current = str(history[-1].get("content", "")) if history else ""
    vietnamese_markers = set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
    if any(char in vietnamese_markers for char in current.lower()):
        return "Vietnamese"
    return "English"


class AgentRuntime:
    def __init__(self, provider: ModelProvider, tools: ToolGateway, store: RunStore, *, max_steps: int = 8, tool_timeout: float = 15.0) -> None:
        self.provider, self.tools, self.store = provider, tools, store
        self.max_steps, self.tool_timeout = max_steps, tool_timeout

    async def execute(self, run_id: str, history: list[dict[str, Any]]) -> None:
        await self.store.set_status(
            run_id, "running", started_at=datetime.now(timezone.utc)
        )
        await self.store.append_event(run_id, "run.started", {})
        language = _response_language(history)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(language=language)},
            *history,
        ]
        try:
            definitions = await self.tools.list_tools()
            completed_calls: set[str] = set()
            for step in range(1, self.max_steps + 1):
                if await self.store.is_cancel_requested(run_id):
                    await self.store.append_event(run_id, "run.cancelled", {"step": step})
                    await self.store.set_status(run_id, "cancelled")
                    return
                await self.store.append_event(run_id, "model.requested", {"step": step})
                turn = await self.provider.next_turn(messages, definitions)
                if await self.store.is_cancel_requested(run_id):
                    await self.store.append_event(run_id, "run.cancelled", {"step": step})
                    await self.store.set_status(run_id, "cancelled")
                    return
                await self.store.append_event(run_id, "model.responded", {"step": step, "text": turn.text, "tool_calls": [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in turn.tool_calls]})
                if not turn.tool_calls:
                    answer = turn.text.strip() or "The agent completed without a textual response."
                    await self.store.set_status(run_id, "completed", output_text=answer, current_step=step)
                    await self.store.append_event(run_id, "run.completed", {"answer": answer})
                    return
                messages.append({"role": "assistant", "content": turn.text or None, "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}} for c in turn.tool_calls]})
                for call in turn.tool_calls:
                    await self.store.append_event(run_id, "tool.started", {"step": step, "tool_call_id": call.id, "name": call.name, "arguments": call.arguments})
                    signature = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, default=str)}"
                    if signature in completed_calls:
                        result = {"ok": False, "error": {"code": "DUPLICATE_TOOL_CALL", "message": "The identical tool call already completed in this run; use its prior result or change the arguments."}}
                    else:
                        timeout = max(self.tool_timeout, settings.E2B_TIMEOUT + 15) if call.name == "analyze_with_python" else self.tool_timeout
                        result = await asyncio.wait_for(self.tools.call_tool(call.name, call.arguments), timeout)
                        completed_calls.add(signature)
                    await self.store.append_event(run_id, "tool.finished", {"step": step, "tool_call_id": call.id, "name": call.name, "result": result})
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, default=str)})
                await self.store.set_status(run_id, "running", current_step=step)
            message = f"Run exceeded the configured limit of {self.max_steps} steps."
            await self.store.append_event(run_id, "run.failed", {"code": "MAX_STEPS", "message": message})
            await self.store.set_status(run_id, "failed", error_code="MAX_STEPS", error_message=message)
        except asyncio.CancelledError:
            # Explicit RPC cancellation persists cancel_requested first. A task
            # cancelled without that flag is an API shutdown and must remain
            # recoverable on the next startup.
            if await self.store.is_cancel_requested(run_id):
                await self.store.set_status(run_id, "cancelled")
                await self.store.append_event(run_id, "run.cancelled", {"source": "task"})
            else:
                await self.store.set_status(run_id, "queued")
                await self.store.append_event(run_id, "run.interrupted", {"reason": "process_shutdown"})
        except Exception as exc:
            await self.store.append_event(run_id, "run.failed", {"code": "RUNTIME_ERROR", "message": str(exc)})
            await self.store.set_status(run_id, "failed", error_code="RUNTIME_ERROR", error_message=str(exc))
