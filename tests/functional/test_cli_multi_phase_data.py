"""Functional tests for the CLI on real data with two labelled phases.

The data are testkit's deep event with P and pP picks, AV.AKRB without pP.
Commands run in-process against `multi_phase_engine`.
"""

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine

from aimbat import settings

from testsupport.cli import error_text

type _Cli = Callable[[str | list[str]], None]
type _CliJson = Callable[[str], list[Any] | dict[str, Any]]

_P_ONLY = "AV.AKRB"


@pytest.fixture
def event_id(multi_phase_engine: Engine, cli_json: _CliJson) -> str:
    (event,) = cli_json("event dump")
    assert isinstance(event, dict)
    return event["id"]


def _dump(cli_json: _CliJson, command: str) -> list[dict[str, Any]]:
    """The rows of a `dump` command that returns a list."""
    dump = cli_json(command)
    assert isinstance(dump, list)
    return dump


def _quality(cli_json: _CliJson) -> dict[str, dict[str, Any]]:
    """`phase quality dump`, keyed by phase name."""
    return {row["phase_name"]: row for row in _dump(cli_json, "phase quality dump")}


class TestAlign:
    def test_needs_a_phase(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        monkeypatch.setattr(settings, "log_level", "INFO")
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc_info:
            cli(f"align iccs --event-id {event_id}")
        assert exc_info.value.code == 1
        assert "has phases P (Z), pP (Z)" in error_text(capsys.readouterr().err)

    def test_named_phase_only(
        self, cli: _Cli, cli_json: _CliJson, event_id: str
    ) -> None:
        cli(f"align iccs --event-id {event_id} --phase pP --autoflip --autoselect")
        cli(f"align mccc --event-id {event_id} --phase pP")

        quality = _quality(cli_json)
        assert quality["pP"]["mccc_rmse"] is not None
        assert quality["P"]["mccc_rmse"] is None
        assert quality["P"]["cc_mean"] is None

    def test_environment_names_the_phase(
        self,
        cli: _Cli,
        cli_json: _CliJson,
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        monkeypatch.setenv("DEFAULT_PHASE", "pP")
        cli(f"align iccs --event-id {event_id}")

        quality = _quality(cli_json)
        assert quality["pP"]["cc_mean"] is not None
        assert quality["P"]["cc_mean"] is None


class TestListings:
    def test_phase_counts(self, cli_json: _CliJson, event_id: str) -> None:
        quality = _quality(cli_json)
        assert {name: row["count"] for name, row in quality.items()} == {
            "P": 14,
            "pP": 13,
        }

    def test_members_of_each_phase(self, cli_json: _CliJson, event_id: str) -> None:
        stations = {
            s["id"]: f"{s['network']}.{s['name']}"
            for s in _dump(cli_json, "station dump")
        }
        station_of = {
            s["id"]: stations[s["station_id"]]
            for s in _dump(cli_json, "seismogram dump")
        }
        members: dict[str, set[str]] = {}
        for row in _dump(cli_json, "seismogram parameter dump"):
            members.setdefault(row["phase_name"], set()).add(
                station_of[row["seismogram_id"]]
            )

        assert len(members["P"]) == 14
        assert members["pP"] == members["P"] - {_P_ONLY}

    def test_picks_name_the_phase(self, cli_json: _CliJson, event_id: str) -> None:
        picks = _dump(cli_json, "pick dump")
        assert {(p["phase_name"], p["label"], p["source_key"]) for p in picks} == {
            ("P", "P", "t0"),
            ("pP", "pP", "t5"),
        }

    def test_snapshot_of_the_named_phase(
        self, cli: _Cli, cli_json: _CliJson, event_id: str
    ) -> None:
        cli(f"snapshot create --event-id {event_id} --phase pP")

        dump = cli_json("snapshot dump")
        assert isinstance(dump, dict)
        pp_id = _quality(cli_json)["pP"]["phase_id"]
        assert [snapshot["phase_id"] for snapshot in dump["snapshots"]] == [pp_id]
