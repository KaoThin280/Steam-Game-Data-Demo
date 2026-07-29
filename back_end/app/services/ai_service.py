"""
AI Service - OpenRouter + native tool calling (function_calling).

The LLM now returns a single JSON `tool_calls` array via the
OpenAI-compatible `chat.completions` API. The arguments are dispatched
server-side without the brittle text parsing that used to fail when
models truncated the response or omitted one of the three fields.

This is the modern pattern recommended by OpenRouter / OpenAI; it
sidesteps the "free model truncates the code block" issue we saw
during testing.
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


# ---------------------------------------------------------------------------
# Tool definitions (passed to OpenAI's `tools=` argument)
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": (
                "Run a read-only SQL SELECT against the public.games / "
                "public.reviews / public.users tables. Always include a "
                "LIMIT clause (max 200) to keep the response small."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A single SELECT statement.",
                    },
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plotting",
            "description": (
                "Create a Plotly chart for the front-end. "
                "Use this for ALL charts — bar, line, pie, doughnut, "
                "scatter, radar, area, timeseries. "
                "Send source_query (the SQL you used in execute_query) "
                "and the backend will fetch the full data and build "
                "the chart automatically. No need to build the figure "
                "yourself — just pass the SQL + chart_title + chart_type. "
                "IMPORTANT: always provide a description so charts can "
                "be found and reused in future sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_title": {"type": "string"},
                    "chart_type": {
                        "type": "string",
                        "description": (
                            "Type of chart: bar, line, pie, doughnut, "
                            "scatter, radar, area."
                        ),
                    },
                    "source_query": {
                        "type": "string",
                        "description": (
                            "The SQL query you verified via execute_query. "
                            "The backend will re-run this to get the full "
                            "dataset and build the Plotly figure. "
                            "Include this instead of building figure yourself."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": (
                            "Natural-language summary of what this chart shows, "
                            "e.g. 'Monthly new games on Steam from 1997 to 2027 "
                            "with peak at 324 in April 2016'. Used to find and "
                            "reuse charts across sessions."
                        ),
                    },
                },
                "required": ["chart_title", "chart_type", "source_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": (
                "Run Python code in an isolated E2B sandbox for ADVANCED "
                "analysis only (statistics, ML, correlation, custom "
                "numpy/pandas transforms). "
                "IMPORTANT: The sandbox has NO database access — "
                "sqlalchemy and psycopg2 are NOT installed. You CANNOT "
                "connect to the database from inside the sandbox. "
                "DO NOT use this for creating charts — use the charting "
                "or plotting tools instead. "
                "Each call creates a FRESH sandbox; files from previous "
                "calls are LOST."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "Python source code. Keep it under ~80 lines. "
                            "Save any output CSV to the current directory. "
                            "Each call runs in a NEW sandbox — do NOT try "
                            "to read files from previous calls."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description of what the code does.",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_data_files",
            "description": (
                "List all available data tables (SQL + any CSV files the "
                "user uploaded to the chat)."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_data_context",
            "description": (
                "Get the schema and the first/last 4 rows of a table so you "
                "can craft an informed SQL query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "One of: games, reviews, users, ...",
                    },
                },
                "required": ["table_name"],
            },
        },
    },
]


SYSTEM_PROMPT = """You are "Steam Data Analyst AI", an assistant that answers questions about a Steam games database.

# TOOLS (use the function-calling API; the system calls the matching tool server-side)

- list_data_files: list all tables available to you.
- get_data_context(table_name): inspect a table's schema + sample rows.
- execute_query(sql): run a read-only SELECT. Always include LIMIT (max 200).
- plotting(chart_title, chart_type, source_query): create a Plotly chart. Send the SQL you verified via execute_query — the backend will fetch all data and build the chart automatically. Use this for ALL charts (bar, line, pie, scatter, area, timeseries).
- execute_python(code, description): run Python in a sandbox for advanced analytics only (statistics, ML, custom transforms). The sandbox has pandas, numpy, plotly pre-installed but NO database access.

# HOW TO CREATE CHARTS

1. Query data: `execute_query(sql="SELECT month, COUNT(*) FROM games GROUP BY month ORDER BY month")`
2. Create chart: `plotting(chart_title="Số game mới mỗi tháng", chart_type="bar", source_query="SELECT month, COUNT(*) FROM games GROUP BY month ORDER BY month")`
3. Done! The backend handles the rest.

# RULES

- After verifying data with execute_query, call plotting with the same SQL as source_query.
- ALL charts use the `plotting` tool. Do NOT use execute_python for charts.
- The sandbox has NO database access. Use execute_query for data, plotting for charts.
- Only use `execute_python` for non-chart analysis (statistics, ML, correlation).
- Each `execute_python` call is a FRESH sandbox — files from previous calls do NOT persist.
- When the user is done, your final message must be plain natural language. Summarise, don't echo tool output verbatim.

# SECURITY
- Read-only. Never write / drop / truncate.
- LIMIT every query (max 200 rows).
- Never reference auth, app_users, roles, chat_histories, ai_chart_history.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tool_call_to_event(name: str, args: dict) -> Dict[str, Any]:
    """Return a workflow event entry for a tool invocation."""
    return {
        "stage": "tool_call",
        "message": f"Calling tool `{name}`\nArguments: {json.dumps(args, ensure_ascii=False, default=str)}",
        "type": "info",
    }


def _assistant_message_event(content: str) -> Dict[str, Any]:
    return {
        "stage": "assistant_message",
        "message": content or "",
        "type": "info",
    }


# ---------------------------------------------------------------------------
# Charting validation
# ---------------------------------------------------------------------------
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

    return {
        "chart_type": ctype,
        "chart_title": title,
        "x_axis_label": args.get("x_axis_label") or None,
        "y_axis_label": args.get("y_axis_label") or None,
        "series_label": args.get("series_label") or None,
        "x_rotation": x_rot,
        "config": config,
        "source_query": args.get("source_query"),
        "notes": args.get("notes"),
    }


# ---- Summary sample size ----
_SUMMARY_HEAD_TAIL = 5  # rows to keep from head and tail of query results


def _summarize_tool_result(result: Any, tool_name: str) -> Any:
    """Trim large query results to save LLM context tokens.

    For ``execute_query`` results with >100 rows, keeps:
      - columns (name + dtype inferred from values)
      - head / tail {_SUMMARY_HEAD_TAIL} rows
      - per-column statistics (mean, median, min, max, p25, p75, null count/%, distinct count)
      - total row_count + truncated flag

    Results with ≤100 rows pass through unchanged (model needs all data
    points to create charts).
    """
    if tool_name != "execute_query" or not isinstance(result, dict):
        return result

    rows = result.get("rows")
    if not isinstance(rows, list):
        return result

    columns: List[str] = result.get("columns", [])
    total_rows = len(rows)

    # Small enough — pass through
    if total_rows <= 100:
        return result

    # ------------------------------------------------------------------
    # Build per-column statistics (pure Python — no pandas/numpy required
    # in this module-level helper)
    # ------------------------------------------------------------------
    col_count = len(columns) if columns else (len(rows[0]) if rows else 0)
    col_stats: List[Dict[str, Any]] = []

    for ci in range(col_count):
        cname = columns[ci] if ci < len(columns) else f"col_{ci}"
        values = [row[ci] for row in rows if ci < len(row)]
        total = len(values)

        # ---- classify: numeric vs text ----
        num_vals: List[float] = []
        null_count = 0
        for v in values:
            if v is None:
                null_count += 1
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                num_vals.append(float(v))

        if num_vals and len(num_vals) >= 1:
            sorted_v = sorted(num_vals)
            n = len(sorted_v)
            mean_v = sum(sorted_v) / n
            mid = n // 2
            median_v = (
                sorted_v[mid]
                if n % 2 == 1
                else (sorted_v[mid - 1] + sorted_v[mid]) / 2
            )
            q25_idx = max(0, int(n * 0.25) - 1)
            q75_idx = min(n - 1, int(n * 0.75))
            col_stats.append({
                "column": cname,
                "dtype": "numeric",
                "count": n,
                "null_count": null_count,
                "null_pct": round(null_count / total * 100, 1) if total else 0,
                "min": float(sorted_v[0]),
                "max": float(sorted_v[-1]),
                "mean": round(mean_v, 2),
                "median": round(median_v, 2),
                "p25": float(sorted_v[q25_idx]),
                "p75": float(sorted_v[q75_idx]),
            })
        else:
            distinct = len({str(v) for v in values if v is not None})
            col_stats.append({
                "column": cname,
                "dtype": "text",
                "count": total - null_count,
                "null_count": null_count,
                "null_pct": round(null_count / total * 100, 1) if total else 0,
                "distinct_values": distinct,
            })

    return {
        "columns": columns,
        "head_rows": rows[:_SUMMARY_HEAD_TAIL],
        "tail_rows": rows[-_SUMMARY_HEAD_TAIL:],
        "full_row_count": total_rows,
        "truncated": result.get("truncated", False),
        "column_statistics": col_stats,
        "note": (
            f"Full result has {total_rows} rows (statistics + head/tail {_SUMMARY_HEAD_TAIL} rows shown). "
            "Use the `plotting` tool to create a chart from the full data — do NOT embed data in execute_python."
        ),
    }


def _extract_plotly_axes(figure: dict) -> tuple:
    """Extract x_axis_label, y_axis_label, series_label from Plotly figure dict."""
    layout = figure.get("layout", {}) if isinstance(figure, dict) else {}

    def _safe_title(obj):
        if isinstance(obj, dict):
            t = obj.get("title")
            if isinstance(t, dict):
                return t.get("text")
            if isinstance(t, str):
                return t
        return None

    x_label = _safe_title(layout.get("xaxis")) or None
    y_label = _safe_title(layout.get("yaxis")) or None

    series_label = None
    data_traces = figure.get("data", []) if isinstance(figure, dict) else []
    if isinstance(data_traces, list) and len(data_traces) > 0:
        first_trace = data_traces[0]
        if isinstance(first_trace, dict):
            series_label = first_trace.get("name") or None

    return x_label, y_label, series_label


async def _build_plotly_from_data(
    rows: list, columns: list, chart_title: str, chart_type: str
) -> dict:
    """Build a Plotly figure dict from query result rows (pure Python)."""
    if not rows or not columns:
        return {
            "data": [],
            "layout": {"title": chart_title or "Chart", "xaxis": {}, "yaxis": {}},
        }

    from datetime import date, datetime as dt

    def _safe_val(v):
        """Convert date/datetime to ISO string so the dict is JSON-serializable."""
        if isinstance(v, (date, dt)):
            return v.isoformat()
        return v

    # Extract x and y from first 2 columns
    x_vals = [_safe_val(row[0]) for row in rows if len(row) > 0]
    y_vals = [float(row[1]) for row in rows if len(row) > 1 and row[1] is not None]
    x_label = columns[0] if len(columns) > 0 else "x"
    y_label = columns[1] if len(columns) > 1 else "y"

    trace_type = "bar" if chart_type == "bar" else "scatter"
    mode = "lines+markers" if chart_type == "line" else None

    trace = {"type": trace_type, "x": x_vals, "y": y_vals, "name": y_label}
    if mode:
        trace["mode"] = mode

    figure = {
        "data": [trace],
        "layout": {
            "title": {"text": chart_title or "Chart"},
            "xaxis": {"title": {"text": x_label}},
            "yaxis": {"title": {"text": y_label}},
            "hovermode": "x unified",
            "template": {"layout": {"plot_bgcolor": "white", "paper_bgcolor": "white"}},
        },
    }

    return figure


def _validate_plotly_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    title = str(args.get("chart_title", "")).strip()[:200]
    figure = args.get("figure")
    source_query = (args.get("source_query") or "").strip()
    chart_type = args.get("chart_type", "bar")

    # Mode A: model sends source_query (SQL) — backend will build figure
    if source_query:
        return {
            "chart_type": chart_type,
            "chart_title": title or "Interactive chart",
            "figure": None,  # built later by _build_plotly_from_query
            "source_query": source_query,
            "notes": args.get("notes"),
        }

    # Mode B: model sends figure dict directly
    if not isinstance(figure, dict):
        raise BadRequestException(
            detail="`figure` must be a Plotly figure dict (data + layout), "
                   "or pass `source_query` to have the backend build it."
        )
    if not isinstance(figure.get("data"), list):
        raise BadRequestException(detail="`figure.data` must be a list of traces.")
    return {
        "chart_type": chart_type,
        "chart_title": title or "Interactive chart",
        "figure": figure,
        "source_query": source_query or None,
        "notes": args.get("notes"),
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class AIService:
    """AI Agent driven by the OpenAI `tool_calls` mechanism."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
        self.model = settings.OPENROUTER_MODEL
        self.fallback_model = settings.OPENROUTER_FALLBACK_MODEL
        self.steam = SteamService(db)

    MAX_TOOL_RETRIES = 5  # bumped from 3 for resilience

    # -----------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------
    async def chat(
        self,
        user: AppUser,
        message: str,
        session_id: Optional[str] = None,
        max_tool_steps: int = 15,
    ) -> Dict[str, Any]:
        """OpenAI-native tool-calling loop.

        For every LLM turn the API may return a list of `tool_calls`.
        We dispatch each one, append the resulting `tool` message to
        the conversation, and keep going until the model emits a plain
        text response (no tool calls).
        """
        user_id = user.id
        session_id = (
            session_id
            or f"session_{user_id}_{int(datetime.now().timestamp())}"
        )
        history = await self.get_chat_history(user_id, session_id, limit=10)

        data_context = session_manager.get_all_tables_info() or "No tables available."
        existing_charts = await self._get_existing_chart_summary(user_id)
        system_text = SYSTEM_PROMPT + existing_charts + "\n\n## CURRENT TABLES\n" + data_context

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_text},
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        await self.save_chat(user_id, session_id, "user", message)

        charts_log: List[Dict[str, Any]] = []
        sandbox_files: List[str] = []
        workflow_events: List[Dict[str, Any]] = []
        plotly_specs: List[Dict[str, Any]] = []
        plotly_title: Optional[str] = None
        last_tool_name: Optional[str] = None
        consecutive_failures = 0
        final_reply = ""

        def _record(event: Dict[str, Any]) -> None:
            workflow_events.append(event)

        _record({"stage": "init", "message": "Starting analysis...", "type": "info"})

        for _step in range(max_tool_steps):
            _record({"stage": "llm", "message": "Calling AI…", "type": "info"})
            assistant_msg = await self._call_llm_with_fallback(messages, tools=TOOLS)

            content = (assistant_msg.get("content") or "").strip()
            tool_calls = assistant_msg.get("tool_calls") or []

            if content:
                _record(_assistant_message_event(content))

            if content and not tool_calls:
                final_reply = content
                _record({"stage": "final", "message": "AI produced the answer.", "type": "done"})
                logger.info(">>> BREAK: assistant returned final message (len=%d)", len(content))
                break

            if not tool_calls:
                final_reply = content or "(no response)"
                _record({"stage": "final", "message": "AI finished (no tool calls).", "type": "done"})
                break

            any_failed = False
            for tc in tool_calls:
                if not isinstance(tc, dict):
                    continue
                fn_name = tc.get("function", {}).get("name")
                raw_args = tc.get("function", {}).get("arguments") or "{}"
                tc_id = tc.get("id")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except (TypeError, ValueError):
                    args = {}
                if not isinstance(args, dict):
                    args = {}

                _record(_tool_call_to_event(fn_name or "?", args))

                result = await self._dispatch_tool(
                    user_id=user_id,
                    session_id=session_id,
                    name=fn_name or "",
                    args=args,
                    charts_log=charts_log,
                    sandbox_files=sandbox_files,
                    plotly_specs=plotly_specs,
                )

                if (
                    isinstance(result, dict)
                    and result.get("chart_type") == "plotly"
                    and isinstance(result.get("figure"), dict)
                ):
                    plotly_specs.append(result["figure"])
                    plotly_title = plotly_title or result.get("chart_title")

                has_error = isinstance(result, dict) and result.get("error") is not None
                if has_error:
                    any_failed = True
                    _record({
                        "stage": "tool_error",
                        "message": f"`{fn_name}` failed: {result['error']}",
                        "type": "error",
                    })
                    tool_result_payload = json.dumps(
                        {
                            "error": result["error"],
                            "hint": (
                                "STOP using execute_python. The sandbox has NO database access — "
                                "you cannot connect to PostgreSQL from inside it. "
                                "Use the `plotting` tool instead to create your chart. "
                                "The plotting tool works with the data you already queried via execute_query."
                            ),
                        },
                        ensure_ascii=False,
                        default=str,
                    )
                else:
                    # Summarize large query results to save LLM context tokens.
                    # The LLM only needs schema + head/tail samples to decide the
                    # next step — not the full dataset.
                    summarized = _summarize_tool_result(result, fn_name or "")
                    tool_result_payload = json.dumps(
                        summarized if isinstance(summarized, (dict, list)) else {"result": str(summarized)},
                        ensure_ascii=False,
                        default=str,
                    )

                messages.append({
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": [tc],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_result_payload,
                })

            if any_failed:
                if last_tool_name is None or all(
                    tc.get("function", {}).get("name") == last_tool_name
                    for tc in tool_calls
                ):
                    consecutive_failures += 1
                else:
                    consecutive_failures = 1
                last_tool_name = tool_calls[0].get("function", {}).get("name")
                if consecutive_failures > self.MAX_TOOL_RETRIES:
                    _record({
                        "stage": "abort",
                        "message": f"Tool `{last_tool_name}` failed {consecutive_failures} times. Aborting.",
                        "type": "error",
                    })
                    final_reply = (
                        "Sorry, the system could not complete this request "
                        "after several attempts. Please try a different question."
                    )
                    break
            else:
                last_tool_name = None
                consecutive_failures = 0
        else:
            final_reply = (
                "Reached the processing step limit. Please retry with a shorter question."
            )

        await self.save_chat(user_id, session_id, "assistant", final_reply)
        return {
            "session_id": session_id,
            "reply": final_reply,
            "tool_calls": [],
            "charts": charts_log,
            "sandbox_files": sandbox_files,
            "workflow_events": workflow_events,
            "plotly_specs": plotly_specs,
            "plotly_title": plotly_title,
        }

    # -----------------------------------------------------------------
    # Tool dispatch (replaces the text-based _run_tool_by_name)
    # -----------------------------------------------------------------
    async def _dispatch_tool(
        self,
        user_id: int,
        session_id: str,
        name: str,
        args: Dict[str, Any],
        charts_log: List[Dict[str, Any]],
        sandbox_files: List[str],
        plotly_specs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Route an LLM tool call to the appropriate backend handler."""
        try:
            if name == "execute_query":
                sql = validate_sql(str(args.get("sql", "")))
                return await self.steam.execute_readonly_query(sql, {}, 200)

            if name == "plotting":
                clean = _validate_plotly_payload(args)
                figure = clean.get("figure")

                # Mode A: figure dict provided by model
                if figure is not None and isinstance(figure, dict):
                    layout = figure.get("layout", {}) if isinstance(figure, dict) else {}
                    x_label, y_label, series_label = _extract_plotly_axes(figure)
                else:
                    # Mode B: backend builds figure from source_query
                    sql = validate_sql(str(clean.get("source_query", "")))
                    query_result = await self.steam.execute_readonly_query(sql, {}, 500)
                    rows_data = query_result.get("rows", [])
                    cols = query_result.get("columns", [])
                    chart_type = clean.get("chart_type", "bar")

                    figure = await _build_plotly_from_data(
                        rows_data, cols, clean["chart_title"], chart_type
                    )
                    layout = figure.get("layout", {}) if isinstance(figure, dict) else {}
                    x_label, y_label, series_label = _extract_plotly_axes(figure)

                record = AIChartHistory(
                    user_id=user_id,
                    session_id=session_id,
                    chart_type="plotly",
                    chart_title=clean["chart_title"],
                    x_axis_label=x_label,
                    y_axis_label=y_label,
                    series_label=series_label,
                    config={"figure": figure},
                    source_query=clean.get("source_query"),
                    description=args.get("description"),
                )
                record.created_at = datetime.now(timezone.utc)
                self.db.add(record)
                await self.db.commit()
                await self.db.refresh(record)
                clean["id"] = record.id
                clean["created_at"] = (
                    record.created_at.isoformat() if record.created_at else None
                )
                clean["figure"] = figure
                plotly_specs.append(figure)
                return clean

            if name == "execute_python":
                result = await self.tool_execute_python_code(args)
                if isinstance(result, dict) and result.get("success"):
                    for fname in result.get("sandbox_files") or []:
                        if fname.endswith((".html", ".png", ".csv")):
                            if fname not in sandbox_files:
                                sandbox_files.append(fname)
                    # If the sandbox produced a Plotly chart.json, add it to plotly_specs
                    # so front-end can render interactive charts from execute_python.
                    for fig_dict in result.get("plotly_figures") or []:
                        if isinstance(fig_dict, dict) and isinstance(fig_dict.get("data"), list):
                            plotly_specs.append(fig_dict)
                return result

            if name == "list_data_files":
                return self.tool_list_data_files()

            if name == "get_data_context":
                return await self.tool_get_data_context(args)

            return {"error": f"Unknown tool: {name!r}"}

        except BadRequestException as exc:
            return {"error": str(exc.detail)}
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return {"error": f"Tool execution failed: {exc}"}

    # -----------------------------------------------------------------
    # Tool 1: EXECUTE_QUERY
    # -----------------------------------------------------------------
    async def tool_execute_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        sql = validate_sql(str(args.get("sql", "")))
        params = args.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        limit = int(args.get("limit") or 200)
        return await self.steam.execute_readonly_query(
            sql, params, limit=limit
        )

    # -----------------------------------------------------------------
    # Tool 2: CHARTING (Chart.js)
    # -----------------------------------------------------------------
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
            x_axis_label=clean.get("x_axis_label"),
            y_axis_label=clean.get("y_axis_label"),
            series_label=clean.get("series_label"),
            config=clean["config"],
            source_query=clean.get("source_query"),
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

    # -----------------------------------------------------------------
    # Tool 3: LIST_DATA_FILES
    # -----------------------------------------------------------------
    @staticmethod
    def tool_list_data_files() -> Dict[str, Any]:
        try:
            table_names = session_manager.get_table_names()
            if not table_names:
                return {
                    "success": True,
                    "tables": [],
                    "total": 0,
                    "error": None,
                }
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

    # -----------------------------------------------------------------
    # Tool 4: GET_DATA_CONTEXT
    # -----------------------------------------------------------------
    @staticmethod
    async def tool_get_data_context(args: Dict[str, Any]) -> Dict[str, Any]:
        table_name = (args.get("table_name") or "").strip()
        if not table_name:
            return {"error": "table_name is required."}

        info = session_manager.get_table_info(table_name)
        file_path = session_manager.get_table_file(table_name)

        known_sql = {
            "games", "reviews", "users", "genres", "categories",
            "languages", "game_genres", "game_categories", "game_languages",
        }

        # If it's a known SQL table, return schema info immediately.
        # get_table_file() may return a stale path that doesn't exist on disk.
        if table_name in known_sql:
            schema_text = info or f"Table '{table_name}' (source: PostgreSQL)"
            return {
                "success": True,
                "table_name": table_name,
                "schema": schema_text,
                "source": "sql",
                "error": None,
            }

        # For CSV tables: file_path must exist
        if not file_path:
            return {"error": f"Unknown table '{table_name}'. Use list_data_files to see available tables."}
        if not os.path.isfile(file_path):
            return {"error": f"Data file for '{table_name}' not found at {file_path}."}

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

    # -----------------------------------------------------------------
    # Tool 5: EXECUTE_PYTHON_CODE (E2B sandbox)
    # -----------------------------------------------------------------
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

        if result.get("success") and result.get("sandbox_files"):
            temp_dir = Path(settings.TEMP_DATA_DIR)
            plotly_figures: List[Dict[str, Any]] = []
            for fname in result["sandbox_files"]:
                if fname.endswith(".csv"):
                    table_name = os.path.splitext(fname)[0]
                    if not session_manager.get_table_file(table_name):
                        fp = str(temp_dir / fname)
                        try:
                            from app.services.data_service import DataProcessor
                            ctx = await DataProcessor.extract_data_context_async(fp)
                            session_manager.add_table(
                                table_name=table_name, file_path=fp,
                                columns=ctx.columns,
                            )
                        except Exception as exc:
                            logger.warning("Could not register %s: %s", fname, exc)
                elif fname.endswith(".json"):
                    # Read Plotly figure JSON generated via fig.write_json()
                    fp = str(temp_dir / fname)
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            fig = json.load(f)
                        if isinstance(fig, dict) and isinstance(fig.get("data"), list):
                            plotly_figures.append(fig)
                            logger.info("Loaded Plotly figure from %s", fname)
                    except Exception as exc:
                        logger.warning("Could not read Plotly JSON %s: %s", fname, exc)
            if plotly_figures:
                result["plotly_figures"] = plotly_figures

        return result

    # -----------------------------------------------------------------
    # LLM call helpers
    # -----------------------------------------------------------------
    async def _call_llm_with_fallback(
        self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Call the primary model; on failure, fall back to the secondary."""
        for attempt, model_name in enumerate(
            [self.model, self.fallback_model], 1
        ):
            try:
                kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 8000,
                }
                if tools:
                    kwargs["tools"] = tools
                    # Force the model to call at least one tool when needed.
                    # We don't pass tool_choice so the model can also
                    # return a plain text response when the user is just
                    # chatting.
                resp = await self.client.chat.completions.create(**kwargs)
                msg = resp.choices[0].message
                # OpenAI client returns tool_calls as a list of objects
                # with .id / .function.name / .function.arguments
                # (arguments is a JSON string). Normalise to dicts.
                tcs: List[Dict[str, Any]] = []
                for tc in (msg.tool_calls or []):
                    tcs.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    })
                return {"content": msg.content or "", "tool_calls": tcs}
            except Exception as e:
                logger.warning(
                    "LLM attempt %s (model=%s) failed: %s",
                    attempt, model_name, e,
                )
                if attempt >= 2:
                    raise ServiceUnavailableException(
                        detail=f"Cannot reach OpenRouter: {e}"
                    ) from e
        return {"content": "", "tool_calls": []}

    # -----------------------------------------------------------------
    # Streaming variant (kept for compatibility with /ai/chat/stream)
    # -----------------------------------------------------------------
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

    # -----------------------------------------------------------------
    # Chart / chat persistence (unchanged helpers)
    # -----------------------------------------------------------------
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
                "description": r.description,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def _get_existing_chart_summary(self, user_id: int) -> str:
        """Build a short summary of user's existing charts for the system prompt."""
        q = (
            select(AIChartHistory)
            .where(AIChartHistory.user_id == user_id, AIChartHistory.description.isnot(None))
            .order_by(AIChartHistory.created_at.desc())
            .limit(20)
        )
        rows = list((await self.db.execute(q)).scalars().all())
        if not rows:
            return ""
        lines = ["\n## EXISTING CHARTS (check before creating new — if a chart matches the user's request, you can simply describe it without creating a new one)"]
        for r in rows:
            lines.append(f"- [{r.chart_type}] {r.chart_title}: {r.description or '(no description)'}")
        return "\n".join(lines)

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
