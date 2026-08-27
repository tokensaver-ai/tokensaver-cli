"""Status / statusline / console trace helpers."""

from __future__ import annotations

import json
import shutil
import sys
import urllib.error
import urllib.request
from typing import Any

from tokensaver_cli.config import RouteConfig, RouteConfigError, resolve_route_config
from tokensaver_cli.state import load_state


def _http_json(
    url: str,
    *,
    headers: dict[str, str],
    method: str = "GET",
    body: bytes | None = None,
    timeout: float = 10.0,
) -> tuple[int, Any]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data: Any = json.loads(raw) if raw.strip() else {}
            return resp.status, data
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            data = {"detail": raw[:200]}
        return exc.code, data


def fetch_recent_flow_id(cfg: RouteConfig) -> str | None:
    """Best-effort recent pipeline run id for a console deep link.

    Prefer ``GET /sdk/runs`` (API-key auth). ``/monitoring/pipelines`` needs a JWT.
    """
    sdk_url = f"{cfg.api_v1_base}/sdk/runs?limit=1"
    code, data = _http_json(sdk_url, headers={"Authorization": f"Bearer {cfg.api_key}"})
    if code == 200 and isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                for key in ("pipeline_run_id", "request_id", "id", "run_id"):
                    rid = first.get(key)
                    if isinstance(rid, str) and rid.strip():
                        return rid.strip()

    url = f"{cfg.api_v1_base}/monitoring/pipelines?days=7"
    code, data = _http_json(url, headers={"Authorization": f"Bearer {cfg.api_key}"})
    if code != 200 or not isinstance(data, dict):
        # Optional JWT from credentials for monitoring surface
        try:
            from tokensaver_cli.credentials import resolve_access_token

            token = resolve_access_token()
        except Exception:  # noqa: BLE001
            token = None
        if token:
            code, data = _http_json(url, headers={"Authorization": f"Bearer {token}"})
        if code != 200 or not isinstance(data, dict):
            return None
    for key in ("recent_run_ids", "recent_runs"):
        items = data.get(key)
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
            if isinstance(first, dict):
                rid = first.get("id") or first.get("run_id")
                if isinstance(rid, str) and rid.strip():
                    return rid.strip()
    pipelines = data.get("pipelines") or data.get("by_pipeline") or []
    if isinstance(pipelines, dict):
        pipelines = list(pipelines.values())
    if isinstance(pipelines, list):
        for entry in pipelines:
            if not isinstance(entry, dict):
                continue
            ids = entry.get("recent_run_ids") or []
            if isinstance(ids, list) and ids and isinstance(ids[0], str):
                return ids[0]
    return None


def format_status_line(cfg: RouteConfig | None = None) -> str:
    try:
        resolved = cfg or resolve_route_config()
    except RouteConfigError:
        return "TokenSaver · not configured"
    routes = load_state()
    claude = routes.get("claude")
    model = "—"
    profile = None
    if claude and isinstance(claude.meta, dict):
        model = str(claude.meta.get("model") or "—")
        profile = claude.meta.get("profile")
    mode = resolved.deploy_mode
    profile_bit = f" · {profile}" if profile else ""
    routed = "routed" if claude else "idle"
    return f"TokenSaver · {routed} · {model}{profile_bit} · {mode}"


def format_hook_message(cfg: RouteConfig | None = None) -> str:
    try:
        resolved = cfg or resolve_route_config()
    except RouteConfigError as exc:
        return f"TokenSaver: {exc}"
    routes = load_state()
    claude = routes.get("claude")
    model = (claude.meta.get("model") if claude else None) or "default"
    profile = claude.meta.get("profile") if claude else None
    profile_bit = f" (profile {profile})" if profile else ""
    flow = fetch_recent_flow_id(resolved)
    link = resolved.flows_url(flow_id=flow)
    return (
        f"Routed via TokenSaver · model {model}{profile_bit} · "
        f"mode {resolved.deploy_mode} · Flux IA: {link}"
    )


def format_welcome_banner(cfg: RouteConfig | None = None) -> str:
    """User-visible SessionStart banner (stderr). No network."""
    try:
        resolved = cfg or resolve_route_config()
    except RouteConfigError as exc:
        return (
            "TokenSaver — pas encore configuré\n"
            f"  {exc}\n"
            "  Terminal: tokensaver login && tokensaver route claude --launch"
        )

    routes = load_state()
    claude = routes.get("claude")
    model = (claude.meta.get("model") if claude and isinstance(claude.meta, dict) else None) or "—"
    plan = ""
    try:
        from tokensaver_cli.credentials import load_credentials, resolve_plan_slug

        plan = resolve_plan_slug() or (load_credentials().plan_slug if load_credentials() else None) or ""
    except Exception:  # noqa: BLE001
        pass
    plan_bit = f"  ·  plan {plan}" if plan else ""
    flows = resolved.flows_url()
    return (
        "────────────────────────────────────────\n"
        "  TokenSaver · Claude Code routé\n"
        f"  Modèle: {model}{plan_bit}\n"
        "  Chaque run IA apparaît en temps réel dans Flux IA (control plane).\n"
        f"  Console: {flows}\n"
        "  → Dites « salut » ou /tokensaver-router:welcome\n"
        "  → tokensaver flows --open  (navigateur, live)\n"
        "────────────────────────────────────────"
    )


def format_welcome_context_short(cfg: RouteConfig | None = None) -> str:
    """Short SessionStart context for Claude — no network calls."""
    try:
        resolved = cfg or resolve_route_config()
    except RouteConfigError as exc:
        return (
            "TokenSaver plugin: not configured. "
            f"Ask user to run tokensaver login && tokensaver route claude. ({exc})"
        )

    routes = load_state()
    claude = routes.get("claude")
    model = (claude.meta.get("model") if claude and isinstance(claude.meta, dict) else None) or "default"
    flows = resolved.flows_url()
    return (
        "TokenSaver session started. Claude Code is routed through the TokenSaver control plane. "
        f"Model: {model}. Flux IA (real-time runs): {flows}. "
        "On the user's FIRST message (even salut), reply immediately with a friendly welcome "
        "in their language using skill tokensaver-onboarding: explain TokenSaver, real-time Flux IA "
        "observability, and suggest /tokensaver-router:welcome, /tokensaver-router:flows, "
        "tokensaver flows --open. Do not ask for API keys (JWT auth). Keep the welcome concise."
    )


def format_welcome_context(cfg: RouteConfig | None = None) -> str:
    """SessionStart context alias — kept short (no network)."""
    return format_welcome_context_short(cfg)


def format_session_start_json(cfg: RouteConfig | None = None) -> str:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "reloadSkills": True,
            "additionalContext": format_welcome_context_short(cfg),
        }
    }
    return json.dumps(payload, ensure_ascii=False)


def _approve_current_quiet(*, timeout_sec: float = 4.0) -> None:
    """Best-effort model approve on session start — never block the hook."""
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeout

    from tokensaver_cli.approve_cmd import run_approve

    def _run() -> None:
        run_approve(current=True, quiet=True)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_run)
            fut.result(timeout=timeout_sec)
    except (FuturesTimeout, Exception):  # noqa: BLE001
        pass


def run_session_start_hook() -> int:
    """Claude Code SessionStart: visible banner (stderr) + short JSON context (stdout)."""
    try:
        cfg = resolve_route_config()
    except RouteConfigError:
        cfg = None
    print(format_welcome_banner(cfg), file=sys.stderr)
    _approve_current_quiet()
    print(format_session_start_json(cfg))
    return 0


def run_status(
    *,
    line: bool = False,
    hook: bool = False,
    welcome_json: bool = False,
    session_start: bool = False,
) -> int:
    if line:
        print(format_status_line())
        return 0
    if session_start or welcome_json:
        return run_session_start_hook()
    if hook:
        print(format_hook_message())
        return 0

    try:
        cfg = resolve_route_config()
    except RouteConfigError as exc:
        print(f"TokenSaver status — {exc}", file=sys.stderr)
        return 1

    routes = load_state()
    print("TokenSaver status")
    print(f"  Mode:     {cfg.deploy_mode}")
    print(f"  API:      {cfg.api_host}")
    print(f"  Console:  {cfg.console_url}")
    print(f"  Flux IA:  {cfg.flows_url()}")
    print()

    if not routes:
        print("  No active routes. Run: tokensaver route claude")
        return 0

    for target, rec in sorted(routes.items()):
        print(f"  Route · {target}")
        print(f"    since:   {rec.routed_at}")
        meta = rec.meta or {}
        if meta.get("scope"):
            print(f"    scope:   {meta['scope']}")
        if meta.get("model"):
            print(f"    model:   {meta['model']}")
        if meta.get("profile"):
            print(f"    profile: {meta['profile']}")
        if meta.get("with_fs"):
            print("    fs:      gateway filesystem enabled")
        if meta.get("plugin_dir"):
            print(f"    plugin:  {meta['plugin_dir']}")

    flow_id = fetch_recent_flow_id(cfg)
    print()
    if flow_id:
        print(f"  Latest flow: {cfg.flows_url(flow_id=flow_id)}")
    else:
        print(f"  Open Flux IA: {cfg.flows_url()}")

    if cfg.deploy_mode == "local":
        print()
        print("  Local checklist:")
        print(f"    - API      {cfg.api_host}  (./scripts/start-platform.sh)")
        print(f"    - MCP      {cfg.mcp_tools_url}")
        print(f"    - Gateway  {cfg.gateway_url}")
        print(f"    - Egress   HTTPS_PROXY={cfg.egress_proxy_url} (optional)")
        gw = shutil.which("tokensaver-mcp-gateway")
        print(f"    - gateway binary: {'OK · ' + gw if gw else 'MISSING · pip install -e apps/backend'}")

    return 0
