"""
Unified LLM Service - OpenRouter API.

Supports:
  - Plain chat (generate_chat_response, generate_chat_response_stream)
  - Code generation with tool calls (generate_code_with_tool_calls)
  - Query classification (needs code or not)

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
            timeout=settings.LLM_TIMEOUT,
            max_retries=3,
        )
        logger.info("OpenRouter client initialised (model=%s, timeout=$(settings.LLM_TIMEOUT)s)", settings.OPENROUTER_MODEL)
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
            "Reply in the user's language. Keep answers concise.\n\n"
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
            "Use ONLY the data context below. Reply in the user's language. "
            "Be concise.\n\n"
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
        """Ask the LLM to produce JSON tool calls for execution.

        Contract:
          - If code is needed, the response MUST be a single JSON object:
              {"tool": "execute_code", "code": "<python>", "description": "<short>"}
            with NO prose before or after the JSON.
          - The execute_code tool returns either
              {"success": true, "logs": "...", "results": [...], "sandbox_files": [...]}
            or
              {"success": false, "logs": "...", "error": "<message>", "sandbox_files": [...]}
          - When the tool returns success=false, the workflow feeds the error back to
            the model and asks for a corrected tool call. The model may retry the
            same tool up to MAX_RETRIES=3 times per user message.
          - The user NEVER sees the raw JSON tool call, the code, or the error.
            The model is asked to keep its final natural-language answer free of
            code/tool/error references.
          - If no code is needed, the model should reply with plain text only
            (no JSON).
        """
        packages = ", ".join(sorted(installed_packages)) if installed_packages else "pandas, matplotlib, seaborn, numpy"
        sys_prompt = (
            "You are a Data Analyst AI running in an automated workflow. "
            "The user NEVER sees your tool calls - they only read your final "
            "natural-language reply. Tool calls and errors are internal.\n\n"
            "You have ONE tool: execute_code. "
            "When code is needed, respond with STRICT JSON only, no prose:\n"
            '{"tool": "execute_code", "code": "<python>", "description": "<short>"}\n\n'
            "If no code is needed, respond with text only (no JSON, no code blocks).\n\n"
            "When the user reports that your previous code failed (you receive a "
            "user-role message containing the error):\n"
            "  1. Read the error carefully.\n"
            "  2. Identify the cause (syntax error, missing import, bad column, "
            "     wrong library, etc.).\n"
            "  3. Reply again with the SAME JSON tool_call shape but with corrected code.\n"
            "  4. Only use pre-installed packages: " + packages + ".\n"
            "  5. If the data you need is not available, reply with a brief plain-text "
            "     explanation instead of a tool call.\n\n"
            "Always keep your code self-contained. Always end with a `print(...)` "
            "of the value(s) the user asked about.\n\n"
            f"DATA CONTEXT:\n{data_context_summary}"
        )
        user_prompt = (
            f"User request: {query}\n"
            "If you need to run Python (statistics, charts, aggregations), respond "
            "with the JSON tool call above. Otherwise answer in plain text."
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

