"""Select Claude routing model/profile (sticky) in one command."""

from __future__ import annotations

import sys

from tokensaver_cli.agents import route_claude
from tokensaver_cli.config import RouteConfigError, resolve_route_config
from tokensaver_cli.models_cmd import is_profile_name
from tokensaver_cli.profiles import PROFILE_NAMES


def run_use(
    choice: str | None,
    *,
    force_local: bool = False,
    scope: str | None = None,
    with_fs: bool = False,
    launch: bool = False,
) -> int:
    value = (choice or "").strip()
    if not value:
        print(
            "Usage: tokensaver use <cheap|default|strong|provider/model>\n"
            "Examples:\n"
            "  tokensaver use cheap\n"
            "  tokensaver use openrouter/z-ai/glm-4.7-flash\n"
            "  tokensaver models   # list options",
            file=sys.stderr,
        )
        return 2

    try:
        cfg = resolve_route_config(force_local=force_local)
    except RouteConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    profile = None
    model = None
    if is_profile_name(value) or value.lower() in PROFILE_NAMES:
        profile = value.lower()
    else:
        model = value

    code = route_claude(
        cfg,
        launch=launch,
        extra_args=[],
        scope=scope or "user",  # type: ignore[arg-type]
        model=model,
        profile=profile,
        with_fs=with_fs,
        install_plugin=True,
    )
    if code != 0:
        return code

    from tokensaver_cli.state import load_state

    mid = model
    if mid is None:
        rec = load_state().get("claude")
        mid = (rec.meta.get("model") if rec else None) or value
    print(f"OK  Claude model → {mid} (sticky)")
    return 0
