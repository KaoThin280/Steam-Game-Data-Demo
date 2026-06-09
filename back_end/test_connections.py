"""
Test kết nối PostgreSQL (Aiven), Redis (Upstash), OpenRouter.
Chạy: python test_connections.py
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import redis
from openai import OpenAI

# Tải biến môi trường từ file .env
load_dotenv()


def test_postgresql():
    print("1. Đang kiểm tra kết nối PostgreSQL (Aiven)...")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ Lỗi: Chưa cấu hình DATABASE_URL trong .env")
        return False
    try:
        # Sync engine (chỉ dùng để test)
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"✅ PostgreSQL OK! Phiên bản: {version[:80]}")
        engine.dispose()
        return True
    except Exception as e:
        print(f"❌ PostgreSQL lỗi: {e}")
        return False


def test_redis():
    print("\n2. Đang kiểm tra kết nối Redis (Upstash)...")
    # Hỗ trợ cả 2 format
    redis_url = os.getenv("REDIS_URL")
    host = os.getenv("REDIS_HOST")
    port = os.getenv("REDIS_PORT")
    password = os.getenv("REDIS_PASSWORD")

    try:
        if redis_url:
            r = redis.Redis.from_url(
                redis_url, decode_responses=True, socket_timeout=5
            )
        elif host and password:
            r = redis.Redis(
                host=host,
                port=int(port or 6379),
                password=password,
                ssl=True,
                decode_responses=True,
                socket_timeout=5,
            )
        else:
            print("❌ Lỗi: Chưa cấu hình REDIS_URL hoặc REDIS_HOST/PASSWORD")
            return False

        if r.ping():
            r.set("test_connection_key", "Hello from Redis", ex=10)
            value = r.get("test_connection_key")
            if value == "Hello from Redis":
                print("✅ Redis OK! Đã đọc/ghi chính xác.")
                r.delete("test_connection_key")
                return True
            else:
                print("⚠️ Redis OK nhưng data không khớp.")
                return False
    except Exception as e:
        print(f"❌ Redis lỗi: {e}")
        return False


def test_openrouter():
    print("\n3. Đang kiểm tra kết nối OpenRouter AI...")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ Lỗi: Chưa cấu hình OPENROUTER_API_KEY trong .env")
        return False
    try:
        client = OpenAI(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key,
        )
        model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3.1:free")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with 'OK' only."}],
            max_tokens=10,
        )
        reply = (response.choices[0].message.content or "").strip()
        print(f"✅ OpenRouter OK! Model={model} | Reply='{reply[:50]}'")
        return True
    except Exception as e:
        print(f"❌ OpenRouter lỗi: {e}")
        return False


if __name__ == "__main__":
    print("=== BẮT ĐẦU KIỂM TRA KẾT NỐI ===\n")
    results = {
        "PostgreSQL": test_postgresql(),
        "Redis": test_redis(),
        "OpenRouter": test_openrouter(),
    }
    print("\n=== KẾT QUẢ ===")
    for name, ok in results.items():
        print(f"  {name}: {'✅ OK' if ok else '❌ FAIL'}")
    all_ok = all(results.values())
    print(f"\nTổng: {'✅ TẤT CẢ OK' if all_ok else '⚠️ CÓ LỖI'}")
