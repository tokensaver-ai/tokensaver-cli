"""CLI agentic capture — envelope + HTTP handler (no network)."""

from __future__ import annotations

import json

from tokensaver_cli.agentic_capture.envelope import (
    build_envelope,
    extract_hook_ids,
    resolve_agentic_ingest_url,
)
from tokensaver_cli.agentic_capture.server import handle_capture_request


def test_build_envelope_seq_monotonic():
    a = build_envelope(source="hook", session_id="s1", payload={"x": 1})
    b = build_envelope(source="hook", session_id="s1", payload={"x": 2})
    assert a["seq"] == 1
    assert b["seq"] == 2
    assert a["source"] == "hook"
    assert a["session_id"] == "s1"


def test_extract_hook_ids_top_level_session():
    ids = extract_hook_ids({"session_id": "abc-123", "tool_use_id": "tu1"})
    assert ids["session_id"] == "abc-123"
    assert ids["tool_use_id"] == "tu1"


def test_resolve_ingest_url_from_host():
    url = resolve_agentic_ingest_url(api_host="https://api.tokensaver.fr")
    assert url.endswith("/api/v1/egress/agentic-events")


def test_health_handler():
    status, body, ctype = handle_capture_request("GET", "/health", {}, b"")
    assert status == 200
    assert ctype.startswith("application/json")
    data = json.loads(body.decode())
    assert data.get("ok") is True
    assert "cli" in str(data.get("service", ""))


def test_hooks_handler_fail_open(monkeypatch):
    enqueued: list = []

    class _FakeShipper:
        def enqueue(self, env):
            enqueued.append(env)

    monkeypatch.setattr(
        "tokensaver_cli.agentic_capture.server.get_shipper",
        lambda: _FakeShipper(),
    )
    payload = json.dumps(
        {"session_id": "sess-1", "hook_event_name": "PostToolUse", "tool_name": "Bash"}
    ).encode()
    status, body, _ = handle_capture_request(
        "POST",
        "/hooks",
        {"content-type": "application/json"},
        payload,
    )
    assert status == 200
    data = json.loads(body.decode())
    assert data.get("continue") is True
    assert len(enqueued) == 1
    assert enqueued[0]["source"] == "hook"
    assert enqueued[0]["session_id"] == "sess-1"
