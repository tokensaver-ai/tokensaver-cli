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


def test_health_handler(monkeypatch):
    class _Ready:
        def ingest_ready(self):
            return True

    monkeypatch.setattr(
        "tokensaver_cli.agentic_capture.server.get_shipper",
        lambda: _Ready(),
    )
    status, body, ctype = handle_capture_request("GET", "/health", {}, b"")
    assert status == 200
    assert ctype.startswith("application/json")
    data = json.loads(body.decode())
    assert data.get("ok") is True
    assert data.get("ingest_ready") is True
    assert "cli" in str(data.get("service", ""))


def test_configure_handler(monkeypatch):
    configured: dict = {}

    class _Ship:
        def ingest_ready(self):
            return True

    def _cfg(*, api_host=None, api_key=None):
        configured["api_host"] = api_host
        configured["api_key"] = api_key
        return _Ship()

    monkeypatch.setattr(
        "tokensaver_cli.agentic_capture.server.configure_shipper",
        _cfg,
    )
    monkeypatch.setattr(
        "tokensaver_cli.agentic_capture.server.get_shipper",
        lambda: _Ship(),
    )
    body = json.dumps(
        {"api_host": "http://localhost:8000", "api_key": "eyJtest"}
    ).encode()
    status, raw, _ = handle_capture_request("POST", "/configure", {}, body)
    assert status == 200
    assert configured["api_host"] == "http://localhost:8000"
    assert configured["api_key"] == "eyJtest"
    assert json.loads(raw.decode()).get("ingest_ready") is True


def test_shipper_loads_login_jwt(monkeypatch, tmp_path):
    from tokensaver_cli.agentic_capture.envelope import AgenticEventShipper
    from tokensaver_cli.credentials import Credentials, save_credentials

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    save_credentials(
        Credentials(
            access_token="jwt-for-capture",
            api_host="http://localhost:8000",
        )
    )
    ship = AgenticEventShipper()
    assert ship.ingest_ready()
    assert ship.api_key == "jwt-for-capture"
    assert ship.url.endswith("/api/v1/egress/agentic-events")


def test_run_capture_serve_prefers_env_local_host(monkeypatch, tmp_path):
    """Local JWT must not be shipped to api.tokensaver.fr (401)."""
    from tokensaver_cli.agentic_capture import server as serve_mod
    from tokensaver_cli.credentials import Credentials, save_credentials

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TOKENSAVER_API_URL", "http://localhost:8000")
    monkeypatch.setenv("TOKENSAVER_API_KEY", "jwt-local")
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    save_credentials(
        Credentials(access_token="jwt-local", api_host="http://localhost:8000")
    )

    configured: dict = {}

    def _cfg(*, api_host=None, api_key=None):
        configured["api_host"] = api_host
        configured["api_key"] = api_key

        class _S:
            def ingest_ready(self):
                return True

        return _S()

    monkeypatch.setattr(serve_mod, "configure_shipper", _cfg)
    monkeypatch.setattr(serve_mod, "capture_enabled", lambda: True)
    monkeypatch.setattr(serve_mod, "capture_port", lambda: 18790)

    def _fake_run(coro):
        try:
            coro.close()
        except Exception:
            pass
        raise OSError("skip bind")

    monkeypatch.setattr(serve_mod.asyncio, "run", _fake_run)

    rc = serve_mod.run_capture_serve()
    assert rc == 1  # bind failed after configure
    assert configured.get("api_host") == "http://localhost:8000"
    assert configured.get("api_key") == "jwt-local"


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
