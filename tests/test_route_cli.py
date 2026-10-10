"""Tests for tokensaver route CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from tokensaver_cli.agents import route_claude, route_cursor, unroute_claude, unroute_cursor
from tokensaver_cli.config import RouteConfig, RouteConfigError, resolve_route_config
from tokensaver_cli.plugin_install import install_claude_plugin, plugin_install_dir
from tokensaver_cli.profiles import BUILTIN_PROFILES, FREE_PROFILES, resolve_model
from tokensaver_cli.state import load_state, route_state_dir


@pytest.fixture
def route_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(config_home))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_test_key_12345678")
    monkeypatch.setenv("TOKENSAVER_API_URL", "https://api.example.test")
    return config_home


@pytest.fixture
def cfg() -> RouteConfig:
    return RouteConfig(
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


def test_resolve_route_config_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    with pytest.raises(RouteConfigError, match="tokensaver login"):
        resolve_route_config()


def test_resolve_route_config_strips_api_v1_suffix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_x")
    monkeypatch.setenv("TOKENSAVER_API_BASE_URL", "https://api.example.test/api/v1")
    resolved = resolve_route_config()
    assert resolved.api_host == "https://api.example.test"
    assert resolved.api_v1_base == "https://api.example.test/api/v1"


def test_resolve_model_profile_and_override() -> None:
    model, profile = resolve_model(model=None, profile="cheap")
    assert model == BUILTIN_PROFILES["cheap"]
    assert profile == "cheap"
    model2, profile2 = resolve_model(model="openai/gpt-5-mini", profile="cheap")
    assert model2 == "openai/gpt-5-mini"
    assert profile2 is None


def test_resolve_model_free_plan_defaults() -> None:
    model, profile = resolve_model(model=None, profile=None, plan_slug="free")
    assert model == FREE_PROFILES["default"]
    assert model == "openrouter/openai/gpt-oss-20b"
    assert profile == "default"
    cheap, _ = resolve_model(model=None, profile="cheap", plan_slug="free")
    assert cheap == FREE_PROFILES["cheap"]


def test_route_claude_writes_settings_and_mcp(route_home: Path, cfg: RouteConfig, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert route_claude(cfg, launch=False, extra_args=[], install_plugin=False) == 0
    finally:
        os.chdir(old_cwd)

    settings_path = route_home / ".claude" / "settings.json"
    assert settings_path.is_file()
    settings = json.loads(settings_path.read_text())
    assert settings["env"]["ANTHROPIC_BASE_URL"] == cfg.anthropic_base_url
    assert settings["env"]["ANTHROPIC_AUTH_TOKEN"] == cfg.api_key
    assert settings["env"]["ANTHROPIC_MODEL"] == BUILTIN_PROFILES["default"]
    assert "statusline.txt" in settings["statusLine"]["command"] or "TokenSaver" in settings["statusLine"]["command"]
    assert "tokensaver status --line" not in settings["statusLine"]["command"]
    assert settings["hooks"]["SessionStart"]
    hook_cmds = json.dumps(settings["hooks"])
    assert "tokensaver status --session-start" in hook_cmds
    assert "prompt-nudge" not in hook_cmds

    mcp_path = project / ".mcp.json"
    assert mcp_path.is_file()
    mcp = json.loads(mcp_path.read_text())
    assert "tokensaver-route-tools" in mcp["mcpServers"]
    assert "tokensaver-route-gateway" in mcp["mcpServers"]

    state = load_state()
    assert "claude" in state
    assert state["claude"].meta["scope"] == "user"
    assert route_state_dir().is_dir()


def test_route_claude_free_plan_default_model(
    route_home: Path,
    cfg: RouteConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOKENSAVER_PLAN", "free")
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert route_claude(cfg, launch=False, extra_args=[], install_plugin=False) == 0
    finally:
        os.chdir(old_cwd)
    settings = json.loads((route_home / ".claude" / "settings.json").read_text())
    assert settings["env"]["ANTHROPIC_MODEL"] == FREE_PROFILES["default"]
    assert settings["env"]["CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT"] == "1"


def test_route_claude_no_unknown_model_env_for_anthropic_native(
    route_home: Path,
    cfg: RouteConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TOKENSAVER_PLAN", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        with patch(
            "tokensaver_cli.approve_cmd.ensure_model_approved",
            return_value="anthropic/claude-sonnet-4-6",
        ):
            assert (
                route_claude(
                    cfg,
                    launch=False,
                    extra_args=[],
                    model="anthropic/claude-sonnet-4-6",
                    install_plugin=False,
                )
                == 0
            )
    finally:
        os.chdir(old_cwd)
    settings = json.loads((route_home / ".claude" / "settings.json").read_text())
    assert "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT" not in settings["env"]


def test_route_claude_launch_aborts_when_model_not_approved(
    route_home: Path,
    cfg: RouteConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        with patch("tokensaver_cli.approve_cmd.ensure_model_approved", return_value=None):
            assert (
                route_claude(
                    cfg,
                    launch=True,
                    extra_args=[],
                    model="openrouter/openai/gpt-oss-20b",
                    install_plugin=False,
                )
                == 1
            )
    finally:
        os.chdir(old_cwd)


def test_route_claude_keeps_sticky_model_on_relaunch(
    route_home: Path,
    cfg: RouteConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bare ``route --launch`` must not reset an explicit --model to plan default."""
    monkeypatch.delenv("TOKENSAVER_PLAN", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    glm = "openrouter/z-ai/glm-4.7-flash"
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert (
            route_claude(
                cfg,
                launch=False,
                extra_args=[],
                model=glm,
                install_plugin=False,
            )
            == 0
        )
        assert (
            route_claude(cfg, launch=False, extra_args=[], install_plugin=False) == 0
        )
    finally:
        os.chdir(old_cwd)
    settings = json.loads((route_home / ".claude" / "settings.json").read_text())
    assert settings["env"]["ANTHROPIC_MODEL"] == glm
    assert load_state()["claude"].meta.get("sticky_model") == glm


def test_route_claude_project_scope(route_home: Path, cfg: RouteConfig, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert (
            route_claude(
                cfg,
                launch=False,
                extra_args=[],
                scope="project",
                profile="cheap",
                install_plugin=False,
            )
            == 0
        )
    finally:
        os.chdir(old_cwd)

    settings = json.loads((project / ".claude" / "settings.json").read_text())
    assert settings["env"]["ANTHROPIC_MODEL"] == BUILTIN_PROFILES["cheap"]
    assert (project / ".mcp.json").is_file()
    assert not (route_home / ".claude" / "settings.json").exists()
    assert load_state()["claude"].meta["profile"] == "cheap"


def test_route_claude_local_scope(route_home: Path, cfg: RouteConfig, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert route_claude(cfg, launch=False, extra_args=[], scope="local", install_plugin=False) == 0
    finally:
        os.chdir(old_cwd)
    assert (project / ".claude" / "settings.local.json").is_file()


def test_route_claude_with_fs_warns_without_gateway(
    route_home: Path,
    cfg: RouteConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("tokensaver_cli.agents.shutil.which", lambda _name: None)
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert route_claude(cfg, launch=False, extra_args=[], with_fs=True, install_plugin=False) == 0
    finally:
        os.chdir(old_cwd)
    err = capsys.readouterr().err
    assert "--with-fs skipped" in err
    mcp = json.loads((project / ".mcp.json").read_text())
    assert "tokensaver-route-fs" not in mcp["mcpServers"]


def test_route_claude_with_fs_wires_stdio(
    route_home: Path,
    cfg: RouteConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def which(name: str) -> str | None:
        if name == "tokensaver-mcp-gateway":
            return "/usr/bin/tokensaver-mcp-gateway"
        if name == "npx":
            return "/usr/bin/npx"
        return None

    monkeypatch.setattr("tokensaver_cli.agents.shutil.which", which)
    project = tmp_path / "project"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert route_claude(cfg, launch=False, extra_args=[], with_fs=True, install_plugin=False) == 0
    finally:
        os.chdir(old_cwd)
    mcp = json.loads((project / ".mcp.json").read_text())
    fs = mcp["mcpServers"]["tokensaver-route-fs"]
    assert fs["command"] == "/usr/bin/tokensaver-mcp-gateway"
    assert "--target" in fs["args"]
    assert load_state()["claude"].meta["with_fs"] is True


def test_install_claude_plugin(route_home: Path) -> None:
    dest = install_claude_plugin(force=True)
    assert dest is not None
    assert dest == plugin_install_dir()
    assert (dest / ".claude-plugin" / "plugin.json").is_file()
    assert (dest / "commands" / "setup.md").is_file()


def test_unroute_claude_restores_backup(route_home: Path, cfg: RouteConfig, tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    settings_path = route_home / ".claude"
    settings_path.mkdir(parents=True)
    original = settings_path / "settings.json"
    original.write_text('{"env": {"FOO": "bar"}}\n', encoding="utf-8")

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        route_claude(cfg, launch=False, extra_args=[], install_plugin=False)
        assert "ANTHROPIC_BASE_URL" in original.read_text()
        assert unroute_claude() == 0
        restored = json.loads(original.read_text())
        assert restored["env"]["FOO"] == "bar"
        assert "ANTHROPIC_BASE_URL" not in restored.get("env", {})
    finally:
        os.chdir(old_cwd)


def test_route_cursor_writes_mcp_json(cfg: RouteConfig, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        assert route_cursor(cfg) == 0
        mcp = json.loads((project / ".cursor" / "mcp.json").read_text())
        assert mcp["mcpServers"]["tokensaver-route-gateway"]["headers"]["X-Tokensaver-Client"] == "cursor/1.0"
    finally:
        os.chdir(old_cwd)


def test_unroute_cursor_restores(route_home: Path, cfg: RouteConfig, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    cursor_dir = project / ".cursor"
    cursor_dir.mkdir(parents=True)
    mcp_path = cursor_dir / "mcp.json"
    mcp_path.write_text('{"mcpServers": {"other": {"url": "http://x"}}}\n', encoding="utf-8")

    old_cwd = os.getcwd()
    try:
        os.chdir(project)
        route_cursor(cfg)
        route_cursor(cfg)
        assert unroute_cursor() == 0
        restored = json.loads(mcp_path.read_text())
        assert "tokensaver-route-tools" not in restored.get("mcpServers", {})
        assert restored["mcpServers"]["other"]["url"] == "http://x"
    finally:
        os.chdir(old_cwd)
