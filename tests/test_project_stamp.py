"""Unit tests for cli_git / cwd project stamp."""

from __future__ import annotations

from pathlib import Path

from tokensaver_cli.project_stamp import (
    _normalize_git_remote,
    project_attrs,
    project_external_id,
)


def test_normalize_git_remote_https() -> None:
    assert _normalize_git_remote("https://github.com/acme/app.git") == "github.com/acme/app"


def test_normalize_git_remote_ssh() -> None:
    assert "github.com" in _normalize_git_remote("git@github.com:acme/app.git")


def test_project_external_id_cwd_fallback(tmp_path: Path) -> None:
    # tmp_path is not a git repo → cwd stamp
    ext, hint = project_external_id(cwd=tmp_path)
    assert ext.startswith("cwd:")
    assert hint == tmp_path.name
    attrs = project_attrs(cwd=tmp_path)
    assert attrs["project_source"] == "cli_cwd"
    assert attrs["project_external_id"] == ext
