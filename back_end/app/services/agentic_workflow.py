"""
Agentic workflow for the Data Analyst chatbot (Python / E2B sandbox).

Loop:
  1. Ask the LLM to classify the user query (needs_code?).
  2. If no code, return a plain chat response.
  3. If yes, ask for JSON tool_calls containing Python code.
  4. Execute the code in E2B (up to MAX_RETRIES retries on failure).
  5. If new files are produced, register them as new tables and feed the
     updated data context back to the LLM for a final answer.
  6. Persist conversation turns to chat_histories (only metadata, never the
     full data values).

User-facing contract:
  - The user ONLY sees the final natural-language answer (user_response).
  - Raw Python code, tool_call payloads, execution logs, and intermediate
    errors are kept server-side for debugging but stripped from the
    payload returned to the frontend.
  - The execute_code tool returns a structured error ``{"success": false,
    "error": "..."}`` whenever execution fails; the LLM reads the error and
    may retry up to MAX_RETRIES times before the workflow gives up.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import ChatHistory
from app.services.data_service import DataProcessor, query_table
from app.services.e2b_service import E2BService
from app.services.llm_service import LLMService
from app.services.session_service import session_manager

logger = logging.getLogger(__name__)


class AgenticWorkflow:
    """Main coordinator for the data analyst chatbot."""

    # Maximum number of times the LLM may retry execute_code after an error.
    MAX_RETRIES = 3

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self.installed_packages: Set[str] = {"pandas", "matplotlib", "seaborn", "numpy"}
        self.last_query: str = ""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def run(
        self,
        user_query: str,
        session_id: str,
        *,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Run the full agentic workflow and return the user-facing payload.

        The payload contains ONLY:
          - ``status``: ``"success"`` or ``"error"``
          - ``user_response``: the final natural-language answer (always
            set, never the raw Python code, logs, or exception text)
          - ``session_id``
          - ``new_files``: artifact filenames produced by the sandbox

        Raw ``code``, ``events`` (tool-call trace), ``logs`` and
        ``error_message`` are kept server-side for logging/debugging but
        NOT exposed to the frontend.
        """
        self.last_query = user_query
        await self._save_chat("user", user_query, session_id)

        # Snapshot temp_data/ so we can detect newly created artifacts
        temp_dir = Path(settings.TEMP_DATA_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        before_files = {f.name for f in temp_dir.iterdir() if f.is_file()} if temp_dir.exists() else set()

        data_context = session_manager.get_all_tables_info()
        files_in_session: List[str] = []
        for name in session_manager.get_table_names():
            fp = session_manager.get_table_file(name)
            if fp and os.path.isfile(fp):
                files_in_session.append(fp)

        # 1) Classify
        classification = await LLMService.generate_query_classification(
            query=user_query,
            data_context_summary=data_context,
            installed_packages=self.installed_packages,
        )
        needs_code = classification.get("needs_code", True)

        if not needs_code:
            result = await LLMService.generate_chat_response(
                query=user_query, data_context_summary=data_context
            )
            return await self._finalize(
                session_id=session_id,
                user_response=result["user_response"],
                new_files=[],
                status="success",
            )

        # 2) Generate code (with retry on parse failure)
        llm_result = await LLMService.generate_code_with_tool_calls(
            query=user_query,
            data_context_summary=data_context,
            installed_packages=self.installed_packages,
        )
        tool_calls = llm_result["tool_calls"]
        if not tool_calls:
            # LLM may have replied in text; treat as final answer
            return await self._finalize(
                session_id=session_id,
                user_response=llm_result["user_response"]
                or "Sorry, I did not understand the request. Could you rephrase it?",
                new_files=[],
                status="success",
            )

        # 3) Execute with retry loop.
        # The execute_code tool returns ``{"success": bool, "error": "..."}``
        # so the LLM can read the error and self-correct. We retry up to
        # MAX_RETRIES times after the first failure.
        attempt = 0
        last_error: Optional[str] = None
        last_logs: str = ""
        execution_result: Dict[str, Any] = {}
        while attempt <= self.MAX_RETRIES:
            logger.info("E2B attempt %d/%d", attempt + 1, self.MAX_RETRIES + 1)
            E2BService.clean_temp(exclude=before_files)
            execution_result = await E2BService.execute_from_tool_call(
                tool_calls[0], files_to_mount=files_in_session
            )
            if execution_result.get("success"):
                break
            last_error = execution_result.get("error", "Unknown error")
            last_logs = execution_result.get("logs", "")
            logger.warning(
                "E2B attempt %d failed: %s", attempt + 1, (last_error or "")[:200]
            )
            if attempt >= self.MAX_RETRIES:
                break
            # Ask the LLM to fix the code (INTERNAL retry - user never sees
            # this back-and-forth).
            fix_query = (
                "The Python code you just produced failed in the sandbox with "
                "this error (this is INTERNAL feedback, do not mention it to "
                "the user):\n\n"
                f"{last_error}\n\n"
                "Diagnose the issue and reply again with a JSON tool call "
                '{"tool": "execute_code", "code": "<corrected python>", '
                '"description": "<short>"}. Make sure the code only uses the '
                "pre-installed packages."
            )
            fix_result = await LLMService.generate_code_with_tool_calls(
                query=fix_query,
                data_context_summary=data_context,
                installed_packages=self.installed_packages,
            )
            if fix_result["tool_calls"]:
                tool_calls = fix_result["tool_calls"]
            attempt += 1

        if not execution_result.get("success"):
            # Don't leak raw traceback to the user. Ask the LLM for a polite
            # apology/explanation; if that fails too, return a generic
            # fallback message.
            friendly = await self._friendly_failure_message(
                user_query=user_query,
                error=last_error or "unknown",
                retries=self.MAX_RETRIES + 1,
            )
            return await self._finalize(
                session_id=session_id,
                user_response=friendly,
                new_files=[],
                status="error",
                server_error=last_error,
                server_logs=last_logs,
                server_code=tool_calls[0].get("code") if tool_calls else None,
                server_retries=attempt,
            )

        # 4) Detect newly produced files
        new_files = E2BService.find_new_temp_files(before_files)
        for f in new_files:
            fp = str(temp_dir / f)
            if not session_manager.get_table_file(os.path.splitext(f)[0]):
                try:
                    ctx = await DataProcessor.extract_data_context_async(fp)
                    session_manager.add_table(
                        table_name=os.path.splitext(f)[0],
                        file_path=fp,
                        columns=ctx.columns,
                    )
                    logger.info("Registered new table from E2B: %s", f)
                except Exception as exc:
                    logger.warning("Could not register %s as table: %s", f, exc)

        # 5) Build final user-facing answer via the LLM so the user sees a
        # natural-language summary of the execution (NOT raw code, logs or
        # row dumps).
        results_raw = execution_result.get("results", [])
        user_response = await self._summarise_execution(
            user_query=user_query,
            llm_first_answer=llm_result.get("user_response"),
            execution_results=results_raw,
            new_files=new_files,
        )

        return await self._finalize(
            session_id=session_id,
            user_response=user_response,
            new_files=new_files,
            status="success",
            server_code=tool_calls[0].get("code") if tool_calls else None,
            server_logs=execution_result.get("logs", ""),
            server_retries=attempt,
        )

    async def _summarise_execution(
        self,
        *,
        user_query: str,
        llm_first_answer: Optional[str],
        execution_results: List[str],
        new_files: List[str],
    ) -> str:
        """Use the LLM to turn raw sandbox output into a natural-language reply."""
        results_preview = "\n".join(str(r) for r in execution_results[:5])[:2000]
        files_note = (
            f"Artifacts saved: {', '.join(new_files)}." if new_files else ""
        )
        prompt = (
            f"The user asked: {user_query}\n\n"
            f"Initial code-generation reply (if any): {llm_first_answer or '(none)'}\n\n"
            f"Sandbox printed the following values:\n{results_preview or '(no stdout)'}\n\n"
            f"{files_note}\n\n"
            "Write a concise natural-language answer for the user (in the user's "
            "language - Vietnamese if the question is in Vietnamese). "
            "Do NOT mention Python code, sandbox, tools, retries, or errors. "
            "Do NOT paste raw code. Show only the values that matter."
        )
        try:
            summary = await LLMService.generate_chat_response(
                query=prompt,
                data_context_summary=session_manager.get_all_tables_info(),
            )
            return (summary.get("user_response") or "").strip()
        except Exception as exc:
            logger.warning("Could not summarise execution: %s", exc)
            # Fallback: a short message so the user always gets something.
            return "Analysis finished. Please open the chart or attached file for details."

    async def _friendly_failure_message(
        self,
        *,
        user_query: str,
        error: str,
        retries: int,
    ) -> str:
        """Generate a user-friendly apology when execution keeps failing."""
        try:
            prompt = (
                f"The user asked: {user_query}\n\n"
                f"The system tried to run the analysis {retries} times but each "
                f"attempt failed with: {error[:500]}\n\n"
                "Reply to the user in plain natural language (Vietnamese if the "
                "question is in Vietnamese). Apologise briefly, explain in general "
                "terms what went wrong (e.g. data not available, query too complex), "
                "and suggest a simpler alternative question. Do NOT mention Python, "
                "sandboxes, retries, or internal tooling."
            )
            result = await LLMService.generate_chat_response(
                query=prompt,
                data_context_summary=session_manager.get_all_tables_info(),
            )
            msg = (result.get("user_response") or "").strip()
            if msg:
                return msg
        except Exception as exc:
            logger.warning("Could not produce friendly failure message: %s", exc)
        return (
            "Sorry, the system could not complete this request after several "
            "attempts. Please try a shorter question with less detail."
        )

    # ------------------------------------------------------------------
    # Streaming (text only)
    # ------------------------------------------------------------------
    async def stream_chat(
        self, user_query: str, session_id: str
    ) -> AsyncGenerator[str, None]:
        """Simple streaming text response (no tool use, for the /chat/stream endpoint)."""
        await self._save_chat("user", user_query, session_id)
        async for chunk in LLMService.generate_chat_response_stream(
            query=user_query,
            data_context_summary=session_manager.get_all_tables_info(),
        ):
            yield chunk
        # Persist the full text at the end (we re-issue a non-streaming call to
        # capture the final text). For a minimal version we just store the
        # query and a placeholder.
        await self._save_chat("assistant", "[streaming response]", session_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _save_chat(self, role: str, content: str, session_id: str) -> None:
        try:
            self.db.add(
                ChatHistory(
                    user_id=self.user_id,
                    session_id=session_id,
                    role=role,
                    content=content[:8000],
                    created_at=datetime.now(timezone.utc),
                )
            )
            await self.db.commit()
        except Exception as exc:
            logger.warning("Could not save chat history: %s", exc)
            await self.db.rollback()

    async def _finalize(
        self,
        *,
        session_id: str,
        user_response: str,
        new_files: List[str],
        status: str,
        server_code: Optional[str] = None,
        server_logs: str = "",
        server_retries: int = 0,
        server_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save the assistant turn and return the user-facing payload.

        The returned dict is the ONLY thing the frontend sees. Raw code,
        logs, events and error messages stay on the server (logged for
        debugging) and are intentionally omitted from the response.
        """
        # Save the assistant's final response (truncated to 8KB).
        await self._save_chat("assistant", user_response[:8000], session_id)
        # Server-side log for debugging (not sent to the user).
        if server_error:
            logger.warning(
                "agentic workflow failed after %d retries: %s",
                server_retries,
                server_error[:300],
            )
        return {
            "status": status,
            "session_id": session_id,
            "user_response": user_response,
            "new_files": new_files,
        }

    # Convenience: ask the LLM to run a SQL query through the read-only gateway.
    async def run_sql_query(self, sql: str, limit: int = 50) -> Dict[str, Any]:
        """Convenience helper so the LLM can query the SQL gateway directly."""
        return await query_table(
            table=sql,
            limit=limit,
        )
