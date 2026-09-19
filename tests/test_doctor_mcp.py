"""Doctor MCP probe treats streamable-HTTP 400/401 as reachable."""

from __future__ import annotations

import io
import json
import urllib.error

from tokensaver_cli.doctor import _probe_mcp


class _FakeHTTPError(urllib.error.HTTPError):
    def __init__(self, code: int, body: bytes):
        super().__init__("http://x/mcp", code, "err", hdrs=None, fp=io.BytesIO(body))


def test_probe_mcp_get_style_session_400_is_ok(monkeypatch) -> None:
    body = json.dumps(
        {"jsonrpc": "2.0", "error": {"code": -32000, "message": "Bad Request: No valid session ID provided"}}
    ).encode()

    def boom(*_a, **_k):
        raise _FakeHTTPError(400, body)

    monkeypatch.setattr("tokensaver_cli.doctor.urllib.request.urlopen", boom)
    ok, detail = _probe_mcp("http://localhost:8788/mcp", "ts_x")
    assert ok is True
    assert "400" in detail


def test_probe_mcp_unauthorized_401_is_ok(monkeypatch) -> None:
    body = b'{"error":"unauthorized","message":"Bearer token required"}'

    def boom(*_a, **_k):
        raise _FakeHTTPError(401, body)

    monkeypatch.setattr("tokensaver_cli.doctor.urllib.request.urlopen", boom)
    ok, detail = _probe_mcp("http://localhost:8787/mcp", "ts_x")
    assert ok is True
    assert "auth" in detail
