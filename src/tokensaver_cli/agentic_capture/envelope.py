"""Agentic event envelopes + shipper (P0 contract, CLI-owned copy)."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

logger = logging.getLogger("tokensaver-cli.agentic_capture")

DEFAULT_CAPTURE_PORT = 8790


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def capture_enabled() -> bool:
    return _env_truthy("TOKENSAVER_CLAUDE_CAPTURE", default=True)


def capture_port() -> int:
    raw = (os.environ.get("TOKENSAVER_CAPTURE_PORT") or "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return DEFAULT_CAPTURE_PORT


@dataclass
class SessionSeqStore:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _seqs: dict[str, int] = field(default_factory=dict)

    def next_seq(self, session_id: str) -> int:
        key = (session_id or "").strip() or "_unknown"
        with self._lock:
            n = self._seqs.get(key, 0) + 1
            self._seqs[key] = n
            return n


_SEQ = SessionSeqStore()


@dataclass
class CurrentClaudeSessionStore:
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _session_id: str | None = None
    _updated_at: float = 0.0

    def note(self, session_id: str | None) -> None:
        sid = (session_id or "").strip() or None
        if not sid:
            return
        with self._lock:
            self._session_id = sid
            self._updated_at = time.monotonic()

    def get(self, max_age_s: float = 6 * 3600) -> str | None:
        with self._lock:
            if not self._session_id:
                return None
            if max_age_s > 0 and (time.monotonic() - self._updated_at) > max_age_s:
                return None
            return self._session_id


_CURRENT_SESSION = CurrentClaudeSessionStore()


def note_claude_session(session_id: str | None) -> None:
    _CURRENT_SESSION.note(session_id)


def current_claude_session_id(max_age_s: float = 6 * 3600) -> str | None:
    return _CURRENT_SESSION.get(max_age_s=max_age_s)


def build_envelope(
    *,
    source: str,
    session_id: str | None,
    payload: Any,
    claude_code_version: str | None = None,
    prompt_id: str | None = None,
    tool_use_id: str | None = None,
    agent_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sid = (session_id or "").strip() or None
    env: dict[str, Any] = {
        "source": source,
        "session_id": sid,
        "seq": _SEQ.next_seq(sid or "_unknown"),
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "claude_code_version": (
            claude_code_version or os.environ.get("CLAUDE_CODE_VERSION") or ""
        ).strip()
        or None,
        "payload": payload,
    }
    if prompt_id:
        env["prompt_id"] = prompt_id
    if tool_use_id:
        env["tool_use_id"] = tool_use_id
    if agent_id:
        env["agent_id"] = agent_id
    if extra:
        env.update(extra)
    return env


def extract_hook_ids(body: dict[str, Any]) -> dict[str, str | None]:
    session_obj = body.get("session")
    session_from_obj = (
        session_obj.get("id") if isinstance(session_obj, dict) else None
    )
    session_id = body.get("session_id") or body.get("sessionId") or session_from_obj
    if isinstance(session_id, dict):
        session_id = session_id.get("id")
    return {
        "session_id": str(session_id).strip() if session_id else None,
        "prompt_id": str(body.get("prompt_id") or body.get("promptId") or "") or None,
        "tool_use_id": str(
            body.get("tool_use_id")
            or body.get("toolUseId")
            or body.get("tool_call_id")
            or ""
        )
        or None,
        "agent_id": str(body.get("agent_id") or body.get("agentId") or "") or None,
        "claude_code_version": str(
            body.get("claude_code_version") or body.get("version") or ""
        )
        or None,
    }


def resolve_agentic_ingest_url(*, api_host: str | None = None) -> str:
    """Build ``…/api/v1/egress/agentic-events`` from env or api host."""
    dedicated = (os.environ.get("TOKENSAVER_AGENTIC_INGEST_URL") or "").strip()
    if dedicated:
        return dedicated
    base = (os.environ.get("TOKENSAVER_INGEST_URL") or "").rstrip("/")
    if base.endswith("/egress/ingest"):
        base = base[: -len("/egress/ingest")]
    if base.endswith("/egress/agentic-events"):
        return base
    if base:
        if base.endswith("/api/v1"):
            return f"{base}/egress/agentic-events"
        return f"{base.rstrip('/')}/api/v1/egress/agentic-events"
    host = (api_host or os.environ.get("TOKENSAVER_API_URL") or "").rstrip("/")
    if host.endswith("/api/v1"):
        return f"{host}/egress/agentic-events"
    if host:
        return f"{host}/api/v1/egress/agentic-events"
    return ""


class AgenticEventShipper:
    """Best-effort batch shipper (never blocks Claude)."""

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.url = (url or "").strip()
        self.api_key = (api_key or "").strip()
        self._buf: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()
        self._ensure_auth()

    def ingest_ready(self) -> bool:
        self._ensure_auth()
        return bool(self.url and self.api_key)

    def _ensure_auth(self) -> None:
        """Fill url/api_key from env + ``tokensaver login`` JWT if missing."""
        if not self.api_key:
            self.api_key = (os.environ.get("TOKENSAVER_API_KEY") or "").strip()
        if not self.api_key:
            try:
                from tokensaver_cli.credentials import resolve_api_key

                self.api_key = (resolve_api_key() or "").strip()
            except Exception:
                pass
        if not self.url:
            host = (os.environ.get("TOKENSAVER_API_URL") or "").strip() or None
            if not host:
                try:
                    from tokensaver_cli.credentials import load_credentials

                    creds = load_credentials()
                    if creds and creds.api_host:
                        host = creds.api_host.strip()
                except Exception:
                    host = None
            self.url = resolve_agentic_ingest_url(api_host=host).strip()

    def enqueue(self, envelope: dict[str, Any]) -> None:
        self._ensure_auth()
        if not self.url or not self.api_key:
            logger.warning(
                "agentic ingest disabled (no url/api_key) — drop event source=%s",
                envelope.get("source"),
            )
            return
        with self._lock:
            self._buf.append(envelope)
            should = (
                len(self._buf) >= 20
                or (time.monotonic() - self._last_flush) > 2.0
            )
        if should:
            self.flush()

    def flush(self) -> None:
        self._ensure_auth()
        with self._lock:
            batch = self._buf
            self._buf = []
            self._last_flush = time.monotonic()
        if not batch:
            return
        if not self.url or not self.api_key:
            logger.warning(
                "agentic ingest flush skipped — missing url/api_key (%d events)",
                len(batch),
            )
            return
        try:
            data = json.dumps({"events": batch}).encode("utf-8")
            req = urlrequest.Request(
                self.url,
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "X-API-Key": self.api_key,
                },
            )
            with urlrequest.urlopen(req, timeout=5.0) as resp:
                resp.read()
        except urlerror.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            logger.warning(
                "agentic ingest failed (%d events): %s → %s (%s)",
                len(batch),
                exc,
                self.url,
                detail,
            )
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "agentic ingest failed (%d events): %s → %s",
                len(batch),
                exc,
                self.url,
            )


_SHIPPER: AgenticEventShipper | None = None


def get_shipper() -> AgenticEventShipper:
    global _SHIPPER
    if _SHIPPER is None:
        _SHIPPER = AgenticEventShipper()
    return _SHIPPER


def configure_shipper(*, api_host: str | None = None, api_key: str | None = None) -> AgenticEventShipper:
    global _SHIPPER
    url = resolve_agentic_ingest_url(api_host=api_host) if api_host else None
    _SHIPPER = AgenticEventShipper(url=url, api_key=api_key)
    return _SHIPPER
