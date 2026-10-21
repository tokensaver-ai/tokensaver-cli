"""``tokensaver capture serve|status`` — Claude agentic graph side-channel."""

from __future__ import annotations

import sys

from tokensaver_cli.agentic_capture import (
    capture_enabled,
    capture_health_ok,
    capture_port,
    run_capture_serve,
)


def run_capture(action: str | None, *, force_local: bool = False) -> int:
    act = (action or "serve").strip().lower()
    if act in ("serve", "run", "start"):
        api_host = None
        api_key = None
        try:
            from tokensaver_cli.config import resolve_route_config

            cfg = resolve_route_config(force_local=force_local)
            api_host = cfg.api_host
            api_key = cfg.api_key
        except Exception as exc:
            print(
                f"WARN  capture: credentials incomplete ({exc}); "
                "set TOKENSAVER_API_KEY / TOKENSAVER_API_URL",
                file=sys.stderr,
            )
        return run_capture_serve(api_host=api_host, api_key=api_key)

    if act in ("status", "health"):
        if not capture_enabled():
            print("capture: disabled (TOKENSAVER_CLAUDE_CAPTURE=0)")
            return 1
        port = capture_port()
        ok = capture_health_ok(port)
        ingest = ""
        if ok:
            try:
                from urllib import request as urlrequest
                import json

                with urlrequest.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=1.0
                ) as resp:
                    data = json.loads(resp.read().decode() or "{}")
                if isinstance(data, dict) and "ingest_ready" in data:
                    ingest = (
                        "  ingest=ready"
                        if data.get("ingest_ready")
                        else "  ingest=NOT READY (restart: tokensaver capture serve)"
                    )
            except Exception:
                pass
        print(
            f"capture: {'ok' if ok else 'down'}  "
            f"http://127.0.0.1:{port}/health{ingest}"
        )
        return 0 if ok else 1

    print(
        "Usage: tokensaver capture serve | status",
        file=sys.stderr,
    )
    return 2
