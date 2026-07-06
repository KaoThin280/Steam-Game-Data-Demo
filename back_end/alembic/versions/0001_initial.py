"""Initial schema - matches db_init_supabase.sql

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-06 14:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial schema from db_init_supabase.sql."""
    # pgcrypto for gen_random_uuid (defensive)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ==== Roles / Permissions / RBAC ====
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("role_name", sa.Text, nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("permission_name", sa.Text, nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("resource", sa.Text),
        sa.Column("action", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.BigInteger, sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    # ==== App users / refresh tokens ====
    op.create_table(
        "app_users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_login", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_app_users_email", "app_users", ["email"])
    op.create_index("idx_app_users_active", "app_users", ["is_active"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("app_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text, nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_refresh_user", "refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_expires", "refresh_tokens", ["expires_at"])

    # ==== Steam data ====
    op.create_table(
        "games",
        sa.Column("steam_appid", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("is_free", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("required_age", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("release_date", sa.Date),
        sa.Column("publishers", sa.Text),
        sa.Column("developers", sa.Text),
        sa.Column("price_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_games_name", "games", ["name"])
    op.create_index("idx_games_is_free", "games", ["is_free"])
    op.create_index("idx_games_release", "games", ["release_date"])

    op.create_table(
        "users",
        sa.Column("steamid", sa.BigInteger, primary_key=True),
        sa.Column("personaname", sa.Text),
        sa.Column("num_games_owned", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_users_personaname", "users", ["personaname"])

    op.create_table(
        "reviews",
        sa.Column("recommendationid", sa.BigInteger, primary_key=True),
        sa.Column("steam_appid", sa.Integer, sa.ForeignKey("games.steam_appid", ondelete="CASCADE"), nullable=False),
        sa.Column("steamid", sa.BigInteger, sa.ForeignKey("users.steamid", ondelete="CASCADE"), nullable=False),
        sa.Column("language", sa.Text),
        sa.Column("review_text", sa.Text),
        sa.Column("timestamp_created", sa.DateTime(timezone=True)),
        sa.Column("timestamp_updated", sa.DateTime(timezone=True)),
        sa.Column("refunded", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("received_for_free", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("written_during_early_access", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("primarily_steam_deck", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("playtime_at_review", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("playtime_last_two_weeks", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("playtime_forever", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_reviews_appid", "reviews", ["steam_appid"])
    op.create_index("idx_reviews_steamid", "reviews", ["steamid"])
    op.create_index("idx_reviews_language", "reviews", ["language"])
    op.create_index("idx_reviews_created", "reviews", ["timestamp_created"])
    op.create_index("idx_reviews_voted", "reviews", ["steam_appid", "refunded"])

    # ==== AI history ====
    op.create_table(
        "chat_histories",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("role IN ('user','assistant','system','tool')", name="chat_histories_role_check"),
    )
    op.create_index("idx_chat_user_session", "chat_histories", ["user_id", "session_id", sa.text("created_at DESC")])

    op.create_table(
        "ai_chart_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("chart_type", sa.Text, nullable=False),
        sa.Column("chart_title", sa.Text),
        sa.Column("x_axis_label", sa.Text),
        sa.Column("y_axis_label", sa.Text),
        sa.Column("series_label", sa.Text),
        sa.Column("config", postgresql.JSONB, nullable=False),
        sa.Column("source_query", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_chart_user_session", "ai_chart_history", ["user_id", "session_id", sa.text("created_at DESC")])


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table("ai_chart_history")
    op.drop_table("chat_histories")
    op.drop_table("reviews")
    op.drop_table("users")
    op.drop_table("games")
    op.drop_table("refresh_tokens")
    op.drop_table("user_roles")
    op.drop_table("app_users")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")