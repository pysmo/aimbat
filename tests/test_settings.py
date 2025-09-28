import pytest


class TestConfig:
    @pytest.mark.parametrize(
        "pretty, expected",
        [(True, "AIMBAT project file location"), (False, 'AIMBAT_PROJECT="aimbat.db"')],
    )
    def test_lib_print_defaults(
        self, pretty: bool, expected: str, capsys: pytest.CaptureFixture
    ) -> None:
        from aimbat.config import print_settings_table

        print_settings_table(pretty)
        output = capsys.readouterr().out
        assert expected in output

    @pytest.mark.parametrize(
        "pretty, expected",
        [
            ("--pretty", "AIMBAT project file location"),
            ("--no-pretty", 'AIMBAT_PROJECT="aimbat.db"'),
        ],
    )
    def test_cli_print_defaults(
        self, pretty: str, expected: str, capsys: pytest.CaptureFixture
    ) -> None:
        from aimbat.app import app

        app(["settings", pretty])

        output = capsys.readouterr().out
        assert expected in output

    @pytest.mark.parametrize("pretty", [True, False])
    def test_lib_print_defaults_without_env_prefix(
        self,
        pretty: bool,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        from aimbat.config import Settings, print_settings_table

        monkeypatch.delitem(Settings.model_config, "env_prefix")

        print_settings_table(pretty)
        output = capsys.readouterr().out
        assert "AIMBAT_" not in output
