from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from app.core.config import Settings


AUTH_EXEMPT_SUFFIXES = {
    "/health",
    "/ready",
    "/auth/login",
    "/auth/session",
    "/ops/metrics",
}


def _secret(settings: Settings) -> str:
    return settings.auth_secret or settings.auth_password or settings.app_name


def _signature(timestamp: int, settings: Settings) -> str:
    message = f"portfolio-auth:{timestamp}".encode("utf-8")
    return hmac.new(_secret(settings).encode("utf-8"), message, hashlib.sha256).hexdigest()


def issue_token(settings: Settings, now: datetime | None = None) -> tuple[str, datetime]:
    current = now or datetime.now(timezone.utc)
    expires_at = current + timedelta(minutes=settings.auth_token_ttl_minutes)
    timestamp = int(expires_at.timestamp())
    payload = f"{timestamp}:{_signature(timestamp, settings)}".encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("utf-8"), expires_at


def verify_token(token: str | None, settings: Settings, now: datetime | None = None) -> datetime | None:
    if not token or not settings.auth_enabled:
        return None
    current = now or datetime.now(timezone.utc)
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        timestamp_raw, signature = decoded.split(":", 1)
        expires_at = datetime.fromtimestamp(int(timestamp_raw), tz=timezone.utc)
    except Exception:
        return None

    expected_signature = _signature(int(timestamp_raw), settings)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    if expires_at <= current:
        return None
    return expires_at


def verify_password(password: str, settings: Settings) -> bool:
    if not settings.auth_enabled or not settings.auth_password:
        return True
    return hmac.compare_digest(password, settings.auth_password)


def parse_bearer_token(header: str | None) -> str | None:
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def is_auth_exempt_path(path: str, settings: Settings) -> bool:
    return any(path == f"{settings.api_prefix}{suffix}" for suffix in AUTH_EXEMPT_SUFFIXES)
