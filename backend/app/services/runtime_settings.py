from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException

from app.core.config import get_settings, get_settings_file_path, refresh_settings_cache
from app.schemas.api import BrokerageSyncConfigRead, BrokerageSyncConfigUpdate


BROKERAGE_SYNC_ENV_KEYS = (
    "BROKERAGE_SYNC_PROVIDER",
    "SNAPTRADE_CLIENT_ID",
    "SNAPTRADE_CONSUMER_KEY",
    "SNAPTRADE_REDIRECT_URI",
)

ENV_ASSIGNMENT_PATTERN = re.compile(r"^\s*([A-Z0-9_]+)=(.*)$")


def get_brokerage_sync_config() -> BrokerageSyncConfigRead:
    settings = get_settings()
    return BrokerageSyncConfigRead(
        provider=settings.brokerage_sync_provider,
        snaptrade_client_id=settings.snaptrade_client_id,
        snaptrade_redirect_uri=settings.snaptrade_redirect_uri,
        consumer_key_configured=bool(settings.snaptrade_consumer_key),
        consumer_key_masked=_mask_secret(settings.snaptrade_consumer_key),
    )


def update_brokerage_sync_config(payload: BrokerageSyncConfigUpdate) -> BrokerageSyncConfigRead:
    provider = payload.provider.strip().lower() or "disabled"
    if provider not in {"disabled", "mock", "snaptrade"}:
        raise HTTPException(status_code=400, detail="Provider must be one of disabled, mock, or snaptrade.")

    current_settings = get_settings()
    consumer_key = current_settings.snaptrade_consumer_key
    if payload.clear_consumer_key:
        consumer_key = None
    elif payload.snaptrade_consumer_key is not None and payload.snaptrade_consumer_key.strip():
        consumer_key = payload.snaptrade_consumer_key.strip()

    updates = {
        "BROKERAGE_SYNC_PROVIDER": provider,
        "SNAPTRADE_CLIENT_ID": _clean_optional(payload.snaptrade_client_id),
        "SNAPTRADE_CONSUMER_KEY": consumer_key,
        "SNAPTRADE_REDIRECT_URI": _clean_optional(payload.snaptrade_redirect_uri),
    }

    _write_env_updates(get_settings_file_path(), updates)
    refresh_settings_cache(updates)
    return get_brokerage_sync_config()


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * max(len(value) - 4, 4)}{value[-4:]}"


def _write_env_updates(path: Path, updates: dict[str, str | None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    assignment_index: dict[str, int] = {}
    for index, line in enumerate(lines):
        match = ENV_ASSIGNMENT_PATTERN.match(line)
        if match:
            assignment_index[match.group(1)] = index

    for key, value in updates.items():
        rendered = f"{key}={value or ''}"
        if key in assignment_index:
            lines[assignment_index[key]] = rendered
        else:
            lines.append(rendered)

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
