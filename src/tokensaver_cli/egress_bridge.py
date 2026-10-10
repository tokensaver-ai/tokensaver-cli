"""Bridge TokenSaver CLI ↔ tokensaver-egress saved config (no manual ``source``).

After ``tokensaver-egress setup`` / ``claude --loop``, credentials and the active
BusinessLoop live under ``~/.tokensaver-egress/``. The CLI loads them when env
vars are unset so ``tokensaver loop status --local`` works from any shell.
"""

from __future__ import annotations

import os
from pathlib import Path

_LOOP_AND_AUTH_KEYS = (
    "TOKENSAVER_API_KEY",
    "TOKENSAVER_INGEST_URL",
    "TOKENSAVER_LOOP_ID",
    "TOKENSAVER_LOOP_KIND",
    "TOKENSAVER_LOOP_ITERATION",
    "TOKENSAVER_LOOP_PRECHECK",
)


def _egress_paths() -> tuple[Path, Path]:
    root = Path(
        os.environ.get("EGRESS_CONFIG_DIR", str(Path.home() / ".tokensaver-egress"))
    )
    return root / "env", root / "current-loop.env"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("export "):
            raw = raw[len("export ") :].strip()
        if "=" not in raw:
            continue
        k, _, v = raw.partition("=")
        k = k.strip()
        v = v.strip().strip("'").strip('"')
        if k:
            out[k] = v
    return out


def apply_egress_bridge(*, only_if_unset: bool = True) -> dict[str, str]:
    """Load egress ``env`` + ``current-loop.env`` into ``os.environ`` (auth + loop only)."""
    env_file, loop_file = _egress_paths()
    merged: dict[str, str] = {}
    merged.update(_parse_env_file(env_file))
    merged.update(_parse_env_file(loop_file))
    applied: dict[str, str] = {}
    for k, v in merged.items():
        if k not in _LOOP_AND_AUTH_KEYS or not v:
            continue
        if only_if_unset and (os.environ.get(k) or "").strip():
            continue
        os.environ[k] = v
        applied[k] = v
    return applied
