"""
Khởi tạo database (tạo schema steam + các bảng) từ SQLAlchemy metadata.
Chạy: python init_db.py
Hoặc dùng file db_init.sql để có nhiều index/tối ưu hơn (khuyến nghị).
"""
import asyncio

from app.db.session import async_engine
from app.db.base import Base
from sqlalchemy import text

# Import models để SQLAlchemy nhận diện
from app.models import user, steam  # noqa: F401


async def main():
    print("=== Khởi tạo database ===")
    async with async_engine.begin() as conn:
        print("1. Tạo schema 'steam'...")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS steam"))
        print("2. Tạo các bảng từ SQLAlchemy metadata...")
        await conn.run_sync(Base.metadata.create_all)
    print("\n✅ DONE. Schema và tables đã được tạo.")
    print("👉 Khuyến nghị: chạy db_init.sql để có thêm index/tối ưu cho 1GB free tier.")
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
