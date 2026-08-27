"""Retro route frame shown when routing an agent through TokenSaver."""

from __future__ import annotations

import sys

from tokensaver_cli.config import RouteConfig
from tokensaver_cli.logo import LOGO_LINES

_BOX_WIDTH = 69


def _box_top() -> str:
    return f"  ┌{'─' * (_BOX_WIDTH - 2)}┐"


def _box_bottom() -> str:
    return f"  └{'─' * (_BOX_WIDTH - 2)}┘"


def _box_line(text: str) -> str:
    inner = f"  {text}"[: _BOX_WIDTH - 4].ljust(_BOX_WIDTH - 4)
    return f"  │ {inner} │"


def _mode_label(cfg: RouteConfig) -> str:
    if cfg.deploy_mode == "local":
        return "LOCAL (self-host)"
    return "SaaS (control plane)"


def print_route_frame(
    *,
    target_label: str,
    cfg: RouteConfig,
    launching: bool = False,
    extra_lines: list[str] | None = None,
    file=None,
) -> None:
    out = file if file is not None else sys.stdout

    for line in LOGO_LINES:
        print(f"  {line}", file=out)
    print(file=out)

    print(_box_top(), file=out)
    print(_box_line(f"ROUTE: {target_label.upper()}"), file=out)
    print(_box_line(f"Mode · {_mode_label(cfg)}"), file=out)
    print(_box_line(f"Anthropic → {cfg.anthropic_base_url}"), file=out)
    print(_box_line(f"OpenAI    → {cfg.openai_base_url}"), file=out)
    print(_box_line(f"MCP tools → {cfg.mcp_tools_url}"), file=out)
    print(_box_line(f"Gateway   → {cfg.gateway_url}"), file=out)
    print(_box_line(f"Console   → {cfg.console_url}"), file=out)

    if cfg.deploy_mode == "local":
        print(_box_line(f"Egress    → {cfg.egress_proxy_url} (HTTPS_PROXY)"), file=out)

    if extra_lines:
        for line in extra_lines:
            print(_box_line(line), file=out)

    if launching:
        print(_box_line(f"Launching {target_label}…"), file=out)

    print(_box_bottom(), file=out)
    print(file=out)
    print("  Undo: tokensaver unroute", target_label.split()[0].lower(), file=out)
    print("  Check: tokensaver doctor", file=out)
    print(file=out)
