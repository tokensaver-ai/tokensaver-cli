"""CLI auto-loads ~/.tokensaver-egress env (bridge with tokensaver-egress)."""

from __future__ import annotations

import os
from pathlib import Path

from tokensaver_cli.credentials import Credentials, save_credentials
from tokensaver_cli.egress_bridge import apply_egress_bridge


def test_apply_egress_bridge(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("EGRESS_CONFIG_DIR", str(tmp_path))
    (tmp_path / "env").write_text(
        "TOKENSAVER_API_KEY=ts_from_egress\n"
        "TOKENSAVER_INGEST_URL=http://localhost:8000/api/v1/egress/ingest\n",
        encoding="utf-8",
    )
    (tmp_path / "current-loop.env").write_text(
        "export TOKENSAVER_LOOP_ID='loop_abc'\n"
        "export TOKENSAVER_LOOP_KIND='goal_based'\n",
        encoding="utf-8",
    )
    for k in (
        "TOKENSAVER_API_KEY",
        "TOKENSAVER_INGEST_URL",
        "TOKENSAVER_LOOP_ID",
    ):
        monkeypatch.delenv(k, raising=False)

    applied = apply_egress_bridge(only_if_unset=True)
    assert applied["TOKENSAVER_API_KEY"] == "ts_from_egress"
    assert applied["TOKENSAVER_LOOP_ID"] == "loop_abc"

    assert os.environ["TOKENSAVER_API_KEY"] == "ts_from_egress"
    assert os.environ["TOKENSAVER_LOOP_ID"] == "loop_abc"


def test_apply_egress_bridge_skips_api_key_when_login_jwt(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("EGRESS_CONFIG_DIR", str(tmp_path / "egress"))
    (tmp_path / "egress").mkdir()
    (tmp_path / "egress" / "env").write_text(
        "TOKENSAVER_API_KEY=ts_from_egress\n"
        "TOKENSAVER_LOOP_ID=loop_keep\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TOKENSAVER_API_KEY", raising=False)
    monkeypatch.delenv("TOKENSAVER_LOOP_ID", raising=False)
    save_credentials(
        Credentials(access_token="jwt-session", api_host="http://localhost:8000")
    )

    applied = apply_egress_bridge(only_if_unset=True)
    assert "TOKENSAVER_API_KEY" not in applied
    assert applied.get("TOKENSAVER_LOOP_ID") == "loop_keep"
    assert not (os.environ.get("TOKENSAVER_API_KEY") or "").strip()
