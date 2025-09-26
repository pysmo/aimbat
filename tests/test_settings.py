import pytest


class TestConfig:
    def test_lib_print_defaults(self, capsys: pytest.CaptureFixture) -> None:
        from aimbat.config import print_settings_table

        print_settings_table(pretty=True)

        output = capsys.readouterr().out
        assert "AIMBAT settings" in output
        assert "AIMBAT project file location" in output

    def test_lib_print_defaults_without_env_prefix(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        from aimbat.config import Settings, print_settings_table

        monkeypatch.delitem(Settings.model_config, "env_prefix")

        # reload(print_settings)

        print_settings_table(pretty=True)
        output = capsys.readouterr().out
        assert "AIMBAT_" not in output

    def test_cli_print_defaults(self, capsys: pytest.CaptureFixture) -> None:
        from aimbat.app import app

        app(["settings"])

        output = capsys.readouterr().out
        assert "AIMBAT settings" in output
        assert "AIMBAT project file location" in output
