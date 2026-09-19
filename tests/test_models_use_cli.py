"""Tests for tokensaver models / use helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from tokensaver_cli.config import RouteConfig
from tokensaver_cli.models_cmd import is_profile_name, run_models
from tokensaver_cli.use_cmd import run_use


@pytest.fixture
def route_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(config_home))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_test_key_models")
    monkeypatch.setenv("TOKENSAVER_API_URL", "https://api.example.test")
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    return config_home


@pytest.fixture
def cfg() -> RouteConfig:
    return RouteConfig(
        api_key="ts_test_key_models",
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


def test_is_profile_name() -> None:
    assert is_profile_name("cheap")
    assert is_profile_name("DEFAULT")
    assert not is_profile_name("openrouter/z-ai/glm-4.7-flash")


def test_run_models_prints_profiles(route_home: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr("tokensaver_cli.models_cmd._list_api_models", lambda: ["openrouter/a", "openai/b"])
    assert run_models() == 0
    out = capsys.readouterr().out
    assert "cheap" in out
    assert "openrouter/a" in out


def test_run_models_free_plan_allowlist_only(
    route_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("TOKENSAVER_PLAN", "free")
    monkeypatch.setattr(
        "tokensaver_cli.models_cmd._list_api_models",
        lambda: [f"openrouter/noise/{i}" for i in range(100)],
    )
    assert run_models() == 0
    out = capsys.readouterr().out
    assert "Free plan allowlist" in out
    assert "openrouter/openai/gpt-oss-20b" in out
    assert "openrouter/z-ai/glm-4.7-flash" in out
    assert "openrouter/noise/" not in out
    assert "15 model(s)" in out


def test_run_use_dispatches_profile(route_home: Path, cfg: RouteConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict = {}

    def fake_route(c, **kwargs):
        called.update(kwargs)
        return 0

    monkeypatch.setattr("tokensaver_cli.use_cmd.resolve_route_config", lambda force_local=False: cfg)
    monkeypatch.setattr("tokensaver_cli.use_cmd.route_claude", fake_route)
    monkeypatch.setattr(
        "tokensaver_cli.state.load_state",
        lambda: {
            "claude": type(
                "R",
                (),
                {"meta": {"model": "openai/gpt-4.1-mini", "profile": "cheap"}},
            )()
        },
    )

    assert run_use("cheap") == 0
    assert called.get("profile") == "cheap"
    assert called.get("model") is None


def test_run_use_dispatches_model_ref(route_home: Path, cfg: RouteConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict = {}

    def fake_route(c, **kwargs):
        called.update(kwargs)
        return 0

    monkeypatch.setattr("tokensaver_cli.use_cmd.resolve_route_config", lambda force_local=False: cfg)
    monkeypatch.setattr("tokensaver_cli.use_cmd.route_claude", fake_route)
    assert run_use("openrouter/z-ai/glm-4.7-flash") == 0
    assert called.get("model") == "openrouter/z-ai/glm-4.7-flash"
    assert called.get("profile") is None
