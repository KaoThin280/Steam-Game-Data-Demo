"""
Main entry point - Khởi tạo FastAPI app, gắn CORS, gắn Routers.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text

from app import __version__
from app.api.v1 import admin, ai_agent, auth, chat, dashboard, data_files, games
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.rate_limit import rate_limit
from app.core.security import decode_token, get_password_hash
from app.db.session import (
    AsyncSessionLocal,
    async_engine,
    close_db,
    close_redis,
    init_redis,
    redis_client,
)
from app.models.user import AppUser, Role, UserRole

# ============== Logging ==============
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============== Lifespan ==============
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connected.")

        await init_redis()
        logger.info("Redis connected.")

        await _bootstrap_admin()
    except Exception as e:
        logger.error("Startup error: %s", e)
        raise

    yield

    logger.info("Shutting down...")
    await close_redis()
    await close_db()
    logger.info("Connections closed.")


async def _bootstrap_admin() -> None:
    """Tạo admin đầu tiên nếu chưa có và BOOTSTRAP_ADMIN_* được cấu hình."""
    if not settings.BOOTSTRAP_ADMIN_EMAIL or not settings.BOOTSTRAP_ADMIN_PASSWORD:
        return
    try:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(AppUser).where(
                    AppUser.email == settings.BOOTSTRAP_ADMIN_EMAIL
                )
            )
            if existing.scalar_one_or_none():
                logger.info("Bootstrap admin already exists.")
                return

            # Look up admin role
            role_q = await session.execute(
                select(Role).where(Role.role_name == "admin")
            )
            admin_role = role_q.scalar_one_or_none()

            new_user = AppUser(
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                username=settings.BOOTSTRAP_ADMIN_EMAIL.split("@")[0],
                full_name="Administrator",
                password_hash=get_password_hash(
                    settings.BOOTSTRAP_ADMIN_PASSWORD
                ),
                is_active=True,
            )
            session.add(new_user)
            await session.flush()

            if admin_role is not None:
                session.add(UserRole(user_id=new_user.id, role_id=admin_role.id))

            await session.commit()
            logger.info(
                "Bootstrap admin created: %s", settings.BOOTSTRAP_ADMIN_EMAIL
            )
    except Exception as e:
        logger.warning("Bootstrap admin failed (ignored): %s", e)


# ============== App ==============
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API cho hệ thống phân tích dữ liệu game Steam + AI Agent (RBAC).",
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


# ============== Auth context middleware ==============
@app.middleware("http")
async def auth_context_middleware(request: Request, call_next):
    """Parse Authorization header (nếu có) và gán user_id vào request.state."""
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
app.include_router(chat.router, prefix=API_V1)
app.include_router(admin.router, prefix=API_V1)
app.include_router(data_files.router, prefix=API_V1)

# ============== Static files (temp_data for E2B-generated artifacts) ==============
# NOTE: StaticFiles mount removed for security. Files are now served via
# /api/v1/data-files/{filename}?token=... with HMAC-signed tokens.
temp_data_dir = Path(settings.TEMP_DATA_DIR)
temp_data_dir.mkdir(parents=True, exist_ok=True)


# ============== Health ==============
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


@app.get("/ping", tags=["Health"])
async def ping(request: Request):
    """Endpoint test rate limit."""
    await rate_limit(request, bucket="ping")
    return {"pong": True}