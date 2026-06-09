"""
Main entry point - Khởi tạo FastAPI app, gắn CORS, gắn Routers.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app import __version__
from app.api.v1 import ai_agent, auth, dashboard, games
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.rate_limit import rate_limit
from app.core.security import decode_token
from app.db.session import (
    AsyncSessionLocal,
    async_engine,
    close_db,
    close_redis,
    init_db,
    init_redis,
    redis_client,
)
from app.models.user import User

# ============== Logging ==============
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============== Lifespan ==============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo và đóng kết nối khi app start/stop."""
    # Startup
    logger.info("🚀 Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connected.")

        await init_redis()
        logger.info("✅ Redis connected.")

        if settings.DEBUG:
            await init_db()
            logger.info("✅ Database tables created (DEBUG mode).")

        await _bootstrap_admin()
    except Exception as e:
        logger.error("❌ Startup error: %s", e)
        raise

    yield

    logger.info("🛑 Shutting down...")
    await close_redis()
    await close_db()
    logger.info("✅ Connections closed.")


async def _bootstrap_admin() -> None:
    """Tạo admin đầu tiên nếu chưa có và BOOTSTRAP_ADMIN_* được cấu hình."""
    if not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return
    try:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(User).where(User.email == settings.BOOTSTRAP_ADMIN_EMAIL)
            )
            if existing.scalar_one_or_none():
                logger.info("Bootstrap admin already exists.")
                return

            from app.core.security import get_password_hash
            from app.models.user import UserRole

            admin = User(
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                username=settings.BOOTSTRAP_ADMIN_EMAIL.split("@")[0],
                full_name="Administrator",
                hashed_password=get_password_hash(settings.BOOTSTRAP_ADMIN_PASSWORD),
                role=UserRole.ADMIN.value,
                is_active=True,
                is_verified=True,
            )
            session.add(admin)
            await session.commit()
            logger.info(
                "✅ Bootstrap admin created: %s", settings.BOOTSTRAP_ADMIN_EMAIL
            )
    except Exception as e:
        logger.warning("Bootstrap admin failed (ignored): %s", e)


# ============== App ==============
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API cho hệ thống phân tích dữ liệu game Steam + AI Agent",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ============== CORS ==============
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ============== Auth Middleware (inject user_id vào request.state) ==============
@app.middleware("http")
async def auth_context_middleware(request: Request, call_next):
    """
    Parse Authorization header (nếu có) và gán user_id vào request.state.
    Rate limit sẽ ưu tiên user_id hơn IP.
    """
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
            if payload.get("type") == "access":
                request.state.user_id = int(payload.get("sub"))
        except Exception:
            # Token không hợp lệ -> middleware không làm gì, dep sẽ tự raise
            pass

    response = await call_next(request)
    return response


# ============== Global Exception Handler ==============
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": getattr(exc, "code", "ERROR"),
            "message": exc.detail,
            "path": str(request.url),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception at %s: %s", request.url, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "code": "INTERNAL_ERROR",
            "message": "Lỗi máy chủ nội bộ.",
            "path": str(request.url),
        },
    )


# ============== Routers ==============
API_V1 = settings.API_V1_PREFIX

app.include_router(auth.router, prefix=API_V1)
app.include_router(games.router, prefix=API_V1)
app.include_router(dashboard.router, prefix=API_V1)
app.include_router(ai_agent.router, prefix=API_V1)


# ============== Health Check ==============
@app.get("/", tags=["Health"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "api_v1": API_V1,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Kiểm tra trạng thái service và kết nối DB/Redis."""
    db_status = "unknown"
    redis_status = "unknown"

    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    try:
        await redis_client.ping()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {e}"

    healthy = db_status == "connected" and redis_status == "connected"

    return {
        "status": "healthy" if healthy else "degraded",
        "version": __version__,
        "database": db_status,
        "redis": redis_status,
    }


# ============== Rate limit demo endpoint ==============
@app.get("/ping", tags=["Health"])
async def ping(request: Request):
    """Endpoint test rate limit."""
    await rate_limit(request, bucket="ping")
    return {"pong": True}
