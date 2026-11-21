"""Functional tests for `aimbat data check`.

Readiness itself is tested against `aimbat.core`. These tests check the
table, the JSON output and the exit status.
"""

import json
from collections.abc import Callable

import pytest
from sqlalchemy import Engine

from testsupport.cli import exit_code
from testsupport.project import add_unpromoted_pick

type _Cli = Callable[[str | list[str]], None]


@pytest.mark.cli
class TestDataCheck:
    """Tests for `data check`."""

    def test_ready(
        self, loaded_engine: Engine, capsys: pytest.CaptureFixture[str]
    ) -> None:
        capsys.readouterr()
        assert exit_code("data check") == 0
        assert "Ready:" in capsys.readouterr().out

    def test_blocking_exits_2(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        add_unpromoted_pick(loaded_engine, event_id, None)
        capsys.readouterr()
        assert exit_code("data check") == 2
        output = capsys.readouterr().out
        assert "unnamed pick" in output
        assert "aimbat pick name PHASE --event" in output
        assert "Not ready:" in output

    def test_notice_exits_2_only_when_strict(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        add_unpromoted_pick(loaded_engine, event_id, "S")
        assert exit_code(f"data check {event_id}") == 0
        assert "unpromoted pick" in capsys.readouterr().out
        assert exit_code(f"data check {event_id} --strict") == 2

    def test_failure_exits_1(
        self,
        loaded_engine: Engine,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import aimbat.actions

        def _fail(*args: object, **kwargs: object) -> None:
            raise RuntimeError("check failed")

        monkeypatch.setattr(aimbat.actions, "check_data", _fail)
        # At INFO, handle_issues prints the panel and exits instead of raising.
        monkeypatch.setattr(aimbat.settings, "log_level", "INFO")
        capsys.readouterr()
        assert exit_code("data check") == 1
        assert "check failed" in capsys.readouterr().err

    def test_json(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        add_unpromoted_pick(loaded_engine, event_id, None)
        capsys.readouterr()
        assert exit_code("data check --json") == 2
        (item,) = json.loads(capsys.readouterr().out)
        assert item["kind"] == "unnamed_pick"
        assert item["event_id"] == event_id
        assert event_id in item["fixes"][0]

    def test_phase_filter(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        add_unpromoted_pick(loaded_engine, event_id, "S")
        capsys.readouterr()
        assert exit_code("data check --phase P --json") == 0
        assert json.loads(capsys.readouterr().out) == []
        assert exit_code("data check --phase S --json") == 0
        (item,) = json.loads(capsys.readouterr().out)
        assert (item["kind"], item["phase_name"]) == ("unpromoted_picks", "S")


@pytest.mark.cli
def test_data_add_reports_blocking_items(
    patched_engine: Engine,
    cli: _Cli,
    capsys: pytest.CaptureFixture[str],
    multi_event_data: list[object],
) -> None:
    capsys.readouterr()
    cli(["data", "add", "--no-progress", *map(str, multi_event_data[:2])])
    assert "Run `aimbat data check`" in capsys.readouterr().err
