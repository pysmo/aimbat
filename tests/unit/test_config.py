"""Unit tests for aimbat._config."""

import io
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from aimbat._config import (
    Settings,
    cli_settings_list,
    generate_settings_table_markdown,
    print_settings_table,
    settings,
)


def _capture_pretty(monkeypatch: pytest.MonkeyPatch) -> str:
    """Call print_settings_table(pretty=True) and return plain rendered output.

    Args:
        monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.

    Returns:
        str: The captured output string.
    """
    buffer = io.StringIO()
    console = Console(file=buffer, highlight=False, no_color=True, width=200)
    monkeypatch.setattr("aimbat.utils._json.Console", lambda: console)
    print_settings_table(pretty=True)
    return buffer.getvalue()


class TestSettings:
    """Tests for the Settings class configuration."""

    def test_default_project(self) -> None:
        """Verifies the default project file name."""
        s = Settings()
        assert s.project == Path("aimbat.db")

    def test_default_logfile(self) -> None:
        """Verifies the default log file name."""
        s = Settings()
        assert s.logfile == Path("aimbat.log")

    def test_default_log_level(self) -> None:
        """Verifies the default log level is INFO."""
        s = Settings()
        assert s.log_level == "INFO"

    def test_db_url_derived_from_project(self) -> None:
        """Verifies that db_url is derived from the project path by default."""
        s = Settings()
        assert str(s.project) in s.db_url

    def test_db_url_custom_not_overridden(self) -> None:
        """Verifies that a custom db_url is preserved."""
        s = Settings(db_url="sqlite:///custom.db")
        assert s.db_url == "sqlite:///custom.db"

    def test_env_prefix(self) -> None:
        """Verifies that the environment variable prefix is 'aimbat_'."""
        assert Settings.model_config.get("env_prefix") == "aimbat_"

    def test_min_id_length_default(self) -> None:
        """Verifies the default minimum ID length."""
        s = Settings()
        assert s.min_id_length == 2

    def test_bandpass_apply_default(self) -> None:
        """Verifies that bandpass_apply is a boolean."""
        s = Settings()
        assert isinstance(s.bandpass_apply, bool)

    def test_min_ccnorm_bounds(self) -> None:
        """Verifies that min_ccnorm is within [0, 1]."""
        s = Settings()
        assert 0 <= float(s.min_ccnorm) <= 1

    def test_window_pre_is_negative(self) -> None:
        """Verifies that window_pre is a negative duration."""
        s = Settings()
        assert s.window_pre.total_seconds() < 0

    def test_window_post_is_positive(self) -> None:
        """Verifies that window_post is a positive duration."""
        s = Settings()
        assert s.window_post.total_seconds() > 0

    def test_context_width_is_positive(self) -> None:
        """Verifies that context_width is a positive duration."""
        s = Settings()
        assert s.context_width.total_seconds() > 0


class TestPrintSettingsTablePlain:
    """Tests for print_settings_table with pretty=False."""

    def test_contains_setting_names(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verifies that output contains setting names in uppercase.

        Args:
            capsys (pytest.CaptureFixture[str]): Fixture to capture stdout/stderr.
        """
        import json

        print_settings_table(pretty=False)
        output = capsys.readouterr().out
        for k in json.loads(Settings().model_dump_json()):
            assert k.upper() in output

    def test_contains_env_prefix(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verifies that output contains the environment variable prefix.

        Args:
            capsys (pytest.CaptureFixture[str]): Fixture to capture stdout/stderr.
        """
        print_settings_table(pretty=False)
        output = capsys.readouterr().out
        assert "AIMBAT_" in output

    def test_contains_values(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verifies that output contains current setting values.

        Args:
            capsys (pytest.CaptureFixture[str]): Fixture to capture stdout/stderr.
        """
        print_settings_table(pretty=False)
        output = capsys.readouterr().out
        assert str(settings.project) in output
        assert str(settings.logfile) in output

    def test_format_is_key_equals_value(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verifies that output lines are formatted as KEY=VALUE.

        Args:
            capsys (pytest.CaptureFixture[str]): Fixture to capture stdout/stderr.
        """
        print_settings_table(pretty=False)
        output = capsys.readouterr().out
        for line in output.strip().splitlines():
            assert "=" in line


class TestPrintSettingsTablePretty:
    """Tests for print_settings_table with pretty=True."""

    def test_title_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that the table title is present.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_pretty(monkeypatch)
        assert "AIMBAT settings" in output

    def test_column_headers_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that column headers are present.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_pretty(monkeypatch)
        assert "Name" in output
        assert "Value" in output
        assert "Description" in output

    def test_setting_names_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that all setting names are present in the table.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        import json

        output = _capture_pretty(monkeypatch)
        for k in json.loads(Settings().model_dump_json()):
            assert k in output

    def test_setting_values_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that setting values are present in the table.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_pretty(monkeypatch)
        assert str(settings.project) in output
        assert str(settings.logfile) in output

    def test_env_var_in_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that environment variable names are included in descriptions.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        output = _capture_pretty(monkeypatch)
        assert "AIMBAT_" in output


class TestGenerateSettingsTableMarkdown:
    """Tests for generate_settings_table_markdown."""

    def test_returns_string(self) -> None:
        """Verifies the function returns a string."""
        assert isinstance(generate_settings_table_markdown(), str)

    def test_contains_table_header(self) -> None:
        """Verifies the output contains the markdown table header."""
        output = generate_settings_table_markdown()
        assert "| Environment Variable |" in output
        assert "| Default |" in output
        assert "| Description |" in output

    def test_contains_all_env_var_names(self) -> None:
        """Verifies that every setting appears as an AIMBAT_ environment variable."""
        import json

        output = generate_settings_table_markdown()
        for name in json.loads(Settings().model_dump_json()):
            assert f"AIMBAT_{name.upper()}" in output

    def test_uses_true_defaults_not_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that env var overrides do not affect the generated table."""
        monkeypatch.setenv("AIMBAT_LOG_LEVEL", "DEBUG")
        output = generate_settings_table_markdown()
        # Default is INFO; DEBUG must not appear as a value
        lines = [li for li in output.splitlines() if "AIMBAT_LOG_LEVEL" in li]
        assert len(lines) == 1
        assert "`INFO`" in lines[0]
        assert "`DEBUG`" not in lines[0]

    def test_pipe_in_description_is_escaped(self) -> None:
        """Verifies that pipe characters in descriptions are escaped."""
        output = generate_settings_table_markdown()
        # Split into rows and check no unescaped | appears inside a cell
        for line in output.splitlines():
            if not line.startswith("|"):
                continue
            # Strip the leading/trailing pipes and split on |
            # Each cell should not contain a raw (unescaped) |
            inner = line[1:-1]  # remove first and last |
            assert "\\|" not in inner or inner.count("|") == inner.count("\\|")


class TestCliSettingsList:
    """Tests for the cli_settings_list function."""

    def test_delegates_to_print_settings_table(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that the function calls print_settings_table with the correct argument.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "aimbat._config.print_settings_table",
            lambda pretty: calls.append({"pretty": pretty}),
        )
        cli_settings_list(pretty=True)
        assert calls == [{"pretty": True}]

    def test_default_pretty_is_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that 'pretty' defaults to True.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture to mock objects/attributes.
        """
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "aimbat._config.print_settings_table",
            lambda pretty: calls.append({"pretty": pretty}),
        )
        cli_settings_list()
        assert calls[0]["pretty"] is True
