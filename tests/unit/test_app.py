"""Unit tests for the main CLI application entry point."""

from importlib import metadata, reload
from typing import Any
import pytest


def mock_return_str(*args: list[Any], **kwargs: dict[str, Any]) -> str:
    """Mock function that returns a fixed string version.

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Returns:
        str: The string "1.2.3".
    """
    return "1.2.3"


def mock_raise(*args: list[Any], **kwargs: dict[str, Any]) -> None:
    """Mock function that raises an Exception.

    Args:
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.

    Raises:
        Exception: Always raised.
    """
    raise Exception


def test_cli_usage(capsys: pytest.CaptureFixture) -> None:
    """Test aimbat cli help output.

    Args:
        capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
    """
    from aimbat import app

    with pytest.raises(SystemExit) as excinfo:
        app.app(["--help"])

    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert "Usage" in captured.out


def test_cli_version(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test aimbat cli version flag.

    Args:
        capsys (pytest.CaptureFixture): Fixture to capture stdout/stderr.
        monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
    """
    from aimbat import app

    monkeypatch.setattr(metadata, "version", mock_return_str)
    reload(app)
    with pytest.raises(SystemExit) as excinfo:
        app.app(["--version"])
    assert excinfo.value.code == 0
    assert "1.2.3" in capsys.readouterr().out

    monkeypatch.setattr(metadata, "version", mock_raise)
    reload(app)
    with pytest.raises(SystemExit) as excinfo:
        app.app(["--version"])
    assert excinfo.value.code == 0
    assert "unknown" in capsys.readouterr().out
