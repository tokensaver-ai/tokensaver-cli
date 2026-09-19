"""CLI auto-loads ~/.tokensaver-egress env (bridge with tokensaver-egress)."""

from __future__ import annotations

from pathlib import Path

from tokensaver_cli.egress_bridge import apply_egress_bridge


def test_apply_egress_bridge(tmp_path: Path, monkeypatch) -> None:
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

    import os

    assert os.environ["TOKENSAVER_API_KEY"] == "ts_from_egress"
    assert os.environ["TOKENSAVER_LOOP_ID"] == "loop_abc"
