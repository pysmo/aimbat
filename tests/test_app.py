from importlib import metadata, reload
from typing import Any
import pytest


def mock_return_str(*args: list[Any], **kwargs: dict[str, Any]) -> str:
    return "1.2.3"


def mock_raise(*args: list[Any], **kwargs: dict[str, Any]) -> None:
    raise Exception


def test_cli(capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test aimbat cli without any subcommands."""
    from aimbat import app

    app.app([])
    assert "Usage" in capsys.readouterr().out

    monkeypatch.setattr(metadata, "version", mock_return_str)
    reload(app)
    app.app("--version")
    assert "1.2.3" in capsys.readouterr().out

    monkeypatch.setattr(metadata, "version", mock_raise)
    reload(app)
    app.app("--version")
    assert "unknown" in capsys.readouterr().out
