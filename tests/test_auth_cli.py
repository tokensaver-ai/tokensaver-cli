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
    return home


def test_save_load_clear_credentials(ts_home: Path) -> None:
    path = save_credentials(
        Credentials(api_key="ts_abc123456789", email="a@b.co", access_token="jwt")
    )
    assert path == credentials_path()
    assert path.stat().st_mode & 0o777 == 0o600
    loaded = load_credentials()
    assert loaded is not None
    assert loaded.api_key == "ts_abc123456789"
    assert loaded.email == "a@b.co"
    # Session JWT wins over stored ts_… (login path never writes secrets).
    assert resolve_api_key() == "jwt"
    assert clear_credentials() is True
    assert load_credentials() is None


def test_resolve_route_config_uses_credentials(ts_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKENSAVER_API_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_API_BASE_URL", raising=False)
    monkeypatch.delenv("TOKENSAVER_MODE", raising=False)
    save_credentials(
        Credentials(
            api_key="ts_from_file_12345678",
            api_host="https://api.example.test",
            console_url="https://platform.example.test",
            organisation_id="org-1",
            workspace_id="ws-1",
        )
    )
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    cfg = resolve_route_config()
    assert cfg.api_key == "ts_from_file_12345678"
    assert cfg.api_host == "https://api.example.test"
    assert cfg.organisation_id == "org-1"
    assert cfg.workspace_id == "ws-1"


def test_resolve_route_config_env_overrides_credentials(
    ts_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_credentials(Credentials(api_key="ts_file_key_xxxxxxxx"))
    monkeypatch.setenv("TOKENSAVER_API_KEY", "ts_env_key_yyyyyyyy")
    cfg = resolve_route_config()
    assert cfg.api_key == "ts_env_key_yyyyyyyy"


def test_resolve_route_config_suggests_login(ts_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    with pytest.raises(RouteConfigError, match="tokensaver login"):
        resolve_route_config()


def test_login_with_key_only(ts_home: Path) -> None:
    assert run_login(api_key="ts_imported_key_abcdef") == 0
    creds = load_credentials()
    assert creds is not None
    assert creds.api_key == "ts_imported_key_abcdef"
    assert creds.access_token is None


def test_login_signup_flow(ts_home: Path) -> None:
    def fake_request(method, url, **kwargs):
        if url.endswith("/auths/check-email"):
            return {"available": True}
        if url.endswith("/auths/signup"):
            assert kwargs["body"]["create_key"] is True
            return {
                "token": "jwt-signup",
                "id": "user-1",
                "email": "new@example.com",
                "api_key_plain": "ts_signup_key_plainxx",
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
    assert resolve_api_key() == "jwt-signup"
    assert creds.organisation_id == "org-1"


def test_login_signin_uses_session_jwt_without_creating_key(ts_home: Path) -> None:
    """Existing account: no POST /api-keys — JWT is enough for route (console-style)."""
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
            raise AssertionError("signin must not create API keys")
        raise AssertionError(url)

    with patch("tokensaver_cli.auth_cmd.request_json", side_effect=fake_request):
        assert run_login(email="old@example.com", password="password123", signup=False) == 0
    creds = load_credentials()
    assert creds is not None
    assert creds.api_key is None
    assert creds.access_token == "jwt-session-token"
    assert resolve_api_key() == "jwt-session-token"
    assert not any("/api-keys" in c for c in calls)


def test_login_signin_clears_previous_local_secret(ts_home: Path) -> None:
    """Re-login must drop any leftover ts_… secret — JWT only."""
    save_credentials(
        Credentials(
            api_key="ts_previous_key_xxxxx",
            email="old@example.com",
            key_prefix="ts_previous",
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
        raise AssertionError(url)

    with patch("tokensaver_cli.auth_cmd.request_json", side_effect=fake_request):
        assert run_login(email="old@example.com", password="password123", signup=False) == 0
    creds = load_credentials()
    assert creds is not None
    assert creds.api_key is None
    assert creds.key_id is None
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
    save_credentials(Credentials(api_key="ts_x", email="a@b.co", access_token="jwt"))
    assert run_logout() == 0
    assert load_credentials() is None
    assert run_whoami() == 1


def test_keys_list_create_revoke(ts_home: Path) -> None:
    save_credentials(
        Credentials(
            access_token="jwt",
            api_key="ts_old",
            key_id="old-id",
            api_host="https://api.example.test",
        )
    )

    def fake_request(method, url, **kwargs):
        if method.upper() == "GET" and url.endswith("/api-keys"):
            return {
                "api_keys": [
                    {
                        "id": "old-id",
                        "name": "Old",
                        "key_prefix": "ts_old",
                        "is_active": True,
                    }
                ]
            }
        if method.upper() == "POST" and url.endswith("/api-keys"):
            return {"api_key": "ts_new_secret_zzzz", "id": "new-id", "key_prefix": "ts_new_secr"}
        if method.upper() == "DELETE":
            return {"success": True}
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
        assert creds.key_prefix == "ts_new_secr"
        assert creds.access_token == "jwt"
        assert run_keys_revoke("new-id") == 0
        creds = load_credentials()
        assert creds is not None
        assert creds.api_key is None
        assert creds.key_id is None
        assert creds.access_token == "jwt"


def test_api_error_format() -> None:
    err = ApiError(400, {"detail": {"error_code": "EMAIL_ALREADY_EXISTS", "message": "taken"}})
    assert "400" in str(err)
