"""List TokenSaver profiles and catalogue models."""

from __future__ import annotations

import sys
from typing import Any

from tokensaver_cli.api_client import ApiError, request_json
from tokensaver_cli.config import RouteConfigError, resolve_route_config
from tokensaver_cli.credentials import resolve_plan_slug
from tokensaver_cli.profiles import PROFILE_NAMES, is_free_plan, profiles_summary
from tokensaver_cli.state import load_state


def _list_api_models() -> list[str]:
    try:
        cfg = resolve_route_config()
    except RouteConfigError:
        return []
    url = f"{cfg.openai_base_url.rstrip('/')}/models"
    try:
        data = request_json(
            "GET",
            url,
            headers={"Authorization": f"Bearer {cfg.api_key}"},
        )
    except ApiError:
        return []
    rows = data.get("data") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    ids: list[str] = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"].strip():
            ids.append(row["id"].strip())
    return sorted(set(ids))


def run_models(*, force_local: bool = False, api_only: bool = False) -> int:
    plan = resolve_plan_slug()
    sticky = None
    rec = load_state().get("claude")
    if rec and isinstance(rec.meta, dict):
        sticky = rec.meta.get("sticky_model") or rec.meta.get("model")

    if not api_only:
        print("TokenSaver model profiles")
        if is_free_plan(plan):
            print(f"  plan: {plan} (Free allowlist defaults)")
        elif plan:
            print(f"  plan: {plan}")
        else:
            print("  plan: unknown (paid/BYOK defaults)")
        if sticky:
            print(f"  sticky (Claude): {sticky}")
        print()
        for row in profiles_summary(plan_slug=plan):
            tag = "builtin" if row["builtin"] else "custom"
            mark = " ← sticky" if sticky and row["model"] == sticky else ""
            print(f"  {row['name']:12}  {row['model']}  ({tag}){mark}")
        print()
        print("Switch: tokensaver use <cheap|default|strong|provider/model>")
        print()

    print("Catalogue (OpenAI-compat /models, plan-filtered)")
    ids = _list_api_models()
    if not ids:
        print("  (none — check API key / TOKENSAVER_MODE / tokensaver doctor)")
        return 1 if api_only else 0
    for mid in ids:
        mark = " ← sticky" if sticky and mid == sticky else ""
        print(f"  {mid}{mark}")
    print()
    print(f"{len(ids)} model(s). Use: tokensaver use <id>")
    return 0


def is_profile_name(value: str) -> bool:
    return value.strip().lower() in PROFILE_NAMES or value.strip().lower() in {
        r["name"] for r in profiles_summary(plan_slug=resolve_plan_slug())
    }
