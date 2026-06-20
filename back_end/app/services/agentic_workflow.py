"""
Agentic workflow for the Data Analyst chatbot.

Loop:
  1. Ask the LLM to classify the user query (needs_code?).
  2. If no code, return a plain chat response.
  3. If yes, ask for JSON tool_calls containing Python code.
  4. Execute the code in E2B (up to 4 retries on failure).
  5. If new files are produced, register them as new tables and feed the
     updated data context back to the LLM for a final answer.
  6. Persist conversation turns to chat_histories (only metadata, never the
     full data values).
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

    MAX_RETRIES = 4  # user requested <= 4 retries

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
        """Run the full agentic workflow. Returns the final payload."""
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
                code=None,
                new_files=[],
                logs="",
                retries_used=0,
                events=[{"type": "classify", "needs_code": False, "reason": classification.get("reason", "")}],
                error=None,
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
                user_response=llm_result["user_response"] or "I couldn't determine an action for your request.",
                code=None,
                new_files=[],
                logs="",
                retries_used=0,
                events=[{"type": "no_tool_call", "raw": llm_result["raw"]}],
                error=None,
            )

        # 3) Execute with retry loop
        attempt = 0
        last_error: Optional[str] = None
        execution_result: Dict[str, Any] = {}
        while attempt <= self.MAX_RETRIES:
            logger.info("E2B attempt %d/%d", attempt + 1, self.MAX_RETRIES + 1)
            E2BService.clean_temp(exclude=before_files)
            execution_result = await E2BService.execute_from_tool_call(
                tool_calls[0], files_to_mount=files_in_session
            )
            if execution_result["success"]:
                break
            last_error = execution_result.get("error", "Unknown error")
            logger.warning("E2B attempt %d failed: %s", attempt + 1, last_error[:200])
            if attempt < self.MAX_RETRIES:
                # Ask the LLM to fix the code
                fix_query = (
                    f"The code I generated failed with this error:\n\n"
                    f"{last_error}\n\n"
                    "Please respond again with a JSON tool call "
                    '{"tool": "execute_code", "code": "<corrected python>", "description": "<short>"}.'
                )
                fix_result = await LLMService.generate_code_with_tool_calls(
                    query=fix_query,
                    data_context_summary=data_context,
                    installed_packages=self.installed_packages,
                )
                if fix_result["tool_calls"]:
                    tool_calls = fix_result["tool_calls"]
                attempt += 1
            else:
                break

        if not execution_result.get("success"):
            return await self._finalize(
                session_id=session_id,
                user_response=f"Execution failed after {attempt + 1} attempts. Last error: {last_error}",
                code=tool_calls[0].get("code"),
                new_files=[],
                logs=execution_result.get("logs", ""),
                retries_used=attempt,
                events=[],
                error=last_error,
            )

        # 4) Detect newly produced files
        new_files = E2BService.find_new_temp_files(before_files)
        for f in new_files:
            fp = str(temp_dir / f)
            if not session_manager.get_table_file(os.path.splitext(f)[0]):
                ctx = await DataProcessor.extract_data_context_async(fp)
                session_manager.add_table(
                    table_name=os.path.splitext(f)[0],
                    file_path=fp,
                    columns=ctx.columns,
                )
                logger.info("Registered new table from E2B: %s", f)

        # 5) Build final user-facing answer (only summary, never full data).
        new_context = session_manager.get_all_tables_info()
        logs = execution_result.get("logs", "")
        results_raw = execution_result.get("results", [])
        summary_parts: List[str] = []
        if llm_result.get("user_response"):
            summary_parts.append(llm_result["user_response"])
        if logs:
            summary_parts.append(f"--- Execution log ---\n{logs}")
        for r in results_raw[:5]:
            summary_parts.append(f"--- Result ---\n{r}")
        if not summary_parts:
            summary_parts.append("Code executed successfully.")
        summary = "\n\n".join(summary_parts)

        return await self._finalize(
            session_id=session_id,
            user_response=summary,
            code=tool_calls[0].get("code"),
            new_files=new_files,
            logs=logs,
            retries_used=attempt,
            events=[{"type": "executed", "retries": attempt, "new_files": new_files}],
            error=None,
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
        code: Optional[str],
        new_files: List[str],
        logs: str,
        retries_used: int,
        events: List[Dict[str, Any]],
        error: Optional[str],
    ) -> Dict[str, Any]:
        # Save the assistant's final response (truncated to 8KB).
        await self._save_chat("assistant", user_response[:8000], session_id)
        return {
            "status": "error" if error else "success",
            "user_response": user_response,
            "code": code,
            "new_files": new_files,
            "logs": logs,
            "retries_used": retries_used,
            "events": events,
            "error_message": error,
        }

    # Convenience: ask the LLM to run a SQL query through the read-only gateway.
    async def run_sql_query(self, sql: str, limit: int = 50) -> Dict[str, Any]:
        """Convenience helper so the LLM can query the SQL gateway directly."""
        return await query_table(
            table=sql,
            limit=limit,
        )
