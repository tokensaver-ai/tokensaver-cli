"""Model profiles for ``tokensaver route claude --profile``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tokensaver_cli.state import route_state_dir

# Paid / BYOK defaults (catalogue provider/model_id).
BUILTIN_PROFILES: dict[str, str] = {
    "cheap": "openai/gpt-4.1-mini",
    "default": "anthropic/claude-sonnet-4-6",
    "strong": "anthropic/claude-opus-4-6",
}

# Hosted Free allowlist — must stay inside apps/backend/data/plan_model_access.json.
# Default Free chat UX: GPT-OSS 20B (openrouter/openai/gpt-oss-20b).
FREE_PROFILES: dict[str, str] = {
    "cheap": "openrouter/openai/gpt-5-nano",
    "default": "openrouter/openai/gpt-oss-20b",
    "strong": "openrouter/deepseek/deepseek-chat-v3-0324",
}

FREE_DEFAULT_MODEL = FREE_PROFILES["default"]

PROFILE_NAMES = ("cheap", "default", "strong")


def profiles_file() -> Path:
    return route_state_dir() / "profiles.json"


def is_free_plan(plan_slug: str | None) -> bool:
    if not plan_slug:
        return False
    return plan_slug.strip().lower() in {"free", "trial", "free_trial"}


def load_profiles(*, plan_slug: str | None = None) -> dict[str, str]:
    """Merge builtins (plan-aware) with optional user overrides in profiles.json."""
    base = dict(FREE_PROFILES) if is_free_plan(plan_slug) else dict(BUILTIN_PROFILES)
    path = profiles_file()
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return base
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(key, str) and isinstance(value, str) and value.strip():
                    base[key.strip().lower()] = value.strip()
    return base


def save_profiles(profiles: dict[str, str]) -> None:
    path = profiles_file()
    path.write_text(json.dumps(profiles, indent=2) + "\n", encoding="utf-8")


def resolve_model(
    *,
    model: str | None,
    profile: str | None,
    plan_slug: str | None = None,
    sticky_model: str | None = None,
) -> tuple[str | None, str | None]:
    """Return ``(model_id, profile_name)``.

    Precedence: ``--model`` > ``--profile`` > sticky (last explicit choice) > plan default.
    """
    profiles = load_profiles(plan_slug=plan_slug)
    if model and model.strip():
        mid = model.strip()
        matched = next((name for name, value in profiles.items() if value == mid), None)
        return mid, matched
    if profile and profile.strip():
        name = profile.strip().lower()
        if name not in profiles:
            known = ", ".join(sorted(profiles))
            raise ValueError(f"Unknown profile {profile!r}. Known: {known}")
        return profiles[name], name
    if sticky_model and sticky_model.strip():
        mid = sticky_model.strip()
        matched = next((name for name, value in profiles.items() if value == mid), None)
        return mid, matched
    return profiles.get("default"), "default"


def profiles_summary(*, plan_slug: str | None = None) -> list[dict[str, Any]]:
    profiles = load_profiles(plan_slug=plan_slug)
    reference = FREE_PROFILES if is_free_plan(plan_slug) else BUILTIN_PROFILES
    rows: list[dict[str, Any]] = []
    for name in sorted(profiles):
        rows.append(
            {
                "name": name,
                "model": profiles[name],
                "builtin": name in reference and profiles[name] == reference[name],
                "plan": "free" if is_free_plan(plan_slug) else (plan_slug or "paid"),
            }
        )
    return rows
