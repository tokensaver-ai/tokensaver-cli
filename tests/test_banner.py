"""Banner tests."""

from tokensaver_cli.banner import banner_enabled, print_banner


def test_banner_enabled_default(monkeypatch) -> None:
    monkeypatch.delenv("TOKENSAVER_NO_BANNER", raising=False)
    assert banner_enabled() is True


def test_banner_disabled(monkeypatch) -> None:
    monkeypatch.setenv("TOKENSAVER_NO_BANNER", "1")
    assert banner_enabled() is False


def test_print_banner_runs(capsys, monkeypatch) -> None:
    monkeypatch.delenv("TOKENSAVER_NO_BANNER", raising=False)
    print_banner()
    out = capsys.readouterr().out
    assert "TokenSaver CLI" in out
    assert "CONTROL PLANE" in out
    # K must use the diagonal glyph (██║ ██╔╝), not the H glyph (██║  ██║).
    assert "██║ ██╔╝" in out
    assert "██║  ██║██╔════╝" not in out
