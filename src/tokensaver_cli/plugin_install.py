"""Install the bundled Claude Code plugin into ``~/.claude/skills/``."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path


PLUGIN_SKILL_NAME = "tokensaver-router"


def plugin_install_dir() -> Path:
    return Path.home() / ".claude" / "skills" / PLUGIN_SKILL_NAME


def _dev_plugin_root() -> Path | None:
    here = Path(__file__).resolve().parent / "claude_plugin"
    if (here / ".claude-plugin" / "plugin.json").is_file():
        return here
    return None


def install_claude_plugin(*, force: bool = True) -> Path | None:
    """Copy the bundled plugin into Claude Code's skills-dir auto-load path.

    Returns the install directory, or ``None`` if the bundle is missing.
    """
    dest = plugin_install_dir()
    if dest.exists() and not force:
        return dest
    if dest.exists() and force:
        shutil.rmtree(dest)

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Prefer importlib resources (installed wheel), then monorepo path.
    try:
        root = resources.files("tokensaver_cli").joinpath("claude_plugin")
        with resources.as_file(root) as path:
            if path.is_dir() and (path / ".claude-plugin" / "plugin.json").is_file():
                shutil.copytree(path, dest)
                return dest
    except (TypeError, ModuleNotFoundError, AttributeError, FileNotFoundError, NotADirectoryError, OSError):
        pass

    src = _dev_plugin_root()
    if src is None:
        return None
    shutil.copytree(src, dest)
    return dest
