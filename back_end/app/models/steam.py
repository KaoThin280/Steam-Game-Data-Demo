"""
Steam Game models - aligned with SCHEMA_DOCUMENTATION.md
Tables:
  - games   (Steam game metadata, flattened)
  - users   (Steam reviewers)
  - reviews (Steam reviews)
  - genres / categories / languages (dimension tables)
  - game_genres / game_categories / game_languages (junction tables)

Note: These tables don't have updated_at columns, so we don't use the
TimestampMixin (which would create them via Base.metadata.create_all).
We still use Base to register them.
"""
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Game(Base):
    """public.games - Steam game metadata (flattened, simplified schema).

    The CSV columns (genres / categories / supported_languages) have been
    removed from the live schema to save storage. They are stored in
    dedicated junction tables (game_genres, game_categories, game_languages).
    """

    __tablename__ = "games"

    steam_appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    required_age: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    release_date: Mapped[Optional[date]] = mapped_column(Date)
    publishers: Mapped[Optional[str]] = mapped_column(Text)
    developers: Mapped[Optional[str]] = mapped_column(Text)
    price_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )

    game_genres: Mapped[list["GameGenre"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan"
    )
    game_categories: Mapped[list["GameCategory"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan"
    )
    game_languages: Mapped[list["GameLanguage"]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan"
    )

    @property
    def genre_names(self) -> List[str]:
        """List of genre names loaded via game_genres -> genre relationship."""
        return [
            gg.genre.name
            for gg in (self.game_genres or [])
            if gg.genre is not None
        ]

    def __repr__(self) -> str:
        return f"<Game(steam_appid={self.steam_appid}, name={self.name})>"


class SteamUser(Base):
    """public.users - Steam reviewer profiles."""

    __tablename__ = "users"

    steamid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    personaname: Mapped[Optional[str]] = mapped_column(Text)
    num_games_owned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SteamUser(steamid={self.steamid}, personaname={self.personaname})>"


class Genre(Base):
    """public.genres - dimension table."""
    __tablename__ = "genres"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    game_genres: Mapped[list["GameGenre"]] = relationship(
        back_populates="genre",
        cascade="all, delete-orphan"
    )


class GameGenre(Base):
    """public.game_genres - junction table."""
    __tablename__ = "game_genres"
    __table_args__ = {"schema": "public"}

    steam_appid: Mapped[int] = mapped_column(Integer, ForeignKey("games.steam_appid", ondelete="CASCADE"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.genres.id", ondelete="CASCADE"), primary_key=True)

    game: Mapped["Game"] = relationship(back_populates="game_genres")
    genre: Mapped["Genre"] = relationship(back_populates="game_genres")


class Category(Base):
    """public.categories - dimension table."""
    __tablename__ = "categories"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class GameCategory(Base):
    """public.game_categories - junction table."""
    __tablename__ = "game_categories"
    __table_args__ = {"schema": "public"}

    steam_appid: Mapped[int] = mapped_column(Integer, ForeignKey("games.steam_appid", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.categories.id", ondelete="CASCADE"), primary_key=True)

    game: Mapped["Game"] = relationship(back_populates="game_categories")


class Language(Base):
    """public.languages - dimension table."""
    __tablename__ = "languages"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class GameLanguage(Base):
    """public.game_languages - junction table."""
    __tablename__ = "game_languages"
    __table_args__ = {"schema": "public"}

    steam_appid: Mapped[int] = mapped_column(Integer, ForeignKey("games.steam_appid", ondelete="CASCADE"), primary_key=True)
    language_id: Mapped[int] = mapped_column(Integer, ForeignKey("public.languages.id", ondelete="CASCADE"), primary_key=True)

    game: Mapped["Game"] = relationship(back_populates="game_languages")


class Review(Base):
    """public.reviews - Steam user reviews."""

    __tablename__ = "reviews"

    recommendationid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    steam_appid: Mapped[int] = mapped_column(
        Integer, ForeignKey("games.steam_appid", ondelete="CASCADE"), nullable=False
    )
    steamid: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.steamid", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[Optional[str]] = mapped_column(String(20))
    review_text: Mapped[Optional[str]] = mapped_column(Text)
    timestamp_created: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    timestamp_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_for_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    written_during_early_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    primarily_steam_deck: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    playtime_at_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    playtime_last_two_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    playtime_forever: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    game: Mapped["Game"] = relationship(back_populates="reviews")
    user: Mapped["SteamUser"] = relationship(back_populates="reviews")

    def __repr__(self) -> str:
        return f"<Review(recommendationid={self.recommendationid})>"