import pytest
from types import SimpleNamespace

from app.core.config import settings
from app.services import error_notification_service as notification_module
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


@pytest.mark.parametrize("prefix", ["Authorization=", "Authorization: ", "authorization = ", ""])
def test_bearer_token_is_redacted_before_assignment(prefix):
    assert "sensitive-token" not in redact_text(prefix + "Bearer sensitive-token")


def test_parse_summary_accepts_fenced_json():
    title, body = _parse_summary(
        '```json\n{"title":"Database unavailable","body":"Check the read-only connection."}\n```',
        ("fallback", "fallback"),
    )
    assert title == "Database unavailable"
    assert body == "Check the read-only connection."


@pytest.mark.asyncio
@pytest.mark.parametrize("clock_start", [0.0, 1.0, 299.0, 300.0, 10000.0])
async def test_duplicate_notification_is_suppressed(monkeypatch, clock_start):
    service = ErrorNotificationService()
    sent: list[str] = []
    monkeypatch.setattr(settings, "ERROR_NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "ERROR_NOTIFICATION_MIN_INTERVAL_SECONDS", 300)
    # Patch only this module's clock, not asyncio's global monotonic clock.
    clock = [clock_start]
    monkeypatch.setattr(notification_module, "time", SimpleNamespace(monotonic=lambda: clock[0]))

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

    # A different error must also respect the global notification interval.
    clock[0] = clock_start + 299.0
    assert await service.notify(component="api.http", error="another error") is False
    clock[0] = clock_start + 300.0
    assert await service.notify(component="api.http", error="boom") is True
    assert sent == ["A title", "A title"]
