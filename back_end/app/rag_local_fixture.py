"""Synthetic local fixtures ONLY; never a production migration."""
import asyncio
from urllib.parse import urlparse

from sqlalchemy import text
from app.core.config import settings
from app.db.base import Base
from app.db.session import async_engine
import app.models.steam  # noqa: F401
import app.models.user  # noqa: F401
import app.models.agent  # noqa: F401


async def seed():
    url = urlparse(settings.DATABASE_URL)
    if url.hostname != "postgres" or url.path != "/rag_local" or url.username != "rag_local":
        raise RuntimeError("Fixture initialization only permits the isolated rag_local database")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("INSERT INTO roles (role_name) VALUES ('admin') ON CONFLICT DO NOTHING"))
        await conn.execute(text("""INSERT INTO games (steam_appid, name, is_free, required_age, release_date)
            VALUES (900001, 'LOCAL FIXTURE Free Game', true, 0, '2025-01-15'),
                   (900002, 'LOCAL FIXTURE Paid Game', false, 0, '2025-02-15'),
                   (900003, 'LOCAL FIXTURE Another Free Game', true, 0, '2025-02-20')
            ON CONFLICT DO NOTHING"""))
        await conn.execute(text("""DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='rag_reader') THEN
                CREATE ROLE rag_reader LOGIN PASSWORD 'rag_reader_fixture';
            END IF;
            END $$"""))
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO rag_reader"))
        await conn.execute(text("GRANT SELECT ON games, reviews, users, genres, categories, languages, game_genres, game_categories, game_languages TO rag_reader"))
    await async_engine.dispose()
    print("Local fixtures ready: 3 synthetic games, 2 free; separate read-only role")


if __name__ == "__main__":
    asyncio.run(seed())
