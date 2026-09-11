"""Health checks for routed integrations."""

from __future__ import annotations

import json
import shutil
import sys
import urllib.error
import urllib.request
from typing import Any

from tokensaver_cli.config import RouteConfig, RouteConfigError, resolve_route_config
from tokensaver_cli.plugin_install import plugin_install_dir
from tokensaver_cli.state import load_state
from tokensaver_cli.status import fetch_recent_flow_id


def _probe(url: str, headers: dict[str, str] | None = None) -> tuple[bool, str]:
    req = urllib.request.Request(url, method="GET", headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 405):
            return True, f"HTTP {exc.code} (reachable)"
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 — doctor surfaces any transport error
        return False, str(exc)


def _probe_mcp(url: str, api_key: str) -> tuple[bool, str]:
    """Streamable HTTP MCP: bare GET /mcp → 400 (no session). Probe via initialize POST."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "tokensaver-doctor", "version": "1"},
        },
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"HTTP {resp.status} (initialize)"
    except urllib.error.HTTPError as exc:
        raw = ""
        try:
            raw = exc.read().decode("utf-8", errors="replace")[:240]
        except Exception:  # noqa: BLE001
            raw = ""
        # Auth required / wrong key / session rules still mean the process is up.
        if exc.code in (400, 401, 403, 406, 415, 422):
            hint = "reachable"
            low = raw.lower()
            if "unauthorized" in low or "bearer" in low or "oauth" in low:
                hint = "reachable · auth"
            elif "session" in low:
                hint = "reachable · session"
            return True, f"HTTP {exc.code} ({hint})"
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> tuple[bool, str]:
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **headers}
    req = urllib.request.Request(url, data=body, method="POST", headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        # 400/401/422 still prove the Anthropic surface is up and parsing.
        if exc.code in (400, 401, 403, 422):
            detail = ""
            try:
                raw = exc.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw) if raw.strip() else {}
                err = parsed.get("error") if isinstance(parsed, dict) else None
                if isinstance(err, dict) and err.get("type"):
                    detail = f" · {err.get('type')}"
                elif isinstance(parsed, dict) and parsed.get("detail"):
                    detail = f" · {parsed.get('detail')}"
            except Exception:  # noqa: BLE001
                detail = ""
            return True, f"HTTP {exc.code} (reachable{detail})"
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _claude_probes(cfg: RouteConfig) -> list[tuple[str, bool, str]]:
    auth = {"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01"}
    checks: list[tuple[str, bool, str]] = []

    models_ok, models_detail = _probe(f"{cfg.anthropic_base_url}/v1/models", auth)
    checks.append(("Claude /v1/models", models_ok, models_detail))

    count_ok, count_detail = _post_json(
        f"{cfg.anthropic_base_url}/v1/messages/count_tokens",
        {
            "model": "anthropic/claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "ping"}],
        },
        auth,
    )
    checks.append(("Claude count_tokens", count_ok, count_detail))

    msg_ok, msg_detail = _post_json(
        f"{cfg.anthropic_base_url}/v1/messages",
        {
            "model": "anthropic/claude-sonnet-4-6",
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Reply with OK"}],
        },
        auth,
    )
    checks.append(("Claude /v1/messages", msg_ok, msg_detail))

    claude_bin = shutil.which("claude")
    checks.append(
        (
            "claude binary",
            bool(claude_bin),
            claude_bin or "not found on PATH",
        )
    )

    routes = load_state()
    claude_route = routes.get("claude")
    if claude_route:
        scope = (claude_route.meta or {}).get("scope", "?")
        model = (claude_route.meta or {}).get("model", "—")
        checks.append(("Claude route", True, f"active · scope={scope} · model={model}"))
    else:
        checks.append(("Claude route", False, "not routed — tokensaver route claude"))

    plugin = plugin_install_dir()
    checks.append(
        (
            "Claude plugin",
            plugin.is_dir() and (plugin / ".claude-plugin" / "plugin.json").is_file(),
            str(plugin) if plugin.is_dir() else "not installed",
        )
    )

    flow_id = fetch_recent_flow_id(cfg)
    checks.append(
        (
            "Flux IA link",
            True,
            cfg.flows_url(flow_id=flow_id),
        )
    )
    return checks


def _local_probes(cfg: RouteConfig) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    api_ok, api_detail = _probe(
        f"{cfg.api_host}/health",
        {"Authorization": f"Bearer {cfg.api_key}"},
    )
    checks.append(("Local API", api_ok or "HTTP 404" in api_detail, api_detail))
    checks.append(("Local MCP tools", *_probe_mcp(cfg.mcp_tools_url, cfg.api_key)))
    checks.append(("Local gateway", *_probe_mcp(cfg.gateway_url, cfg.api_key)))
    gw = shutil.which("tokensaver-mcp-gateway")
    checks.append(
        (
            "mcp-gateway bin",
            bool(gw),
            gw or "MISSING — pip install -e apps/backend",
        )
    )
    return checks


def run_doctor(*, claude: bool = False, force_local: bool = False) -> int:
    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(f"FAIL  config — {exc}", file=sys.stderr)
        return 1

    ok = True
    print("TokenSaver route doctor")
    print(f"  Mode: {cfg.deploy_mode} ({'self-host' if cfg.deploy_mode == 'local' else 'api.tokensaver.fr'})")
    print(f"  Console: {cfg.console_url}")
    print()

    checks: list[tuple[str, bool, str]] = [
        ("API key", True, f"{cfg.api_key[:8]}… ({len(cfg.api_key)} chars)"),
        ("OpenAI-compat", *_probe(f"{cfg.openai_base_url}/models", {"Authorization": f"Bearer {cfg.api_key}"})),
        ("Anthropic-compat", *_probe(f"{cfg.anthropic_base_url}/v1/models", {"x-api-key": cfg.api_key})),
        ("MCP tools", *_probe_mcp(cfg.mcp_tools_url, cfg.api_key)),
        ("MCP gateway", *_probe_mcp(cfg.gateway_url, cfg.api_key)),
    ]

    if cfg.deploy_mode == "local":
        checks.extend(_local_probes(cfg))

    if claude:
        checks.extend(_claude_probes(cfg))

    for name, passed, detail in checks:
        status = "OK" if passed else "FAIL"
        print(f"  {status:4}  {name:18}  {detail}")
        if not passed:
            ok = False

    routes = load_state()
    if routes:
        print()
        print("  Active routes:")
        for target, rec in sorted(routes.items()):
            meta_bits = []
            if rec.meta.get("scope"):
                meta_bits.append(f"scope={rec.meta['scope']}")
            if rec.meta.get("model"):
                meta_bits.append(f"model={rec.meta['model']}")
            suffix = f" ({', '.join(meta_bits)})" if meta_bits else ""
            print(f"    - {target} since {rec.routed_at}{suffix}")
    else:
        print()
        print("  No active routes. Run: tokensaver route claude")

    print()
    print(f"  Flux IA: {cfg.flows_url()}")
    if not claude:
        print("  Tip: tokensaver doctor --claude  for Claude Code end-to-end probes")

    return 0 if ok else 1
