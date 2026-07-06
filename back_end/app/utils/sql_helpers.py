"""
SQL validation helper - shared by ai_service.py and data_service.py.

Validates that a SQL string is read-only (SELECT/WITH only) and does not
contain any DDL/DML keywords. This is defense-in-depth; the database user
should also be granted SELECT-only permissions.
"""
import re

from app.core.exceptions import BadRequestException

# Unified forbidden keywords (merged from ai_service.py and data_service.py).
# Matches: insert, update, delete, drop, alter, truncate, copy, grant, revoke,
# create, vacuum, analyze, refresh, call, do, set, select into, merge,
# returning, and CTEs that wrap write operations.
_FORBIDDEN_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|copy|grant|revoke|"
    r"create|vacuum|analyze|refresh|call|do|set\s+|select\s+into|"
    r"merge|returning|with\s+\w+\s+as\s+\(\s*(insert|update|delete))\b",
    re.IGNORECASE,
)


def validate_sql(sql: str) -> str:
    """Allow only SELECT / WITH statements; reject any DDL/DML keyword.

    Returns the cleaned SQL string (without trailing semicolon).
    Raises BadRequestException if the SQL is empty or contains forbidden keywords.
    """
    if not sql or not sql.strip():
        raise BadRequestException(detail="Empty SQL.")
    cleaned = sql.strip().rstrip(";").strip()
    head = cleaned[:64].lower().lstrip(" (")
    if not (head.startswith("select") or head.startswith("with")):
        raise BadRequestException(
            detail="Only SELECT/WITH statements are allowed (read-only)."
        )
    match = _FORBIDDEN_PATTERN.search(cleaned)
    if match:
        raise BadRequestException(
            detail=f"SQL contains forbidden keyword: {match.group(0)}."
        )
    return cleaned