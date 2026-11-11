"""Tests for credentials store and auth helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tokensaver_cli.api_client import ApiError
from tokensaver_cli.auth_cmd import run_login, run_logout, run_resend_verification, run_verify_email, run_whoami
from tokensaver_cli.config import RouteConfigError, resolve_route_config
from tokensaver_cli.credentials import (
    Credentials,
    clear_credentials,
    credentials_path,
    load_credentials,
    resolve_api_key,
    save_credentials,
)
from tokensaver_cli.keys_cmd import run_keys_create, run_keys_list, run_keys_revoke


@pytest.fixture
def ts_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    monkeypatch.delenv("TOKENSAVER_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_PREFER_API_KEY", raising=False)
    return home


def test_save_load_clear_credentials(ts_home: Path) -> None:
    path = save_credentials(
        Credentials(api_key="tsv_abc123456789", email="a@b.co", access_token="jwt")
    )
    assert path == credentials_path()
    assert path.stat().st_mode & 0o777 == 0o600
    loaded = load_credentials()
    assert loaded is not None
    assert loaded.api_key == "tsv_abc123456789"
    assert loaded.email == "a@b.co"
    # Session JWT wins over stored tsv_… (login path never writes secrets).
    assert resolve_api_key() == "jwt"
    assert clear_credentials() is True
    assert load_credentials() is None


def test_resolve_route_config_uses_credentials(ts_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_BASE_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    save_credentials(
        Credentials(
            api_key="tsv_from_file_12345678",
            api_host="https://api.example.test",
            console_url="https://platform.example.test",
            organisation_id="org-1",
            workspace_id="ws-1",
        )
    )
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    cfg = resolve_route_config()
    assert cfg.api_key == "tsv_from_file_12345678"
    assert cfg.api_host == "https://api.example.test"
    assert cfg.organisation_id == "org-1"
    assert cfg.workspace_id == "ws-1"


def test_resolve_route_config_env_overrides_credentials(
    ts_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env wins when there is no session JWT (CI / login --key only)."""
    save_credentials(Credentials(api_key="tsv_file_key_xxxxxxxx"))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "tsv_env_key_yyyyyyyy")
    cfg = resolve_route_config()
    assert cfg.api_key == "tsv_env_key_yyyyyyyy"


def test_login_jwt_beats_egress_api_key_env(
    ts_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After tokensaver login, session JWT wins over leftover egress TOKENSAVER_API_KEY."""
    save_credentials(
        Credentials(
            access_token="jwt-from-login",
            email="a@b.co",
            api_host="http://localhost:8000",
        )
    )
    monkeypatch.setenv("TOKENSAVER_API_KEY", "tsv_from_egress_saasxxxx")
    assert resolve_api_key() == "jwt-from-login"
    cfg = resolve_route_config(force_local=True)
    assert cfg.api_key == "jwt-from-login"
    assert "localhost" in cfg.api_host


def test_prefer_api_key_flag_overrides_jwt(
    ts_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_credentials(Credentials(access_token="jwt-from-login"))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "tsv_forced_key_yyyyyyyy")
    monkeypatch.setenv("TOKENSAVER_PREFER_API_KEY", "1")
    assert resolve_api_key() == "tsv_forced_key_yyyyyyyy"


def test_resolve_api_key_rejects_legacy_ts(
    ts_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_legacy_key_yyyyyyyy")
    with pytest.raises(RuntimeError, match="Legacy ts_"):
        resolve_api_key()


def test_resolve_route_config_suggests_login(ts_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    with pytest.raises(RouteConfigError, match="tokensaver login"):
        resolve_route_config()


def test_login_with_key_only(ts_home: Path) -> None:
    assert run_login(api_key="tsv_imported_key_abcdef") == 0
    creds = load_credentials()
    assert creds is not None
    assert creds.api_key == "tsv_imported_key_abcdef"
    assert creds.access_token is None


def test_login_rejects_legacy_ts_key(ts_home: Path) -> None:
    assert run_login(api_key="ts_imported_key_abcdef") == 2
    assert load_credentials() is None


def _vk_list_or_create(method: str, url: str, **kwargs):
    if url.endswith("/gateway/virtual-keys") and method.upper() == "GET":
        return [{"id": "vk-1", "name": "CLI", "key_prefix": "tsv_abc", "status": "active"}]
    if url.endswith("/gateway/virtual-keys") and method.upper() == "POST":
        return {"id": "vk-new", "key": "tsv_new_secret", "key_prefix": "tsv_new"}
    raise AssertionError(f"unexpected VK call {method} {url}")


def test_login_signup_flow(ts_home: Path) -> None:
    def fake_request(method, url, **kwargs):
        if url.endswith("/auths/check-email"):
            return {"available": True}
        if url.endswith("/auths/signup"):
            assert kwargs["body"]["create_key"] is False
            return {
                "token": "jwt-signup",
                "id": "user-1",
                "email": "new@example.com",
                "email_verified": True,
            }
        if url.endswith("/users/me"):
            return {
                "id": "user-1",
                "email": "new@example.com",
                "workspace": {"id": "ws-1", "name": "Default"},
                "organisation": {"id": "org-1", "name": "Acme"},
                "plan": {"slug": "free", "name": "Free"},
            }
        if "/gateway/virtual-keys" in url:
            return _vk_list_or_create(method, url, **kwargs)
        raise AssertionError(url)

    with patch("tokensaver_cli.auth_cmd.request_json", side_effect=fake_request):
        code = run_login(
            email="new@example.com",
            password="password123",
            name="Ada",
            organisation="Acme",
            workspace="Default",
            signup=True,
            yes=True,
        )
    assert code == 0
    creds = load_credentials()
    assert creds is not None
    # Backend may return api_key_plain — OSS must ignore it (no secret on disk).
    assert creds.api_key is None
    assert creds.access_token == "jwt-signup"
    assert creds.key_id == "vk-1"
    assert resolve_api_key() == "jwt-signup"
    assert creds.organisation_id == "org-1"


def test_login_signin_uses_session_jwt_without_creating_legacy_key(ts_home: Path) -> None:
    """Existing account: JWT + virtual key id — no POST /api-keys."""
    calls: list[str] = []

    def fake_request(method, url, **kwargs):
        calls.append(f"{method} {url}")
        if url.endswith("/auths/check-email"):
            return {"available": False}
        if url.endswith("/auths/signin"):
            return {"token": "jwt-session-token", "id": "user-2", "email": "old@example.com"}
        if url.endswith("/users/me"):
            return {
                "email": "old@example.com",
                "workspace": {"id": "ws-2"},
                "organisation": {"id": "org-2"},
                "plan": {"slug": "free"},
            }
        if "/api-keys" in url:
            raise AssertionError("signin must not create legacy API keys")
        if "/gateway/virtual-keys" in url:
            return _vk_list_or_create(method, url, **kwargs)
        raise AssertionError(url)

    with patch("tokensaver_cli.auth_cmd.request_json", side_effect=fake_request):
        assert run_login(email="old@example.com", password="password123", signup=False) == 0
    creds = load_credentials()
    assert creds is not None
    assert creds.api_key is None
    assert creds.access_token == "jwt-session-token"
    assert creds.key_id == "vk-1"
    assert resolve_api_key() == "jwt-session-token"
    assert not any("/api-keys" in c for c in calls)


def test_login_signin_clears_previous_local_secret(ts_home: Path) -> None:
    """Re-login must drop any leftover tsv_… secret — JWT + vk id only."""
    save_credentials(
        Credentials(
            api_key="tsv_previous_key_xxxxx",
            email="old@example.com",
            key_prefix="tsv_previous",
            key_id="key-old",
            api_host="https://api.tokensaver.fr",
        )
    )

    def fake_request(method, url, **kwargs):
        if url.endswith("/auths/check-email"):
            return {"available": False}
        if url.endswith("/auths/signin"):
            return {"token": "jwt-in", "id": "user-2", "email": "old@example.com"}
        if url.endswith("/users/me"):
            return {
                "email": "old@example.com",
                "workspace": {"id": "ws-2"},
                "organisation": {"id": "org-2"},
            }
        if "/api-keys" in url:
            raise AssertionError("signin must not create API keys")
        if "/gateway/virtual-keys" in url:
            return _vk_list_or_create(method, url, **kwargs)
        raise AssertionError(url)

    with patch("tokensaver_cli.auth_cmd.request_json", side_effect=fake_request):
        assert run_login(email="old@example.com", password="password123", signup=False) == 0
    creds = load_credentials()
    assert creds is not None
    assert creds.api_key is None
    assert creds.key_id == "vk-1"
    assert creds.access_token == "jwt-in"
    assert resolve_api_key() == "jwt-in"


def test_verify_email_with_url(ts_home: Path) -> None:
    def fake_request(method, url, **kwargs):
        assert method.upper() == "POST"
        assert url.endswith("/auths/verify-email")
        assert kwargs["body"]["token"] == "abc123"
        return {"ok": True, "email": "a@b.co", "email_verified": True}

    with patch("tokensaver_cli.auth_cmd.request_json", side_effect=fake_request):
        assert run_verify_email("https://platform.tokensaver.fr/fr/verify-email?token=abc123") == 0


def test_resend_verification(ts_home: Path) -> None:
    save_credentials(Credentials(access_token="jwt", email="a@b.co"))

    def fake_request(method, url, **kwargs):
        assert method.upper() == "POST"
        assert url.endswith("/auths/resend-verification")
        return {"ok": True, "message": "Verification email sent."}

    with patch("tokensaver_cli.auth_cmd.request_json", side_effect=fake_request):
        assert run_resend_verification() == 0


def test_logout_and_whoami(ts_home: Path) -> None:
    save_credentials(Credentials(api_key="tsv_x", email="a@b.co", access_token="jwt"))
    assert run_logout() == 0
    assert load_credentials() is None
    assert run_whoami() == 1


def test_keys_list_create_revoke(ts_home: Path) -> None:
    save_credentials(
        Credentials(
            access_token="jwt",
            api_key="tsv_old",
            key_id="old-id",
            api_host="https://api.example.test",
        )
    )

    def fake_request(method, url, **kwargs):
        if method.upper() == "GET" and url.endswith("/gateway/virtual-keys"):
            return [
                {
                    "id": "old-id",
                    "name": "Old",
                    "key_prefix": "tsv_old",
                    "status": "active",
                    "effective_status": "active",
                }
            ]
        if method.upper() == "POST" and url.endswith("/gateway/virtual-keys"):
            return {"key": "tsv_new_secret_zzzz", "id": "new-id", "key_prefix": "tsv_new_secr"}
        if method.upper() == "DELETE" and "/gateway/virtual-keys/" in url:
            return None
        if url.endswith("/users/me"):
            return {"email": "a@b.co", "workspace": {"id": "ws"}, "organisation": {"id": "org"}}
        raise AssertionError(f"{method} {url}")

    with patch("tokensaver_cli.keys_cmd.request_json", side_effect=fake_request):
        assert run_keys_list() == 0
        assert run_keys_create(name="New", use=True) == 0
        creds = load_credentials()
        assert creds is not None
        assert creds.api_key is None  # never persist plaintext secret
        assert creds.key_id == "new-id"
        assert creds.key_prefix == "tsv_new_secr"
        assert creds.access_token == "jwt"
        assert run_keys_revoke("new-id") == 0
        creds = load_credentials()
        assert creds is not None
        assert creds.api_key is None
        assert creds.key_id is None
        assert creds.access_token == "jwt"
