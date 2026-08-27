"""SessionStart welcome context for Claude Code plugin."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tokensaver_cli.config import RouteConfig
from tokensaver_cli.credentials import Credentials, save_credentials
from tokensaver_cli.state import RouteRecord, save_state
from tokensaver_cli.status import format_session_start_json, format_welcome_context


@pytest.fixture
def ts_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    cfg_dir = home / ".config" / "tokensaver"
    cfg_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    return home


def test_welcome_context_includes_route_facts(ts_home: Path) -> None:
    save_credentials(
        Credentials(
            access_token="jwt-session",
            email="user@example.com",
            api_host="https://api.example.test",
            console_url="https://platform.example.test",
            workspace_id="ws-1",
            plan_slug="free",
        )
    )
    save_state(
        {
            "claude": RouteRecord(
                target="claude",
                routed_at="2026-01-01T00:00:00Z",
                files=[],
                meta={
                    "model": "openrouter/openai/gpt-oss-20b",
                    "profile": "default",
                    "scope": "user",
                },
            )
        }
    )
    cfg = RouteConfig(
        api_key="jwt-session",
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
    with patch("tokensaver_cli.status.fetch_recent_flow_id", return_value=None):
        text = format_welcome_context(cfg)
    assert "gpt-oss-20b" in text
    assert "TokenSaver" in text
    assert "answer the user's message first" in text.lower() or "Always answer" in text
    assert "MUST be the TokenSaver welcome" not in text
    assert "real time" in text.lower() or "real-time" in text.lower() or "Flux IA" in text
    assert "ws-1" in text or "Flux IA" in text


def test_welcome_json_is_valid_session_start_hook(ts_home: Path) -> None:
    save_credentials(
        Credentials(
            access_token="jwt-session",
            api_host="https://api.example.test",
            console_url="https://platform.example.test",
            workspace_id="ws-1",
        )
    )
    save_state(
        {
            "claude": RouteRecord(
                target="claude",
                routed_at="2026-01-01T00:00:00Z",
                files=[],
                meta={"model": "openrouter/openai/gpt-oss-20b", "profile": "default"},
            )
        }
    )
    cfg = RouteConfig(
        api_key="jwt-session",
        api_host="https://api.example.test",
        anthropic_base_url="https://api.example.test/anthropic",
        openai_base_url="https://api.example.test/openai/v1",
        mcp_tools_url="https://mcp.example.test/mcp",
        gateway_url="https://gateway.example.test/mcp",
        organisation_id=None,
        workspace_id="ws-1",
        deploy_mode="saas",
        egress_proxy_url="http://127.0.0.1:8888",
        console_url="https://platform.example.test",
    )
    with patch("tokensaver_cli.status.fetch_recent_flow_id", return_value=None):
        raw = format_session_start_json(cfg)
    data = json.loads(raw)
    assert data["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "additionalContext" in data["hookSpecificOutput"]
    assert data["hookSpecificOutput"].get("reloadSkills") is True
    assert "initialUserMessage" in data["hookSpecificOutput"]
    assert "accueil" in data["hookSpecificOutput"]["initialUserMessage"].lower() or "TokenSaver" in data["hookSpecificOutput"]["initialUserMessage"]
