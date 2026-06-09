"""
AI Service - Gọi OpenRouter API, khởi tạo sandbox E2B chạy code.
Cải tiến:
  - Thêm fallback model khi model chính lỗi.
  - E2B sandbox: gọi API trực tiếp với timeout + cleanup đảm bảo.
  - Bổ sung log/debug mode.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableException
from app.models.user import ChatHistory, User

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """
Bạn là một trợ lý AI chuyên phân tích dữ liệu game trên Steam.
Bạn có quyền truy cập vào cơ sở dữ liệu game và review của hệ thống.
Hãy trả lời ngắn gọn, chính xác, sử dụng tiếng Việt.
Nếu cần tính toán hoặc phân tích số liệu, bạn có thể yêu cầu chạy code Python
trong sandbox E2B. Bạn hãy chủ động đề xuất insight có giá trị cho người dùng.
Khi trả lời có chứa code Python, hãy đặt trong code block ```python ... ```.
"""


def _extract_python_code(text: str) -> Optional[str]:
    """Trích code Python từ markdown code block."""
    if not text or "```python" not in text:
        return None
    match = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


class AIService:
    """Service xử lý logic AI Agent (OpenRouter + E2B sandbox)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )
        self.model = settings.OPENROUTER_MODEL
        self.fallback_model = settings.OPENROUTER_FALLBACK_MODEL
        self.e2b_api_key = settings.E2B_API_KEY
        self.e2b_template = settings.E2B_TEMPLATE
        self.e2b_timeout = settings.E2B_TIMEOUT

    # ============== Chat thường ==============
    async def chat(
        self,
        user: User,
        message: str,
        session_id: Optional[str] = None,
        use_sandbox: bool = False,
    ) -> Dict[str, Any]:
        session_id = session_id or f"session_{user.id}_{int(datetime.now().timestamp())}"
        history = await self.get_chat_history(user, session_id, limit=10)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        reply = await self._call_llm_with_fallback(messages)

        # Nếu AI trả về code block và use_sandbox=True, chạy code
        code_result = None
        if use_sandbox:
            code = _extract_python_code(reply)
            if code:
                code_result = await self.run_python_sandbox(code)
                if code_result is not None:
                    final_msg = (
                        reply
                        + "\n\n**Kết quả chạy code:**\n```\n"
                        + code_result
                        + "\n```"
                    )
                    reply = final_msg

        # Lưu lịch sử chat
        await self.save_chat(user, session_id, "user", message)
        await self.save_chat(user, session_id, "assistant", reply)

        return {
            "session_id": session_id,
            "reply": reply,
            "code_executed": code_result,
        }

    # ============== Chat stream ==============
    async def chat_stream(
        self,
        user: User,
        message: str,
        session_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        session_id = session_id or f"session_{user.id}_{int(datetime.now().timestamp())}"
        history = await self.get_chat_history(user, session_id, limit=10)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT}
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
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_reply += delta
                    yield delta
        except Exception as e:
            err = f"[Lỗi stream: {e}]"
            full_reply += err
            yield err
            logger.exception("Stream chat error")

        await self.save_chat(user, session_id, "assistant", full_reply)

    # ============== LLM call with fallback ==============
    async def _call_llm_with_fallback(
        self, messages: List[Dict[str, str]]
    ) -> str:
        """Gọi LLM. Nếu model chính lỗi -> fallback sang model phụ."""
        for attempt, model_name in enumerate([self.model, self.fallback_model], 1):
            try:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1500,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning("LLM call attempt %s failed (model=%s): %s", attempt, model_name, e)
                if attempt >= 2:
                    raise ServiceUnavailableException(
                        detail=f"Không thể kết nối OpenRouter: {e}"
                    ) from e
                # tiếp tục thử fallback
        return ""

    # ============== E2B Sandbox ==============
    async def run_python_sandbox(self, code: str) -> Optional[str]:
        """
        Chạy code Python trong E2B sandbox.
        E2B SDK là sync, nên ta gọi API REST trực tiếp để giữ async.
        """
        if not self.e2b_api_key:
            return "(E2B chưa được cấu hình. Đặt E2B_API_KEY trong .env.)"

        if not code or not code.strip():
            return None

        sandbox_id: Optional[str] = None
        try:
            timeout = self.e2b_timeout
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 1) Tạo sandbox
                create_resp = await client.post(
                    "https://api.e2b.dev/sandboxes",
                    headers={"Authorization": f"Bearer {self.e2b_api_key}"},
                    json={"template": self.e2b_template},
                )
                create_resp.raise_for_status()
                sandbox = create_resp.json()
                sandbox_id = sandbox.get("sandboxId") or sandbox.get("id")

                if not sandbox_id:
                    return "(Không tạo được sandbox E2B.)"

                # 2) Chạy code
                exec_resp = await client.post(
                    f"https://api.e2b.dev/sandboxes/{sandbox_id}/execute",
                    headers={"Authorization": f"Bearer {self.e2b_api_key}"},
                    json={"code": code},
                )
                exec_resp.raise_for_status()
                result = exec_resp.json()
                output = (result.get("stdout") or "").strip()
                errors = (result.get("stderr") or "").strip()

                if errors:
                    return f"stdout:\n{output}\nstderr:\n{errors}"
                return output or "(Code chạy thành công, không có output.)"
        except httpx.TimeoutException:
            return f"(Sandbox timeout sau {self.e2b_timeout}s.)"
        except Exception as e:
            logger.exception("E2B sandbox error")
            return f"(Lỗi sandbox: {e})"
        finally:
            # 3) Cleanup sandbox
            if sandbox_id:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.delete(
                            f"https://api.e2b.dev/sandboxes/{sandbox_id}",
                            headers={"Authorization": f"Bearer {self.e2b_api_key}"},
                        )
                except Exception as cleanup_err:
                    logger.warning("Sandbox cleanup failed: %s", cleanup_err)

    # ============== Chat history ==============
    async def save_chat(
        self, user: User, session_id: str, role: str, content: str
    ) -> None:
        history = ChatHistory(
            user_id=user.id,
            session_id=session_id,
            role=role,
            content=content[:5000],
        )
        self.db.add(history)
        await self.db.commit()

    async def get_chat_history(
        self, user: User, session_id: str, limit: int = 10
    ) -> List[Dict[str, str]]:
        result = await self.db.execute(
            select(ChatHistory)
            .where(ChatHistory.user_id == user.id, ChatHistory.session_id == session_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
        )
        rows = list(result.scalars().all())
        rows.reverse()
        return [{"role": r.role, "content": r.content} for r in rows]

    async def list_sessions(self, user: User) -> List[Dict[str, Any]]:
        """Liệt kê các phiên chat của user (gộp theo session_id)."""
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

