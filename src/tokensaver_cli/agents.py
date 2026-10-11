"""Route / unroute handlers per agent or integration mode."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tokensaver_cli.config import (
    LOCAL_EGRESS_PROXY,
    MCP_FS_KEY,
    MCP_GATEWAY_KEY,
    MCP_TOOLS_KEY,
    ClaudeScope,
    RouteConfig,
)
from tokensaver_cli.json_merge import deep_merge, read_json, write_json
from tokensaver_cli.credentials import resolve_plan_slug
from tokensaver_cli.plugin_install import install_claude_plugin
from tokensaver_cli.profiles import is_free_plan, resolve_model
from tokensaver_cli.route_frame import print_route_frame
from tokensaver_cli.state import (
    RoutedFile,
    backup_file,
    clear_route,
    load_state,
    record_route,
    restore_file,
    route_state_dir,
)
from tokensaver_cli.status import format_status_line


def _is_claude_native_model_id(model_id: str) -> bool:
    """True for Anthropic catalog IDs Claude Code recognizes natively."""
    lower = model_id.strip().lower()
    return lower.startswith("anthropic/") or lower.startswith("claude-")


def _claude_env_extras(model_id: str | None) -> dict[str, str]:
    """Extra Claude Code env when routing gateway / third-party model refs."""
    if not model_id or not model_id.strip():
        return {}
    if _is_claude_native_model_id(model_id):
        return {}
    # openrouter/…, openai/… via TokenSaver — avoids yellow "unrecognized model" banner.
    return {"CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT": "1"}


def _ensure_claude_model_approved(
    cfg: RouteConfig,
    model_id: str,
    *,
    launching: bool,
    allow_pick: bool = True,
) -> str | None:
    """Zero-trust Agent Registry gate before Claude route/launch.

    Returns the approved model id to use, or ``None`` to abort when launching
    (or keep going with a warning when not launching).

    ``allow_pick=False`` (e.g. ``tokensaver use <id>`` / ``--model``) approves
    the given ref directly — no interactive catalog dump.
    """
    from tokensaver_cli.approve_cmd import ensure_model_approved

    chosen = ensure_model_approved(
        model_id,
        force_local=cfg.deploy_mode == "local",
        allow_pick=allow_pick,
    )
    if chosen:
        return chosen
    if launching:
        print(
            "Launch cancelled — approve a model to continue (zero-trust).",
            file=sys.stderr,
        )
        return None
    print(
        f"WARN  route applied but {model_id} is not approved yet. "
        f"Run: tokensaver approve {model_id}",
        file=sys.stderr,
    )
    return model_id


def _begin_route_files(target: str, paths: list[Path]) -> list[RoutedFile]:
    """Backup config files once per target; preserve originals on re-route."""
    existing = load_state().get(target)
    if existing and existing.files:
        # Re-use backups but allow new paths to be added (e.g. scope change).
        known = {f.path: f for f in existing.files}
        routed: list[RoutedFile] = []
        for path in paths:
            key = str(path)
            if key in known:
                routed.append(known[key])
            else:
                backup = backup_file(path) if path.is_file() else None
                routed.append(RoutedFile(path=key, backup=backup or ""))
        return routed
    routed = []
    for path in paths:
        backup = backup_file(path) if path.is_file() else None
        routed.append(RoutedFile(path=str(path), backup=backup or ""))
    return routed


def _mcp_tools_entry(cfg: RouteConfig) -> dict[str, Any]:
    return {
        "type": "http",
        "url": cfg.mcp_tools_url,
        "headers": {"Authorization": f"Bearer {cfg.api_key}"},
    }


def _mcp_gateway_entry(cfg: RouteConfig, client: str) -> dict[str, Any]:
    headers: dict[str, str] = {
        "Authorization": f"Bearer {cfg.api_key}",
        "X-Tokensaver-Client": client,
    }
    if cfg.organisation_id:
        headers["X-Organisation-ID"] = cfg.organisation_id
    if cfg.workspace_id:
        headers["X-Workspace-ID"] = cfg.workspace_id
    return {
        "type": "http",
        "url": cfg.gateway_url,
        "headers": headers,
    }


def _mcp_fs_entry(cfg: RouteConfig, project_root: Path) -> dict[str, Any] | None:
    """Stdio MCP: Trust Gateway wrapping filesystem for the project cwd."""
    gateway_bin = shutil.which("tokensaver-mcp-gateway")
    npx_bin = shutil.which("npx")
    if not gateway_bin:
        return None
    if not npx_bin:
        return None
    root = str(project_root.resolve())
    env: dict[str, str] = {
        "TOKENSAVER_API_KEY": cfg.api_key,
        "TOKENSAVER_API_BASE_URL": cfg.api_v1_base,
    }
    if cfg.organisation_id:
        env["X-Organisation-ID"] = cfg.organisation_id
    if cfg.workspace_id:
        env["X-Workspace-ID"] = cfg.workspace_id
    target = f"npx -y @modelcontextprotocol/server-filesystem {root}"
    return {
        "command": gateway_bin,
        "args": [
            "--target",
            target,
            "--workspace",
            cfg.workspace_id or "route-cli",
        ],
        "env": env,
    }


def _claude_settings_path(scope: ClaudeScope) -> Path:
    if scope == "user":
        return Path.home() / ".claude" / "settings.json"
    if scope == "local":
        return Path.cwd() / ".claude" / "settings.local.json"
    return Path.cwd() / ".claude" / "settings.json"


def _claude_mcp_path(_scope: ClaudeScope) -> Path:
    # Claude Code loads project ``.mcp.json`` reliably; keep MCP wiring there for
    # every settings scope (user / project / local).
    return Path.cwd() / ".mcp.json"


def _strip_tokensaver_mcp(data: dict[str, Any]) -> dict[str, Any]:
    servers = dict(data.get("mcpServers") or {})
    for key in (MCP_TOOLS_KEY, MCP_GATEWAY_KEY, MCP_FS_KEY):
        servers.pop(key, None)
    out = dict(data)
    if servers:
        out["mcpServers"] = servers
    else:
        out.pop("mcpServers", None)
    return out


# Proxy / capture keys left by egress or older CLI — must not survive unroute.
_STALE_PROXY_ENV_KEYS = (
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "https_proxy",
    "http_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NODE_EXTRA_CA_CERTS",
    "NO_PROXY",
    "no_proxy",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "CLAUDE_CODE_ENABLE_TELEMETRY",
    "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA",
    "TOKENSAVER_CLAUDE_HOOKS_URL",
    "TOKENSAVER_CAPTURE_PORT",
)


def _strip_tokensaver_env(settings: dict[str, Any]) -> dict[str, Any]:
    env = dict(settings.get("env") or {})
    for key in (
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "TOKENSAVER_API_KEY",
        "TOKENSAVER_CONSOLE_URL",
        "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT",
        *_STALE_PROXY_ENV_KEYS,
    ):
        if key == "ANTHROPIC_API_KEY" and env.get(key) not in ("", None):
            # Keep a non-empty user key if present; we only clear our empty override.
            continue
        if key in env:
            env.pop(key, None)
    out = dict(settings)
    # Remove TokenSaver statusLine / hooks we injected
    status = out.get("statusLine")
    if isinstance(status, dict) and "tokensaver status" in str(status.get("command", "")):
        out.pop("statusLine", None)
    hooks = out.get("hooks")
    if isinstance(hooks, dict):
        cleaned = _strip_tokensaver_hooks(hooks)
        if cleaned:
            out["hooks"] = cleaned
        else:
            out.pop("hooks", None)
    if env:
        out["env"] = env
    else:
        out.pop("env", None)
    return out


def _strip_tokensaver_hooks(hooks: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for event, matchers in hooks.items():
        if not isinstance(matchers, list):
            out[event] = matchers
            continue
        kept = []
        for matcher in matchers:
            if not isinstance(matcher, dict):
                kept.append(matcher)
                continue
            inner = matcher.get("hooks")
            if not isinstance(inner, list):
                kept.append(matcher)
                continue
            filtered = [
                h
                for h in inner
                if not (
                    isinstance(h, dict)
                    and (
                        "tokensaver status" in str(h.get("command", ""))
                        or "forward-capture.sh" in str(h.get("command", ""))
                    )
                )
            ]
            if filtered:
                kept.append({**matcher, "hooks": filtered})
        if kept:
            out[event] = kept
    return out


_CAPTURE_HOOK_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "Stop",
    "SessionEnd",
)


def _forward_capture_script() -> Path | None:
    """Absolute path to forward-capture.sh (skills install or package bundle)."""
    from tokensaver_cli.plugin_install import plugin_install_dir

    candidates = (
        plugin_install_dir() / "hooks" / "forward-capture.sh",
        Path(__file__).resolve().parent / "claude_plugin" / "hooks" / "forward-capture.sh",
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def _tokensaver_hooks_patch() -> dict[str, Any]:
    """Claude settings hooks: welcome banner + agentic capture forward.

    Capture hooks are written into ``settings.json`` (absolute script path) so the
    causal graph works even when Claude Code does not load plugin ``hooks.json``
    from the skills install dir (``CLAUDE_PLUGIN_ROOT`` unset).
    """
    # Do not spawn ``tokensaver`` on every UserPromptSubmit — only SessionStart banner.
    session_start: list[dict[str, Any]] = [
        {
            "type": "command",
            "command": "tokensaver status --session-start",
        },
    ]
    script = _forward_capture_script()
    if script is None:
        return {"SessionStart": [{"hooks": session_start}]}

    script_s = str(script)
    out: dict[str, Any] = {}
    for event in _CAPTURE_HOOK_EVENTS:
        hooks: list[dict[str, Any]] = []
        if event == "SessionStart":
            hooks.extend(session_start)
        hooks.append(
            {
                "type": "command",
                "command": f'bash "{script_s}" {event}',
                "timeout": 5,
            }
        )
        out[event] = [{"hooks": hooks}]
    return out


def _status_line_path() -> Path:
    return route_state_dir() / "statusline.txt"


def write_status_line_cache(text: str) -> Path:
    path = _status_line_path()
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return path


def _status_line_patch() -> dict[str, Any]:
    # `cat` is ~instant vs cold-starting Python for every statusLine refresh.
    path = _status_line_path()
    return {
        "type": "command",
        "command": f'cat "{path}" 2>/dev/null || echo "TokenSaver"',
    }


def _restore_routed_files(files: list[RoutedFile], *, strip_if_no_backup: bool = True) -> None:
    for item in files:
        path = Path(item.path)
        if item.backup:
            restore_file(path, item.backup)
            continue
        if not strip_if_no_backup:
            path.unlink(missing_ok=True)
            continue
        # No original backup: surgically remove TokenSaver keys when possible.
        if not path.is_file():
            continue
        name = path.name
        data = read_json(path)
        if name in {"mcp.json", ".mcp.json"} or path.suffix == ".json" and "mcp" in name:
            cleaned = _strip_tokensaver_mcp(data)
            if cleaned:
                write_json(path, cleaned)
            else:
                path.unlink(missing_ok=True)
        elif "settings" in name:
            cleaned = _strip_tokensaver_env(data)
            if cleaned:
                write_json(path, cleaned)
            else:
                path.unlink(missing_ok=True)
        else:
            path.unlink(missing_ok=True)


def _sticky_claude_model() -> str | None:
    """Last model chosen via ``--model`` / ``--profile`` (survives bare ``route --launch``)."""
    rec = load_state().get("claude")
    if not rec or not isinstance(rec.meta, dict):
        return None
    for key in ("sticky_model", "model"):
        value = rec.meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def route_claude(
    cfg: RouteConfig,
    *,
    launch: bool,
    extra_args: list[str],
    scope: ClaudeScope = "user",
    model: str | None = None,
    profile: str | None = None,
    with_fs: bool = False,
    install_plugin: bool = True,
) -> int:
    plan_slug = resolve_plan_slug()
    explicit_model = bool(model and model.strip())
    explicit_profile = bool(profile and profile.strip())
    sticky = None if (explicit_model or explicit_profile) else _sticky_claude_model()
    try:
        model_id, profile_name = resolve_model(
            model=model,
            profile=profile,
            plan_slug=plan_slug,
            sticky_model=sticky,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if sticky and model_id == sticky and not explicit_model and not explicit_profile:
        print(
            f"Keeping previous model {model_id} (set with --model / --profile to change)",
            file=sys.stderr,
        )
    elif is_free_plan(plan_slug) and not explicit_model and not sticky:
        print(
            f"Free plan → default model {model_id} (override with --model / --profile)",
            file=sys.stderr,
        )

    settings_path = _claude_settings_path(scope)
    mcp_path = _claude_mcp_path(scope)
    routed = _begin_route_files("claude", [settings_path, mcp_path])

    env_patch: dict[str, str] = {
        "ANTHROPIC_BASE_URL": cfg.anthropic_base_url,
        "ANTHROPIC_AUTH_TOKEN": cfg.api_key,
        "ANTHROPIC_API_KEY": "",
        "TOKENSAVER_API_KEY": cfg.api_key,
        "TOKENSAVER_CONSOLE_URL": cfg.console_url,
    }
    # Do NOT inject HTTPS_PROXY into Claude settings. Local egress (:8888) is
    # optional; when it is down Claude Code gets Connection refused on every
    # request. Agentic graph capture is CLI-owned (hooks/OTEL → :8790).
    from tokensaver_cli.agentic_capture import (
        capture_client_environ,
        capture_port,
        ensure_capture_running,
    )

    env_patch.update(capture_client_environ())
    cap_port = capture_port()
    if not ensure_capture_running(api_host=cfg.api_host, api_key=cfg.api_key):
        print(
            f"WARN  agentic capture not reachable on "
            f"http://127.0.0.1:{cap_port} — run: tokensaver capture serve",
            file=sys.stderr,
        )
    else:
        print(
            f"Agentic capture → http://127.0.0.1:{cap_port} "
            "(hooks/OTEL → causal graph)",
            file=sys.stderr,
        )
    if model_id:
        original_model = model_id
        chosen = _ensure_claude_model_approved(
            cfg,
            model_id,
            launching=launch or bool(extra_args),
            # Explicit use/--model/--profile: approve that id, no catalog dump.
            allow_pick=not (explicit_model or explicit_profile),
        )
        if chosen is None:
            return 1
        if chosen != model_id:
            model_id = chosen
            try:
                _, profile_name = resolve_model(
                    model=model_id,
                    profile=None,
                    plan_slug=plan_slug,
                    sticky_model=None,
                )
            except ValueError:
                profile_name = None
        env_patch["ANTHROPIC_MODEL"] = model_id
        env_patch.update(_claude_env_extras(model_id))
    else:
        original_model = None

    # Install plugin before writing settings so forward-capture.sh path resolves.
    plugin_dir = None
    if install_plugin:
        plugin_dir = install_claude_plugin(force=True)
        if plugin_dir is None:
            print(
                "WARN  Claude plugin bundle missing — slash commands /tokensaver:* unavailable.",
                file=sys.stderr,
            )

    settings = read_json(settings_path)
    # Drop leftover egress proxy — Claude talks to ANTHROPIC_BASE_URL directly;
    # a dead :8888 HTTPS_PROXY yields Connection refused in Claude Code.
    existing_env = dict(settings.get("env") or {})
    existing_env.pop("HTTPS_PROXY", None)
    existing_env.pop("HTTP_PROXY", None)
    settings["env"] = existing_env
    settings = deep_merge(
        settings,
        {
            "env": env_patch,
            "statusLine": _status_line_patch(),
            "hooks": _tokensaver_hooks_patch(),
        },
    )
    write_json(settings_path, settings)
    write_status_line_cache(format_status_line(cfg))

    data = read_json(mcp_path)
    servers: dict[str, Any] = {
        MCP_TOOLS_KEY: _mcp_tools_entry(cfg),
        MCP_GATEWAY_KEY: _mcp_gateway_entry(cfg, "claude-code/1.0"),
    }
    fs_ok = False
    if with_fs:
        fs_entry = _mcp_fs_entry(cfg, Path.cwd())
        if fs_entry is None:
            print(
                "WARN  --with-fs skipped: need `tokensaver-mcp-gateway` and `npx` on PATH.",
                file=sys.stderr,
            )
        else:
            servers[MCP_FS_KEY] = fs_entry
            fs_ok = True
    else:
        # Re-route without --with-fs: drop previous FS server.
        existing_servers = dict(data.get("mcpServers") or {})
        existing_servers.pop(MCP_FS_KEY, None)
        data = {**data, "mcpServers": existing_servers} if existing_servers else {
            k: v for k, v in data.items() if k != "mcpServers"
        }

    write_json(mcp_path, deep_merge(data, {"mcpServers": servers}))

    prev_sticky = _sticky_claude_model()
    picked_new = bool(model_id and original_model and model_id != original_model)
    sticky_model = (
        model_id
        if (explicit_model or explicit_profile or picked_new)
        else (prev_sticky or model_id)
    )
    meta = {
        "scope": scope,
        "model": model_id,
        "sticky_model": sticky_model,
        "profile": profile_name,
        "with_fs": fs_ok,
        "console_url": cfg.console_url,
        "flows_url": cfg.flows_url(),
        "plugin_dir": str(plugin_dir) if plugin_dir else None,
        "deploy_mode": cfg.deploy_mode,
        "plan_slug": plan_slug,
    }
    record_route("claude", routed, meta=meta)

    extra_lines = [
        f"Scope · {scope} → {settings_path}",
        f"Client tag · claude-code/1.0",
    ]
    if model_id:
        label = f"Model · {model_id}"
        if profile_name:
            label += f" (profile {profile_name})"
        extra_lines.append(label)
    if fs_ok:
        extra_lines.append(f"FS gateway · {Path.cwd()}")
    if plugin_dir:
        extra_lines.append(f"Plugin · {plugin_dir}  (/tokensaver:setup)")
    extra_lines.append(f"Flux IA · {cfg.flows_url()}")
    if cfg.organisation_id:
        extra_lines.append(f"Org scope · {cfg.organisation_id}")
    if cfg.deploy_mode == "local":
        extra_lines.append("Local · ensure API :8000, MCP :8787, gateway :8788 are up")

    print_route_frame(
        target_label="Claude Code",
        cfg=cfg,
        launching=launch or bool(extra_args),
        extra_lines=extra_lines,
    )

    if launch or extra_args:
        env = os.environ.copy()
        env.update(env_patch)
        agent_args = list(extra_args)
        # Prefer explicit model for Claude Code CLI when not already passed.
        if model_id and "--model" not in agent_args:
            agent_args = ["--model", model_id, *agent_args]
        return subprocess.call(["claude", *agent_args], env=env)
    return 0


def _egress_listen_port() -> int:
    raw = (os.environ.get("TOKENSAVER_EGRESS_PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    host = urlparse(LOCAL_EGRESS_PROXY)
    if host.port:
        return int(host.port)
    return 8888


def _kill_tcp_listeners(port: int) -> list[int]:
    """Best-effort SIGTERM of PIDs listening on ``port`` (macOS/Linux)."""
    try:
        out = subprocess.check_output(
            ["lsof", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    killed: list[int] = []
    for line in out.splitlines():
        pid_s = line.strip()
        if not pid_s.isdigit():
            continue
        pid = int(pid_s)
        try:
            os.kill(pid, 15)
            killed.append(pid)
        except OSError:
            pass
    return killed


def _looks_like_classic_egress(key: str, value: str) -> bool:
    """True for old egress/cli capture leftovers — not the VS Code sidecar (:18888/:18790)."""
    v = (value or "").lower()
    k = key.upper()
    if "tokensaver-egress" in v:
        return True
    if any(p in v for p in (":8888", "127.0.0.1:8888", "localhost:8888")):
        return True
    if any(p in v for p in (":8789", "127.0.0.1:8789", "localhost:8789")):
        return True
    # CLI default capture :8790 (extension uses :18790).
    if k in {
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "TOKENSAVER_CLAUDE_HOOKS_URL",
        "TOKENSAVER_CAPTURE_PORT",
    } and any(p in v for p in (":8790", "127.0.0.1:8790", "localhost:8790")):
        return True
    return False


def _should_drop_proxy_key(key: str, value: str, *, aggressive: bool) -> bool:
    if key not in _STALE_PROXY_ENV_KEYS:
        return False
    if aggressive:
        return True
    return _looks_like_classic_egress(key, str(value or ""))


def _strip_stale_proxy_from_settings(path: Path, *, aggressive: bool) -> bool:
    """Remove egress/proxy env keys from a Claude settings.json. Returns True if changed."""
    if not path.is_file():
        return False
    try:
        data = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    env = data.get("env")
    if not isinstance(env, dict):
        return False
    changed = False
    for key in list(env.keys()):
        if _should_drop_proxy_key(str(key), str(env.get(key) or ""), aggressive=aggressive):
            env.pop(key, None)
            changed = True
    if not changed:
        return False
    if env:
        data["env"] = env
    else:
        data.pop("env", None)
    write_json(path, data)
    return True


def _strip_stale_proxy_from_vscode_settings(path: Path, *, aggressive: bool) -> bool:
    """Strip managed proxy keys from VS Code/Cursor ``claudeCode.environmentVariables``."""
    if not path.is_file():
        return False
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    # settings.json is often JSONC; strip // and /* */ comments best-effort.
    cleaned = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    cleaned = re.sub(r"//.*?$", "", cleaned, flags=re.M)
    try:
        data = json.loads(cleaned)
    except ValueError:
        return False
    key = "claudeCode.environmentVariables"
    existing = data.get(key)
    if not isinstance(existing, list):
        return False
    kept: list[Any] = []
    changed = False
    for item in existing:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
            value = str(item.get("value") or "")
            if _should_drop_proxy_key(name, value, aggressive=aggressive):
                changed = True
                continue
        kept.append(item)
    if not changed:
        return False
    if kept:
        data[key] = kept
    else:
        data.pop(key, None)
    try:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return False
    return True


def _stop_local_egress_best_effort() -> list[str]:
    """Stop classic egress (:8888) + hint capture; never touch vscode-sidecar :18888."""
    notes: list[str] = []
    # Prefer official stop / unproxy when installed.
    for cmd in (
        ["tokensaver-egress", "stop"],
        ["tokensaver-egress", "unproxy", "--ide"],
    ):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if proc.returncode == 0:
                notes.append(f"ran `{' '.join(cmd)}`")
            elif proc.stderr.strip():
                notes.append(
                    f"`{' '.join(cmd)}` exit {proc.returncode} "
                    f"({proc.stderr.strip().splitlines()[0][:120]})"
                )
        except FileNotFoundError:
            continue
        except (OSError, subprocess.TimeoutExpired) as exc:
            notes.append(f"`{' '.join(cmd)}` failed: {exc}")

    egress_port = _egress_listen_port()
    # Never kill the VS Code extension sidecar default ports.
    if egress_port not in {18790, 18888}:
        pids = _kill_tcp_listeners(egress_port)
        if pids:
            notes.append(
                f"stopped listeners on :{egress_port} (pids {', '.join(map(str, pids))})"
            )

    try:
        from tokensaver_cli.agentic_capture.envelope import capture_port

        cap = capture_port()
        if cap not in {18790, 18888}:
            pids = _kill_tcp_listeners(cap)
            if pids:
                notes.append(
                    f"stopped capture on :{cap} (pids {', '.join(map(str, pids))})"
                )
    except Exception:
        pass

    # Legacy capture port sometimes used by older installs.
    for legacy in (8789,):
        pids = _kill_tcp_listeners(legacy)
        if pids:
            notes.append(
                f"stopped legacy capture on :{legacy} (pids {', '.join(map(str, pids))})"
            )
    return notes


def _cleanup_claude_proxy_leftovers(*, aggressive: bool) -> list[str]:
    """Clear stale proxy env after unroute (backups may still contain :8888).

    ``aggressive=True`` (after a real route restore) removes all managed proxy keys.
    ``aggressive=False`` only removes classic egress fingerprints so the VS Code
    sidecar (:18888 / :18790) Keep my Claude env is preserved.
    """
    notes: list[str] = []
    scrubbed = False
    for path in (
        Path.home() / ".claude" / "settings.json",
        Path.cwd() / ".claude" / "settings.json",
    ):
        if _strip_stale_proxy_from_settings(path, aggressive=aggressive):
            notes.append(f"cleared proxy env in {path}")
            scrubbed = True

    for path in (
        Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json",
        Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "settings.json",
    ):
        if _strip_stale_proxy_from_vscode_settings(path, aggressive=aggressive):
            notes.append(f"cleared claudeCode.environmentVariables proxy keys in {path}")
            scrubbed = True

    # Only stop egress processes when we actually scrubbed classic leftovers or
    # finished a real unroute (avoid touching a healthy Keep my Claude session).
    if aggressive or scrubbed:
        notes.extend(_stop_local_egress_best_effort())
    return notes


def unroute_claude() -> int:
    rec = clear_route("claude")
    if rec:
        _restore_routed_files(rec.files)
        # Also strip MCP FS keys from cwd .mcp.json if present outside recorded files.
        for extra in (
            Path.cwd() / ".mcp.json",
            Path.home() / ".claude" / "mcp.json",
        ):
            if not extra.is_file():
                continue
            if any(Path(f.path) == extra for f in rec.files):
                continue
            cleaned = _strip_tokensaver_mcp(read_json(extra))
            if cleaned.get("mcpServers"):
                write_json(extra, cleaned)
            elif cleaned:
                write_json(extra, cleaned)
            else:
                extra.unlink(missing_ok=True)
        print("Claude Code unrouted — original config restored.")
        print(
            f"  Flux IA remains at: "
            f"{(rec.meta or {}).get('flows_url') or 'https://platform.tokensaver.fr/fr/<workspace>/dashboard?tab=flows'}"
        )
    else:
        print(
            "Claude Code is not routed through TokenSaver — "
            "cleaning leftover proxy / egress anyway.",
            file=sys.stderr,
        )

    # Always scrub proxy leftovers: restore may reintroduce a dead :8888 HTTPS_PROXY.
    cleanup_notes = _cleanup_claude_proxy_leftovers(aggressive=bool(rec))
    if cleanup_notes:
        print("Cleanup:")
        for note in cleanup_notes:
            print(f"  · {note}")
    elif not rec:
        print("Nothing to clean (no route record, no stale proxy).", file=sys.stderr)
        return 1

    print("  Tip: reload Claude Code / the IDE window so env changes apply.")
    return 0


def route_cursor(cfg: RouteConfig) -> int:
    mcp_path = Path.cwd() / ".cursor" / "mcp.json"
    routed = _begin_route_files("cursor", [mcp_path])

    data = read_json(mcp_path)
    patch = {
        "mcpServers": {
            MCP_TOOLS_KEY: _mcp_tools_entry(cfg),
            MCP_GATEWAY_KEY: _mcp_gateway_entry(cfg, "cursor/1.0"),
        }
    }
    mcp_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(mcp_path, deep_merge(data, patch))
    record_route(
        "cursor",
        routed,
        meta={"flows_url": cfg.flows_url(), "deploy_mode": cfg.deploy_mode},
    )

    print_route_frame(
        target_label="Cursor",
        cfg=cfg,
        extra_lines=[
            "Manual · Settings → Models → Override OpenAI Base URL",
            "Model id · openai/gpt-4o or anthropic/claude-sonnet-4-6",
            f"Flux IA · {cfg.flows_url()}",
            "Loops · tokensaver loop start + eval \"$(tokensaver loop env)\"",
            "Console · Espace développeur / Developer workspace",
        ],
    )
    return 0


def unroute_cursor() -> int:
    rec = clear_route("cursor")
    if not rec:
        print("Cursor is not routed through TokenSaver.", file=sys.stderr)
        return 1
    _restore_routed_files(rec.files)
    print("Cursor unrouted — .cursor/mcp.json restored.")
    print("Remove Override OpenAI Base URL in Cursor Settings if you set it manually.")
    return 0


def route_codex(cfg: RouteConfig, *, launch: bool, extra_args: list[str]) -> int:
    env_patch = {
        "OPENAI_BASE_URL": cfg.openai_base_url,
        "OPENAI_API_KEY": cfg.api_key,
        "TOKENSAVER_API_KEY": cfg.api_key,
    }
    routed = [RoutedFile(path="__env__", backup="")]
    record_route(
        "codex",
        routed,
        meta={"flows_url": cfg.flows_url(), "deploy_mode": cfg.deploy_mode},
    )
    print_route_frame(
        target_label="OpenAI Codex",
        cfg=cfg,
        launching=launch or bool(extra_args),
        extra_lines=[
            "Export OPENAI_BASE_URL + OPENAI_API_KEY in shell (or --launch)",
            f"Flux IA · {cfg.flows_url()}",
            "Loops · tokensaver loop start; export TOKENSAVER_LOOP_* for egress",
            "Optional header · X-Tokensaver-Client: codex/1.0",
        ],
    )

    if launch or extra_args:
        env = os.environ.copy()
        env.update(env_patch)
        return subprocess.call(["codex", *extra_args], env=env)
    return 0


def unroute_codex() -> int:
    rec = clear_route("codex")
    if not rec:
        print("Codex is not routed through TokenSaver.", file=sys.stderr)
        return 1
    print("Codex unrouted.")
    print("Unset OPENAI_BASE_URL and OPENAI_API_KEY if you exported them in your shell profile.")
    return 0


def route_proxy(cfg: RouteConfig) -> int:
    record_route("proxy", [], meta={"flows_url": cfg.flows_url(), "deploy_mode": cfg.deploy_mode})
    extra = [
        "Use base URLs above in any OpenAI-compatible SDK",
        f"Flux IA · {cfg.flows_url()}",
    ]
    if cfg.deploy_mode == "local":
        extra.append(f"Capture all HTTPS · export HTTPS_PROXY={cfg.egress_proxy_url}")
    print_route_frame(target_label="API proxy", cfg=cfg, extra_lines=extra)
    return 0


def unroute_proxy() -> int:
    if not clear_route("proxy"):
        print("Proxy route state was not set.", file=sys.stderr)
        return 1
    print("Proxy route cleared. Unset HTTPS_PROXY if you configured egress capture.")
    return 0


def route_mcp(cfg: RouteConfig, *, target: str | None) -> int:
    if not target:
        print_route_frame(
            target_label="MCP gateway",
            cfg=cfg,
            extra_lines=[
                "SaaS gateway URL injected by route claude/cursor",
                "Local stdio · tokensaver-mcp-gateway --target CMD",
                "Claude FS · tokensaver route claude --with-fs",
                f"Flux IA · {cfg.flows_url()}",
            ],
        )
        return 0

    cmd = [
        "tokensaver-mcp-gateway",
        "--target",
        target,
        "--workspace",
        cfg.workspace_id or "route-cli",
    ]
    env = os.environ.copy()
    env.setdefault("TOKENSAVER_API_KEY", cfg.api_key)
    env.setdefault("TOKENSAVER_API_BASE_URL", cfg.api_v1_base)
    record_route("mcp", [], meta={"flows_url": cfg.flows_url(), "deploy_mode": cfg.deploy_mode})
    print_route_frame(
        target_label="MCP gateway",
        cfg=cfg,
        extra_lines=[f"Starting · {' '.join(cmd)}"],
    )
    return subprocess.call(cmd, env=env)


def unroute_mcp() -> int:
    if not clear_route("mcp"):
        print("MCP route state was not set.", file=sys.stderr)
        return 1
    print("MCP route cleared. Stop any running tokensaver-mcp-gateway process manually.")
    return 0
