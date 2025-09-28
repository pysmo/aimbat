from aimbat.config import Settings
import pytest


def test_simple_exception(
    patch_settings: Settings, capsys: pytest.CaptureFixture
) -> None:
    patch_settings.debug = False
    from aimbat.app import app

    with pytest.raises(SystemExit) as e:
        app(["event", "activate", "nonexistent-uuid-str"])
        captured = capsys.readouterr()
        assert "╭─ Error ────────────────────" in captured.out
        assert e.value.code == 1
