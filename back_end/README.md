# Steam Game Data API - Backend (v1.1.0)

FastAPI backend cho hệ thống phân tích dữ liệu game Steam + AI Agent.
Thể hiện: **Authentication, Authorization, Rate Limit, Dashboard, AI Agent**.

## 🏗 Kiến trúc

```
Free-tier stack (đã tối ưu cho 1GB RAM/Storage):
┌─────────────────────────────────────────────────────┐
│  Client (Web/Mobile)                                │
└──────────────────┬──────────────────────────────────┘
                   │ HTTPS + JWT
┌──────────────────▼──────────────────────────────────┐
│  Compute: GCP Free-tier e2.micro (1GB RAM)          │
│  - FastAPI + Uvicorn (4 workers)                    │
│  - Python 3.12 + asyncpg + httpx                   │
└────┬───────────────────────────┬───────────────────┘
     │                           │
┌────▼──────────────┐    ┌──────▼─────────────┐
│  Database         │    │  Cache             │
│  Aiven PostgreSQL │    │  Upstash Redis     │
│  1GB free tier    │    │  0.5GB free tier   │
│  schema: 'steam'  │    │  rate limit counter│
└───────────────────┘    └────────────────────┘
                                ▲
┌───────────────────────────────┴───────────────────┐
│  External APIs                                    │
│  - OpenRouter (LLM): chat phân tích dữ liệu      │
│  - E2B (Code Interpreter): chạy code Python        │
└───────────────────────────────────────────────────┘
```

## 📁 Cấu trúc thư mục

```
back_end/
├── app/
│   ├── api/             # Tầng giao tiếp: Endpoints/Routes
│   │   ├── dependencies.py
│   │   └── v1/
│   │       ├── auth.py        # /api/v1/auth/*
│   │       ├── games.py       # /api/v1/games/*
│   │       ├── dashboard.py   # /api/v1/dashboard/*
│   │       └── ai_agent.py    # /api/v1/ai/*
│   ├── core/            # Cấu hình cốt lõi
│   │   ├── config.py          # Settings từ .env
│   │   ├── security.py        # JWT + bcrypt
│   │   ├── rate_limit.py      # Redis-based rate limit
│   │   └── exceptions.py      # Custom HTTP exceptions
│   ├── db/              # Kết nối Database
│   │   ├── session.py         # Async engine + Redis
│   │   └── base.py            # SQLAlchemy Base
│   ├── models/          # SQLAlchemy ORM models
│   │   ├── user.py            # User, RefreshToken, ChatHistory
│   │   └── steam.py           # GameMeta, GameReview
│   ├── schemas/         # Pydantic models
│   │   ├── user_schema.py
│   │   ├── steam_schema.py
│   │   └── token_schema.py
│   ├── services/        # Business logic
│   │   ├── auth_service.py
│   │   ├── steam_service.py
│   │   └── ai_service.py
│   └── main.py          # Entry point
├── db_init.sql          # Script tạo schema + tables + index (recommended)
├── init_db.py           # Auto-create schema/tables từ SQLAlchemy
├── test_connections.py  # Test 3 kết nối (DB, Redis, AI)
├── _smoke_test.py       # Smoke test (DB/Redis/Schema)
├── _e2e_test.py         # E2E test toàn bộ API
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## 🚀 Setup & Chạy

### Bước 1: Chuẩn bị môi trường

```bash
cd back_end
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### Bước 2: Cấu hình .env

```bash
cp .env.example .env
# Sửa .env với thông tin thật từ Aiven, Upstash, OpenRouter
```

**Lưu ý quan trọng cho Aiven PostgreSQL:**
- URL phải có dạng `postgresql://...?...sslmode=require` (sẽ tự chuyển)
- asyncpg dùng `ssl=True` (đã handle tự động trong code)

**Lưu ý cho Upstash Redis:**
- URL dùng `rediss://...` (SSL bắt buộc)

### Bước 3: Khởi tạo Database (chỉ làm 1 lần)

**Cách A: Dùng SQL script (khuyến nghị - nhiều index tối ưu):**
```bash
# Cách 1: psql
psql "host=HOST port=PORT user=avnadmin dbname=defaultdb sslmode=require" -f db_init.sql

# Cách 2: Aiven console -> Query Editor -> paste nội dung db_init.sql
```

**Cách B: Dùng Python (tự động, ít index hơn):**
```bash
python init_db.py
```

### Bước 4: Chạy server

```bash
# Dev mode (auto-reload, auto tạo bảng nếu DEBUG=True)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Bước 5: Kiểm tra

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 Testing

```bash
# 1. Test các kết nối (DB, Redis, OpenRouter)
python test_connections.py

# 2. Smoke test (DB/Redis/Schema)
python _smoke_test.py

# 3. End-to-end test (toàn bộ API: login, me, import game, list, reviews, AI chat...)
python _e2e_test.py
```

## 📡 API Endpoints chính

### Auth (`/api/v1/auth`)
| Method | Path | Mô tả | Auth |
|--------|------|--------|------|
| POST | `/register` | Đăng ký | Public (rate limit) |
| POST | `/login` | Đăng nhập -> JWT | Public (rate limit) |
| POST | `/refresh` | Refresh access token | Public (rate limit) |
| POST | `/logout` | Revoke refresh token | Bearer |
| GET | `/me` | Thông tin user hiện tại | Bearer |
| PUT | `/me` | Cập nhật profile | Bearer |
| PUT | `/me/password` | Đổi mật khẩu | Bearer |

### Games (`/api/v1/games`)
| Method | Path | Mô tả | Auth |
|--------|------|--------|------|
| GET | `/` | Danh sách games (filter, sort, phân trang) | Bearer |
| GET | `/{id}` | Chi tiết một game | Bearer |
| GET | `/{id}/reviews` | Reviews của game (filter) | Bearer |
| POST | `/import` | Import dữ liệu từ JSON | **Admin** (rate limit) |

### Dashboard (`/api/v1/dashboard`)
| Method | Path | Mô tả | Auth |
|--------|------|--------|------|
| GET | `/overview` | Tổng quan (total games, reviews, free/paid, %) | Bearer |
| GET | `/top-games` | Top games theo tiêu chí | Bearer |
| GET | `/genres` | Phân bố game theo genre | Bearer |
| GET | `/prices` | Phân bố game theo khoảng giá | Bearer |

### AI Agent (`/api/v1/ai`)
| Method | Path | Mô tả | Auth |
|--------|------|--------|------|
| POST | `/chat` | Chat với AI (có thể chạy code E2B) | Bearer (rate limit) |
| POST | `/chat/stream` | Chat streaming (SSE) | Bearer (rate limit) |
| GET | `/sessions` | Danh sách phiên chat | Bearer |
| GET | `/history/{session_id}` | Lịch sử chat | Bearer |

## 🔐 Bảo mật & Phân quyền (RBAC)

### 3 Roles:
- `admin`: Toàn quyền (import, xem tất cả)
- `premium`: Xem data, dùng AI
- `user`: Xem data, dùng AI với quota thấp hơn

### Rate Limit (Redis Upstash):
| Bucket | Limit | Áp dụng cho |
|--------|-------|-------------|
| `default` | 60/min/user | Endpoints chung |
| `ai` | 10/min/user | `/ai/chat` |
| `ai-stream` | 10/min/user | `/ai/chat/stream` |
| `auth-login` | 20/min/IP | `/auth/login` |
| `auth-register` | 20/min/IP | `/auth/register` |
| `auth-refresh` | 20/min/IP | `/auth/refresh` |
| `import` | 30/min/user | `/games/import` |
| `ping` | 60/min/IP | `/ping` (test) |

> **Lưu ý:** Rate limit ưu tiên `user_id` (nếu đã đăng nhập) hơn IP.
> Middleware `auth_context_middleware` tự động parse JWT và gán `request.state.user_id`.

### Bootstrap Admin:
- Đặt `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD` trong `.env`
- App sẽ tự tạo admin đầu tiên khi start (nếu email chưa tồn tại)

## 🗄 Database Schema (Aiven PostgreSQL)

- Schema: `steam`
- 5 bảng: `users`, `refresh_tokens`, `chat_histories`, `game_metas`, `game_reviews`
- Tối ưu cho 1GB storage:
  - 150K games × ~1.2KB = ~180MB
  - 3M reviews × ~0.8KB = ~2.4GB
  - **Lưu ý**: Reviews có thể vượt 1GB nếu `review_text` quá dài. Cân nhắc truncate hoặc lưu vào S3.

## 🤖 Công nghệ sử dụng

- **Framework**: FastAPI 0.115.6 + Uvicorn
- **Database**: PostgreSQL 17 (Aiven) + SQLAlchemy 2.0 async + asyncpg
- **Cache/Rate Limit**: Redis (Upstash) - `rediss://`
- **Auth**: JWT (python-jose) HS256 + bcrypt
- **AI**: OpenRouter API (deepseek/deepseek-v4-flash + fallback)
- **Sandbox**: E2B Code Interpreter (HTTP API)
- **Validation**: Pydantic v2

## ⚠️ Lưu ý cho Production

1. **Đổi `SECRET_KEY`** trong `.env` thành random 32+ bytes: `openssl rand -hex 32`
2. **Đổi `BOOTSTRAP_ADMIN_PASSWORD`** thành mật khẩu mạnh
3. **Set `DEBUG=False`**
4. **CORS**: Cập nhật `CORS_ORIGINS` thành domain thật (không dùng `*`)
5. **DB Pool**: Tăng `DB_POOL_SIZE` và `DB_MAX_OVERFLOW` theo RAM
6. **Backup**: Bật backup tự động trên Aiven console
7. **Monitoring**: Tích hợp Sentry/Prometheus

## 🐛 Troubleshooting

| Lỗi | Nguyên nhân | Giải pháp |
|-----|------------|-----------|
| `sslmode not supported` (asyncpg) | URL có `sslmode=require` | Code đã handle tự động |
| `self-signed certificate` | Aiven self-signed cert | Code dùng `CERT_NONE` cho SSL context |
| `Connection refused` Redis | URL sai hoặc không có SSL | Dùng `rediss://` (không phải `redis://`) |
| `permission denied for schema steam` | User DB không có quyền | Trong Aiven console, set `search_path` cho user |
| `Out of memory` trên VPS 1GB | Pool quá lớn | Giảm `DB_POOL_SIZE` xuống 3-5 |
| AI model 404 | Model free bị thu hồi | Đổi `OPENROUTER_MODEL` sang model khác |
