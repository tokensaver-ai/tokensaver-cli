"""Retro ASCII banner shown when the ``tokensaver`` command starts."""

from __future__ import annotations

import os
import sys

from tokensaver_cli import __version__
from tokensaver_cli.logo import LOGO_LINES

_LOGO_BLOCK = "\n".join(f"  {line}" for line in LOGO_LINES)
_BANNER = f"""
{_LOGO_BLOCK}

        ┌─────────────────────────────────────────────────────────────┐
        │  CONTROL PLANE  ·  route  ·  compress  ·  govern  ·  save   │
        │  Claude Code · Cursor · Codex · LangChain · your code       │
        └─────────────────────────────────────────────────────────────┘
"""


def banner_enabled() -> bool:
    flag = (os.environ.get("TOKENSAVER_NO_BANNER") or "").strip().lower()
    return flag not in ("1", "true", "yes", "on")


def print_banner(*, file=None) -> None:
    if not banner_enabled():
        return
    out = file if file is not None else sys.stdout
    print(_BANNER, file=out)
    print(f"  TokenSaver CLI v{__version__}  —  https://platform.tokensaver.fr", file=out)
    print(file=out)
