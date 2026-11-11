"""Resolve a stable project external id from git remote or cwd (ADR-010 cli_git)."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path


def _normalize_git_remote(url: str) -> str:
    u = url.strip()
    if u.endswith(".git"):
        u = u[:-4]
    if u.startswith("git@"):
        # git@github.com:org/repo → github.com/org/repo
        u = u[4:].replace(":", "/", 1)
    elif u.startswith("ssh://"):
        u = re.sub(r"^ssh://[^/]+/", "", u)
    u = re.sub(r"^https?://", "", u)
    return u.strip("/").lower()


def resolve_git_remote_url(*, cwd: Path | None = None) -> str | None:
    root = cwd or Path.cwd()
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    url = (out.stdout or "").strip()
    return url or None


def project_external_id(*, cwd: Path | None = None) -> tuple[str, str]:
    """Return ``(project_external_id, display_hint)``.

    Prefer a short hash of the normalized git remote; fallback to cwd name.
    """
    root = (cwd or Path.cwd()).resolve()
    remote = resolve_git_remote_url(cwd=root)
    if remote:
        norm = _normalize_git_remote(remote)
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
        return f"git:{digest}", norm
    name = root.name or "workspace"
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return f"cwd:{digest}", name


def project_attrs(*, cwd: Path | None = None) -> dict[str, str]:
    ext_id, hint = project_external_id(cwd=cwd)
    remote = resolve_git_remote_url(cwd=cwd)
    attrs: dict[str, str] = {
        "project_external_id": ext_id,
        "project_source": "cli_git" if remote else "cli_cwd",
        "project_hint": hint[:256],
    }
    if remote:
        attrs["git_remote"] = remote[:512]
    attrs["cwd"] = str((cwd or Path.cwd()).resolve())[:512]
    return attrs
