"""
Steam Service - Logic for public.games / public.reviews / public.users.
Aligned with SCHEMA_DOCUMENTATION.md.

Schema notes:
  - games.publishers / games.developers are TEXT columns containing
    comma-separated values (e.g. "Action, RPG, Indie").
  - games.genres / categories / supported_languages have been removed
    from the schema (2026-Q2 simplification).
  - reviews stores one row per user recommendation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import selectinload

from sqlalchemy import and_, asc, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.steam import Game, Review, SteamUser
from app.schemas.steam_schema import (
    GameCreate,
    GameFilter,
    ReviewCreate,
    ReviewFilter,
)


def _contains_ci(column, value: str):
    """Case-insensitive contains on a TEXT (CSV) column."""
    pattern = f"%{value}%"
    return column.ilike(pattern)


class SteamService:
    """Service for Steam game data logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ===================== Games =====================
    async def get_game_by_appid(self, steam_appid: int) -> Game:
        result = await self.db.execute(
            select(Game).where(Game.steam_appid == steam_appid)
        )
        game = result.scalar_one_or_none()
        if not game:
            raise NotFoundException(
                detail=f"Game steam_appid={steam_appid} not found."
            )
        return game

    async def list_games(
        self, filter_: GameFilter
    ) -> Tuple[List[Game], int]:
        """List games filtered + sorted + paginated."""
        query = select(Game).options(selectinload(Game.game_genres))
        from sqlalchemy.orm import selectinload

    count_q = select(func.count(Game.steam_appid))
        conds = []

        if filter_.search:
            kw = f"%{filter_.search}%"
            conds.append(
                or_(
                    Game.name.ilike(kw),
                    Game.developers.ilike(kw),
                    Game.publishers.ilike(kw),
                )
            )
        # NOTE: the genre/category filters used to query the games.genres and
        # games.categories CSV columns. Those columns have been REMOVED from
        # the schema, so these filters are no-ops. They are kept for
        # backwards compatibility with the existing FE.
        if filter_.developer:
            conds.append(_contains_ci(Game.developers, filter_.developer))
        if filter_.publisher:
            conds.append(_contains_ci(Game.publishers, filter_.publisher))
        if filter_.is_free is not None:
            conds.append(Game.is_free == filter_.is_free)
        if filter_.year is not None:
            conds.append(
                func.extract("year", Game.release_date) == filter_.year
            )

        if conds:
            query = query.where(and_(*conds))
            count_q = count_q.where(and_(*conds))

        sort_col = {
            "release_date": Game.release_date,
            "name": Game.name,
            "required_age": Game.required_age,
        }.get(filter_.sort_by, Game.release_date)
        query = query.order_by(
            asc(sort_col) if filter_.sort_order == "asc" else desc(sort_col)
        )

        offset = (filter_.page - 1) * filter_.page_size
        query = query.offset(offset).limit(filter_.page_size)
        items = list((await self.db.execute(query)).scalars().all())
        total = (await self.db.execute(count_q)).scalar() or 0
        return items, int(total)

    async def upsert_game(self, payload: GameCreate) -> Game:
        """Create or update a game by steam_appid (admin)."""
        data = payload.model_dump()
        existing = await self.db.execute(
            select(Game).where(Game.steam_appid == data["steam_appid"])
        )
        game = existing.scalar_one_or_none()
        if game:
            for k, v in data.items():
                setattr(game, k, v)
        else:
            game = Game(**data)
            self.db.add(game)
        await self.db.commit()
        await self.db.refresh(game)
        return game

    async def delete_game(self, steam_appid: int) -> None:
        """Delete a game by steam_appid (admin)."""
        result = await self.db.execute(
            select(Game).where(Game.steam_appid == steam_appid)
        )
        game = result.scalar_one_or_none()
        if not game:
            raise NotFoundException(
                detail=f"Game steam_appid={steam_appid} not found."
            )
        await self.db.delete(game)
        await self.db.commit()

    # ===================== Reviews =====================
    async def list_reviews(
        self,
        steam_appid: int,
        filter_: ReviewFilter,
    ) -> Tuple[List[Review], int]:
        # Ensure game exists
        await self.get_game_by_appid(steam_appid)
        query = select(Review).where(Review.steam_appid == steam_appid)
        count_q = select(func.count(Review.recommendationid)).where(
            Review.steam_appid == steam_appid
        )
        if filter_.language:
            query = query.where(Review.language == filter_.language)
            count_q = count_q.where(Review.language == filter_.language)
        if filter_.refunded is not None:
            query = query.where(Review.refunded == filter_.refunded)
            count_q = count_q.where(Review.refunded == filter_.refunded)
        if filter_.received_for_free is not None:
            query = query.where(
                Review.received_for_free == filter_.received_for_free
            )
            count_q = count_q.where(
                Review.received_for_free == filter_.received_for_free
            )
        if filter_.primarily_steam_deck is not None:
            query = query.where(
                Review.primarily_steam_deck == filter_.primarily_steam_deck
            )
            count_q = count_q.where(
                Review.primarily_steam_deck == filter_.primarily_steam_deck
            )
        if filter_.min_playtime_forever is not None:
            query = query.where(
                Review.playtime_forever >= filter_.min_playtime_forever
            )
            count_q = count_q.where(
                Review.playtime_forever >= filter_.min_playtime_forever
            )

        query = query.order_by(
            desc(Review.timestamp_created), desc(Review.recommendationid)
        )
        offset = (filter_.page - 1) * filter_.page_size
        query = query.offset(offset).limit(filter_.page_size)
        items = list((await self.db.execute(query)).scalars().all())
        total = (await self.db.execute(count_q)).scalar() or 0
        return items, int(total)

    async def create_review(self, payload: ReviewCreate) -> Review:
        """Create a new review (scientist / admin)."""
        review = Review(**payload.model_dump())
        self.db.add(review)
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def delete_review(self, recommendationid: int) -> None:
        result = await self.db.execute(
            select(Review).where(Review.recommendationid == recommendationid)
        )
        review = result.scalar_one_or_none()
        if not review:
            raise NotFoundException(
                detail=f"Review #{recommendationid} not found."
            )
        await self.db.delete(review)
        await self.db.commit()

    # ===================== Dashboard =====================
    async def get_overview_stats(self) -> Dict[str, Any]:
        """Aggregate dashboard statistics."""
        total_games = (
            await self.db.execute(select(func.count(Game.steam_appid)))
        ).scalar() or 0
        total_reviews = (
            await self.db.execute(select(func.count(Review.recommendationid)))
        ).scalar() or 0
        free_games = (
            await self.db.execute(
                select(func.count(Game.steam_appid)).where(
                    Game.is_free == True  # noqa: E712
                )
            )
        ).scalar() or 0

        # Count unique developers (PostgreSQL string_to_array + DISTINCT).
        devs_q = text(
            """
            SELECT COUNT(DISTINCT dev) FROM (
                SELECT TRIM(dev) AS dev
                FROM games, UNNEST(STRING_TO_ARRAY(developers, ',')) AS dev
                WHERE developers IS NOT NULL AND developers <> ''
            ) t WHERE dev <> ''
            """
        )
        total_devs = (await self.db.execute(devs_q)).scalar() or 0

        # Count real languages (junction table)
        langs_q = text("SELECT COUNT(*) FROM languages")
        total_langs = (await self.db.execute(langs_q)).scalar() or 0

        return {
            "total_games": int(total_games),
            "total_reviews": int(total_reviews),
            "free_games": int(free_games),
            "paid_games": int(total_games - free_games),
            "total_developers": int(total_devs),
            "total_languages": int(total_langs),
        }

    async def get_genre_distribution(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Genre distribution via game_genres junction table."""
        q = text(
            """
            SELECT g.name AS genre, COUNT(gg.steam_appid) AS count
            FROM genres g
            JOIN game_genres gg ON g.id = gg.genre_id
            GROUP BY g.id, g.name
            ORDER BY count DESC
            LIMIT :lim
            """
        )
        result = await self.db.execute(q, {"lim": limit})
        return [{"genre": r[0], "count": int(r[1])} for r in result.fetchall()]

    async def get_year_distribution(self, limit: int = 30) -> List[Dict[str, Any]]:
        q = text(
            """
            SELECT EXTRACT(YEAR FROM release_date)::INT AS year, COUNT(*) AS count
            FROM games
            WHERE release_date IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
            LIMIT :lim
            """
        )
        result = await self.db.execute(q, {"lim": limit})
        rows = []
        for r in result.fetchall():
            year_val = int(r[0]) if r[0] is not None else 0
            rows.append({"year": year_val, "count": int(r[1])})
        return rows

    async def get_language_distribution(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Language distribution via game_languages junction table."""
        q = text(
            """
            SELECT l.name AS language, COUNT(gl.steam_appid) AS count
            FROM languages l
            JOIN game_languages gl ON l.id = gl.language_id
            GROUP BY l.id, l.name
            ORDER BY count DESC
            LIMIT :lim
            """
        )
        result = await self.db.execute(q, {"lim": limit})
        return [{"language": r[0], "count": int(r[1])} for r in result.fetchall()]

    async def get_top_games(
        self, limit: int = 10, sort_by: str = "total_reviews"
    ) -> List[Game]:
        """
        Top games by review count. Because the schema does not pre-aggregate,
        we JOIN reviews + COUNT.
        """
        count_col = func.count(Review.recommendationid).label("total_reviews")
        q = (
            select(Game, count_col)
            .outerjoin(Review, Review.steam_appid == Game.steam_appid)
            .group_by(Game.steam_appid)
            .order_by(desc(count_col))
            .limit(limit)
        )
        rows = (await self.db.execute(q)).all()
        return [row[0] for row in rows]

    # ===================== AI helpers =====================
    async def execute_readonly_query(
        self, sql: str, params: Optional[Dict[str, Any]] = None, limit: int = 200
    ) -> Dict[str, Any]:
        """
        Run a single SELECT (read-only) statement safely for the AI.
        Returns: {columns, rows, row_count, truncated}.
        """
        max_rows = max(1, min(limit, 500))
        # Wrap in a subquery with LIMIT to bound the result set.
        wrapped = f"SELECT * FROM ({sql.rstrip(';')}) AS _ai_sub LIMIT {max_rows}"
        result = await self.db.execute(text(wrapped), params or {})
        cols = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
        truncated = len(rows) >= max_rows
        return {
            "columns": cols,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
