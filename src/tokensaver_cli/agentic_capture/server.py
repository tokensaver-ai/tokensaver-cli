"""Local HTTP capture side-channel for Claude Code (hooks + OTLP)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from tokensaver_cli.agentic_capture.envelope import (
    build_envelope,
    capture_enabled,
    capture_port,
    configure_shipper,
    current_claude_session_id,
    extract_hook_ids,
    get_shipper,
    note_claude_session,
)

logger = logging.getLogger("tokensaver-cli.agentic_capture")

# Re-export for package __init__
__all__ = [
    "capture_client_environ",
    "capture_enabled",
    "capture_health_ok",
    "capture_port",
    "ensure_capture_running",
    "handle_capture_request",
    "run_capture_serve",
]


def _json_response(status: int, body: dict[str, Any]) -> tuple[int, bytes, str]:
    return status, json.dumps(body).encode("utf-8"), "application/json"


def handle_capture_request(
    method: str,
    path: str,
    headers: dict[str, str],
    body: bytes,
) -> tuple[int, bytes, str]:
    method = method.upper()
    path = path.split("?", 1)[0]
    shipper = get_shipper()

    if method == "GET" and path in ("/health", "/"):
        return _json_response(
            200, {"ok": True, "service": "tokensaver-cli-claude-capture"}
        )

    if method == "POST" and path == "/hooks":
        try:
            parsed = json.loads(body.decode("utf-8") or "{}")
            if not isinstance(parsed, dict):
                parsed = {"raw": parsed}
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = {"raw_b64": body.hex()}
        ids = extract_hook_ids(parsed)
        hook_event = str(
            parsed.get("hook_event_name")
            or parsed.get("hookEventName")
            or parsed.get("event")
            or headers.get("x-claude-hook-event")
            or "unknown"
        )
        note_claude_session(ids["session_id"])
        env = build_envelope(
            source="hook",
            session_id=ids["session_id"],
            payload={"hook_event": hook_event, **parsed},
            claude_code_version=ids["claude_code_version"],
            prompt_id=ids["prompt_id"],
            tool_use_id=ids["tool_use_id"],
            agent_id=ids["agent_id"],
        )
        shipper.enqueue(env)
        return _json_response(200, {"continue": True, "suppressOutput": True})

    if method == "POST" and path in ("/v1/logs", "/v1/metrics", "/v1/traces"):
        ctype = (headers.get("content-type") or "").lower()
        signal = path.rsplit("/", 1)[-1]
        session_hdr = headers.get("x-session-id") or headers.get("session-id")
        payload: dict[str, Any] = {
            "otlp_signal": signal,
            "content_type": ctype,
            "byte_length": len(body),
            "body_hex_prefix": body[:64].hex() if body else "",
            "body_b64": None,
        }
        max_inline = int(
            os.environ.get("TOKENSAVER_OTLP_INLINE_MAX", "262144") or "262144"
        )
        if len(body) <= max_inline:
            payload["body_b64"] = base64.b64encode(body).decode("ascii")
        else:
            payload["truncated"] = True
            payload["body_b64_prefix"] = base64.b64encode(body[:max_inline]).decode(
                "ascii"
            )

        note_claude_session(session_hdr)
        env = build_envelope(
            source="otel",
            session_id=session_hdr or current_claude_session_id(),
            payload=payload,
            extra={"otlp_path": path},
        )
        shipper.enqueue(env)
        return 200, b"", "application/json"

    return _json_response(404, {"error": "not_found"})


async def _read_http_request(
    reader: asyncio.StreamReader,
) -> tuple[str, str, dict[str, str], bytes] | None:
    try:
        request_line = await asyncio.wait_for(reader.readline(), timeout=30.0)
    except (asyncio.TimeoutError, ConnectionError, asyncio.IncompleteReadError):
        return None
    if not request_line:
        return None
    try:
        line = request_line.decode("latin-1").strip()
        method, path, _proto = line.split(" ", 2)
    except ValueError:
        return None
    headers: dict[str, str] = {}
    while True:
        raw = await reader.readline()
        if raw in (b"\r\n", b"\n", b""):
            break
        try:
            hk, hv = raw.decode("latin-1").split(":", 1)
            headers[hk.strip().lower()] = hv.strip()
        except ValueError:
            continue
    length = int(headers.get("content-length") or "0")
    body = b""
    if length > 0:
        body = await reader.readexactly(min(length, 8 * 1024 * 1024))
    return method, path, headers, body


async def _handle_capture_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        parsed = await _read_http_request(reader)
        if not parsed:
            return
        method, path, headers, body = parsed
        status, resp_body, ctype = await asyncio.to_thread(
            handle_capture_request, method, path, headers, body
        )
        reason = {200: "OK", 404: "Not Found"}.get(status, "OK")
        header = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {ctype}\r\n"
            f"Content-Length: {len(resp_body)}\r\n"
            "Connection: close\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "\r\n"
        ).encode("latin-1")
        writer.write(header + resp_body)
        await writer.drain()
    except Exception:
        logger.debug("capture client error", exc_info=True)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


def capture_client_environ(port: int | None = None) -> dict[str, str]:
    """Env vars for Claude settings so hooks/OTEL hit this side-channel."""
    if not capture_enabled():
        return {}
    p = port if port is not None else capture_port()
    base = f"http://127.0.0.1:{p}"
    return {
        "OTEL_EXPORTER_OTLP_ENDPOINT": base,
        "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
        "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",
        "TOKENSAVER_CLAUDE_HOOKS_URL": f"{base}/hooks",
        "TOKENSAVER_CAPTURE_PORT": str(p),
    }


def capture_health_ok(port: int | None = None, timeout: float = 0.8) -> bool:
    p = port if port is not None else capture_port()
    url = f"http://127.0.0.1:{p}/health"
    try:
        req = urlrequest.Request(url, method="GET")
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8") or "{}")
        return bool(isinstance(data, dict) and data.get("ok"))
    except (urlerror.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return False


def ensure_capture_running(
    *,
    api_host: str | None = None,
    api_key: str | None = None,
    port: int | None = None,
) -> bool:
    """Start background ``tokensaver capture serve`` if health fails. Returns True if healthy."""
    if not capture_enabled():
        return False
    p = port if port is not None else capture_port()
    if capture_health_ok(p):
        return True
    env = os.environ.copy()
    if api_key:
        env["TOKENSAVER_API_KEY"] = api_key
    if api_host:
        env["TOKENSAVER_API_URL"] = api_host
    env["TOKENSAVER_CAPTURE_PORT"] = str(p)
    try:
        subprocess.Popen(
            [sys.executable, "-m", "tokensaver_cli.agentic_capture.__main__", "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        logger.warning("failed to start agentic capture: %s", exc)
        return False
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        if capture_health_ok(p):
            return True
        time.sleep(0.15)
    return capture_health_ok(p)


async def _serve_forever(host: str, port: int) -> None:
    shipper = get_shipper()

    async def _flush_loop() -> None:
        while True:
            await asyncio.sleep(2.0)
            try:
                await asyncio.to_thread(shipper.flush)
            except Exception:
                logger.debug("agentic flush error", exc_info=True)

    server = await asyncio.start_server(_handle_capture_client, host, port)
    asyncio.create_task(_flush_loop(), name="cli-claude-capture-flush")
    addr = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(
        f"TokenSaver Claude capture listening on {addr}  "
        f"(POST /hooks, POST /v1/logs|metrics|traces)",
        flush=True,
    )
    async with server:
        await server.serve_forever()


def run_capture_serve(
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    api_host: str | None = None,
    api_key: str | None = None,
) -> int:
    """Blocking serve loop for ``tokensaver capture serve``."""
    if not capture_enabled():
        print(
            "Claude capture disabled (TOKENSAVER_CLAUDE_CAPTURE=0)",
            file=sys.stderr,
        )
        return 1
    p = port if port is not None else capture_port()
    if api_host or api_key:
        configure_shipper(api_host=api_host, api_key=api_key)
    else:
        # Refresh shipper from credentials if env incomplete.
        try:
            from tokensaver_cli.credentials import resolve_api_key
            from tokensaver_cli.config import resolve_route_config

            key = resolve_api_key()
            try:
                cfg = resolve_route_config()
                configure_shipper(api_host=cfg.api_host, api_key=key or cfg.api_key)
            except Exception:
                if key:
                    configure_shipper(api_key=key)
        except Exception:
            get_shipper()
    try:
        asyncio.run(_serve_forever(host, p))
    except KeyboardInterrupt:
        get_shipper().flush()
        return 0
    except OSError as exc:
        print(f"capture serve failed: {exc}", file=sys.stderr)
        return 1
    return 0
