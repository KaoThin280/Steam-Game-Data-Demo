"""LLM boundary. The runtime has no dependency on OpenAI/OpenRouter."""
import json
from typing import Any

from openai import AsyncOpenAI

from app.agent_harness.types import ModelTurn, ToolCall, ToolDefinition
from app.core.config import settings


class OpenRouterProvider:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=settings.LLM_TIMEOUT,
            max_retries=1,
        )

    async def next_turn(
        self, messages: list[dict[str, Any]], tools: list[ToolDefinition]
    ) -> ModelTurn:
        response = await self.client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=messages,
            tools=[{
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            } for tool in tools],
            tool_choice="auto",
            temperature=0.1,
            max_tokens=1800,
        )
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {"_invalid_json": call.function.arguments}
            calls.append(ToolCall(call.id, call.function.name, arguments))
        return ModelTurn(text=message.content or "", tool_calls=calls)
