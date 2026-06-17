"""
AI Service - OpenRouter + 2 tools for the model:
  1. Charting : generate Chart.js config that the FE will render.
  2. ExecuteQuery : run a read-only SELECT against the database.

The model emits a JSON tool_call; this service runs the tool and feeds
the result back to the model until it produces a natural-language reply.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestException, ServiceUnavailableException
from app.models.user import AIChartHistory, AppUser, ChatHistory
from app.services.steam_service import SteamService

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên phân tích dữ liệu game trên Steam.
Bạn có quyền truy cập schema public của hệ thống (games, reviews, users, app_users, roles).

QUY TẮC BẮT BUỘC:
- Luôn trả lời ngắn gọn, dùng tiếng Việt.
- Với câu hỏi cần dữ liệu, hãy gọi tool `execute_query` để lấy dữ liệu từ DB.
- Với câu hỏi cần biểu đồ, hãy gọi tool `charting` với config Chart.js hợp lệ.
- CHỈ gọi tool bằng JSON tool_call; KHÔNG chạy SQL hoặc tạo chart inline trong text.
- execute_query CHỈ chấp nhận câu SELECT/WITH (read-only). KHÔNG INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/COPY/CREATE/GRANT.

Schema (public):
- games(steam_appid PK, name, is_free, supported_languages CSV, required_age, release_date DATE, publishers CSV, developers CSV, categories CSV, genres CSV, price_text, created_at)
- reviews(recommendationid PK, steam_appid FK->games, steamid FK->users, language, review_text, timestamp_created TIMESTAMPTZ, timestamp_updated TIMESTAMPTZ, refunded, received_for_free, written_during_early_access, primarily_steam_deck, playtime_at_review INT, playtime_last_two_weeks INT, playtime_forever INT, created_at)
- users(steamid PK, personaname, num_games_owned, created_at)
- app_users(id PK, username, email, password_hash, full_name, is_active, created_at, last_login)

CSV split: dùng `UNNEST(STRING_TO_ARRAY(genres, ','))` cho genres/categories/publishers/developers/supported_languages.

Bạn PHẢI trả lời bằng JSON tool_call duy nhất:
{"tool_call": {"name": "execute_query", "arguments": {"sql": "SELECT genre, COUNT(*) FROM (SELECT TRIM(g) AS genre FROM games, UNNEST(STRING_TO_ARRAY(genres, ',')) AS g) t GROUP BY genre ORDER BY 2 DESC LIMIT 10", "limit": 10}}}

HOẶC

{"tool_call": {"name": "charting", "arguments": {
    "chart_type": "bar",
    "chart_title": "Top 10 thể loại game",
    "x_axis_label": "Thể loại",
    "y_axis_label": "Số lượng",
    "x_rotation": 30,
    "y_unit": "games",
    "series_label": "Số game",
    "config": {"labels": ["A","B"], "datasets": [{"label": "Số game", "data": [10, 20]}]},
    "source_query": "SELECT ...",
    "notes": "..."
}}}

Sau khi nhận tool_result, hãy diễn giải bằng tiếng Việt.
Nếu user chỉ chào hỏi hoặc hỏi ngoài phạm vi, trả lời text bình thường, KHÔNG gọi tool.
"""


_TOOL_CALL_RE = re.compile(r"\{[\s\S]*?\"tool_call\"[\s\S]*?\}")


def _extract_tool_call(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "tool_call" in data:
            return data["tool_call"]
    except Exception:
        pass
    m = _TOOL_CALL_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        if isinstance(data, dict) and "tool_call" in data:
            return data["tool_call"]
    except Exception:
        return None
    return None


ALLOWED_CHART_TYPES = {
    "bar",
    "line",
    "pie",
    "doughnut",
    "scatter",
    "radar",
    "area",
    "polarArea",
}


def _validate_chart_payload(args: Dict[str, Any]) -> Dict[str, Any]:
    ctype = str(args.get("chart_type", "bar")).lower().strip()
    if ctype == "area":
        ctype = "line"
    if ctype not in ALLOWED_CHART_TYPES:
        raise BadRequestException(detail=f"chart_type không hợp lệ: {ctype}")

    title = str(args.get("chart_title", "")).strip()[:200]
    if not title:
        raise BadRequestException(detail="chart_title là bắt buộc.")

    config = args.get("config") or {}
    if not isinstance(config, dict):
        raise BadRequestException(detail="config phải là object Chart.js.")

    options = config.get("options") or {}
    x_rot = args.get("x_rotation")
    if isinstance(x_rot, (int, float)):
        x_rot = max(-90, min(90, int(x_rot)))
        scales = options.setdefault("scales", {})
        x_scale = scales.setdefault("x", {})
        ticks = x_scale.setdefault("ticks", {})
        ticks["maxRotation"] = x_rot
        ticks["minRotation"] = x_rot
    else:
        x_rot = None

    y_unit = args.get("y_unit")
    y_label = args.get("y_axis_label")
    if y_unit and y_label and isinstance(y_label, str):
        if f"({y_unit})" not in y_label:
            y_label = f"{y_label} ({y_unit})"
    elif y_unit and not y_label:
        y_label = f"({y_unit})"

    options.setdefault("responsive", True)
    options.setdefault("maintainAspectRatio", False)
    config["options"] = options

    return {
        "chart_type": ctype,
        "chart_title": title,
        "x_axis_label": args.get("x_axis_label") or None,
        "y_axis_label": y_label,
        "series_label": args.get("series_label") or None,
        "x_rotation": x_rot,
        "y_unit": y_unit,
        "config": config,
        "source_query": args.get("source_query"),
        "notes": args.get("notes"),
    }


_FORBIDDEN_KEYWORDS = (
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bcopy\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bcreate\b",
    r"\bvacuum\b",
    r"\banalyze\b",
    r"\brefresh\b",
    r"\bcreateextension\b",
    r"\bset\b",
    r"\bcall\b",
    r"\bdo\b",
    r"\bexplain\b",
    r"\bselect\s+into\b",
)


def _validate_sql(sql: str) -> str:
    if not sql or not sql.strip():
        raise BadRequestException(detail="SQL rỗng.")
    cleaned = sql.strip().rstrip(";").strip()
    head = cleaned[:64].lower().lstrip(" (")
    if not (head.startswith("select") or head.startswith("with")):
        raise BadRequestException(
            detail="Chỉ chấp nhận câu SELECT/WITH (read-only)."
        )
    low = cleaned.lower()
    for kw in _FORBIDDEN_KEYWORDS:
        if re.search(kw, low):
            raise BadRequestException(
                detail=f"SQL chứa từ khóa bị cấm: {kw}."
            )
    return cleaned


class AIService:
    """AI Agent: chat, chat_stream, charting tool, execute_query tool."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
        self.model = settings.OPENROUTER_MODEL
        self.fallback_model = settings.OPENROUTER_FALLBACK_MODEL
        self.steam = SteamService(db)

    async def chat(
        self,
        user: AppUser,
        message: str,
        session_id: Optional[str] = None,
        max_tool_steps: int = 3,
    ) -> Dict[str, Any]:
        session_id = (
            session_id
            or f"session_{user.id}_{int(datetime.now().timestamp())}"
        )
        history = await self.get_chat_history(user, session_id, limit=10)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        await self.save_chat(user, session_id, "user", message)

        tool_calls_log: List[Dict[str, Any]] = []
        charts_log: List[Dict[str, Any]] = []

        final_reply = ""
        for _step in range(max_tool_steps):
            raw = await self._call_llm_with_fallback(messages)
            tool_call = _extract_tool_call(raw)
            if not tool_call:
                final_reply = raw
                break

            name = tool_call.get("name")
            args = tool_call.get("arguments") or {}
            try:
                if name == "execute_query":
                    tool_result = await self.tool_execute_query(args)
                elif name == "charting":
                    tool_result = await self.tool_charting(
                        user, session_id, args
                    )
                    charts_log.append(tool_result)
                else:
                    tool_result = {"error": f"Unknown tool: {name}"}
            except BadRequestException as e:
                tool_result = {"error": str(e.detail)}
            except Exception as e:
                logger.exception("Tool %s error", name)
                tool_result = {"error": f"Lỗi tool: {e}"}

            tool_calls_log.append(
                {"name": name, "arguments": args, "result": tool_result}
            )
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Tool result (JSON): "
                        + json.dumps(
                            tool_result, ensure_ascii=False, default=str
                        )
                        + "\nHãy tóm tắt kết quả bằng tiếng Việt cho người dùng."
                    ),
                }
            )
        else:
            final_reply = "Đã đạt giới hạn bước xử lý tool."

        await self.save_chat(user, session_id, "assistant", final_reply)
        return {
            "session_id": session_id,
            "reply": final_reply,
            "tool_calls": tool_calls_log,
            "charts": charts_log,
        }

    async def chat_stream(
        self,
        user: AppUser,
        message: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        session_id = (
            session_id
            or f"session_{user.id}_{int(datetime.now().timestamp())}"
        )
        history = await self.get_chat_history(user, session_id, limit=10)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        await self.save_chat(user, session_id, "user", message)

        full_reply = ""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
                stream=True,
            )
            async for chunk in stream:
                delta = (
                    chunk.choices[0].delta.content if chunk.choices else None
                )
                if delta:
                    full_reply += delta
                    yield delta
        except Exception as e:
            err = f"[Lỗi stream: {e}]"
            full_reply += err
            yield err
            logger.exception("Stream chat error")
        await self.save_chat(user, session_id, "assistant", full_reply)

    async def _call_llm_with_fallback(
        self, messages: List[Dict[str, str]]
    ) -> str:
        for attempt, model_name in enumerate(
            [self.model, self.fallback_model], 1
        ):
            try:
                resp = await self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=1500,
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                logger.warning(
                    "LLM attempt %s (model=%s) failed: %s",
                    attempt,
                    model_name,
                    e,
                )
                if attempt >= 2:
                    raise ServiceUnavailableException(
                        detail=f"Không thể kết nối OpenRouter: {e}"
                    ) from e
        return ""

    async def tool_execute_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        sql = _validate_sql(str(args.get("sql", "")))
        params = args.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        limit = int(args.get("limit") or 200)
        return await self.steam.execute_readonly_query(
            sql, params, limit=limit
        )

    async def tool_charting(
        self,
        user: AppUser,
        session_id: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        clean = _validate_chart_payload(args)
        record = AIChartHistory(
            user_id=user.id,
            session_id=session_id,
            chart_type=clean["chart_type"],
            chart_title=clean["chart_title"],
            x_axis_label=clean["x_axis_label"],
            y_axis_label=clean["y_axis_label"],
            series_label=clean["series_label"],
            config=clean["config"],
            source_query=clean["source_query"],
        )
        record.created_at = datetime.now(timezone.utc)
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        clean["chart_id"] = record.id
        clean["created_at"] = (
            record.created_at.isoformat() if record.created_at else None
        )
        return clean

    async def list_charts(
        self, user: AppUser, session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        q = select(AIChartHistory).where(AIChartHistory.user_id == user.id)
        if session_id:
            q = q.where(AIChartHistory.session_id == session_id)
        q = q.order_by(AIChartHistory.created_at.desc()).limit(100)
        rows = list((await self.db.execute(q)).scalars().all())
        return [
            {
                "id": r.id,
                "session_id": r.session_id,
                "chart_type": r.chart_type,
                "chart_title": r.chart_title,
                "x_axis_label": r.x_axis_label,
                "y_axis_label": r.y_axis_label,
                "series_label": r.series_label,
                "config": r.config,
                "source_query": r.source_query,
                "created_at": (
                    r.created_at.isoformat() if r.created_at else None
                ),
            }
            for r in rows
        ]

    async def save_chat(
        self,
        user: AppUser,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        record = ChatHistory(
            user_id=user.id,
            session_id=session_id,
            role=role,
            content=content[:8000],
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.commit()

    async def get_chat_history(
        self,
        user: AppUser,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:
        result = await self.db.execute(
            select(ChatHistory)
            .where(
                ChatHistory.user_id == user.id,
                ChatHistory.session_id == session_id,
            )
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def list_sessions(self, user: AppUser) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(
                ChatHistory.session_id,
                func.max(ChatHistory.created_at).label("last_active"),
            )
            .where(ChatHistory.user_id == user.id)
            .group_by(ChatHistory.session_id)
            .order_by(func.max(ChatHistory.created_at).desc())
        )
        return [
            {
                "session_id": row[0],
                "last_active": row[1].isoformat() if row[1] else None,
            }
            for row in result.fetchall()
        ]
