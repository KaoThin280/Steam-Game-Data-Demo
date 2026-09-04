"""Redacted, AI-assisted operational error email notifications."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_URL_CREDENTIALS = re.compile(r"(?i)\b(postgres(?:ql)?|redis(?:s)?)://[^\s]+")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|passwd|secret|token)\b\s*[:=]\s*[^\s,;]+"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_KNOWN_TOKEN = re.compile(r"\b(?:sk-or-v1-|e2b_)[A-Za-z0-9_-]{12,}")


def redact_text(value: Any, limit: int = 3000) -> str:
    """Remove common credentials and cap data sent to the model/email."""
    text = str(value or "")
    text = _URL_CREDENTIALS.sub(r"\1://<redacted>", text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _BEARER.sub("Bearer <redacted>", text)
    text = _KNOWN_TOKEN.sub("<redacted-token>", text)
    return text[:limit]


def _fallback_summary(component: str, error_type: str, message: str) -> tuple[str, str]:
    title = f"Lỗi {component}: {error_type}"[:160]
    body = (
        f"Hệ thống phát hiện lỗi tại {component}.\n\n"
        f"Chi tiết: {message or 'Không có thông báo lỗi.'}\n\n"
        "OpenRouter không tạo được phần giải thích bổ sung. Hãy kiểm tra log máy chủ theo thời điểm xảy ra lỗi."
    )
    return title, body


def _parse_summary(raw: str, fallback: tuple[str, str]) -> tuple[str, str]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I)
    try:
        payload = json.loads(candidate)
        title = str(payload.get("title", "")).strip().replace("\r", " ").replace("\n", " ")
        body = str(payload.get("body", "")).strip()
        if title and body:
            return title[:160], body[:4000]
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    return fallback


class ErrorNotificationService:
    """Summarize operational failures with OpenRouter and send via SMTP."""

    def __init__(self) -> None:
        self._last_sent: dict[str, float] = {}
        self._last_any_sent = 0.0
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[bool]] = set()

    def schedule(
        self,
        *,
        component: str,
        error: BaseException | str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Queue delivery without delaying an API response or agent cleanup."""
        if not settings.ERROR_NOTIFICATIONS_ENABLED:
            return
        task = asyncio.create_task(
            self.notify(component=component, error=error, context=context),
            name=f"error-notification-{component}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def notify(
        self,
        *,
        component: str,
        error: BaseException | str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        if not settings.ERROR_NOTIFICATIONS_ENABLED:
            return False

        error_type = type(error).__name__ if isinstance(error, BaseException) else "ApplicationError"
        message = redact_text(error)
        safe_context = {
            str(key)[:80]: redact_text(value, 500)
            for key, value in (context or {}).items()
            if key.lower() not in {"authorization", "cookie", "password", "token", "request_body"}
        }
        fingerprint = hashlib.sha256(
            f"{component}|{error_type}|{message}".encode("utf-8", errors="replace")
        ).hexdigest()
        if not await self._claim(fingerprint):
            return False

        fallback = _fallback_summary(component, error_type, message)
        try:
            title, body = await self._summarize(component, error_type, message, safe_context, fallback)
            await asyncio.to_thread(self._send_email, title, body, component, error_type, safe_context)
            logger.info("Operational error notification sent for %s", component)
            return True
        except Exception as notification_error:
            # Never let alerting replace or recursively report the original failure.
            logger.warning("Error notification delivery failed: %s", redact_text(notification_error, 500))
            return False

    async def _claim(self, fingerprint: str) -> bool:
        now = time.monotonic()
        interval = settings.ERROR_NOTIFICATION_MIN_INTERVAL_SECONDS
        async with self._lock:
            if now - self._last_any_sent < interval:
                return False
            last = self._last_sent.get(fingerprint)
            if last is not None and now - last < interval:
                return False
            self._last_sent[fingerprint] = now
            self._last_any_sent = now
            if len(self._last_sent) > 500:
                cutoff = now - interval
                self._last_sent = {key: value for key, value in self._last_sent.items() if value >= cutoff}
        return True

    async def _summarize(
        self,
        component: str,
        error_type: str,
        message: str,
        context: dict[str, str],
        fallback: tuple[str, str],
    ) -> tuple[str, str]:
        client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            timeout=min(settings.LLM_TIMEOUT, 30),
            max_retries=1,
        )
        prompt = {
            "component": component,
            "environment": settings.ERROR_NOTIFICATION_ENVIRONMENT,
            "error_type": error_type,
            "message": message,
            "context": context,
        }
        models = [settings.OPENROUTER_MODEL]
        if settings.OPENROUTER_FALLBACK_MODEL not in models:
            models.append(settings.OPENROUTER_FALLBACK_MODEL)
        for model in models:
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Bạn là trợ lý vận hành backend. Tóm tắt lỗi bằng tiếng Việt, ngắn gọn nhưng hữu ích. "
                                "Chỉ trả JSON hợp lệ với hai chuỗi: title và body. Body nêu hiện tượng, nguyên nhân có thể "
                                "và bước kiểm tra tiếp theo. Không bịa dữ kiện, không yêu cầu hoặc lặp lại secret."
                            ),
                        },
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                    ],
                    temperature=0.1,
                    max_tokens=500,
                )
                content = response.choices[0].message.content or ""
                parsed = _parse_summary(content, fallback)
                if parsed != fallback or content.strip():
                    return parsed
            except Exception as model_error:
                logger.warning("Error summarizer model %s failed: %s", model, redact_text(model_error, 300))
        return fallback

    def _send_email(
        self,
        title: str,
        body: str,
        component: str,
        error_type: str,
        context: dict[str, str],
    ) -> None:
        sender = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        message = EmailMessage()
        message["Subject"] = f"[Steam API][{settings.ERROR_NOTIFICATION_ENVIRONMENT}] {title}"[:240]
        message["From"] = sender
        message["To"] = settings.ERROR_NOTIFICATION_TO
        context_lines = "\n".join(f"- {key}: {value}" for key, value in context.items())
        message.set_content(
            f"{body}\n\nThông tin hệ thống:\n- Component: {component}\n- Error type: {error_type}"
            + (f"\n{context_lines}" if context_lines else "")
        )
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
            if settings.SMTP_STARTTLS:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)


error_notification_service = ErrorNotificationService()


async def _manual_test() -> None:
    delivered = await error_notification_service.notify(
        component="manual.test",
        error="Controlled test notification; no production request data is included.",
        context={"source": "python -m app.services.error_notification_service"},
    )
    print("Notification sent." if delivered else "Notification skipped or delivery failed; check configuration and logs.")


if __name__ == "__main__":
    asyncio.run(_manual_test())
