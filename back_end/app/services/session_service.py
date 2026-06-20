"""
Session service - holds the active data context (tables, columns) for a chat session.

We support two table sources:
  - SQL tables (games, reviews, users) from Supabase via the read-only SQL gateway.
  - CSV-derived tables produced by the AI in the E2B sandbox (saved to temp_data/).

The session_manager below is a small in-process registry; the API layer also persists
session metadata in the database (chat_histories).
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class TableInfo:
    """Lightweight description of a tabular data source."""

    def __init__(self, name: str, columns: Dict[str, Dict[str, Any]], source: str, file_path: Optional[str] = None):
        self.name = name
        self.columns = columns  # {col_name: {dtype, business_meaning}}
        self.source = source    # "sql" or "csv"
        self.file_path = file_path

    def describe(self) -> str:
        lines = [f"Table: {self.name} (source: {self.source})"]
        for col, info in self.columns.items():
            lines.append(
                f"  - {col} ({info.get('dtype', 'unknown')}, {info.get('business_meaning', 'Unknown')})"
            )
        return "\n".join(lines)


class SessionManager:
    """In-memory registry of available data tables for the current session."""

    def __init__(self) -> None:
        self.tables: Dict[str, TableInfo] = {}
        self.generated_files: List[str] = []  # absolute paths to generated artifacts
        self._bootstrap_default_tables()

    def _bootstrap_default_tables(self) -> None:
        """Seed the canonical SQL tables so the LLM always knows the schema."""
        self.tables["games"] = TableInfo(
            name="games",
            source="sql",
            columns={
                "steam_appid": {"dtype": "INTEGER", "business_meaning": "Unique Steam application id (PK)"},
                "name": {"dtype": "TEXT", "business_meaning": "Game title"},
                "is_free": {"dtype": "BOOLEAN", "business_meaning": "True if the game is free-to-play"},
                "supported_languages": {"dtype": "TEXT", "business_meaning": "Comma-separated language list"},
                "required_age": {"dtype": "INTEGER", "business_meaning": "Minimum required age"},
                "release_date": {"dtype": "DATE", "business_meaning": "Date the game was released"},
                "publishers": {"dtype": "TEXT", "business_meaning": "Comma-separated publisher names"},
                "developers": {"dtype": "TEXT", "business_meaning": "Comma-separated developer names"},
                "categories": {"dtype": "TEXT", "business_meaning": "Comma-separated category list"},
                "genres": {"dtype": "TEXT", "business_meaning": "Comma-separated genre list"},
                "price_text": {"dtype": "TEXT", "business_meaning": "Human-readable price string"},
                "created_at": {"dtype": "TIMESTAMPTZ", "business_meaning": "Row created at"},
            },
        )
        self.tables["reviews"] = TableInfo(
            name="reviews",
            source="sql",
            columns={
                "recommendationid": {"dtype": "BIGINT", "business_meaning": "Steam recommendation id (PK)"},
                "steam_appid": {"dtype": "INTEGER", "business_meaning": "FK -> games.steam_appid"},
                "steamid": {"dtype": "BIGINT", "business_meaning": "FK -> users.steamid"},
                "language": {"dtype": "TEXT", "business_meaning": "ISO language code"},
                "review_text": {"dtype": "TEXT", "business_meaning": "Body of the review"},
                "timestamp_created": {"dtype": "TIMESTAMPTZ", "business_meaning": "Review creation time"},
                "timestamp_updated": {"dtype": "TIMESTAMPTZ", "business_meaning": "Last update time"},
                "refunded": {"dtype": "BOOLEAN", "business_meaning": "True if the purchase was refunded"},
                "received_for_free": {"dtype": "BOOLEAN", "business_meaning": "True if the game was free"},
                "written_during_early_access": {"dtype": "BOOLEAN", "business_meaning": "Early access flag"},
                "primarily_steam_deck": {"dtype": "BOOLEAN", "business_meaning": "Played mostly on Steam Deck"},
                "playtime_at_review": {"dtype": "INTEGER", "business_meaning": "Playtime at the moment of review (minutes)"},
                "playtime_last_two_weeks": {"dtype": "INTEGER", "business_meaning": "Last 2 weeks playtime"},
                "playtime_forever": {"dtype": "INTEGER", "business_meaning": "Total playtime"},
            },
        )
        self.tables["users"] = TableInfo(
            name="users",
            source="sql",
            columns={
                "steamid": {"dtype": "BIGINT", "business_meaning": "Steam user id (PK)"},
                "personaname": {"dtype": "TEXT", "business_meaning": "Steam display name"},
                "num_games_owned": {"dtype": "INTEGER", "business_meaning": "Number of games owned"},
                "created_at": {"dtype": "TIMESTAMPTZ", "business_meaning": "Row created at"},
            },
        )

    # ---------- table management ----------
    def add_table(self, table_name: str, file_path: Optional[str] = None, columns: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        cols = columns or {}
        self.tables[table_name] = TableInfo(
            name=table_name, columns=cols, source="csv", file_path=file_path
        )

    def get_table_names(self) -> List[str]:
        return list(self.tables.keys())

    def get_all_tables_info(self) -> str:
        if not self.tables:
            return "No tables available."
        return "\n\n".join(t.describe() for t in self.tables.values())

    def get_table_info(self, table_name: str) -> Optional[str]:
        if table_name in self.tables:
            return self.tables[table_name].describe()
        return None

    def get_table_file(self, table_name: str) -> Optional[str]:
        t = self.tables.get(table_name)
        return t.file_path if t else None


# Module-level singleton (per process). Each chat session uses this same registry,
# but tracks per-user state in the DB (chat_histories).
session_manager = SessionManager()
