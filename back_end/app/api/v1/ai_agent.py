"""
AI Agent API - chat / chat_stream / list sessions / list charts.
Mỗi endpoint AI đều có rate limit riêng để bảo vệ quota OpenRouter.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import AppUser
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI Agent"])


def get_ai_service(db: AsyncSession = Depends(get_db)) -> AIService:
    return AIService(db)


# ============ Schemas ============
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChartItem(BaseModel):
    id: int
    session_id: str
    chart_type: str
    chart_title: str
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    series_label: Optional[str] = None
    config: dict
    source_query: Optional[str] = None
    created_at: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_calls: list = []
    charts: List[ChartItem] = []


class SessionItem(BaseModel):
    session_id: str
    last_active: Optional[str] = None


class HistoryItem(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    history: List[HistoryItem]


# ============ Endpoints ============
@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat với AI agent (tool loop: execute_query + charting)",
)
async def chat(
    request: Request,
    payload: ChatRequest,
    current_user: AppUser = Depends(get_current_active_user),
    service: AIService = Depends(get_ai_service),
):
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AI_PER_MINUTE,
        window=60,
        bucket="ai",
    )
    result = await service.chat(
        user=current_user,
        message=payload.message,
        session_id=payload.session_id,
    )
    return ChatResponse(**result)


@router.post(
    "/chat/stream",
    summary="Chat với AI agent (SSE stream, không chạy tool)",
)
async def chat_stream(
    request: Request,
    payload: ChatRequest,
    current_user: AppUser = Depends(get_current_active_user),
    service: AIService = Depends(get_ai_service),
):
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AI_PER_MINUTE,
        window=60,
        bucket="ai-stream",
    )

    async def event_generator():
        try:
            async for chunk in service.chat_stream(
                user=current_user,
                message=payload.message,
                session_id=payload.session_id,
            ):
                safe = chunk.replace("\n", "\\n")
                yield f"data: {safe}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e).replace(chr(10), ' ')}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions",
    response_model=List[SessionItem],
    summary="Danh sách phiên chat của user hiện tại",
)
async def list_sessions(
    current_user: AppUser = Depends(get_current_active_user),
    service: AIService = Depends(get_ai_service),
):
    rows = await service.list_sessions(current_user)
    return [SessionItem(**r) for r in rows]


@router.get(
    "/history/{session_id}",
    response_model=HistoryResponse,
    summary="Lấy lịch sử chat theo session_id",
)
async def get_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: AppUser = Depends(get_current_active_user),
    service: AIService = Depends(get_ai_service),
):
    history = await service.get_chat_history(
        user=current_user, session_id=session_id, limit=limit
    )
    return HistoryResponse(
        session_id=session_id,
        history=[HistoryItem(**h) for h in history],
    )


@router.get(
    "/charts",
    response_model=List[ChartItem],
    summary="Danh sách chart đã sinh ra (theo session hoặc tất cả)",
)
async def list_charts(
    session_id: Optional[str] = Query(None),
    current_user: AppUser = Depends(get_current_active_user),
    service: AIService = Depends(get_ai_service),
):
    rows = await service.list_charts(current_user, session_id=session_id)
    return [ChartItem(**r) for r in rows]