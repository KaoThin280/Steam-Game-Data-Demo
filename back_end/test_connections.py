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
        print("Lỗi: Chưa cấu hình DATABASE_URL trong .env")
        return

    try:
        # Khởi tạo engine của SQLAlchemy
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.connect() as connection:
            # Chạy một query đơn giản để test
            result = connection.execute(text("SELECT version();"))
            version = result.scalar()
            print(f"Kết nối PostgreSQL thành công! Phiên bản: {version}")
    except Exception as e:
        print(f"Kết nối PostgreSQL thất bại: {e}")

def test_redis():
    print("\n2. Đang kiểm tra kết nối Redis (Upstash)...")
    
    host = os.getenv("REDIS_HOST")
    port = os.getenv("REDIS_PORT")
    password = os.getenv("REDIS_PASSWORD")

    if not all([host, port, password]):
        print("Lỗi: Vui lòng cấu hình đầy đủ REDIS_HOST, REDIS_PORT, REDIS_PASSWORD trong .env")
        return

    try:
        # Khởi tạo kết nối tường minh, bỏ qua URL parsing
        r = redis.Redis(
            host=host,
            port=int(port),
            password=password,
            ssl=True,                # Bắt buộc True với Upstash
            decode_responses=True    # Để trả về string thay vì bytes
        )
        
        # Test ping trước
        if r.ping():
            # Test ghi và đọc dữ liệu
            r.set("test_connection_key", "Hello from Redis", ex=10)
            value = r.get("test_connection_key")
            
            if value == "Hello from Redis":
                print("Kết nối Redis thành công! Đã đọc/ghi dữ liệu chính xác.")
            else:
                print("Kết nối Redis thành công nhưng dữ liệu không khớp.")
    except Exception as e:
        print(f"Kết nối Redis thất bại: {e}")

def test_openrouter():
    print("\n3. Đang kiểm tra kết nối AI API (OpenRouter)...")
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Lỗi: Chưa cấu hình OPENROUTER_API_KEY trong .env")
        return

    try:
        # OpenRouter tương thích hoàn toàn với OpenAI SDK, chỉ cần đổi base_url
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        response = client.chat.completions.create(
            model="deepseek/deepseek-v4-flash", # Có thể thay bằng model bạn muốn dùng (miễn phí hoặc trả phí) trên OpenRouter
            messages=[{"role": "user", "content": "Say 'Connection successful!' if you receive this."}],
            max_tokens=10
        )
        reply = response.choices[0].message.content.strip()
        print(f"Kết nối OpenRouter thành công! Phản hồi từ AI: '{reply}'")
    except Exception as e:
        print(f"Kết nối OpenRouter thất bại: {e}")

if __name__ == "__main__":
    print("=== BẮT ĐẦU KIỂM TRA KẾT NỐI ===")
    test_postgresql()
    test_redis()
    test_openrouter()
    print("\n=== HOÀN TẤT KIỂM TRA ===")