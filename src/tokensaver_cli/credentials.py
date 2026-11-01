"""Local credentials store for CLI auth (JWT + API key)."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone

try:
    from datetime import UTC
except ImportError:  # Python < 3.11
    UTC = timezone.utc
from pathlib import Path
from typing import Any


def config_home() -> Path:
    base = Path.home() / ".config" / "tokensaver"
    base.mkdir(parents=True, exist_ok=True)
    return base


def credentials_path() -> Path:
    return config_home() / "credentials.json"


@dataclass
class Credentials:
    """Persisted CLI session. ``api_key`` is enough for ``route``; JWT unlocks keys/me."""

    api_key: str | None = None
    access_token: str | None = None
    email: str | None = None
    user_id: str | None = None
    workspace_id: str | None = None
    organisation_id: str | None = None
    key_id: str | None = None
    key_prefix: str | None = None
    api_host: str | None = None
    console_url: str | None = None
    plan_slug: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Credentials:
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in raw.items() if k in known}
        return cls(**data)


def load_credentials() -> Credentials | None:
    path = credentials_path()
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    creds = Credentials.from_dict(raw)
    if not creds.api_key and not creds.access_token:
        return None
    return creds


def save_credentials(creds: Credentials) -> Path:
    path = credentials_path()
    creds.updated_at = datetime.now(UTC).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(creds.to_dict(), indent=2) + "\n"
    # Write privately (owner read/write only).
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return path


def clear_credentials() -> bool:
    path = credentials_path()
    if not path.is_file():
        return False
    path.unlink(missing_ok=True)
    return True


def is_virtual_key(raw: str | None) -> bool:
    """True for TokenSaver virtual keys (``tsv_…``). Legacy ``ts_…`` is rejected."""
    return (raw or "").strip().startswith("tsv_")


def is_legacy_api_key(raw: str | None) -> bool:
    """True for deprecated product keys (``ts_…`` but not ``tsv_…``)."""
    k = (raw or "").strip()
    return k.startswith("ts_") and not k.startswith("tsv_")


def _reject_legacy_api_key(raw: str) -> None:
    if is_legacy_api_key(raw):
        raise RuntimeError(
            "Legacy ts_… API keys are no longer supported. "
            "Use a virtual key (tsv_…) from Console → Clés virtuelles, "
            "or: tokensaver login  (JWT + virtual key id)."
        )


def resolve_selected_api_key_id() -> str | None:
    """Virtual-key UUID for ``X-Selected-Api-Key-Id`` (D-20e).

    Used when Bearer is a session JWT (no ``tsv_…`` secret on disk).
    """
    env = (os.environ.get("TOKENSAVER_API_KEY_ID") or "").strip()
    if env:
        return env
    creds = load_credentials()
    if creds and creds.key_id and str(creds.key_id).strip():
        return str(creds.key_id).strip()
    return None


def auth_headers(*, accept: str = "application/json") -> dict[str, str]:
    """Authorization (+ optional ``X-Selected-Api-Key-Id``) for ``/sdk/*`` and loops."""
    key = resolve_api_key()
    if not key:
        raise RuntimeError("No credentials. Run: tokensaver login")
    headers: dict[str, str] = {
        "Authorization": f"Bearer {key}",
        "Accept": accept,
    }
    if not is_virtual_key(key):
        kid = resolve_selected_api_key_id()
        if kid:
            headers["X-Selected-Api-Key-Id"] = kid
    return headers


def resolve_api_key() -> str | None:
    """Bearer material for Claude / MCP / OpenAI routes.

    Priority:
    1. Session JWT from ``tokensaver login``. Pair with
       ``resolve_selected_api_key_id()`` / ``auth_headers()`` for ``/sdk/*``.
    2. ``TOKENSAVER_API_KEY`` env (virtual key ``tsv_…`` only).
    3. ``credentials.api_key`` (virtual key ``tsv_…`` only).

    Force env over JWT: ``TOKENSAVER_PREFER_API_KEY=1``.
    Legacy ``ts_…`` keys raise ``RuntimeError``.
    """
    creds = load_credentials()
    jwt = (
        creds.access_token.strip()
        if creds and creds.access_token and creds.access_token.strip()
        else None
    )
    env = (os.environ.get("TOKENSAVER_API_KEY") or "").strip() or None
    prefer_env = (os.environ.get("TOKENSAVER_PREFER_API_KEY") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if jwt and not prefer_env:
        return jwt
    if env:
        _reject_legacy_api_key(env)
        return env
    if jwt:
        return jwt
    if creds and creds.api_key and creds.api_key.strip():
        key = creds.api_key.strip()
        _reject_legacy_api_key(key)
        return key
    return None


def resolve_access_token() -> str | None:
    env = (os.environ.get("TOKENSAVER_ACCESS_TOKEN") or "").strip()
    if env:
        return env
    creds = load_credentials()
    if creds and creds.access_token:
        return creds.access_token.strip() or None
    return None


def resolve_plan_slug() -> str | None:
    """Env ``TOKENSAVER_PLAN`` wins, then credentials ``plan_slug``."""
    env = (os.environ.get("TOKENSAVER_PLAN") or "").strip().lower()
    if env:
        return env
    creds = load_credentials()
    if creds and creds.plan_slug:
        return creds.plan_slug.strip().lower() or None
    return None


def update_credentials(**kwargs: Any) -> Credentials | None:
    """Merge fields into the credentials file (no-op if missing)."""
    creds = load_credentials()
    if creds is None:
        return None
    for key, value in kwargs.items():
        if hasattr(creds, key):
            setattr(creds, key, value)
    save_credentials(creds)
    return creds
