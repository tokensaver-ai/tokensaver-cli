"""Tests for tokensaver approve (Agent Registry)."""

from __future__ import annotations

from typing import Any
from pathlib import Path

import pytest

from tokensaver_cli.approve_cmd import (
    approve_catalog_ref,
    ensure_model_approved,
    resolve_current_model_ref,
    run_approve,
)


@pytest.fixture
def api_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_test_key_approve")
    monkeypatch.setenv("TOKENSAVER_API_URL", "https://api.example.test")
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    return tmp_path


def test_resolve_current_model_from_settings(api_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    settings = Path.home() / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        '{"env": {"ANTHROPIC_MODEL": "openrouter/z-ai/glm-4.7-flash"}}\n',
        encoding="utf-8",
    )
    assert resolve_current_model_ref() == "openrouter/z-ai/glm-4.7-flash"


def test_approve_creates_when_missing(api_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, Any]] = []

    def fake_request(method: str, url: str, *, headers=None, body=None, timeout=30.0):
        calls.append((method, url, body))
        if method == "GET":
            return {"items": []}
        if method == "POST":
            return {"id": "asset-1", "ref": body["ref"], "status": "approved", "type": "model"}
        raise AssertionError(f"unexpected {method} {url}")

    monkeypatch.setattr("tokensaver_cli.approve_cmd.request_json", fake_request)
    out = approve_catalog_ref("openrouter/z-ai/glm-4.7-flash")
    assert out["status"] == "approved"
    assert any(c[0] == "POST" for c in calls)


def test_approve_patches_quarantined(api_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(method: str, url: str, *, headers=None, body=None, timeout=30.0):
        if method == "GET":
            return {
                "items": [
                    {
                        "id": "uuid-q",
                        "ref": "openrouter/z-ai/glm-4.7-flash",
                        "status": "quarantined",
                        "type": "model",
                    }
                ]
            }
        if method == "PATCH":
            assert "uuid-q" in url
            assert body == {"status": "approved"}
            return {"id": "uuid-q", "ref": "openrouter/z-ai/glm-4.7-flash", "status": "approved"}
        raise AssertionError(method)

    monkeypatch.setattr("tokensaver_cli.approve_cmd.request_json", fake_request)
    out = approve_catalog_ref("openrouter/z-ai/glm-4.7-flash")
    assert out["status"] == "approved"


def test_run_approve_current(api_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_MODEL", "openrouter/openai/gpt-5-nano")

    def fake_request(method: str, url: str, *, headers=None, body=None, timeout=30.0):
        if method == "GET":
            return {"items": []}
        return {"id": "x", "ref": body["ref"], "status": "approved"}

    monkeypatch.setattr("tokensaver_cli.approve_cmd.request_json", fake_request)
    assert run_approve(None, current=True, quiet=True) == 0


def test_ensure_model_approved_already_ok(api_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.catalog_model_status",
        lambda *a, **k: "approved",
    )
    assert ensure_model_approved("openrouter/openai/gpt-oss-20b", interactive=False) == (
        "openrouter/openai/gpt-oss-20b"
    )


def test_ensure_model_approved_prompts_and_approves(
    api_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("TOKENSAVER_PLAN", "free")
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.catalog_model_status",
        lambda *a, **k: "missing",
    )
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.approve_catalog_ref",
        lambda *a, **k: {"id": "1", "ref": a[0], "status": "approved"},
    )
    # Even if /models returns the full catalog, Free picker must stay on allowlist.
    monkeypatch.setattr(
        "tokensaver_cli.models_cmd._list_api_models",
        lambda: [f"openrouter/noise/model-{i}" for i in range(200)],
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    assert (
        ensure_model_approved("openrouter/openai/gpt-oss-20b", interactive=True)
        == "openrouter/openai/gpt-oss-20b"
    )
    err = capsys.readouterr().err
    assert "zero-trust" in err.lower()
    assert "choose a model" in err.lower()
    assert "Free plan models" in err
    assert "TokenSaver zero-trust" in err
    assert "openrouter/noise/model-" not in err
    assert "openrouter/z-ai/glm-4.7-flash" in err
    assert "Free plan models (15)" in err or "Free plan models (1" in err


def test_ensure_model_approved_pick_other(
    api_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOKENSAVER_PLAN", "free")
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.catalog_model_status",
        lambda *a, **k: "missing",
    )
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.approve_catalog_ref",
        lambda *a, **k: {"id": "1", "ref": a[0], "status": "approved"},
    )
    monkeypatch.setattr(
        "tokensaver_cli.models_cmd._list_api_models",
        lambda: [f"openrouter/noise/model-{i}" for i in range(50)],
    )
    # Free Enter-default first (oss-20b), then cheap = gpt-5-nano at index 2
    monkeypatch.setattr("builtins.input", lambda _prompt="": "2")
    assert (
        ensure_model_approved(
            "openrouter/openai/gpt-oss-20b", interactive=True, allow_pick=True
        )
        == "openrouter/openai/gpt-5-nano"
    )


def test_ensure_model_approved_free_enter_uses_plan_default(
    api_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Sticky previous model must not win Enter — Free plan default does."""
    monkeypatch.setenv("TOKENSAVER_PLAN", "free")
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.catalog_model_status",
        lambda *a, **k: "missing",
    )
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.approve_catalog_ref",
        lambda *a, **k: {"id": "1", "ref": a[0], "status": "approved"},
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    assert (
        ensure_model_approved(
            "openrouter/openai/gpt-oss-120b", interactive=True, allow_pick=True
        )
        == "openrouter/openai/gpt-oss-20b"
    )
    err = capsys.readouterr().err
    assert "Enter →  openrouter/openai/gpt-oss-20b" in err
    assert "Previous openrouter/openai/gpt-oss-120b" in err
    assert "← Enter" in err


def test_ensure_model_approved_rejects_non_free_typed_id(
    api_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("TOKENSAVER_PLAN", "free")
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.catalog_model_status",
        lambda *a, **k: "missing",
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": "openrouter/x-ai/grok-4.6")
    assert (
        ensure_model_approved("openrouter/openai/gpt-oss-20b", interactive=True) is None
    )
    err = capsys.readouterr().err
    assert "not on the Free plan allowlist" in err


def test_ensure_model_approved_decline(
    api_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tokensaver_cli.approve_cmd.catalog_model_status",
        lambda *a, **k: "quarantined",
    )
    monkeypatch.setattr("builtins.input", lambda _prompt="": "q")
    assert (
        ensure_model_approved("openrouter/openai/gpt-oss-20b", interactive=True) is None
    )
