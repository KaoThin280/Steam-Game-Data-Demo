"""
Signed URL utilities - HMAC-based tokens for file serving.

Used by the data_files router to allow files in temp_data/ to be fetched
via signed URLs (e.g. inside iframes) without requiring the Authorization
header. Tokens are time-limited and bound to a specific filename.
"""
import hashlib
import hmac
import time
from urllib.parse import urlencode

from app.core.config import settings


# Token TTL in seconds (1 hour).
DEFAULT_TOKEN_TTL = 3600


def _sign(payload: str) -> str:
    """Return hex HMAC-SHA256 of the payload using the app SECRET_KEY."""
    secret = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_file_token(filename: str, expires_in: int = DEFAULT_TOKEN_TTL) -> str:
    """Build a signed token for a specific filename."""
    expiry = int(time.time()) + max(1, expires_in)
    payload = f"{expiry}.{filename}"
    return f"{expiry}.{_sign(payload)}"


def verify_file_token(filename: str, token: str) -> bool:
    """
    Verify that the token is valid for the given filename and has not expired.
    Uses constant-time comparison to avoid timing attacks.
    """
    if not token or "." not in token:
        return False
    try:
        expiry_str, provided_sig = token.rsplit(".", 1)
        expiry = int(expiry_str)
    except (ValueError, AttributeError):
        return False
    if expiry < int(time.time()):
        return False
    expected_sig = _sign(f"{expiry}.{filename}")
    return hmac.compare_digest(expected_sig, provided_sig)


def build_signed_url(base_url: str, filename: str, expires_in: int = DEFAULT_TOKEN_TTL) -> str:
    """Build a signed URL pointing at a specific file."""
    token = generate_file_token(filename, expires_in=expires_in)
    return f"{base_url}/{filename}?{urlencode({'token': token})}"