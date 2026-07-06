"""
AI Service - OpenRouter + structured text protocol.

The AI communicates via structured text:
  Response to user: <natural-language answer or None>
  Request system: None | EXECUTE_QUERY | CHARTING | LIST_DATA_FILES | GET_DATA_CONTEXT | EXECUTE_PYTHON_CODE
  Code: None | <SQL> | <JSON chart config> | <python code> | <table_name>

This is more reliable than free-form JSON because the model cannot
nest JSON inside markdown code blocks and cause parse failures.
"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.models.user import AIChartHistory, AppUser, ChatHistory
from app.services.e2b_service import E2BService
from app.services.session_service import session_manager
from app.services.steam_service import SteamService
from app.utils.sql_helpers import validate_sql


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are "Steam Data Analyst AI", an assistant that answers questions about a Steam games database.

# OUTPUT FORMAT (CRITICAL)

You MUST respond in this exact structured text format every time:

Response to user: <your answer in natural language, or None if not ready to answer>
Request system: None | EXECUTE_QUERY | CHARTING | LIST_DATA_FILES | GET_DATA_CONTEXT | EXECUTE_PYTHON_CODE
Code: None | <SQL query> | <JSON chart config> | <table name> | <python code>

Examples:
----
Response to user: None
Request system: EXECUTE_QUERY
Code: SELECT g.name, COUNT(gg.steam_appid) AS cnt FROM genres g JOIN game_genres gg ON g.id = gg.genre_id GROUP BY g.name ORDER BY cnt DESC LIMIT 10;
----
Response to user: None
Request system: CHARTING
Code: {"chart_type": "bar", "chart_title": "Top 10 Genres", "config": {"labels": ["Indie", "Action"], "datasets": [{"label": "Games", "data": [6561, 4550]}]}, "x_axis_label": "Genre", "y_axis_label": "Count", "source_query": "SELECT ..."}
----
Response to user: Here are the top 10 genres...
Request system: None
Code: None
----

Set "Response to user" to a non-empty string ONLY when you are ready to answer.
The user ONLY sees the "Response to user" text. They NEVER see "Request system" or "Code".

<<DATA_CONTEXT>>

## SECURITY
- ONLY SELECT/WITH queries allowed (read-only).
- DO NOT query auth, app_users, roles, chat_histories, ai_chart_history.
- Add LIMIT to large queries (DB ~10k games, ~169k reviews, 1 GB RAM).

# TOOLS

## EXECUTE_QUERY
Run a read-only SQL SELECT. The Code field must contain the SQL.
Result: columns + rows from the database.

## CHARTING
Register a Chart.js configuration for the frontend. The Code field must contain JSON:
{
  "chart_type": "bar|line|pie|doughnut|scatter|radar|polarArea",
  "chart_title": "...",
  "config": {"labels": [...], "datasets": [{"label": "...", "data": [...]}]},
  "x_axis_label": "...",
  "y_axis_label": "...",
  "source_query": "..."
}

## LIST_DATA_FILES
List all available data tables (SQL + CSV). Code field is ignored.

## GET_DATA_CONTEXT
Get schema, descriptive stats, first 4 and last 4 rows of a table.
Code field must contain the table name (e.g. "games", "reviews", or a CSV-derived table name).
CRITICAL: Use this tool BEFORE charting to understand data types (categorical vs. continuous) and cardinality.

## EXECUTE_PYTHON_CODE
Run Python code in an isolated E2B sandbox. The Code field must contain the Python code.
The sandbox has pandas, matplotlib, seaborn, numpy, plotly pre-installed.
- Save interactive Plotly charts to "temp_data/<filename>.html" (Must explicitly enable rangesliders for continuous time-series).
- Save CSVs to "temp_data/<filename>.csv"
- Save images to "temp_data/<filename>.png"

# CHART SELECTION GUIDELINES
Analyze the data types and user request to determine the chart:
1. Time-Series (Date/Year/Month vs. Value): ALWAYS use `line` chart. If data is continuous and long, use EXECUTE_PYTHON_CODE to generate a Plotly line chart with `rangeslider_visible=True`.
2. Categorical Comparison (String/Categories vs. Value): Use `bar`. If labels are long or > 7 categories, use horizontal bars.
3. Proportions/Parts of a Whole: Use `pie` or `doughnut`. Group minor categories into "Others" if > 6 items.
4. Correlation (Value vs. Value): Use `scatter`.
5. Distributions (Frequency of values): Use EXECUTE_PYTHON_CODE to generate a Plotly histogram.

# DECISION RULES

- Greeting/out-of-scope: set Response to user to plain text, Request system to None.
- Analysis Planning: ALWAYS call LIST_DATA_FILES and GET_DATA_CONTEXT first to understand the data schema before querying or charting.
- Numeric answer: call EXECUTE_QUERY, then set Response to user with summary.
- Simple charting: call EXECUTE_QUERY -> evaluate data via CHART SELECTION GUIDELINES -> call CHARTING.
- Advanced/Interactive charting: call EXECUTE_QUERY -> call EXECUTE_PYTHON_CODE with plotly -> set Response to user with link to HTML.
- Auto-retry: if a tool returns an error, fix it and retry (up to 3 times).
- Final answer: pure natural language. Never mention SQL, code, tools, or errors.
"""


def parse_ai_response(text: str) -> Dict[str, Any]:
    """Parse structured text response from AI into {response_to_user, request_system, code}.

    Handles messy formatting: missing newlines, "Responseto" (no space),
    "Response to user: ... Request system: ..." all on one line, etc.
    """
    result = {"response_to_user": None, "request_system": None, "code": None}

    if not text:
        return result

    # Normalise: insert newlines before each known field header (case-insensitive)
    # This handles the "all-on-one-line" case
    for pat in ["Response to user:", "Request system:", "Code:"]:
        # Insert newline before the field if not already at start of line
        text = re.sub(
            rf"(?<!\n)\s*({pat})",
            r"\n\1",
            text,
            flags=re.IGNORECASE,
        )

    lines = text.strip().split("\n")
    field_order = ["response_to_user", "request_system", "code"]
    current_field = None
    collected_values: Dict[str, List[str]] = {}

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        # Detect field headers
        if lower.startswith("response to user:"):
            current_field = "response_to_user"
            val = stripped[len("response to user:"):].strip()
            if val.lower() != "none" and val:
                collected_values.setdefault(current_field, []).append(val)
            continue
        if lower.startswith("request system:"):
            current_field = "request_system"
            val = stripped[len("request system:"):].strip()
            if val.lower() != "none" and val:
                collected_values.setdefault(current_field, []).append(val)
            continue
        if lower.startswith("code:"):
            current_field = "code"
            val = stripped[len("code:"):].strip()
            if val.lower() != "none" and val:
                collected_values.setdefault(current_field, []).append(val)
            continue

        # Continuation lines belong to current field
        if current_field and current_field in collected_values:
            collected_values[current_field].append(stripped)

    # Join multi-line values
    for field in field_order:
        if field in collected_values:
            result[field] = "\n".join(collected_values[field]).strip()

    # Fallback: if no structured fields found at all, treat entire response as answer
    if result["response_to_user"] is None and result["request_system"] is None:
        result["response_to_user"] = text.strip()

    return result


ALLOWED_CHART_TYPES = {
    "bar", "line", "pie", "doughnut", "scatter", "radar", "area", "polarArea",
}


def _validate_chart_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    ctype = str(args.get("chart_type", "bar")).lower().strip()
    if ctype == "area":
        ctype = "line"
    if ctype not in ALLOWED_CHART_TYPES:
        raise BadRequestException(detail=f"Invalid chart_type: {ctype}")

    title = str(args.get("chart_title", "")).strip()[:200]
    if not title:
        raise BadRequestException(detail="chart_title is required.")

    config = args.get("config") or {}
    if not isinstance(config, dict):
        raise BadRequestException(detail="config must be a Chart.js object.")

    options = config.get("options") or {}
    x_rot = args.get("x_rotation")
    if isinstance(x_rot, (int, float)):
        x_rot = max(-90, min(90, int(x_rot)))
        scales = options.setdefault("scales", {})
        x_scale = scales.setdefault("x", {})
        ticks = x_scale.setdefault("ticks", {})
        ticks["maxRotation"] = x_rot
        ticks["minRotation"] = x_rot
    else:
        x_rot = None

    y_unit = args.get("y_unit")
    y_label = args.get("y_axis_label")
    if y_unit and y_label and isinstance(y_label, str):
        if f"({y_unit})" not in y_label:
            y_label = f"{y_label} ({y_unit})"
    elif y_unit and not y_label:
        y_label = f"({y_unit})"

    options.setdefault("responsive", True)
    options.setdefault("maintainAspectRatio", False)
    config["options"] = options

    return {
        "chart_type": ctype,
        "chart_title": title,
        "x_axis_label": args.get("x_axis_label") or None,
        "y_axis_label": y_label,
        "series_label": args.get("series_label") or None,
        "x_rotation": x_rot,
        "y_unit": y_unit,
        "config": config,
        "source_query": args.get("source_query"),
        "notes": args.get("notes"),
    }


class AIService:
    """AI Agent with structured text protocol and 5 tools."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
        self.model = settings.OPENROUTER_MODEL
        self.fallback_model = settings.OPENROUTER_FALLBACK_MODEL
        self.steam = SteamService(db)

    MAX_TOOL_RETRIES = 3

    async def chat(
        self,
        user: AppUser,
        message: str,
        session_id: Optional[str] = None,
        max_tool_steps: int = 12,
    ) -> Dict[str, Any]:
        """
        Structured text protocol loop.

        Each iteration:
          1. Call LLM -> get structured response (parse_ai_response)
          2. If response_to_user is set -> return it (final answer)
          3. If request_system is set -> dispatch tool -> feed result back
          4. If tool errors, retry (up to MAX_TOOL_RETRIES)
        """
        user_id = user.id
        session_id = (
            session_id
            or f"session_{user_id}_{int(datetime.now().timestamp())}"
        )
        history = await self.get_chat_history(user_id, session_id, limit=10)
        # Inject current data context (tables, columns, stats) into SYSTEM_PROMPT
        data_context = session_manager.get_all_tables_info() or "No tables available."
        system_text = SYSTEM_PROMPT.replace("<<DATA_CONTEXT>>", data_context)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_text}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        await self.save_chat(user_id, session_id, "user", message)

        charts_log: List[Dict[str, Any]] = []
        sandbox_files: List[str] = []
        workflow_events: List[Dict[str, Any]] = []

        def _add_event(stage: str, message: str, ev_type: str = "info") -> None:
            workflow_events.append({
                "stage": stage,
                "message": message,
                "type": ev_type,
            })

        _add_event("init", "Starting analysis...")

        last_request: Optional[str] = None
        consecutive_failures = 0
        final_reply = ""

        for _step in range(max_tool_steps):
            _add_event("llm", "Calling AI to analyse your request...")
            raw = await self._call_llm_with_fallback(messages)
            parsed = parse_ai_response(raw)

            response_to_user = parsed.get("response_to_user")
            request_system = (parsed.get("request_system") or "").strip()
            code = parsed.get("code")

            # DEBUG: log what the model actually returned
            logger.info(
                ">>> LLM step %d | response_to_user=%s | request_system=%s | response_to_user_len=%d | raw_preview=%s",
                _step,
                response_to_user is not None,
                request_system or "None",
                len(response_to_user or ""),
                raw[:200] if raw else "EMPTY",
            )

            # If AI is ready to answer, finish
            if response_to_user:
                _add_event("final", "AI produced the answer.", "done")
                final_reply = response_to_user
                logger.info(">>> BREAK: response_to_user is set (len=%d)", len(response_to_user))
                break

            # No tool requested -> treat as final reply
            if not request_system or request_system.lower() == "none":
                _add_event("final", "AI produced the answer.", "done")
                final_reply = raw
                logger.info(">>> BREAK: request_system is None/none (raw=%s)", raw[:300] if raw else "EMPTY")
                break

            # Execute the requested tool
            tool_result = await self._run_tool_by_name(
                user_id, session_id, request_system, code or "",
                charts_log, sandbox_files, _add_event
            )
            has_error = isinstance(tool_result, dict) and "error" in tool_result

            if has_error:
                # Single event for tool+error (avoids duplicate rows in UI)
                _add_event("error", f"{request_system} failed — retrying...", "error")
            else:
                if request_system == "EXECUTE_QUERY":
                    n = len(tool_result.get("rows", []))
                    _add_event("result", f"SQL query returned {n} rows.")
                elif request_system == "CHARTING":
                    _add_event("result", "Chart created.")
                elif request_system == "EXECUTE_PYTHON_CODE":
                    files = tool_result.get("sandbox_files", [])
                    _add_event("result", f"Python code executed. {len(files)} file(s) generated: {', '.join(files)}" if files else "Python code executed (no output files).")

            # Retry logic
            if has_error:
                if request_system == last_request:
                    consecutive_failures += 1
                else:
                    last_request = request_system
                    consecutive_failures = 1
                if consecutive_failures > self.MAX_TOOL_RETRIES:
                    logger.warning(
                        "Request %s exceeded retries; aborting.", request_system
                    )
                    final_reply = (
                        "Sorry, the system could not complete this request "
                        "after several attempts. Please try a different question."
                    )
                    break
            else:
                last_request = None
                consecutive_failures = 0

            # Feed result back to the model
            messages.append({"role": "assistant", "content": raw})
            feedback = self._format_feedback(
                request_system, tool_result, has_error
            )
            messages.append({"role": "user", "content": feedback})
        else:
            final_reply = "Reached the processing step limit. Please retry with a shorter question."

        await self.save_chat(user_id, session_id, "assistant", final_reply)
        return {
            "session_id": session_id,
            "reply": final_reply,
            "tool_calls": [],
            "charts": charts_log,
            "sandbox_files": sandbox_files,
            "workflow_events": workflow_events,
        }

    async def _run_tool_by_name(
        self,
        user_id: int,
        session_id: str,
        request_system: str,
        code: str,
        charts_log: List[Dict[str, Any]],
        sandbox_files: List[str],
        _add_event: Any = None,
    ) -> Dict[str, Any]:
        """Dispatch based on the structured request_system field."""
        try:
            if request_system == "EXECUTE_QUERY":
                result = await self.tool_execute_query({"sql": code})
                return result

            if request_system == "CHARTING":
                args = self._parse_chart_code(code)
                result = await self.tool_charting(user_id, session_id, args)
                charts_log.append(result)
                return result

            if request_system == "LIST_DATA_FILES":
                return self.tool_list_data_files()

            if request_system == "GET_DATA_CONTEXT":
                return await self.tool_get_data_context({"table_name": code.strip()})

            if request_system == "EXECUTE_PYTHON_CODE":
                result = await self.tool_execute_python_code({"code": code})
                if isinstance(result, dict) and result.get("success"):
                    for fname in result.get("sandbox_files") or []:
                        if fname.endswith((".html", ".png", ".csv")):
                            if fname not in sandbox_files:
                                sandbox_files.append(fname)
                return result

            return {"error": f"Unknown request: {request_system}"}

        except BadRequestException as exc:
            await self.db.rollback()
            return {"error": str(exc.detail)}
        except Exception as exc:
            logger.exception("Tool %s failed", request_system)
            await self.db.rollback()
            return {"error": f"Tool execution failed: {exc}"}

    @staticmethod
    def _parse_chart_code(code: str) -> Dict[str, Any]:
        """Parse Chart.js JSON config from the Code field."""
        code = code.strip()
        # Extract JSON from markdown fences if present
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", code, re.DOTALL)
        if fence:
            code = fence.group(1)
        try:
            return json.loads(code)
        except json.JSONDecodeError as exc:
            raise BadRequestException(
                detail=f"Invalid chart JSON: {exc}"
            ) from exc

    @staticmethod
    def _format_feedback(
        request_system: str,
        tool_result: Dict[str, Any],
        has_error: bool,
    ) -> str:
        """Format tool result as user-role feedback message."""
        payload = json.dumps(tool_result, ensure_ascii=False, default=str)
        if has_error:
            return (
                f"System feedback for '{request_system}' (INTERNAL, do not show to user):\n"
                f"{payload}\n\n"
                "Fix the error and try again, OR set Response to user with a polite explanation."
            )
        return (
            f"System feedback for '{request_system}' (INTERNAL, do not show raw data):\n"
            f"{payload}\n\n"
            "If you have all the data you need, set Response to user with your final answer. "
            "Otherwise continue with another request."
        )

    async def chat_stream(
        self,
        user: AppUser,
        message: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        session_id = (
            session_id
            or f"session_{user.id}_{int(datetime.now().timestamp())}"
        )
        history = await self.get_chat_history(user.id, session_id, limit=10)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        await self.save_chat(user.id, session_id, "user", message)

        full_reply = ""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
                stream=True,
            )
            async for chunk in stream:
                delta = (
                    chunk.choices[0].delta.content if chunk.choices else None
                )
                if delta:
                    full_reply += delta
                    yield delta
        except Exception as e:
            err = f"[Stream error: {e}]"
            full_reply += err
            yield err
            logger.exception("Stream chat error")
        await self.save_chat(user.id, session_id, "assistant", full_reply)

    async def _call_llm_with_fallback(
        self, messages: List[Dict[str, str]]
    ) -> str:
        for attempt, model_name in enumerate(
            [self.model, self.fallback_model], 1
        ):
            try:
                resp = await self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=2000,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                logger.warning(
                    "LLM attempt %s (model=%s) failed: %s",
                    attempt, model_name, e,
                )
                if attempt >= 2:
                    raise ServiceUnavailableException(
                        detail=f"Cannot reach OpenRouter: {e}"
                    ) from e
        return ""

    # ------------------------------------------------------------------
    # Tool 1: EXECUTE_QUERY
    # ------------------------------------------------------------------
    async def tool_execute_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        sql = validate_sql(str(args.get("sql", "")))
        params = args.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        limit = int(args.get("limit") or 200)
        return await self.steam.execute_readonly_query(
            sql, params, limit=limit
        )

    # ------------------------------------------------------------------
    # Tool 2: CHARTING
    # ------------------------------------------------------------------
    async def tool_charting(
        self,
        user_id: int,
        session_id: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        clean = _validate_chart_payload(args)
        record = AIChartHistory(
            user_id=user_id,
            session_id=session_id,
            chart_type=clean["chart_type"],
            chart_title=clean["chart_title"],
            x_axis_label=clean["x_axis_label"],
            y_axis_label=clean["y_axis_label"],
            series_label=clean["series_label"],
            config=clean["config"],
            source_query=clean["source_query"],
        )
        record.created_at = datetime.now(timezone.utc)
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        clean["id"] = record.id
        clean["session_id"] = session_id
        clean["created_at"] = (
            record.created_at.isoformat() if record.created_at else None
        )
        return clean

    # ------------------------------------------------------------------
    # Tool 3: LIST_DATA_FILES
    # ------------------------------------------------------------------
    @staticmethod
    def tool_list_data_files() -> Dict[str, Any]:
        try:
            table_names = session_manager.get_table_names()
            tables_info = []
            for name in table_names:
                info = session_manager.get_table_info(name)
                if info:
                    first_line = info.split("\n")[0] if info else name
                    tables_info.append({"name": name, "summary": first_line})
                else:
                    tables_info.append({"name": name, "summary": name})
            return {
                "success": True,
                "tables": tables_info,
                "total": len(tables_info),
                "error": None,
            }
        except Exception as exc:
            logger.exception("list_data_files failed")
            return {"error": f"Failed to list data files: {exc}"}

    # ------------------------------------------------------------------
    # Tool 4: GET_DATA_CONTEXT
    # ------------------------------------------------------------------
    @staticmethod
    async def tool_get_data_context(args: Dict[str, Any]) -> Dict[str, Any]:
        table_name = (args.get("table_name") or "").strip()
        if not table_name:
            return {"error": "table_name is required."}

        info = session_manager.get_table_info(table_name)
        file_path = session_manager.get_table_file(table_name)

        if not info and not file_path:
            known_sql = {"games", "reviews", "users", "genres", "categories",
                         "languages", "game_genres", "game_categories", "game_languages"}
            if table_name not in known_sql:
                return {"error": f"Unknown table '{table_name}'."}
            schema_text = info or f"Table '{table_name}' (source: PostgreSQL)"
            return {
                "success": True,
                "table_name": table_name,
                "schema": schema_text,
                "source": "sql",
                "error": None,
            }

        if not file_path or not os.path.isfile(file_path):
            return {"error": f"Data file for '{table_name}' not found."}

        return await AIService._load_csv_context(table_name, file_path)

    @staticmethod
    async def _load_csv_context(
        table_name: str, file_path: str
    ) -> Dict[str, Any]:
        try:
            import pandas as pd

            def _build() -> Dict[str, Any]:
                df = pd.read_csv(file_path)
                schema_lines = [f"Table: {table_name} (source: CSV)"]
                for col in df.columns:
                    dtype = str(df[col].dtype)
                    friendly = "TEXT"
                    if dtype.startswith("int"):
                        friendly = "INTEGER"
                    elif dtype.startswith("float"):
                        friendly = "FLOAT"
                    elif dtype == "bool":
                        friendly = "BOOLEAN"
                    elif "datetime" in dtype:
                        friendly = "TIMESTAMP"
                    schema_lines.append(f"  - {col} ({friendly})")
                schema_text = "\n".join(schema_lines)

                stats_text = ""
                numeric_cols = df.select_dtypes(include=["number"]).columns
                if len(numeric_cols) > 0:
                    desc = df[numeric_cols].describe()
                    stats_text = "Descriptive statistics:\n" + desc.to_string()

                head_text = "First 4 rows:\n" + df.head(4).to_string(index=False)
                tail_text = "Last 4 rows:\n" + df.tail(4).to_string(index=False)

                return {
                    "success": True,
                    "table_name": table_name,
                    "source": "csv",
                    "schema": schema_text,
                    "columns": list(df.columns),
                    "total_rows": len(df),
                    "descriptive_stats": stats_text,
                    "head": head_text,
                    "tail": tail_text,
                    "error": None,
                }

            return await asyncio.to_thread(_build)
        except ImportError:
            return {"error": "pandas not installed."}
        except Exception as exc:
            return {"error": f"Failed to read CSV: {exc}"}

    # ------------------------------------------------------------------
    # Tool 5: EXECUTE_PYTHON_CODE
    # ------------------------------------------------------------------
    @staticmethod
    async def tool_execute_python_code(args: Dict[str, Any]) -> Dict[str, Any]:
        code = (args.get("code") or "").strip()
        if not code:
            return {"error": "code is required."}

        description = (args.get("description") or "").strip()
        deps_to_install = args.get("deps_to_install") or []
        file_to_mount_name = (args.get("file_to_mount") or "").strip()

        files_to_mount: List[str] = []
        if file_to_mount_name:
            file_path = session_manager.get_table_file(file_to_mount_name)
            if file_path and os.path.isfile(file_path):
                files_to_mount.append(file_path)
            else:
                temp_path = Path(settings.TEMP_DATA_DIR) / file_to_mount_name
                if temp_path.is_file():
                    files_to_mount.append(str(temp_path))

        logger.info(
            "Executing Python code (desc=%s, deps=%s, files=%s)",
            description[:100] if description else "",
            deps_to_install, files_to_mount,
        )

        result = await E2BService.execute(
            code=code,
            files_to_mount=files_to_mount if files_to_mount else None,
            deps_to_install=deps_to_install if deps_to_install else None,
        )

        # Register new CSV files as tables
        if result.get("success") and result.get("sandbox_files"):
            temp_dir = Path(settings.TEMP_DATA_DIR)
            for fname in result["sandbox_files"]:
                if fname.endswith(".csv"):
                    table_name = os.path.splitext(fname)[0]
                    if not session_manager.get_table_file(table_name):
                        fp = str(temp_dir / fname)
                        try:
                            from app.services.data_service import DataProcessor
                            ctx = await DataProcessor.extract_data_context_async(fp)
                            session_manager.add_table(
                                table_name=table_name, file_path=fp, columns=ctx.columns,
                            )
                        except Exception as exc:
                            logger.warning("Could not register %s: %s", fname, exc)

        return result

    # ------------------------------------------------------------------
    # Chart listing & chat persistence
    # ------------------------------------------------------------------
    async def list_charts(
        self, user: AppUser, session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        q = select(AIChartHistory).where(AIChartHistory.user_id == user.id)
        if session_id:
            q = q.where(AIChartHistory.session_id == session_id)
        q = q.order_by(AIChartHistory.created_at.desc()).limit(100)
        rows = list((await self.db.execute(q)).scalars().all())
        return [
            {
                "id": r.id, "session_id": r.session_id,
                "chart_type": r.chart_type, "chart_title": r.chart_title,
                "x_axis_label": r.x_axis_label, "y_axis_label": r.y_axis_label,
                "series_label": r.series_label, "config": r.config,
                "source_query": r.source_query,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def save_chat(
        self, user_id: int, session_id: str, role: str, content: str,
    ) -> None:
        record = ChatHistory(
            user_id=user_id, session_id=session_id,
            role=role, content=content[:8000],
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.commit()

    async def get_chat_history(
        self, user_id: int, session_id: str, limit: int = 10,
    ) -> List[Dict[str, str]]:
        result = await self.db.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == user_id, ChatHistory.session_id == session_id)
            .order_by(ChatHistory.created_at.desc()).limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def list_sessions(self, user: AppUser) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(
                ChatHistory.session_id,
                func.max(ChatHistory.created_at).label("last_active"),
            )
            .where(ChatHistory.user_id == user.id)
            .group_by(ChatHistory.session_id)
            .order_by(func.max(ChatHistory.created_at).desc())
        )
        return [
            {
                "session_id": row[0],
                "last_active": row[1].isoformat() if row[1] else None,
            }
            for row in result.fetchall()
        ]