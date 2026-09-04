"""Small MCP-style gateway and mock server, kept outside the agent runtime.

The gateway deliberately exposes only list_tools/call_tool. Replacing this local
server with an HTTP or stdio MCP client does not change the agent loop.
"""
import asyncio
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx
from sqlalchemy import select, text

from app.agent_harness.types import ToolDefinition
from app.core.config import settings
from app.db.session import AsyncSessionLocal, ReadonlySessionLocal
from app.models.user import AIChartHistory
from app.services.e2b_service import E2BService
from app.utils.sql_helpers import validate_sql


Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

DATA_TABLES = (
    "games", "reviews", "users", "genres", "categories", "languages",
    "game_genres", "game_categories", "game_languages",
)
NUMERIC_TYPES = {"smallint", "integer", "bigint", "numeric", "decimal", "real", "double precision"}
FORBIDDEN_PYTHON = re.compile(
    r"(?i)(?:^|[\s;])(import|from)\s+(?:os|sys|subprocess|socket|requests|httpx|urllib|ftplib|paramiko)\b"
    r"|\b(?:open|eval|exec|compile|__import__)\s*\("
)


def _flatten_output(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _flatten_output(child)]
    return [str(value)]


def _extract_agent_result(execution: dict[str, Any]) -> Any:
    combined = "\n".join(
        _flatten_output(execution.get("results")) + _flatten_output(execution.get("logs"))
    )
    marker = "__AGENT_RESULT__"
    position = combined.rfind(marker)
    if position < 0:
        raise ValueError("Python completed but did not produce a JSON result")
    payload = combined[position + len(marker):].lstrip()
    result, _end = json.JSONDecoder().raw_decode(payload)
    return result


class MockSteamMCPServer:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {
            "query_steam_data": self._query,
            "describe_steam_table": self._describe_table,
            "analyze_with_python": self._analyze_with_python,
            "steam_catalog_overview": self._overview,
            "monthly_game_releases": self._monthly_releases,
            "create_chart": self._create_chart,
            "search_saved_charts": self._search_saved_charts,
            "get_saved_chart": self._get_saved_chart,
            "simulate_failure": self._failure,
            "simulate_slow_tool": self._slow,
            "simulate_disconnect": self._disconnect,
        }

    async def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle the MCP JSON-RPC methods used by this assessment server."""
        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0":
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid Request"}}
        try:
            if request.get("method") == "tools/list":
                tools = await self.list_tools()
                result = {"tools": [{"name": x.name, "description": x.description, "inputSchema": x.input_schema} for x in tools]}
            elif request.get("method") == "tools/call":
                params = request.get("params") or {}
                result = await self.call_tool(str(params.get("name", "")), params.get("arguments") or {})
            else:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except ConnectionError:
            raise
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": str(exc)}}

    async def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                "query_steam_data",
                "Run one read-only SELECT/WITH query over allowlisted Steam tables. Aggregate queries return at most 1200 grouped points; non-aggregate queries return at most 10 sample rows. Never use it to dump a whole table.",
                {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
            ),
            ToolDefinition(
                "describe_steam_table",
                "Inspect one allowlisted Steam table. Returns its columns, row count, compact descriptive statistics, and only 1-10 sample rows. Use this instead of loading raw data when learning the schema.",
                {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "enum": list(DATA_TABLES)},
                        "sample_size": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                    },
                    "required": ["table"],
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                "analyze_with_python",
                "Run a read-only SQL query (max 5000 rows, kept outside model context), then execute model-written Python in isolated E2B with pandas DataFrame `df`. Python must assign a JSON-serializable `result` containing a concise summary and optionally chart {type,title,x,y,x_label,y_label}. Only that compact result is returned to the model.",
                {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "SELECT/WITH query selecting only columns and rows needed for the analysis."},
                        "code": {"type": "string", "description": "Python using the pre-created pandas DataFrame df; assign final output to variable result. Do not read files or make network calls."},
                    },
                    "required": ["sql", "code"],
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                "steam_catalog_overview",
                "Return small aggregate counts for games and reviews.",
                {"type": "object", "properties": {}, "additionalProperties": False},
            ),
            ToolDefinition(
                "monthly_game_releases",
                "Return games grouped by release month and persist a reusable chart. Honor the requested chart_type. Search saved charts first when the user permits cached results.",
                {
                    "type": "object",
                    "properties": {
                        "start_month": {"type": "string", "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$", "description": "Inclusive YYYY-MM; omit only if user gives no lower bound."},
                        "end_month": {"type": "string", "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$", "description": "Inclusive YYYY-MM; omit only if user gives no upper bound."},
                        "chart_type": {"type": "string", "enum": ["bar", "line", "scatter", "area"], "default": "line"},
                        "force_refresh": {"type": "boolean", "default": False, "description": "Set true when the user explicitly requests fresh/current data."},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                "create_chart",
                "Create and persist a reusable chart from a read-only aggregate SQL query. Supports bar, line, scatter and area; returns a chart payload the UI can render. Search saved charts before creating an equivalent chart.",
                {
                    "type": "object",
                    "properties": {
                        "source_query": {"type": "string"},
                        "chart_type": {"type": "string", "enum": ["bar", "line", "scatter", "area"]},
                        "title": {"type": "string", "maxLength": 200},
                        "description": {"type": "string", "maxLength": 1000},
                        "x_column": {"type": "string"},
                        "y_column": {"type": "string"},
                        "x_label": {"type": "string"},
                        "y_label": {"type": "string"},
                        "force_refresh": {"type": "boolean", "default": False},
                    },
                    "required": ["source_query", "chart_type", "title"],
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                "search_saved_charts",
                "Search the current user's saved chart catalog by title/description and optional chart type. Use this before generating a chart to save database, model and sandbox cost.",
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "maxLength": 200},
                        "chart_type": {"type": "string", "enum": ["bar", "line", "scatter", "area"]},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
                    },
                    "additionalProperties": False,
                },
            ),
            ToolDefinition(
                "get_saved_chart",
                "Load one saved chart by chart_id after search_saved_charts. Ownership is enforced from trusted agent context.",
                {"type": "object", "properties": {"chart_id": {"type": "integer"}}, "required": ["chart_id"], "additionalProperties": False},
            ),
            ToolDefinition(
                "simulate_failure",
                "Demo/test tool which returns an intentional tool error.",
                {"type": "object", "properties": {"message": {"type": "string"}}},
            ),
            ToolDefinition(
                "simulate_slow_tool",
                "Test-only tool that sleeps, used to demonstrate MCP timeout handling.",
                {"type": "object", "properties": {"seconds": {"type": "number", "minimum": 0, "maximum": 60}}, "required": ["seconds"]},
            ),
            ToolDefinition(
                "simulate_disconnect",
                "Test-only tool that simulates an MCP transport disconnect.",
                {"type": "object", "properties": {}, "additionalProperties": False},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(name)
        if handler is None:
            return {"ok": False, "error": {"code": "TOOL_NOT_FOUND", "message": f"Unknown tool: {name}"}}
        return await handler(arguments)

    async def _query(self, arguments: dict[str, Any]) -> dict[str, Any]:
        sql = str(arguments.get("sql", "")).strip()
        try:
            sql = validate_sql(sql)
        except Exception as exc:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": str(exc)}}
        is_aggregate = bool(re.search(
            r"(?i)\b(group\s+by|count\s*\(|sum\s*\(|avg\s*\(|min\s*\(|max\s*\(|stddev\w*\s*\(|percentile_\w+\s*\(|date_trunc\s*\()",
            sql,
        ))
        result_limit = 1200 if is_aggregate else 10
        bounded = f"SELECT * FROM ({sql}) AS agent_query LIMIT {result_limit + 1}"
        async with ReadonlySessionLocal() as db:
            result = await db.execute(text(bounded))
            rows = [dict(row._mapping) for row in result.fetchall()]
        truncated = len(rows) > result_limit
        rows = rows[:result_limit]
        return {"ok": True, "content": {"rows": rows, "row_count": len(rows), "truncated": truncated, "data_kind": "aggregate" if is_aggregate else "sample"}}

    async def _overview(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._query({"sql": "SELECT (SELECT count(*) FROM games) AS games, (SELECT count(*) FROM reviews) AS reviews"})

    async def _describe_table(self, arguments: dict[str, Any]) -> dict[str, Any]:
        table = str(arguments.get("table", ""))
        if table not in DATA_TABLES:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "Table is not in the Steam data allowlist"}}
        try:
            sample_size = max(1, min(int(arguments.get("sample_size", 5)), 10))
        except (TypeError, ValueError):
            sample_size = 5
        async with ReadonlySessionLocal() as db:
            column_result = await db.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table
                ORDER BY ordinal_position
            """), {"table": table})
            columns = [dict(row._mapping) for row in column_result.fetchall()]
            if not columns:
                return {"ok": False, "error": {"code": "TABLE_NOT_FOUND", "message": f"Table {table} was not found"}}
            expressions = ["count(*) AS row_count"]
            for column in columns:
                name = column["column_name"]
                expressions.append(f'count(*) - count("{name}") AS "{name}__nulls"')
                if column["data_type"] in NUMERIC_TYPES:
                    expressions.extend([
                        f'min("{name}") AS "{name}__min"',
                        f'max("{name}") AS "{name}__max"',
                        f'avg("{name}")::double precision AS "{name}__avg"',
                    ])
            profile_result = await db.execute(text(f'SELECT {", ".join(expressions)} FROM public."{table}"'))
            profile = dict(profile_result.one()._mapping)
            sample_result = await db.execute(text(f'SELECT * FROM public."{table}" LIMIT {sample_size}'))
            sample = [dict(row._mapping) for row in sample_result.fetchall()]
        return {"ok": True, "content": {"table": table, "columns": columns, "profile": profile, "sample": sample, "sample_size": len(sample)}}

    async def _analyze_with_python(self, arguments: dict[str, Any]) -> dict[str, Any]:
        context = self._context(arguments)
        sql = str(arguments.get("sql", "")).strip()
        code = str(arguments.get("code", "")).strip()
        if not code or len(code) > 12000:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "Python code is empty or exceeds 12000 characters"}}
        if FORBIDDEN_PYTHON.search(code):
            return {"ok": False, "error": {"code": "UNSAFE_PYTHON", "message": "Python may only transform df; filesystem, process, dynamic-code, and network access are forbidden"}}
        try:
            sql = validate_sql(sql)
        except Exception as exc:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": str(exc)}}
        async with ReadonlySessionLocal() as db:
            query_result = await db.execute(text(f"SELECT * FROM ({sql}) AS python_input LIMIT 5001"))
            rows = [dict(row._mapping) for row in query_result.fetchall()]
        if len(rows) > 5000:
            return {"ok": False, "error": {"code": "DATASET_TOO_LARGE", "message": "Python input exceeds 5000 rows. Aggregate or filter the SQL query first."}}
        dataset_json = json.dumps(rows, default=str).replace("</", "<\\/")
        if len(dataset_json.encode("utf-8")) > 5 * 1024 * 1024:
            return {"ok": False, "error": {"code": "DATASET_TOO_LARGE", "message": "Python input exceeds 5 MiB. Select fewer columns or aggregate/filter in SQL first."}}
        wrapped = (
            "import json\nimport pandas as pd\n"
            f"df = pd.DataFrame(json.loads({dataset_json!r}))\n"
            "result = None\n"
            + code
            + "\nif result is None:\n    raise ValueError('Python code must assign result')\n"
              "print('__AGENT_RESULT__' + json.dumps(result, default=str, ensure_ascii=False))\n"
        )
        execution = await E2BService.execute(wrapped, timeout_s=settings.E2B_TIMEOUT)
        if not execution.get("success"):
            return {"ok": False, "error": {"code": "PYTHON_EXECUTION_FAILED", "message": str(execution.get("error", "Sandbox execution failed"))[:1200]}}
        try:
            compact_result = _extract_agent_result(execution)
        except (ValueError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": {"code": "INVALID_PYTHON_RESULT", "message": str(exc)}}
        if not isinstance(compact_result, dict):
            return {"ok": False, "error": {"code": "INVALID_PYTHON_RESULT", "message": "result must be an object with summary/statistics/chart/notes"}}
        unexpected = set(compact_result) - {"summary", "statistics", "chart", "notes"}
        if unexpected:
            return {"ok": False, "error": {"code": "INVALID_PYTHON_RESULT", "message": f"Unsupported result fields: {', '.join(sorted(unexpected))}"}}
        chart = compact_result.get("chart")
        if chart is not None:
            if not isinstance(chart, dict) or not isinstance(chart.get("x"), list) or not isinstance(chart.get("y"), list):
                return {"ok": False, "error": {"code": "INVALID_CHART", "message": "chart must contain x and y arrays"}}
            if len(chart["x"]) != len(chart["y"]) or len(chart["x"]) > 1200:
                return {"ok": False, "error": {"code": "INVALID_CHART", "message": "chart x/y must have equal length and at most 1200 points"}}
        encoded = json.dumps(compact_result, default=str)
        if len(encoded.encode("utf-8")) > 65536:
            return {"ok": False, "error": {"code": "RESULT_TOO_LARGE", "message": "Python result exceeds 64 KiB; return only summary statistics and a bounded chart."}}
        content = {"input_row_count": len(rows), "result": compact_result, "raw_data_exposed_to_model": False}
        if isinstance(compact_result, dict) and isinstance(compact_result.get("chart"), dict):
            # Keep the common chart location so the existing web client renders it.
            content["chart"] = compact_result["chart"]
            chart_id = await self._save_chart(
                context, compact_result["chart"], sql,
                str(compact_result.get("summary") or compact_result.get("notes") or "Python analysis chart"),
            )
            if chart_id is not None:
                content["chart_id"] = chart_id
        return {"ok": True, "content": content}

    async def _monthly_releases(self, arguments: dict[str, Any]) -> dict[str, Any]:
        # This is a bounded aggregate tool, not an arbitrary row query. Do not
        # inherit query_steam_data's 200-row cap: one point represents a month,
        # and 1,200 months still bounds the payload to a century of data.
        start_month = arguments.get("start_month")
        end_month = arguments.get("end_month")
        chart_type = str(arguments.get("chart_type", "line")).lower()
        if chart_type not in {"bar", "line", "scatter", "area"}:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "Unsupported chart_type"}}
        context = self._context(arguments)
        cache_material = f"monthly_game_releases|{start_month}|{end_month}|{chart_type}"
        if context.get("user_id") and not bool(arguments.get("force_refresh", False)):
            cache_key = self._cache_key(cache_material, chart_type)
            cached = await self._find_cached_chart(int(context["user_id"]), cache_key)
            if cached is not None and isinstance(cached.config, dict) and isinstance(cached.config.get("chart"), dict):
                return {"ok": True, "content": {"chart_id": cached.id, "chart": cached.config["chart"], "cached": True}}
        month_pattern = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
        if start_month and not month_pattern.fullmatch(str(start_month)) or end_month and not month_pattern.fullmatch(str(end_month)):
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "Months must use YYYY-MM"}}
        filters = ["release_date IS NOT NULL"]
        params: dict[str, Any] = {}
        if start_month:
            filters.append("release_date >= to_date(:start_month, 'YYYY-MM')")
            params["start_month"] = start_month
        if end_month:
            filters.append("release_date < (to_date(:end_month, 'YYYY-MM') + interval '1 month')")
            params["end_month"] = end_month
        sql = f"""SELECT to_char(date_trunc('month', release_date), 'YYYY-MM') AS month,
                        count(*) AS game_count
                 FROM games
                 WHERE {' AND '.join(filters)}
                 GROUP BY date_trunc('month', release_date)
                 ORDER BY date_trunc('month', release_date)
                 LIMIT 1200"""
        async with ReadonlySessionLocal() as db:
            query_result = await db.execute(text(sql), params)
            rows = [dict(row._mapping) for row in query_result.fetchall()]
        content = {"rows": rows, "row_count": len(rows), "truncated": len(rows) == 1200,
                   "applied_filters": {"start_month": start_month, "end_month": end_month},
                   "data_range": {"start_month": rows[0]["month"] if rows else None, "end_month": rows[-1]["month"] if rows else None}}
        content["chart"] = {
            "type": chart_type,
            "title": "Games released by month",
            "x": [row["month"] for row in rows],
            "y": [row["game_count"] for row in rows],
            "x_label": "Month",
            "y_label": "New games",
        }
        chart_id = await self._save_chart(
            context,
            content["chart"],
            sql,
            f"Monthly game releases from {start_month or 'earliest data'} to {end_month or 'latest data'}",
            cache_material=cache_material,
        )
        if chart_id is not None:
            content["chart_id"] = chart_id
        return {"ok": True, "content": content}

    @staticmethod
    def _context(arguments: dict[str, Any]) -> dict[str, Any]:
        value = arguments.pop("__agent_context", {})
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _cache_key(source_query: str, chart_type: str) -> str:
        normalized = " ".join(source_query.lower().split())
        return hashlib.sha256(f"{chart_type}|{normalized}".encode("utf-8")).hexdigest()

    async def _find_cached_chart(self, user_id: int, cache_key: str) -> AIChartHistory | None:
        async with AsyncSessionLocal() as db:
            rows = (await db.scalars(
                select(AIChartHistory)
                .where(AIChartHistory.user_id == user_id)
                .order_by(AIChartHistory.created_at.desc())
                .limit(100)
            )).all()
            return next((row for row in rows if isinstance(row.config, dict) and row.config.get("cache_key") == cache_key), None)

    @staticmethod
    def _chart_from_record(row: AIChartHistory) -> dict[str, Any] | None:
        """Normalize current, legacy Plotly, and legacy Chart.js records."""
        config = row.config if isinstance(row.config, dict) else {}
        if isinstance(config.get("chart"), dict):
            return config["chart"]
        figure = config.get("figure")
        if isinstance(figure, dict) and isinstance(figure.get("data"), list) and figure["data"]:
            trace = figure["data"][0]
            if isinstance(trace, dict) and isinstance(trace.get("x"), list) and isinstance(trace.get("y"), list):
                trace_type = str(trace.get("type", "scatter")).lower()
                chart_type = "bar" if trace_type == "bar" else "scatter" if trace.get("mode") == "markers" else "line"
                return {
                    "type": chart_type, "title": row.chart_title or "Saved chart",
                    "x": trace["x"], "y": trace["y"],
                    "x_label": row.x_axis_label or "", "y_label": row.y_axis_label or "",
                }
        labels = config.get("labels")
        datasets = config.get("datasets")
        if isinstance(labels, list) and isinstance(datasets, list) and datasets and isinstance(datasets[0], dict) and isinstance(datasets[0].get("data"), list):
            chart_type = row.chart_type if row.chart_type in {"bar", "line", "scatter", "area"} else "bar"
            return {
                "type": chart_type, "title": row.chart_title or "Saved chart",
                "x": labels, "y": datasets[0]["data"],
                "x_label": row.x_axis_label or "", "y_label": row.y_axis_label or datasets[0].get("label", ""),
            }
        return None

    async def _save_chart(
        self,
        context: dict[str, Any],
        chart: dict[str, Any],
        source_query: str,
        description: str,
        *,
        cache_material: str | None = None,
    ) -> int | None:
        user_id = context.get("user_id")
        session_id = context.get("session_id")
        if not user_id or not session_id:
            return None
        chart_type = str(chart.get("type", "line"))
        cache_key = self._cache_key(cache_material or source_query, chart_type)
        cached = await self._find_cached_chart(int(user_id), cache_key)
        if cached is not None:
            return int(cached.id)
        config = {"chart": chart, "cache_key": cache_key, "created_by_run_id": context.get("run_id")}
        row = AIChartHistory(
            user_id=int(user_id), session_id=str(session_id), chart_type=chart_type,
            chart_title=str(chart.get("title") or "Chart")[:200],
            x_axis_label=str(chart.get("x_label") or "")[:200] or None,
            y_axis_label=str(chart.get("y_label") or "")[:200] or None,
            series_label=str(chart.get("y_label") or "")[:200] or None,
            config=config, source_query=source_query,
            description=description[:1000], created_at=datetime.now(timezone.utc),
        )
        async with AsyncSessionLocal() as db:
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return int(row.id)

    async def _search_saved_charts(self, arguments: dict[str, Any]) -> dict[str, Any]:
        context = self._context(arguments)
        if not context.get("user_id"):
            return {"ok": False, "error": {"code": "MISSING_AGENT_CONTEXT", "message": "Authenticated user context is required"}}
        query = str(arguments.get("query", "")).lower().strip()
        chart_type = arguments.get("chart_type")
        limit = max(1, min(int(arguments.get("limit", 10)), 20))
        async with AsyncSessionLocal() as db:
            rows = (await db.scalars(
                select(AIChartHistory)
                .where(AIChartHistory.user_id == int(context["user_id"]))
                .order_by(AIChartHistory.created_at.desc()).limit(100)
            )).all()
        matches = []
        for row in rows:
            haystack = f"{row.chart_title or ''} {row.description or ''}".lower()
            if query and not all(token in haystack for token in query.split()):
                continue
            normalized = self._chart_from_record(row)
            normalized_type = normalized.get("type") if normalized else row.chart_type
            if chart_type and normalized_type != chart_type:
                continue
            matches.append({"chart_id": row.id, "title": row.chart_title, "description": row.description, "chart_type": normalized_type, "created_at": row.created_at, "renderable": normalized is not None})
            if len(matches) >= limit:
                break
        return {"ok": True, "content": {"charts": matches, "count": len(matches)}}

    async def _get_saved_chart(self, arguments: dict[str, Any]) -> dict[str, Any]:
        context = self._context(arguments)
        if not context.get("user_id"):
            return {"ok": False, "error": {"code": "MISSING_AGENT_CONTEXT", "message": "Authenticated user context is required"}}
        try:
            chart_id = int(arguments.get("chart_id"))
        except (TypeError, ValueError):
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "chart_id must be an integer"}}
        async with AsyncSessionLocal() as db:
            row = await db.scalar(select(AIChartHistory).where(AIChartHistory.id == chart_id, AIChartHistory.user_id == int(context["user_id"])))
        if row is None:
            return {"ok": False, "error": {"code": "CHART_NOT_FOUND", "message": "Saved chart was not found"}}
        chart = self._chart_from_record(row)
        if not isinstance(chart, dict):
            return {"ok": False, "error": {"code": "UNSUPPORTED_CHART_FORMAT", "message": "This saved chart format cannot be rendered by the current client"}}
        return {"ok": True, "content": {"chart_id": row.id, "chart": chart, "cached": True, "source_query": row.source_query, "description": row.description}}

    async def _create_chart(self, arguments: dict[str, Any]) -> dict[str, Any]:
        context = self._context(arguments)
        source_query = str(arguments.get("source_query", "")).strip()
        chart_type = str(arguments.get("chart_type", "bar")).lower()
        if chart_type not in {"bar", "line", "scatter", "area"}:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": "Unsupported chart_type"}}
        try:
            source_query = validate_sql(source_query)
        except Exception as exc:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": str(exc)}}
        cache_key = self._cache_key(source_query, chart_type)
        if context.get("user_id") and not bool(arguments.get("force_refresh", False)):
            cached = await self._find_cached_chart(int(context["user_id"]), cache_key)
            if cached is not None and isinstance(cached.config, dict) and isinstance(cached.config.get("chart"), dict):
                return {"ok": True, "content": {"chart_id": cached.id, "chart": cached.config["chart"], "cached": True}}
        async with ReadonlySessionLocal() as db:
            result = await db.execute(text(f"SELECT * FROM ({source_query}) AS chart_source LIMIT 1201"))
            rows = [dict(row._mapping) for row in result.fetchall()]
        if len(rows) > 1200:
            return {"ok": False, "error": {"code": "CHART_TOO_LARGE", "message": "Chart query exceeds 1200 points; aggregate or filter it"}}
        if not rows:
            return {"ok": False, "error": {"code": "NO_DATA", "message": "Chart query returned no rows"}}
        columns = list(rows[0])
        x_column = str(arguments.get("x_column") or columns[0])
        y_column = str(arguments.get("y_column") or (columns[1] if len(columns) > 1 else ""))
        if x_column not in columns or y_column not in columns:
            return {"ok": False, "error": {"code": "INVALID_ARGUMENT", "message": f"x_column/y_column must be among: {', '.join(columns)}"}}
        chart = {
            "type": chart_type, "title": str(arguments.get("title") or "Chart")[:200],
            "x": [row[x_column] for row in rows], "y": [row[y_column] for row in rows],
            "x_label": str(arguments.get("x_label") or x_column)[:200],
            "y_label": str(arguments.get("y_label") or y_column)[:200],
        }
        chart_id = await self._save_chart(context, chart, source_query, str(arguments.get("description") or chart["title"]))
        return {"ok": True, "content": {"chart_id": chart_id, "chart": chart, "cached": False, "row_count": len(rows)}}

    async def _failure(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "error": {"code": "MOCK_FAILURE", "message": arguments.get("message", "Intentional failure")}}

    async def _slow(self, arguments: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(max(0.0, min(float(arguments.get("seconds", 0)), 60.0)))
        return {"ok": True, "content": {"slept": arguments.get("seconds", 0)}}

    async def _disconnect(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        raise ConnectionError("Mock MCP connection dropped")


class MCPGateway:
    def __init__(self, server: MockSteamMCPServer, timeout_seconds: float = 12.0, agent_context: dict[str, Any] | None = None) -> None:
        self.server = server
        self.timeout_seconds = timeout_seconds
        self.agent_context = agent_context or {}

    async def list_tools(self) -> list[ToolDefinition]:
        response = await self._request("tools/list", {})
        return [ToolDefinition(x["name"], x["description"], x["inputSchema"]) for x in response["tools"]]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            arguments = {**arguments, "__agent_context": self.agent_context}
            timeout = max(self.timeout_seconds, settings.E2B_TIMEOUT + 10) if name == "analyze_with_python" else self.timeout_seconds
            return await self._request("tools/call", {"name": name, "arguments": arguments}, timeout_seconds=timeout)
        except asyncio.TimeoutError:
            return {"ok": False, "error": {"code": "TOOL_TIMEOUT", "message": f"Tool {name} timed out"}}
        except ConnectionError as exc:
            return {"ok": False, "error": {"code": "MCP_DISCONNECTED", "message": str(exc)}}

    async def _request(self, method: str, params: dict[str, Any], timeout_seconds: float | None = None) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        response = await asyncio.wait_for(
            self.server.handle({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}),
            timeout_seconds or self.timeout_seconds,
        )
        if response.get("id") != request_id:
            raise ConnectionError("MCP response id did not match request")
        if "error" in response:
            error = response["error"]
            return {"ok": False, "error": {"code": f"MCP_RPC_{error.get('code')}", "message": error.get("message", "MCP error")}}
        return response["result"]


class HTTPMCPGateway:
    """Client for the independently runnable MCP JSON-RPC HTTP server."""

    def __init__(self, url: str, shared_secret: str, timeout_seconds: float = 12.0, agent_context: dict[str, Any] | None = None) -> None:
        self.url = url
        self.shared_secret = shared_secret
        self.timeout_seconds = timeout_seconds
        self.agent_context = agent_context or {}

    async def list_tools(self) -> list[ToolDefinition]:
        result = await self._request("tools/list", {})
        return [ToolDefinition(x["name"], x["description"], x["inputSchema"]) for x in result["tools"]]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            arguments = {**arguments, "__agent_context": self.agent_context}
            timeout = max(self.timeout_seconds, settings.E2B_TIMEOUT + 10) if name == "analyze_with_python" else self.timeout_seconds
            return await self._request("tools/call", {"name": name, "arguments": arguments}, timeout_seconds=timeout)
        except httpx.TimeoutException:
            return {"ok": False, "error": {"code": "TOOL_TIMEOUT", "message": f"Tool {name} timed out"}}
        except (httpx.HTTPError, ConnectionError) as exc:
            return {"ok": False, "error": {"code": "MCP_DISCONNECTED", "message": str(exc)}}

    async def _request(self, method: str, params: dict[str, Any], timeout_seconds: float | None = None) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        headers = {"Accept": "application/json"}
        if self.shared_secret:
            headers["Authorization"] = f"Bearer {self.shared_secret}"
        async with httpx.AsyncClient(timeout=timeout_seconds or self.timeout_seconds) as client:
            response = await client.post(
                self.url,
                headers=headers,
                json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            )
            response.raise_for_status()
            envelope = response.json()
        if envelope.get("id") != request_id:
            raise ConnectionError("MCP response id did not match request")
        if "error" in envelope:
            error = envelope["error"]
            return {"ok": False, "error": {"code": f"MCP_RPC_{error.get('code')}", "message": error.get("message", "MCP error")}}
        return envelope["result"]
