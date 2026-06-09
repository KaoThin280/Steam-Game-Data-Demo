"""
Steam Service - Logic filter, sort, map dữ liệu game Steam.
Đồng bộ với cấu trúc JSON mẫu:
  - meta: { steam_appid, name, is_free, release_date.date, publishers[], developers[],
            categories[], genres[], price_overview.{initial,final,discount_percent,currency,...},
            supported_languages (string), required_age, ratings, ... }
  - reviews: { recommendationid, language, review, timestamp_created, timestamp_updated,
               voted_up, votes_up, votes_funny, comment_count, steam_purchase, received_for_free,
               written_during_early_access, primarily_steam_deck, refunded,
               steamid, personaname, num_games_owned,
               playtime_forever, playtime_at_review, playtime_last_two_weeks, app_release_date }
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.steam import GameMeta, GameReview
from app.schemas.steam_schema import GameMetaFilter, GameReviewFilter


def _parse_steam_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse chuỗi ngày kiểu Steam: '3 Jun, 2016', 'Jun 2016', '2016', ..."""
    if not date_str:
        return None
    s = str(date_str).strip()
    formats = (
        "%d %b, %Y",    # "3 Jun, 2016"
        "%b %d, %Y",    # "Jun 3, 2016"
        "%b %Y",        # "Jun 2016"
        "%Y",           # "2016"
        "%d %B, %Y",    # "3 June, 2016"
        "%B %d, %Y",    # "June 3, 2016"
    )
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


class SteamService:
    """Service xử lý logic dữ liệu game Steam."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ============== GameMeta ==============
    async def get_game_by_id(self, game_id: int) -> GameMeta:
        result = await self.db.execute(
            select(GameMeta).where(GameMeta.id == game_id)
        )
        game = result.scalar_one_or_none()
        if not game:
            raise NotFoundException(detail=f"Game với id={game_id} không tồn tại.")
        return game

    async def get_game_by_app_id(self, app_id: int) -> Optional[GameMeta]:
        result = await self.db.execute(
            select(GameMeta).where(GameMeta.app_id == app_id)
        )
        return result.scalar_one_or_none()

    async def list_games(
        self, filter_: GameMetaFilter
    ) -> Tuple[List[GameMeta], int]:
        """Lấy danh sách games theo filter. Returns (items, total)."""
        query = select(GameMeta)
        count_query = select(func.count(GameMeta.id))

        conditions = []
        if filter_.search:
            kw = f"%{filter_.search}%"
            conditions.append(
                or_(
                    GameMeta.name.ilike(kw),
                    GameMeta.developer.ilike(kw),
                    GameMeta.publisher.ilike(kw),
                )
            )
        if filter_.genre:
            conditions.append(GameMeta.genres.contains([filter_.genre]))
        if filter_.tag:
            conditions.append(GameMeta.tags.contains([filter_.tag]))
        if filter_.developer:
            conditions.append(GameMeta.developer.ilike(f"%{filter_.developer}%"))
        if filter_.publisher:
            conditions.append(GameMeta.publisher.ilike(f"%{filter_.publisher}%"))
        if filter_.is_free is not None:
            conditions.append(GameMeta.is_free == filter_.is_free)
        if filter_.min_price is not None:
            conditions.append(GameMeta.price_final >= filter_.min_price)
        if filter_.max_price is not None:
            conditions.append(GameMeta.price_final <= filter_.max_price)
        if filter_.min_positive_percent is not None:
            conditions.append(
                GameMeta.positive_percent >= filter_.min_positive_percent
            )

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        sort_col = getattr(GameMeta, filter_.sort_by, GameMeta.total_reviews)
        if filter_.sort_order == "asc":
            query = query.order_by(asc(sort_col))
        else:
            query = query.order_by(desc(sort_col))

        offset = (filter_.page - 1) * filter_.page_size
        query = query.offset(offset).limit(filter_.page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        return items, total

    # ============== GameReview ==============
    async def list_reviews(
        self, game_id: int, filter_: GameReviewFilter
    ) -> Tuple[List[GameReview], int]:
        await self.get_game_by_id(game_id)
        query = select(GameReview).where(GameReview.game_id == game_id)
        count_query = select(func.count(GameReview.id)).where(
            GameReview.game_id == game_id
        )

        if filter_.language:
            query = query.where(GameReview.language == filter_.language)
            count_query = count_query.where(GameReview.language == filter_.language)
        if filter_.voted_up is not None:
            query = query.where(GameReview.voted_up == filter_.voted_up)
            count_query = count_query.where(
                GameReview.voted_up == filter_.voted_up
            )
        if filter_.steam_purchase is not None:
            query = query.where(GameReview.steam_purchase == filter_.steam_purchase)
            count_query = count_query.where(
                GameReview.steam_purchase == filter_.steam_purchase
            )
        if filter_.min_playtime is not None:
            query = query.where(
                GameReview.author_playtime_forever >= filter_.min_playtime
            )
            count_query = count_query.where(
                GameReview.author_playtime_forever >= filter_.min_playtime
            )

        query = query.order_by(
            desc(GameReview.votes_up), desc(GameReview.timestamp_created)
        )
        offset = (filter_.page - 1) * filter_.page_size
        query = query.offset(offset).limit(filter_.page_size)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        return items, total

    # ============== Import Data ==============
    async def import_steam_data(self, data: Dict[str, Any]) -> GameMeta:
        """
        Import dữ liệu Steam từ JSON.
        Input: { "meta": {...}, "reviews": [...] }
        """
        meta_data = data.get("meta", {}) or {}
        reviews_data = data.get("reviews", []) or []

        app_id = meta_data.get("steam_appid") or meta_data.get("app_id")
        if not app_id:
            raise ValueError("Thiếu steam_appid trong dữ liệu meta.")

        game_dict = self._map_meta(meta_data)
        game_dict["raw_data"] = meta_data

        existing = await self.get_game_by_app_id(int(app_id))
        if existing:
            for k, v in game_dict.items():
                setattr(existing, k, v)
            game = existing
        else:
            game = GameMeta(**game_dict)
            self.db.add(game)
        await self.db.flush()

        self._update_review_stats(game, reviews_data)
        await self._replace_reviews(game.id, reviews_data)

        await self.db.commit()
        await self.db.refresh(game)
        return game

    def _map_meta(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Map dữ liệu JSON meta sang GameMeta columns."""

        def _extract_descriptions(items: Any) -> Optional[List[str]]:
            if not items or not isinstance(items, list):
                return None
            result = []
            for g in items:
                if isinstance(g, dict):
                    desc = g.get("description") or g.get("path_full") or g.get("url")
                    if desc:
                        result.append(str(desc))
                elif isinstance(g, str):
                    result.append(g)
            return result or None

        def _first_or_value(field: Any) -> Optional[str]:
            if isinstance(field, list):
                return field[0] if field else None
            return field

        platforms = meta.get("platforms", {}) or {}
        price = meta.get("price_overview", {}) or {}
        release = meta.get("release_date", {}) or {}

        release_date = None
        if release.get("date") and not release.get("coming_soon"):
            release_date = _parse_steam_date(release.get("date"))

        # supported_languages: string -> list
        supported_languages = None
        if meta.get("supported_languages"):
            supported_languages = [
                s.strip() for s in str(meta["supported_languages"]).split(",")
                if s.strip()
            ] or None

        # price_overview: cents -> số thực
        price_initial = None
        price_final = None
        if price.get("initial") is not None:
            try:
                price_initial = float(price["initial"]) / 100.0
            except (TypeError, ValueError):
                price_initial = None
        if price.get("final") is not None:
            try:
                price_final = float(price["final"]) / 100.0
            except (TypeError, ValueError):
                price_final = None

        # screenshots: dict {path_thumbnail, path_full} -> lấy path_full
        screenshots = None
        ss_raw = meta.get("screenshots") or []
        if isinstance(ss_raw, list) and ss_raw:
            ss_list = []
            for s in ss_raw:
                if isinstance(s, dict):
                    p = s.get("path_full")
                    if p:
                        ss_list.append(p)
                elif isinstance(s, str):
                    ss_list.append(s)
            screenshots = ss_list or None

        # movies: list of {url, ...}
        movies = None
        mv_raw = meta.get("movies") or []
        if isinstance(mv_raw, list) and mv_raw:
            mv_list = []
            for m in mv_raw:
                if isinstance(m, dict) and m.get("url"):
                    mv_list.append(m["url"])
                elif isinstance(m, str):
                    mv_list.append(m)
            movies = mv_list or None

        return {
            "app_id": int(meta.get("steam_appid") or meta.get("app_id") or 0),
            "name": meta.get("name") or meta.get("game_name") or "Unknown",
            "short_description": meta.get("short_description"),
            "detailed_description": meta.get("detailed_description"),
            "about_the_game": meta.get("about_the_game"),
            "header_image": meta.get("header_image"),
            "capsule_image": meta.get("capsule_image"),
            "capsule_imagev5": meta.get("capsule_imagev5"),
            "website": meta.get("website"),
            "developer": _first_or_value(meta.get("developer")),
            "publisher": _first_or_value(
                meta.get("publisher") or meta.get("publishers")
            ),
            "genres": _extract_descriptions(meta.get("genres")),
            "categories": _extract_descriptions(meta.get("categories")),
            "tags": meta.get("tags") if isinstance(meta.get("tags"), list) else None,
            "windows": bool(platforms.get("windows", False)),
            "mac": bool(platforms.get("mac", False)),
            "linux": bool(platforms.get("linux", False)),
            "release_date": release_date,
            "coming_soon": bool(release.get("coming_soon", False)),
            "price_initial": price_initial,
            "price_final": price_final,
            "currency": price.get("currency"),
            "discount_percent": price.get("discount_percent"),
            "is_free": bool(meta.get("is_free", False)),
            "review_score": meta.get("review_score"),
            "review_score_desc": meta.get("review_score_desc"),
            "pc_requirements_min": (meta.get("pc_requirements") or {}).get(
                "minimum"
            ),
            "pc_requirements_rec": (meta.get("pc_requirements") or {}).get(
                "recommended"
            ),
            "mac_requirements_min": (meta.get("mac_requirements") or {}).get(
                "minimum"
            ),
            "linux_requirements_min": (meta.get("linux_requirements") or {}).get(
                "minimum"
            ),
            "supported_languages": supported_languages,
            "full_audio_languages": meta.get("full_audio_languages"),
            "screenshots": screenshots,
            "movies": movies,
            "required_age": int(meta.get("required_age") or 0),
        }

    def _update_review_stats(
        self, game: GameMeta, reviews_data: List[dict]
    ) -> None:
        """Tính toán và cập nhật các chỉ số review cho game."""
        total = len(reviews_data)
        positive = sum(1 for r in reviews_data if r.get("voted_up") is True)
        negative = total - positive
        game.total_reviews = total
        game.total_positive = positive
        game.total_negative = negative
        if total > 0:
            game.positive_percent = round((positive / total) * 100, 2)

    async def _replace_reviews(
        self, game_id: int, reviews_data: List[dict]
    ) -> None:
        """Xóa reviews cũ và thêm mới. Map field JSON steam review -> column."""
        from sqlalchemy import delete

        await self.db.execute(
            delete(GameReview).where(GameReview.game_id == game_id)
        )

        if not reviews_data:
            return

        def _to_dt(value: Any) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromtimestamp(int(value))
            except (ValueError, TypeError, OSError):
                return None

        rows: List[GameReview] = []
        for r in reviews_data:
            rows.append(
                GameReview(
                    game_id=game_id,
                    recommendation_id=str(r.get("recommendationid"))
                    if r.get("recommendationid")
                    else None,
                    review_text=r.get("review"),
                    language=r.get("language"),
                    # JSON mẫu KHÔNG có voted_up -> mặc định True (recommend)
                    voted_up=bool(r.get("voted_up", True)),
                    votes_up=int(r.get("votes_up", 0) or 0),
                    votes_funny=int(r.get("votes_funny", 0) or 0),
                    comment_count=int(r.get("comment_count", 0) or 0),
                    steam_purchase=bool(r.get("steam_purchase", True)),
                    received_for_free=bool(r.get("received_for_free", False)),
                    written_during_early_access=bool(
                        r.get("written_during_early_access", False)
                    ),
                    primarily_steam_deck=bool(
                        r.get("primarily_steam_deck", False)
                    ),
                    refunded=bool(r.get("refunded", False)),
                    # JSON: 'steamid' / 'personaname' / 'num_games_owned'
                    author_steamid=r.get("steamid") or r.get("author_steamid"),
                    author_personaname=r.get("personaname")
                    or r.get("author_personaname"),
                    author_num_games_owned=r.get("num_games_owned")
                    or r.get("author_num_games_owned"),
                    author_num_reviews=r.get("author_num_reviews"),
                    author_playtime_forever=r.get("playtime_forever")
                    or r.get("author_playtime_forever"),
                    author_playtime_at_review=r.get("playtime_at_review")
                    or r.get("author_playtime_at_review"),
                    author_playtime_last_two_weeks=r.get("playtime_last_two_weeks")
                    or r.get("author_playtime_last_two_weeks")
                    or 0,
                    timestamp_created=_to_dt(r.get("timestamp_created")),
                    timestamp_updated=_to_dt(r.get("timestamp_updated")),
                    app_release_date=_to_dt(r.get("app_release_date")),
                )
            )

        if rows:
            self.db.add_all(rows)
            await self.db.flush()

    # ============== Dashboard stats ==============
    async def get_overview_stats(self) -> Dict[str, Any]:
        """Thống kê tổng quan cho dashboard."""
        total_games = (
            await self.db.execute(select(func.count(GameMeta.id)))
        ).scalar() or 0
        total_reviews = (
            await self.db.execute(
                select(func.coalesce(func.sum(GameMeta.total_reviews), 0))
            )
        ).scalar() or 0
        free_games = (
            await self.db.execute(
                select(func.count(GameMeta.id)).where(
                    GameMeta.is_free == True  # noqa: E712
                )
            )
        ).scalar() or 0
        avg_positive = (
            await self.db.execute(
                select(func.avg(GameMeta.positive_percent)).where(
                    GameMeta.positive_percent.isnot(None)
                )
            )
        ).scalar() or 0

        return {
            "total_games": total_games,
            "total_reviews": int(total_reviews),
            "free_games": free_games,
            "paid_games": total_games - free_games,
            "average_positive_percent": (
                round(float(avg_positive), 2) if avg_positive else 0.0
            ),
        }

    async def get_top_games(
        self, limit: int = 10, sort_by: str = "total_reviews"
    ) -> List[GameMeta]:
        """Lấy top games theo tiêu chí."""
        sort_col = getattr(GameMeta, sort_by, GameMeta.total_reviews)
        result = await self.db.execute(
            select(GameMeta).order_by(desc(sort_col)).limit(limit)
        )
        return list(result.scalars().all())

    async def get_genre_distribution(self) -> List[Dict[str, Any]]:
        """Phân bố số lượng game theo genre. Dùng UNNEST trên mảng."""
        from sqlalchemy import text

        query = text(
            """
            SELECT genre, COUNT(*) AS count
            FROM game_metas, UNNEST(genres) AS genre
            WHERE genres IS NOT NULL
            GROUP BY genre
            ORDER BY count DESC
            LIMIT 20
            """
        )
        result = await self.db.execute(query)
        return [{"genre": row[0], "count": int(row[1])} for row in result.fetchall()]

    async def get_price_distribution(self) -> List[Dict[str, Any]]:
        """Phân bố giá game (bucket)."""
        from sqlalchemy import case

        price_bucket = case(
            (GameMeta.is_free == True, "Free"),  # noqa: E712
            (GameMeta.price_final < 5, "Under $5"),
            (GameMeta.price_final < 10, "$5 - $10"),
            (GameMeta.price_final < 20, "$10 - $20"),
            (GameMeta.price_final < 30, "$20 - $30"),
            (GameMeta.price_final < 50, "$30 - $50"),
            else_="$50+",
        ).label("bucket")

        result = await self.db.execute(
            select(price_bucket, func.count(GameMeta.id))
            .group_by("bucket")
            .order_by(func.count(GameMeta.id).desc())
        )
        return [
            {"bucket": row[0], "count": int(row[1])} for row in result.fetchall()
        ]
   