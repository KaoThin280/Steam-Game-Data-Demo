"""
Unified LLM Service - OpenRouter API.

Supports:
  - Plain chat (generate_chat_response, generate_chat_response_stream)
  - Code generation with tool calls (generate_code_with_tool_calls)
  - Query classification (needs code or not)
  - Structured workflow (call_llm_structured for parser-based protocols)

Provider: OpenRouter (OpenAI compatible)
Default model: deepseek/deepseek-chat-v3.1:free
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import ChatHistory

logger = logging.getLogger(__name__)


# Lazy-init client (one per process).
_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY not configured in .env")
        _client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
        logger.info("OpenRouter client initialised (model=%s)", settings.OPENROUTER_MODEL)
    return _client


# ===================== Low-level calls =====================
async def _call_openrouter_async(
    system_text: str,
    user_text: str,
    *,
    max_tokens: int = 3000,
    temperature: float = 0.2,
) -> str:
    """Call OpenRouter asynchronously. Used by both chat and structured workflow."""
    client = _get_client()
    resp = await client.chat.completions.create(
        model=settings.OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        extra_headers={
            "HTTP-Referer": "https://steam-game-data-demo.local",
            "X-Title": "Steam Game Data AI",
        },
    )
    return resp.choices[0].message.content or ""


def _call_openrouter_sync(
    system_text: str,
    user_text: str,
    *,
    max_tokens: int = 3000,
    temperature: float = 0.2,
) -> str:
    """Synchronous version for legacy structured-workflow code paths."""
    import asyncio
    return asyncio.run(
        _call_openrouter_async(
            system_text, user_text,
            max_tokens=max_tokens, temperature=temperature,
        )
    )


# ===================== Public service class =====================
class LLMService:
    """High-level LLM helper used by both agentic and structured workflows."""

    # ---------- Plain chat ----------
    @staticmethod
    async def generate_chat_response(
        query: str,
        data_context_summary: str,
        installed_packages: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a plain natural-language answer.
        Used when the model decides the question doesn't need code.
        """
        sys_prompt = (
            "You are a Data Analyst AI for a Steam games database. "
            "Use ONLY the data context below to answer. Do NOT invent values. "
            "Keep answers concise and in Vietnamese unless the user asks otherwise.\n\n"
            f"DATA CONTEXT:\n{data_context_summary}"
        )
        user_prompt = f"User question: {query}\nAnswer concisely."
        text = await _call_openrouter_async(
            sys_prompt, user_prompt, max_tokens=2000, temperature=0.3
        )
        return {"user_response": text.strip()}

    @staticmethod
    async def generate_chat_response_stream(
        query: str,
        data_context_summary: str,
    ):
        """Async generator that yields text chunks (SSE-friendly)."""
        client = _get_client()
        sys_prompt = (
            "You are a Data Analyst AI for a Steam games database. "
            "Use ONLY the data context below. Be concise, in Vietnamese.\n\n"
            f"DATA CONTEXT:\n{data_context_summary}"
        )
        stream = await client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": query},
            ],
            max_tokens=2000,
            temperature=0.3,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    # ---------- Classification ----------
    @staticmethod
    async def generate_query_classification(
        query: str,
        data_context_summary: str,
        installed_packages: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Ask the LLM if the query needs code execution."""
        sys_prompt = (
            "You are a classifier. Reply with strict JSON only.\n"
            "Schema: {\"needs_code\": bool, \"reason\": str, \"reasoning_steps\": [str]}"
        )
        user_prompt = (
            f"Question: {query}\n\n"
            f"Available data:\n{data_context_summary}\n\n"
            "Does answering this question require running Python code (statistics, "
            "charts, data transformations)? Reply JSON only."
        )
        try:
            raw = await _call_openrouter_async(
                sys_prompt, user_prompt, max_tokens=300, temperature=0
            )
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                data = json.loads(match.group(0))
                return {
                    "needs_code": bool(data.get("needs_code", False)),
                    "reason": data.get("reason", ""),
                    "reasoning_steps": data.get("reasoning_steps", []),
                }
        except Exception as exc:
            logger.warning("Classification failed: %s", exc)
        # Default: treat as needs_code to be safe
        return {
            "needs_code": True,
            "reason": "classification fallback",
            "reasoning_steps": [],
        }

    # ---------- Code generation with JSON tool calls ----------
    @staticmethod
    async def generate_code_with_tool_calls(
        query: str,
        data_context_summary: str,
        installed_packages: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Ask the LLM to produce JSON tool calls for execution."""
        sys_prompt = (
            "You are a Data Analyst AI. You have ONE tool: execute_code.\n"
            "When code is needed, respond with STRICT JSON only:\n"
            '{"tool": "execute_code", "code": "<python>", "description": "<short>"}\n'
            "If no code is needed, respond with text only (no JSON).\n\n"
            f"DATA CONTEXT:\n{data_context_summary}"
        )
        user_prompt = (
            f"User request: {query}\n"
            "If you need to run Python (e.g. statistics, charts, aggregations), "
            "respond with the JSON tool call. Otherwise just answer in text."
        )
        raw = await _call_openrouter_async(
            sys_prompt, user_prompt, max_tokens=3500, temperature=0.2
        )
        tool_calls = LLMService.extract_tool_calls_json(raw)
        return {
            "raw": raw,
            "tool_calls": tool_calls,
            "user_response": None if tool_calls else raw.strip(),
        }

    @staticmethod
    def extract_tool_calls_json(text: str) -> List[Dict[str, Any]]:
        """Pull out the first {tool, code, description} JSON object from text."""
        if not text:
            return []
        # Try strict parse of the whole string first
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get("tool"):
                return [data]
        except Exception:
            pass
        # Search for the first JSON block
        match = re.search(r"\{[\s\S]*?\"tool\"[\s\S]*?\}", text)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict) and data.get("tool"):
                return [data]
        except Exception:
            return []
        return []

    @staticmethod
    def extract_code(text: str) -> Optional[str]:
        """Extract Python code from a ```python ... ``` block."""
        if not text:
            return None
        m = re.search(r"```(?:python|py)\s*\n(.*?)\n```", text, re.DOTALL)
        return m.group(1).strip() if m else None

    # ---------- Structured workflow (used by structured_workflow.py) ----------
    @staticmethod
    def call_llm_structured(
        system_text: str,
        user_text: str,
        max_tokens: int = 3000,
        temperature: float = 0.2,
    ) -> str:
        """Synchronous helper for the legacy parser-based structured workflow."""
        return _call_openrouter_sync(
            system_text, user_text,
            max_tokens=max_tokens, temperature=temperature,
        )


# ===================== SQL safety wrapper =====================
# Re-export so other modules can patch this consistently.
async def call_openrouter(
    system_text: str,
    user_text: str,
    *,
    max_tokens: int = 3000,
    temperature: float = 0.2,
) -> str:
    return await _call_openrouter_async(
        system_text, user_text,
        max_tokens=max_tokens, temperature=temperature,
    )