"""API key management via session JWT."""

from __future__ import annotations

import sys
from typing import Any

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.auth_cmd import _api_host, _api_v1, _console_url
from tokensaver_cli.credentials import (
    Credentials,
    load_credentials,
    resolve_access_token,
    save_credentials,
)


def _require_token(*, force_local: bool = False) -> tuple[str, str, Credentials | None]:
    token = resolve_access_token()
    if not token:
        print(
            "Session JWT required. Run: tokensaver login\n"
            "(Importing only --key does not unlock keys management.)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    creds = load_credentials()
    api_host = (creds.api_host if creds and creds.api_host else None) or _api_host(force_local=force_local)
    return token, _api_v1(api_host), creds


def run_keys_list(*, force_local: bool = False) -> int:
    token, api_v1, _creds = _require_token(force_local=force_local)
    try:
        data = request_json(
            "GET",
            f"{api_v1}/api-keys",
            headers={"Authorization": f"Bearer {token}"},
        )
    except ApiError as exc:
        print(f"FAIL  list keys — {exc}", file=sys.stderr)
        return 1

    keys = data.get("api_keys") or []
    if not keys:
        print("No API keys. Create one: tokensaver keys create --name CLI --use")
        return 0

    print(f"{'PREFIX':14}  {'ACTIVE':6}  {'NAME':24}  ID")
    for row in keys:
        if not isinstance(row, dict):
            continue
        active = "yes" if row.get("is_active") else "no"
        name = (row.get("name") or "")[:24]
        prefix = (row.get("key_prefix") or "")[:14]
        print(f"{prefix:14}  {active:6}  {name:24}  {row.get('id')}")
    return 0


def run_keys_create(
    *,
    name: str = "CLI",
    description: str | None = None,
    use: bool = False,
    force_local: bool = False,
) -> int:
    token, api_v1, creds = _require_token(force_local=force_local)
    body: dict[str, Any] = {"name": name.strip() or "CLI"}
    if description:
        body["description"] = description
    try:
        data = request_json(
            "POST",
            f"{api_v1}/api-keys",
            headers={"Authorization": f"Bearer {token}"},
            body=body,
        )
    except ApiError as exc:
        print(f"FAIL  create key — {exc}", file=sys.stderr)
        detail = str(exc.detail or exc).lower()
        if exc.status == 403 and ("quota" in detail or "maximum" in detail or "api key" in detail):
            print(
                "Free plan allows 1 key. Claude / MCP already use your session JWT\n"
                "(backend maps it to that key). No need to create another.",
                file=sys.stderr,
            )
        return 1

    plain = data.get("api_key")
    key_id = data.get("id")
    prefix = data.get("key_prefix")
    print("Created API key (shown once — copy if you need it for CI):")
    print(f"  {plain}")
    print(f"  id={key_id}  prefix={prefix}")
    print("OSS CLI does not store API key secrets; session JWT remains the default Bearer.")

    if use:
        # Metadata only — never persist the plaintext secret on disk.
        base = creds or Credentials()
        api_host = base.api_host or _api_host(force_local=force_local)
        console = base.console_url or _console_url(force_local=force_local, api_host=api_host)
        updated = Credentials(
            api_key=None,
            access_token=token,
            email=base.email,
            user_id=base.user_id,
            workspace_id=base.workspace_id,
            organisation_id=base.organisation_id,
            key_id=str(key_id) if key_id else None,
            key_prefix=str(prefix) if prefix else None,
            api_host=api_host,
            console_url=console,
            plan_slug=base.plan_slug,
        )
        path = save_credentials(updated)
        print(f"Recorded key metadata → {path} (JWT Bearer unchanged)")
    return 0


def run_keys_revoke(key_id: str, *, force_local: bool = False) -> int:
    token, api_v1, creds = _require_token(force_local=force_local)
    kid = key_id.strip()
    if not kid:
        print("Usage: tokensaver keys revoke <key-id>", file=sys.stderr)
        return 2
    try:
        request_json(
            "DELETE",
            f"{api_v1}/api-keys?id={kid}",
            headers={"Authorization": f"Bearer {token}"},
        )
    except ApiError as exc:
        print(f"FAIL  revoke key — {exc}", file=sys.stderr)
        return 1

    print(f"Deleted API key {kid}")
    if creds and creds.key_id == kid:
        creds.api_key = None
        creds.key_id = None
        creds.key_prefix = None
        save_credentials(creds)
        print("Cleared key metadata from local credentials (JWT kept).")
        print("Claude / MCP keep using the session JWT → backend API key mapping.")
    return 0
