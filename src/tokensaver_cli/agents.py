"""Route / unroute handlers per agent or integration mode."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from tokensaver_cli.config import (
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
from tokensaver_cli.state import RoutedFile, backup_file, clear_route, load_state, record_route, restore_file


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


def _ensure_claude_model_approved(cfg: RouteConfig, model_id: str, *, launching: bool) -> int | None:
    """Zero-trust Agent Registry gate before Claude route/launch.

    Returns an exit code to abort, or ``None`` to continue.
    """
    from tokensaver_cli.approve_cmd import ensure_model_approved

    ok = ensure_model_approved(
        model_id,
        force_local=cfg.deploy_mode == "local",
    )
    if ok:
        return None
    if launching:
        print(
            "Launch cancelled — approve the model to continue (zero-trust).",
            file=sys.stderr,
        )
        return 1
    print(
        f"WARN  route applied but {model_id} is not approved yet. "
        f"Run: tokensaver approve {model_id}",
        file=sys.stderr,
    )
    return None


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


def _strip_tokensaver_env(settings: dict[str, Any]) -> dict[str, Any]:
    env = dict(settings.get("env") or {})
    for key in (
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "TOKENSAVER_API_KEY",
        "TOKENSAVER_CONSOLE_URL",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT",
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
                    and "tokensaver status" in str(h.get("command", ""))
                )
            ]
            if filtered:
                kept.append({**matcher, "hooks": filtered})
        if kept:
            out[event] = kept
    return out


def _tokensaver_hooks_patch() -> dict[str, Any]:
    return {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "tokensaver status --session-start",
                    },
                ]
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "tokensaver status --prompt-nudge",
                    },
                ]
            }
        ],
    }


def _status_line_patch() -> dict[str, Any]:
    return {
        "type": "command",
        "command": "tokensaver status --line",
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
    if model_id:
        env_patch["ANTHROPIC_MODEL"] = model_id
        env_patch.update(_claude_env_extras(model_id))
    if cfg.deploy_mode == "local":
        # Optional full-capture hint; user can unset. Documented in frame.
        env_patch.setdefault("HTTPS_PROXY", cfg.egress_proxy_url)

    if model_id:
        abort = _ensure_claude_model_approved(
            cfg,
            model_id,
            launching=launch or bool(extra_args),
        )
        if abort is not None:
            return abort

    settings = read_json(settings_path)
    # SaaS must not keep a leftover local egress proxy (Connection refused if :8888 is down).
    existing_env = dict(settings.get("env") or {})
    if cfg.deploy_mode != "local":
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

    plugin_dir = None
    if install_plugin:
        plugin_dir = install_claude_plugin(force=True)
        if plugin_dir is None:
            print(
                "WARN  Claude plugin bundle missing — slash commands /tokensaver:* unavailable.",
                file=sys.stderr,
            )

    prev_sticky = _sticky_claude_model()
    sticky_model = model_id if (explicit_model or explicit_profile) else (prev_sticky or model_id)
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


def unroute_claude() -> int:
    rec = clear_route("claude")
    if not rec:
        print("Claude Code is not routed through TokenSaver.", file=sys.stderr)
        return 1
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
