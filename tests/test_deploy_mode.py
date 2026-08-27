"""Tests for deploy mode and route frame."""

from __future__ import annotations

import json
import os
from io import StringIO
from pathlib import Path

import pytest

from tokensaver_cli.agents import route_claude
from tokensaver_cli.config import RouteConfig, resolve_deploy_mode, resolve_route_config
from tokensaver_cli.route_frame import print_route_frame
from tokensaver_cli.status import format_status_line, run_status


@pytest.fixture
def cfg_saas() -> RouteConfig:
    return RouteConfig(
        api_key="ts_test_key_12345678",
        api_host="https://api.tokensaver.fr",
        anthropic_base_url="https://api.tokensaver.fr/anthropic",
        openai_base_url="https://api.tokensaver.fr/openai/v1",
        mcp_tools_url="https://mcp.tokensaver.fr/mcp",
        gateway_url="https://gateway.tokensaver.fr/mcp",
        organisation_id=None,
        workspace_id=None,
        deploy_mode="saas",
        egress_proxy_url="http://127.0.0.1:8888",
        console_url="https://platform.tokensaver.fr",
    )


def test_flows_url_includes_locale_and_workspace(cfg_saas: RouteConfig) -> None:
    with_ws = RouteConfig(**{**cfg_saas.__dict__, "workspace_id": "ws-abc"})
    url = with_ws.flows_url()
    assert url == "https://platform.tokensaver.fr/fr/ws-abc/dashboard?tab=flows"
    assert with_ws.flows_url(flow_id="run-1").endswith("&flowId=run-1")
    assert "/fr/" in cfg_saas.flows_url()


def test_resolve_deploy_mode_defaults_to_saas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_BASE_URL", raising=False)
    assert resolve_deploy_mode() == "saas"


def test_resolve_deploy_mode_explicit_host_beats_mode_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOKENSAVER_MODE", "local")
    assert resolve_deploy_mode(api_host="https://api.tokensaver.fr") == "saas"
    assert resolve_deploy_mode(api_host="http://localhost:8000") == "local"


def test_resolve_deploy_mode_explicit_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENSAVER_MODE", "local")
    assert resolve_deploy_mode() == "local"


def test_resolve_deploy_mode_force_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    assert resolve_deploy_mode(force_local=True) == "local"


def test_resolve_deploy_mode_auto_local_from_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    assert resolve_deploy_mode(api_host="http://localhost:8000") == "local"


def test_resolve_route_config_local_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_x")
    monkeypatch.setenv("TOKENSAVER_MODE", "local")
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_MCP_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_GATEWAY_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_CONSOLE_URL", raising=False)

    resolved = resolve_route_config()
    assert resolved.deploy_mode == "local"
    assert resolved.api_host == "http://localhost:8000"
    assert resolved.mcp_tools_url == "http://localhost:8787/mcp"
    assert resolved.gateway_url == "http://localhost:8788/mcp"
    assert resolved.egress_proxy_url == "http://127.0.0.1:8888"
    assert resolved.console_url == "http://localhost:3000"


def test_resolve_route_config_force_local_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_x")
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    resolved = resolve_route_config(force_local=True)
    assert resolved.deploy_mode == "local"
    assert resolved.api_host == "http://localhost:8000"


def test_resolve_route_config_saas_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_x")
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_BASE_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_CONSOLE_URL", raising=False)

    resolved = resolve_route_config()
    assert resolved.deploy_mode == "saas"
    assert resolved.api_host == "https://api.tokensaver.fr"
    assert resolved.mcp_tools_url == "https://mcp.tokensaver.fr/mcp"
    assert resolved.gateway_url == "https://gateway.tokensaver.fr/mcp"
    assert resolved.console_url == "https://platform.tokensaver.fr"
    assert "tab=flows" in resolved.flows_url()
    assert "/dashboard?tab=flows" in resolved.flows_url()


def test_login_ignores_localhost_env_without_local_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monorepo .env / TOKENSAVER_MODE=local must not hijack bare login → SaaS."""
    from tokensaver_cli.auth_cmd import _api_host, _console_url

    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    monkeypatch.setenv("TOKENSAVER_API_URL", "http://localhost:8000/api/v1")
    monkeypatch.setenv("TOKENSAVER_API_BASE_URL", "http://localhost:8000/api/v1")
    monkeypatch.setenv("TOKENSAVER_CONSOLE_URL", "http://localhost:3000")
    assert _api_host(force_local=False) == "https://api.tokensaver.fr"
    assert _console_url(force_local=False) == "https://platform.tokensaver.fr"
    assert _api_host(force_local=True) == "http://localhost:8000"
    assert _console_url(force_local=True) == "http://localhost:3000"
    # Leftover MODE=local in the shell must NOT force SaaS login onto localhost.
    monkeypatch.setenv("TOKENSAVER_MODE", "local")
    assert _api_host(force_local=False) == "https://api.tokensaver.fr"
    assert _api_host(force_local=True) == "http://localhost:8000"


def test_resolve_route_config_prefers_saas_creds_over_localhost_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tokensaver_cli.credentials import Credentials, save_credentials

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_saas_key_xxxxxxxx")
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    monkeypatch.setenv("TOKENSAVER_API_URL", "http://localhost:8000/api/v1")
    monkeypatch.setenv("TOKENSAVER_CONSOLE_URL", "http://localhost:3000")
    save_credentials(
        Credentials(
            api_key="ts_saas_key_xxxxxxxx",
            api_host="https://api.tokensaver.fr",
            console_url="https://platform.tokensaver.fr",
        )
    )
    resolved = resolve_route_config()
    assert resolved.deploy_mode == "saas"
    assert resolved.api_host == "https://api.tokensaver.fr"
    assert resolved.console_url == "https://platform.tokensaver.fr"


def test_resolve_route_config_saas_creds_beat_mode_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sticky SaaS login must win over a leftover TOKENSAVER_MODE=local export."""
    from tokensaver_cli.credentials import Credentials, save_credentials

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_saas_key_xxxxxxxx")
    monkeypatch.setenv("TOKENSAVER_MODE", "local")
    monkeypatch.setenv("TOKENSAVER_API_URL", "http://localhost:8000/api/v1")
    monkeypatch.setenv("TOKENSAVER_MCP_URL", "http://localhost:8787/mcp")
    monkeypatch.setenv("TOKENSAVER_GATEWAY_URL", "http://localhost:8788/mcp")
    monkeypatch.setenv("TOKENSAVER_CONSOLE_URL", "http://localhost:3000")
    save_credentials(
        Credentials(
            api_key="ts_saas_key_xxxxxxxx",
            api_host="https://api.tokensaver.fr",
            console_url="https://platform.tokensaver.fr",
            workspace_id="ws-1",
        )
    )
    resolved = resolve_route_config()
    assert resolved.deploy_mode == "saas"
    assert resolved.api_host == "https://api.tokensaver.fr"
    assert resolved.console_url == "https://platform.tokensaver.fr"
    assert resolved.mcp_tools_url == "https://mcp.tokensaver.fr/mcp"
    assert resolved.gateway_url == "https://gateway.tokensaver.fr/mcp"
    assert "platform.tokensaver.fr" in resolved.flows_url()


def test_print_route_frame_contains_logo_and_mode(cfg_saas: RouteConfig) -> None:
    buf = StringIO()
    print_route_frame(target_label="Claude Code", cfg=cfg_saas, launching=True, file=buf)
    out = buf.getvalue()
    assert "██║ ██╔╝" in out
    assert "ROUTE: CLAUDE CODE" in out
    assert "SaaS (control plane)" in out
    assert "Launching Claude Code" in out
    assert "Console" in out
    assert "Egress" not in out


def test_print_route_frame_local_shows_egress(cfg_saas: RouteConfig) -> None:
    local = RouteConfig(
        **{
            **cfg_saas.__dict__,
            "deploy_mode": "local",
            "api_host": "http://localhost:8000",
            "console_url": "http://localhost:3000",
        }
    )
    buf = StringIO()
    print_route_frame(target_label="Claude Code", cfg=local, file=buf)
    out = buf.getvalue()
    assert "LOCAL (self-host)" in out
    assert "Egress" in out
    assert "127.0.0.1:8888" in out


def test_status_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cfg_saas: RouteConfig) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TOKENSAVER_API_KEY", cfg_saas.api_key)
    line = format_status_line(cfg_saas)
    assert "TokenSaver" in line
    assert "idle" in line


def test_run_status_line_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cfg_saas: RouteConfig,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TOKENSAVER_API_KEY", cfg_saas.api_key)
    monkeypatch.setenv("TOKENSAVER_API_URL", cfg_saas.api_host)
    assert run_status(line=True) == 0
    assert "TokenSaver" in capsys.readouterr().out


def test_route_claude_prints_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(config_home))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_test_key_12345678")
    monkeypatch.setenv("TOKENSAVER_API_URL", "https://api.example.test")

    cfg = RouteConfig(
        api_key="ts_test_key_12345678",
        api_host="https://api.example.test",
        anthropic_base_url="https://api.example.test/anthropic",
        openai_base_url="https://api.example.test/openai/v1",
        mcp_tools_url="https://mcp.example.test/mcp",
        gateway_url="https://gateway.example.test/mcp",
        organisation_id="org-1",
        workspace_id="ws-1",
        deploy_mode="saas",
        egress_proxy_url="http://127.0.0.1:8888",
        console_url="https://platform.example.test",
    )

    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        route_claude(cfg, launch=False, extra_args=[], install_plugin=False)
    finally:
        os.chdir(old_cwd)

    out = capsys.readouterr().out
    assert "ROUTE: CLAUDE CODE" in out
    assert "██║ ██╔╝" in out
    assert "Flux IA" in out
    settings = json.loads((config_home / ".claude" / "settings.json").read_text())
    assert settings["env"]["ANTHROPIC_BASE_URL"] == cfg.anthropic_base_url
