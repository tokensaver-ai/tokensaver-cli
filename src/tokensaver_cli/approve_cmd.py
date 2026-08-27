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
    return sys.stdin.isatty() and sys.stderr.isatty()


def _env_auto_approve() -> bool:
    return (os.environ.get("TOKENSAVER_AUTO_APPROVE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
    )


def _selectable_models(default_ref: str) -> list[str]:
    """Plan-filtered catalogue + profiles, default first.

    Free plan: **only** the hosted allowlist (~15 models) — never the full
    OpenAI-compat ``/models`` dump (local backends often return the whole catalog).
    Paid/BYOK: profiles + live ``/models``.
    """
    from tokensaver_cli.credentials import resolve_plan_slug
    from tokensaver_cli.models_cmd import _list_api_models
    from tokensaver_cli.profiles import (
        free_allowlist_models,
        is_free_plan,
        load_profiles,
    )

    plan = resolve_plan_slug()
    profiles = load_profiles(plan_slug=plan)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(mid: str) -> None:
        m = (mid or "").strip()
        if not m or m in seen:
            return
        seen.add(m)
        ordered.append(m)

    _add(default_ref)
    for name in ("cheap", "default", "strong"):
        if name in profiles:
            _add(profiles[name])
    for mid in profiles.values():
        _add(mid)

    if is_free_plan(plan):
        for mid in free_allowlist_models():
            _add(mid)
    else:
        for mid in _list_api_models():
            _add(mid)
    return ordered or ([default_ref] if default_ref else [])


def _prompt_pick_and_approve(default_ref: str, status: str) -> str | None:
    """List plan models, let the user pick one (or keep Enter default). Returns chosen ref or None."""
    status_label = {
        "missing": "not registered",
        "quarantined": "quarantined",
        "discovered": "discovered (not approved)",
        "disabled": "disabled",
    }.get(status, status)

    from tokensaver_cli.credentials import resolve_plan_slug
    from tokensaver_cli.profiles import is_free_plan, load_profiles

    plan = resolve_plan_slug()
    profiles = load_profiles(plan_slug=plan)
    plan_default = (profiles.get("default") or "").strip() or default_ref
    # Free: Enter always validates the plan default profile, not a leftover sticky model.
    enter_ref = plan_default if is_free_plan(plan) else default_ref

    choices = _selectable_models(enter_ref)
    # Keep the previously requested model visible even if it is not Enter-default.
    if default_ref and default_ref not in choices:
        choices.append(default_ref)

    print(file=sys.stderr)
    print("────────────────────────────────────────", file=sys.stderr)
    print("  TokenSaver zero-trust · choose a model", file=sys.stderr)
    print("────────────────────────────────────────", file=sys.stderr)
    if default_ref and default_ref != enter_ref:
        print(f"  Previous {default_ref}", file=sys.stderr)
    print(f"  Enter →  {enter_ref}", file=sys.stderr)
    print(f"  Status   {status_label}", file=sys.stderr)
    print(file=sys.stderr)
    print("  Unapproved models are blocked until allowed in the Agent Registry.", file=sys.stderr)
    print(file=sys.stderr)
    profile_by_model = {v: k for k, v in profiles.items()}
    if is_free_plan(plan):
        print(f"  Free plan models ({len(choices)}):", file=sys.stderr)
    else:
        print(f"  Available models ({len(choices)}):", file=sys.stderr)
    for i, mid in enumerate(choices, start=1):
        tags: list[str] = []
        prof = profile_by_model.get(mid)
        if prof:
            tags.append(f"[{prof}]")
        if mid == enter_ref:
            tags.append("← Enter")
        elif mid == default_ref:
            tags.append("previous")
        tag_bit = f"  {' '.join(tags)}" if tags else ""
        print(f"  {i:2}. {mid}{tag_bit}", file=sys.stderr)
    print(file=sys.stderr)
    print("  Enter = approve default · number = pick another · q = cancel", file=sys.stderr)
    try:
        answer = input("  Model [Enter] ").strip().lower()
    except EOFError:
        return None
    if answer in ("q", "quit", "n", "no"):
        return None
    if answer in ("", "y", "yes"):
        return enter_ref
    if answer.isdigit():
        idx = int(answer)
        if 1 <= idx <= len(choices):
            return choices[idx - 1]
        print(f"  Invalid choice {answer!r} — cancelled.", file=sys.stderr)
        return None
    # Allow typing a full provider/model id (Free: must stay on allowlist)
    if "/" in answer:
        from tokensaver_cli.profiles import is_free_allowlisted, is_free_plan

        if is_free_plan(plan) and not is_free_allowlisted(answer):
            print(
                f"  {answer!r} is not on the Free plan allowlist — cancelled.",
                file=sys.stderr,
            )
            print(
                "      See: tokensaver models   or docs/models-and-free-plan.md",
                file=sys.stderr,
            )
            return None
        return answer
    print(f"  Invalid choice {answer!r} — cancelled.", file=sys.stderr)
    return None


def ensure_model_approved(
    ref: str,
    *,
    asset_type: str = "model",
    force_local: bool = False,
    interactive: bool | None = None,
    allow_pick: bool = False,
) -> str | None:
    """Ensure a model is approved in Agent Registry.

    Returns the approved model ref (may differ from ``ref`` when ``allow_pick``
    and the user chooses another), or ``None`` if cancelled / failed.

    Interactive TTY: list plan models (Free allowlist) and pick before approve.
    On Free + ``allow_pick`` (``tokensaver route claude``), the list is always
    shown so the user can confirm/change — Enter selects the Free plan default.
    Non-interactive (or ``TOKENSAVER_AUTO_APPROVE=1``): approve ``ref`` silently.
    """
    from tokensaver_cli.credentials import resolve_plan_slug
    from tokensaver_cli.profiles import is_free_plan, load_profiles

    ref = (ref or "").strip()
    if not ref:
        return None

    try:
        status = catalog_model_status(
            ref, asset_type=asset_type, force_local=force_local
        )
    except ApiError as exc:
        print(f"WARN  Agent Registry lookup failed ({exc})", file=sys.stderr)
        status = "missing"

    if status == "disabled":
        print(
            f"FAIL  {ref} is disabled in Agent Registry — re-enable it in the console.",
            file=sys.stderr,
        )
        return None

    ask = interactive if interactive is not None else _stdin_is_tty()
    plan = resolve_plan_slug()
    # Free route: always offer the allowlist (Enter = plan default), even if
    # the sticky/current model is already approved.
    free_pick = bool(
        allow_pick
        and is_free_plan(plan)
        and ask
        and not _env_auto_approve()
    )

    if status == "approved" and not free_pick:
        print(f"Agent Registry → {ref} (already approved)", file=sys.stderr)
        return ref

    chosen = ref
    show_picker = free_pick or (ask and not _env_auto_approve() and status != "approved")
    if show_picker:
        prompt_status = status
        if free_pick:
            plan_default = (load_profiles(plan_slug=plan).get("default") or ref).strip()
            if plan_default != ref:
                try:
                    prompt_status = catalog_model_status(
                        plan_default, asset_type=asset_type, force_local=force_local
                    )
                except ApiError:
                    prompt_status = "missing"
        picked = _prompt_pick_and_approve(ref, prompt_status)
        if not picked:
            print(
                f"Skipped. To approve later: tokensaver approve {ref}",
                file=sys.stderr,
            )
            return None
        chosen = picked
        if chosen != ref:
            print(f"  → selected {chosen}", file=sys.stderr)
        try:
            status = catalog_model_status(
                chosen, asset_type=asset_type, force_local=force_local
            )
        except ApiError:
            status = "missing"
        if status == "approved":
            print(f"Agent Registry → {chosen} (already approved)", file=sys.stderr)
            return chosen
        if status == "disabled":
            print(
                f"FAIL  {chosen} is disabled in Agent Registry.",
                file=sys.stderr,
            )
            return None
    else:
        print(
            f"Agent Registry → approving {chosen} (zero-trust)…",
            file=sys.stderr,
        )

    try:
        asset = approve_catalog_ref(
            chosen, asset_type=asset_type, force_local=force_local
        )
    except ApiError as exc:
        msg = str(exc)
        if "verify your email" in msg.lower():
            print(
                "FAIL  Email not verified — confirm your inbox before approving models.",
                file=sys.stderr,
            )
            print(
                "      Open https://platform.tokensaver.fr → Account / Settings,",
                file=sys.stderr,
            )
            print(
                "      or: tokensaver resend-verification / tokensaver verify-email '<link>'",
                file=sys.stderr,
            )
        else:
            print(f"FAIL  could not approve {chosen} — {exc}", file=sys.stderr)
            print(
                "      Need admin API key (tokensaver login). "
                "Console: Governance → Agent Registry.",
                file=sys.stderr,
            )
        return None

    final_status = asset.get("status") or "approved"
    print(f"OK  Agent Registry → {chosen} ({final_status})", file=sys.stderr)
    return chosen


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
        print(f"approved:{target}:{status}", file=sys.stderr)
    else:
        print(f"OK  Agent Registry → {target}")
        print(f"    status={status}  id={asset_id}")
        print("    Retry your Claude Code message — zero-trust should allow this model.")
    return 0
