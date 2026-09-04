import pytest

from app.core.config import settings
from app.services.error_notification_service import (
    ErrorNotificationService,
    _parse_summary,
    redact_text,
)


def test_redact_text_removes_credentials_and_tokens():
    source = (
        "connect postgresql://user:pa@ss@db.example.com:5432/db "
        "Authorization=Bearer secret-value sk-or-v1-abcdefghijkl"
    )
    redacted = redact_text(source)
    assert "pa@ss" not in redacted
    assert "secret-value" not in redacted
    assert "sk-or-v1-" not in redacted
    assert "postgresql://<redacted>" in redacted


def test_parse_summary_accepts_fenced_json():
    title, body = _parse_summary(
        '```json\n{"title":"Database unavailable","body":"Check the read-only connection."}\n```',
        ("fallback", "fallback"),
    )
    assert title == "Database unavailable"
    assert body == "Check the read-only connection."


@pytest.mark.asyncio
async def test_duplicate_notification_is_suppressed(monkeypatch):
    service = ErrorNotificationService()
    sent: list[str] = []
    monkeypatch.setattr(settings, "ERROR_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "ERROR_NOTIFICATION_MIN_INTERVAL_SECONDS", 300)

    async def summarize(*_args, **_kwargs):
        return "A title", "A body"

    def send_email(title, *_args, **_kwargs):
        sent.append(title)

    monkeypatch.setattr(service, "_summarize", summarize)
    monkeypatch.setattr(service, "_send_email", send_email)

    first = await service.notify(component="api.http", error="boom")
    second = await service.notify(component="api.http", error="boom")
    assert first is True
    assert second is False
    assert sent == ["A title"]
