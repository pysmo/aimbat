from importlib import metadata, reload


def mock_return_str(*args, **kwargs):  # type: ignore
    return "1.2.3"


def mock_raise(*args, **kwargs):  # type: ignore
    raise Exception


def test_cli(capsys, monkeypatch):  # type: ignore
    """Test aimbat cli without any subcommands."""
    from aimbat import app

    app.app([])
    assert "Usage" in capsys.readouterr().out

    monkeypatch.setattr(metadata, "version", mock_return_str)
    _ = reload(app)
    app.app("--version")
    assert "1.2.3" in capsys.readouterr().out

    monkeypatch.setattr(metadata, "version", mock_raise)
    _ = reload(app)
    app.app("--version")
    assert "unknown" in capsys.readouterr().out
