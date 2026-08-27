"""Approve Agent Registry (catalog) models from the CLI — unblocks zero-trust 403."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.auth_cmd import _api_host, _api_v1
from tokensaver_cli.config import resolve_route_config
from tokensaver_cli.credentials import load_credentials, resolve_api_key


def _auth_headers() -> dict[str, str]:
    key = resolve_api_key()
    if not key:
        raise ApiError(401, "No API key. Run: tokensaver login")
    return {"Authorization": f"Bearer {key}"}


def _api_base(*, force_local: bool = False) -> str:
    creds = load_credentials()
    host = (creds.api_host if creds and creds.api_host else None) or _api_host(force_local=force_local)
    # Prefer resolved route host when env/credentials agree (local vs SaaS).
    try:
        host = resolve_route_config(force_local=force_local).api_host
    except Exception:
        pass
    return _api_v1(host)


def resolve_current_model_ref() -> str | None:
    """ANTHROPIC_MODEL env, else ~/.claude/settings.json env patch."""
    env = (os.environ.get("ANTHROPIC_MODEL") or "").strip()
    if env:
        return env
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.is_file():
        return None
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    env_block = data.get("env") if isinstance(data, dict) else None
    if isinstance(env_block, dict):
        mid = env_block.get("ANTHROPIC_MODEL")
        if isinstance(mid, str) and mid.strip():
            return mid.strip()
    return None


def find_catalog_asset(
    api_v1: str,
    ref: str,
    *,
    asset_type: str = "model",
) -> dict[str, Any] | None:
    url = f"{api_v1}/sdk/catalog/assets?q={quote(ref)}&type={quote(asset_type)}&limit=20"
    data = request_json("GET", url, headers=_auth_headers())
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    exact = [
        i
        for i in items
        if isinstance(i, dict) and str(i.get("ref") or "").lower() == ref.lower()
    ]
    if exact:
        return exact[0]
    return items[0] if items and isinstance(items[0], dict) else None


def _find_via_jwt(api_v1: str, ref: str, *, asset_type: str) -> dict[str, Any] | None:
    from tokensaver_cli.credentials import resolve_access_token

    token = resolve_access_token()
    if not token:
        return None
    url = f"{api_v1}/catalog/assets?q={quote(ref)}&type={quote(asset_type)}&limit=20"
    data = request_json("GET", url, headers={"Authorization": f"Bearer {token}"})
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    exact = [
        i
        for i in items
        if isinstance(i, dict) and str(i.get("ref") or "").lower() == ref.lower()
    ]
    if exact:
        return exact[0]
    return items[0] if items and isinstance(items[0], dict) else None


def lookup_catalog_asset(
    ref: str,
    *,
    asset_type: str = "model",
    force_local: bool = False,
) -> dict[str, Any] | None:
    """Return the catalog asset for ``ref`` if present, else ``None``."""
    api_v1 = _api_base(force_local=force_local)
    try:
        return find_catalog_asset(api_v1, ref, asset_type=asset_type)
    except ApiError:
        return _find_via_jwt(api_v1, ref, asset_type=asset_type)


def catalog_model_status(
    ref: str,
    *,
    asset_type: str = "model",
    force_local: bool = False,
) -> str:
    """Return status string: approved|quarantined|discovered|disabled|missing."""
    asset = lookup_catalog_asset(ref, asset_type=asset_type, force_local=force_local)
    if not asset:
        return "missing"
    status = str(asset.get("status") or "").strip().lower()
    return status or "missing"


def _stdin_is_tty() -> bool:
    return hasattr(sys.stdin, "isatty") and sys.stdin.isatty()


def _env_auto_approve() -> bool:
    return (os.environ.get("TOKENSAVER_AUTO_APPROVE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
    )


def _prompt_zero_trust_approve(ref: str, status: str) -> bool:
    """Explain zero-trust and ask Y/n. Returns True if user accepts."""
    status_label = {
        "missing": "not registered",
        "quarantined": "quarantined",
        "discovered": "discovered (not approved)",
        "disabled": "disabled",
    }.get(status, status)
    print(file=sys.stderr)
    print("────────────────────────────────────────", file=sys.stderr)
    print("  TokenSaver zero-trust policy", file=sys.stderr)
    print("────────────────────────────────────────", file=sys.stderr)
    print(f"  Model   {ref}", file=sys.stderr)
    print(f"  Status  {status_label}", file=sys.stderr)
    print(file=sys.stderr)
    print(
        "  Unapproved models are blocked until you allow them in the",
        file=sys.stderr,
    )
    print(
        "  Agent Registry. This is TokenSaver's zero-trust security",
        file=sys.stderr,
    )
    print(
        "  policy — approve once to continue with this model.",
        file=sys.stderr,
    )
    print(file=sys.stderr)
    try:
        answer = input("  Approve this model now? [Y/n] ").strip().lower()
    except EOFError:
        return False
    return answer in ("", "y", "yes")


def ensure_model_approved(
    ref: str,
    *,
    asset_type: str = "model",
    force_local: bool = False,
    interactive: bool | None = None,
) -> bool:
    """Ensure ``ref`` is approved in Agent Registry.

    Interactive TTY: prompt with a short zero-trust explanation when the model
    is not yet approved. Non-interactive (or ``TOKENSAVER_AUTO_APPROVE=1``):
    approve silently (previous CLI behaviour).

    Returns True when the model is approved and ready for egress.
    """
    ref = (ref or "").strip()
    if not ref:
        return False

    try:
        status = catalog_model_status(
            ref, asset_type=asset_type, force_local=force_local
        )
    except ApiError as exc:
        print(f"WARN  Agent Registry lookup failed ({exc})", file=sys.stderr)
        status = "missing"

    if status == "approved":
        print(f"Agent Registry → {ref} (already approved)", file=sys.stderr)
        return True

    if status == "disabled":
        print(
            f"FAIL  {ref} is disabled in Agent Registry — re-enable it in the console.",
            file=sys.stderr,
        )
        return False

    ask = interactive if interactive is not None else _stdin_is_tty()
    if ask and not _env_auto_approve():
        if not _prompt_zero_trust_approve(ref, status):
            print(
                f"Skipped. To approve later: tokensaver approve {ref}",
                file=sys.stderr,
            )
            return False
    else:
        print(
            f"Agent Registry → approving {ref} (zero-trust)…",
            file=sys.stderr,
        )

    try:
        asset = approve_catalog_ref(
            ref, asset_type=asset_type, force_local=force_local
        )
    except ApiError as exc:
        msg = str(exc)
        if "verify your email" in msg.lower():
            print(
                "FAIL  Email not verified — confirm your inbox before approving models.",
                file=sys.stderr,
            )
            print(
                "      Open https://platform.tokensaver.fr → Account / Settings.",
                file=sys.stderr,
            )
        else:
            print(f"FAIL  could not approve {ref} — {exc}", file=sys.stderr)
            print(
                "      Need admin API key (tokensaver login). "
                "Console: Governance → Agent Registry.",
                file=sys.stderr,
            )
        return False

    print(
        f"OK  Agent Registry → {ref}  status={asset.get('status') or 'approved'}",
        file=sys.stderr,
    )
    return True


def approve_catalog_ref(
    ref: str,
    *,
    asset_type: str = "model",
    force_local: bool = False,
) -> dict[str, Any]:
    """Create (approved) or patch status=approved for ``ref``. Returns asset dict."""
    api_v1 = _api_base(force_local=force_local)
    headers = _auth_headers()
    ref = ref.strip()
    if not ref:
        raise ApiError(400, "Empty model ref")

    existing: dict[str, Any] | None = None
    try:
        existing = find_catalog_asset(api_v1, ref, asset_type=asset_type)
    except ApiError:
        existing = _find_via_jwt(api_v1, ref, asset_type=asset_type)

    if existing and existing.get("status") == "approved":
        return existing

    if existing and existing.get("id"):
        asset_id = str(existing["id"])
        if existing.get("status") == "disabled":
            raise ApiError(
                403,
                f"Asset {ref!r} is disabled — re-enable from Agent Registry first.",
            )
        return request_json(
            "PATCH",
            f"{api_v1}/sdk/catalog/assets/{asset_id}",
            headers=headers,
            body={"status": "approved"},
        )

    try:
        return request_json(
            "POST",
            f"{api_v1}/sdk/catalog/assets",
            headers=headers,
            body={
                "type": asset_type,
                "ref": ref,
                "display_name": ref,
                "status": "approved",
                "description": "Approved via tokensaver CLI",
            },
        )
    except ApiError as exc:
        # Race / already observed as quarantined
        detail = str(exc.detail).lower() if exc.detail else str(exc).lower()
        if exc.status not in (409, 400) and "already exists" not in detail:
            raise
        existing = None
        try:
            existing = find_catalog_asset(api_v1, ref, asset_type=asset_type)
        except ApiError:
            existing = _find_via_jwt(api_v1, ref, asset_type=asset_type)
        if not existing or not existing.get("id"):
            raise
        return request_json(
            "PATCH",
            f"{api_v1}/sdk/catalog/assets/{existing['id']}",
            headers=headers,
            body={"status": "approved"},
        )


def run_approve(
    ref: str | None = None,
    *,
    current: bool = False,
    asset_type: str = "model",
    force_local: bool = False,
    quiet: bool = False,
) -> int:
    target = (ref or "").strip()
    if current or not target:
        target = resolve_current_model_ref() or target
    if not target:
        print(
            "Usage: tokensaver approve <provider/model>\n"
            "   or: tokensaver approve --current\n"
            "Example: tokensaver approve openrouter/z-ai/glm-4.7-flash",
            file=sys.stderr,
        )
        return 2

    try:
        asset = approve_catalog_ref(target, asset_type=asset_type, force_local=force_local)
    except ApiError as exc:
        if not quiet:
            print(f"FAIL  approve {target} — {exc}", file=sys.stderr)
            print(
                "Need admin API key (tokensaver login). Console: Governance → Agent Registry.",
                file=sys.stderr,
            )
        return 1

    status = asset.get("status") or "approved"
    asset_id = asset.get("id") or "?"
    if quiet:
        print(f"approved:{target}:{status}")
    else:
        print(f"OK  Agent Registry → {target}")
        print(f"    status={status}  id={asset_id}")
        print("    Retry your Claude Code message — zero-trust should allow this model.")
    return 0
