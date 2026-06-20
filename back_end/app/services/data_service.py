"""
Data service - read-only helpers for SQL and CSV data.

We deliberately separate read-only SQL (against Supabase games/reviews/users)
from CSV analysis (from E2B-produced temp files). The AI agent calls into
this module; it is the only path data can reach the model.
"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.db.session import async_engine
from app.services.session_service import session_manager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL gateway (read-only)
# ---------------------------------------------------------------------------
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|copy|grant|revoke|"
    r"create|vacuum|analyze|refresh|call|do|set\s+|select\s+into|"
    r"merge|returning|with\s+\w+\s+as\s+\(\s*(insert|update|delete))\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> str:
    """Allow only SELECT / WITH statements; reject any DDL/DML keyword."""
    if not sql or not sql.strip():
        raise BadRequestException("SQL trống.")
    cleaned = sql.strip().rstrip(";").strip()
    head = cleaned[:64].lower().lstrip(" (")
    if not (head.startswith("select") or head.startswith("with")):
        raise BadRequestException("Chỉ chấp nhận câu SELECT/WITH (read-only).")
    m = _FORBIDDEN.search(cleaned)
    if m:
        raise BadRequestException(f"SQL chứa từ khóa bị cấm: {m.group(0)}")
    return cleaned


async def _run_sql(sql: str, limit: int) -> Dict[str, Any]:
    cleaned = _validate_sql(sql)
    capped = max(1, min(limit, 500))
    wrapped = f"SELECT * FROM ({cleaned}) AS _ai_sub LIMIT {capped}"
    async with async_engine.connect() as conn:
        result = await conn.execute(text(wrapped))
        cols = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    return {
        "success": True,
        "columns": cols,
        "rows": rows,
        "row_count": len(rows),
        "truncated": len(rows) >= capped,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Public API: query_table (matches structured_workflow's contract)
# ---------------------------------------------------------------------------
async def query_table(
    table: str,
    columns: Optional[List[str]] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
    order_by: Optional[str] = None,
    order_dir: str = "asc",
    limit: int = 20,
) -> Dict[str, Any]:
    """Read-only table query used by the AI agent."""
    if not table:
        return {"success": False, "text": "", "columns": [], "rows": [], "error": "table is required"}
    if limit < 1 or limit > 50:
        limit = 20

    # If table lives on disk (CSV), use pandas-style local read.
    csv_path = session_manager.get_table_file(table)
    if csv_path:
        return await _query_csv(csv_path, columns, filters, order_by, order_dir, limit)

    # Otherwise treat as a SQL table.
    select_cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
    sql = f'SELECT {select_cols} FROM "{table}"'

    params: Dict[str, Any] = {}
    if filters:
        clauses = []
        for i, f in enumerate(filters):
            col = f.get("column")
            op = f.get("op", "=")
            val = f.get("value")
            if not col or op not in ("=", "!=", "<", "<=", ">", ">="):
                continue
            key = f"p{i}"
            clauses.append(f'"{col}" {op} :{key}')
            params[key] = val
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
    if order_by:
        sql += f' ORDER BY "{order_by}" {order_dir.upper()}'
    sql += f" LIMIT {limit}"

    try:
        result = await _run_sql(sql, limit)
    except BadRequestException as exc:
        return {"success": False, "text": "", "columns": [], "rows": [], "error": str(exc.detail)}
    except Exception as exc:
        logger.exception("SQL query failed")
        return {"success": False, "text": "", "columns": [], "rows": [], "error": f"SQL failed: {exc}"}

    # Render a text preview (truncated for prompt context).
    text_lines = [", ".join(result["columns"]) if result["columns"] else "(no columns)"]
    for r in result["rows"][:10]:
        text_lines.append(", ".join(str(v) for v in r))
    return {
        "success": True,
        "text": "\n".join(text_lines) if result["rows"] else "(empty result)",
        "columns": result["columns"],
        "rows": result["rows"],
        "row_count": result["row_count"],
        "truncated": result["truncated"],
    }


async def describe_tables() -> str:
    """Return a human-readable description of all known tables."""
    return session_manager.get_all_tables_info()


# ---------------------------------------------------------------------------
# CSV processing (used by E2B workflow to register new tables)
# ---------------------------------------------------------------------------
class DataProcessor:
    """Helpers to extract column metadata from a CSV file (top rows only)."""

    @staticmethod
    def extract_data_context(csv_path: str, max_rows: int = 50) -> "DataContext":
        import pandas as pd

        df = pd.read_csv(csv_path, nrows=max_rows)
        columns: Dict[str, Dict[str, Any]] = {}
        for col in df.columns:
            dtype = str(df[col].dtype)
            # Map pandas dtype to a friendlier name
            friendly = "TEXT"
            if dtype.startswith("int"):
                friendly = "INTEGER"
            elif dtype.startswith("float"):
                friendly = "FLOAT"
            elif dtype == "bool":
                friendly = "BOOLEAN"
            elif "datetime" in dtype:
                friendly = "TIMESTAMP"
            columns[col] = {
                "dtype": friendly,
                "business_meaning": f"Imported from {Path(csv_path).name}",
            }
        return DataContext(file_path=csv_path, columns=columns)

    @staticmethod
    async def extract_data_context_async(csv_path: str, max_rows: int = 50) -> "DataContext":
        return await asyncio.to_thread(DataProcessor.extract_data_context, csv_path, max_rows)


class DataContext:
    def __init__(self, file_path: str, columns: Dict[str, Dict[str, Any]]):
        self.file_path = file_path
        self.columns = columns


async def _query_csv(
    csv_path: str,
    columns: Optional[List[str]],
    filters: Optional[List[Dict[str, Any]]],
    order_by: Optional[str],
    order_dir: str,
    limit: int,
) -> Dict[str, Any]:
    import pandas as pd

    def _run() -> Dict[str, Any]:
        df = pd.read_csv(csv_path)
        if columns:
            df = df[[c for c in columns if c in df.columns]]
        if filters:
            for f in filters:
                col, op, val = f.get("column"), f.get("op", "="), f.get("value")
                if col not in df.columns:
                    continue
                if op == "=":
                    df = df[df[col] == val]
                elif op == "!=":
                    df = df[df[col] != val]
                else:
                    try:
                        df = df[df[col] <= val] if op == "<=" else df[df[col] >= val] if op == ">=" else df[df[col] < val] if op == "<" else df[df[col] > val]
                    except Exception:
                        pass
        if order_by and order_by in df.columns:
            df = df.sort_values(order_by, ascending=(order_dir.lower() != "desc"))
        truncated = len(df) > limit
        df = df.head(limit)
        cols = list(df.columns)
        rows = [[None if v is None or (isinstance(v, float) and pd.isna(v)) else (v.isoformat() if hasattr(v, "isoformat") else v) for v in row] for row in df.itertuples(index=False, name=None)]
        preview_lines = [", ".join(str(c) for c in cols)] + [", ".join(str(v) for v in r) for r in rows[:10]]
        return {
            "success": True,
            "text": "\n".join(preview_lines) if rows else "(empty)",
            "columns": cols,
            "rows": rows,
            "row_count": len(df),
            "truncated": truncated,
        }

    try:
        return await asyncio.to_thread(_run)
    except Exception as exc:
        return {"success": False, "text": "", "columns": [], "rows": [], "error": f"CSV read failed: {exc}"}
