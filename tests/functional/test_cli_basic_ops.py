"""Functional tests for the project, data, event, station and seismogram commands.

All commands are invoked in-process via `app()` with `aimbat.db.engine`
monkeypatched to the test fixture's in-memory database. The rules behind each
command are tested against `aimbat.actions` and `aimbat.core`. These tests
check that arguments reach them and that results are shown.
"""

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine

type _Cli = Callable[[str], None]
type _CliJson = Callable[[str], list[Any] | dict[str, Any]]


@pytest.mark.cli
class TestProjectLifecycle:
    """Tests for project commands against an in-memory database."""

    def test_create_project_twice_fails(
        self, patched_engine: Engine, cli: _Cli
    ) -> None:
        """Verifies that creating a project when one already exists fails."""
        with pytest.raises((SystemExit, RuntimeError)):
            cli("project create")

    def test_project_info(
        self,
        patched_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that project info displays a panel for an in-memory database."""
        cli("project info")
        output = capsys.readouterr().out
        assert "Project Info" in output
        assert "in-memory database" in output

    def test_delete_project_succeeds_for_in_memory(
        self, patched_engine: Engine, cli: _Cli
    ) -> None:
        """Verifies that project delete completes without error in memory."""
        cli("project delete --yes")


@pytest.mark.cli
class TestDataAdd:
    """Tests for `data add`."""

    def test_add_data(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: _Cli,
        cli_json: _CliJson,
    ) -> None:
        """Verifies that data are added and snapshotted automatically."""
        files = " ".join(f.as_posix() for f in multi_event_data)
        cli(f"data add {files} --no-progress --unlabelled-as P")

        assert len(cli_json("seismogram dump")) == len(multi_event_data)
        snapshots = cli_json("snapshot dump")
        assert isinstance(snapshots, dict)
        assert snapshots["snapshots"]

    def test_no_snapshot_flag(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: _Cli,
        cli_json: _CliJson,
    ) -> None:
        """Verifies that `--no-snapshot` suppresses automatic snapshots."""
        files = " ".join(f.as_posix() for f in multi_event_data)
        cli(f"data add {files} --no-progress --no-snapshot")

        snapshots = cli_json("snapshot dump")
        assert isinstance(snapshots, dict)
        assert snapshots["snapshots"] == []

    def test_summary_after_a_real_add(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        files = " ".join(f.as_posix() for f in multi_event_data)
        capsys.readouterr()
        cli(f"data add {files} --no-progress --unlabelled-as P")
        output = capsys.readouterr().out

        n = len(multi_event_data)
        assert re.search(rf"Added {n} seismogram\(s\)", output)
        assert re.search(
            rf"Picks: \d+ stored, \d+ matched, {n} promoted \(P: {n}\)", output
        )
        assert "Phases created for event" in output
        assert "Snapshotted" in output

    def test_phase_option_limits_promotion(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: _Cli,
        cli_json: _CliJson,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        files = " ".join(f.as_posix() for f in multi_event_data)
        capsys.readouterr()
        cli(f"data add {files} --no-progress --unlabelled-as P --phase S")
        output = capsys.readouterr().out

        assert "0 promoted" in output
        assert "not given with --phase" in output
        assert "Snapshotted" not in output
        snapshots = cli_json("snapshot dump")
        assert isinstance(snapshots, dict)
        assert snapshots["snapshots"] == []

    def test_skip_unnamed(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        files = " ".join(f.as_posix() for f in multi_event_data)
        capsys.readouterr()
        cli(f"data add {files} --no-progress --skip-unnamed")
        output = capsys.readouterr().out

        assert re.search(r"Picks: 0 stored, .* \d+ unnamed skipped\.", output)

    def test_dry_run_summary_predicts_the_real_add(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: _Cli,
        cli_json: _CliJson,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies the dry-run summary counts distinct records, not data sources.

        Many SAC files routinely resolve to one event, so counting per data
        source reported one event added per file.
        """
        files = " ".join(f.as_posix() for f in multi_event_data)
        capsys.readouterr()
        cli(f"data add {files} --no-progress --dry-run")
        output = capsys.readouterr().out
        assert cli_json("event dump") == []

        pattern = re.compile(
            r"(\d+) station\(s\) added, (\d+) skipped\. "
            r"(\d+) event\(s\) added, (\d+) skipped\. "
            r"(\d+) seismogram\(s\) added, (\d+) skipped\."
        )
        matches = [pattern.fullmatch(line.strip()) for line in output.splitlines()]
        match = next((m for m in matches if m is not None), None)
        assert match is not None, f"No dry-run summary line in: {output!r}"
        stations, _, events, _, seismograms, _ = (int(g) for g in match.groups())

        cli(f"data add {files} --no-progress --no-snapshot")
        actual = {
            "station": len(cli_json("station dump")),
            "event": len(cli_json("event dump")),
            "seismogram": len(cli_json("seismogram dump")),
        }
        assert {
            "station": stations,
            "event": events,
            "seismogram": seismograms,
        } == actual
        assert actual["event"] < len(multi_event_data), (
            "Fixture no longer exercises the bug: it needs several data sources "
            "sharing one event for a per-source count to differ from a per-event one."
        )

    def test_use_station_and_event(
        self,
        patched_engine: Engine,
        sac_file_good: Path,
        cli: _Cli,
        cli_json: _CliJson,
        tmp_path: Path,
    ) -> None:
        """Verifies that `--use-station` and `--use-event` link to existing records."""
        station_json = tmp_path / "station.json"
        station_json.write_text(
            '{"name": "STAT", "network": "NW", "location": "00", "channel": "BHZ", '
            '"latitude": 10.0, "longitude": 20.0, "elevation": 100.0}'
        )
        event_json = tmp_path / "event.json"
        event_json.write_text(
            '{"time": "2020-01-01T00:00:00Z", "latitude": 30.0, '
            '"longitude": 40.0, "depth": 50.0}'
        )
        cli(f"data add {station_json.as_posix()} --type json_station --no-progress")
        cli(f"data add {event_json.as_posix()} --type json_event --no-progress")
        stations = cli_json("station dump")
        events = cli_json("event dump")
        assert isinstance(stations, list) and isinstance(events, list)
        assert stations[0]["name"] == "STAT"
        assert events[0]["latitude"] == 30.0

        cli(
            f"data add {sac_file_good.as_posix()} --no-progress "
            f"--use-station {stations[0]['id']} --use-event {events[0]['id']}"
        )

        (seismogram,) = cli_json("seismogram dump")
        assert isinstance(seismogram, dict)
        assert seismogram["station_id"] == stations[0]["id"]
        assert seismogram["event_id"] == events[0]["id"]


@pytest.mark.cli
class TestReads:
    """Smoke tests for the list and dump commands."""

    @pytest.mark.parametrize(
        "command",
        [
            "data list --event-id all",
            "event list",
            "station list --event-id all",
        ],
    )
    def test_list(self, loaded_engine: Engine, cli: _Cli, command: str) -> None:
        """Verifies that the list command runs."""
        cli(command)

    def test_list_for_one_event(
        self, loaded_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        """Verifies that `--event-id` selects one event."""
        cli(f"seismogram list --event-id {event_id}")

    @pytest.mark.parametrize("kind", ["data", "event", "station", "seismogram"])
    def test_dump(self, loaded_engine: Engine, cli_json: _CliJson, kind: str) -> None:
        """Verifies that the dump command returns a non-empty list."""
        data = cli_json(f"{kind} dump")
        assert isinstance(data, list)
        assert data


@pytest.mark.cli
class TestDelete:
    """Tests for the delete commands."""

    @pytest.mark.parametrize("kind", ["event", "station", "seismogram"])
    @pytest.mark.parametrize("short", [False, True], ids=["full-id", "short-id"])
    def test_delete(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        cli_json: _CliJson,
        kind: str,
        short: bool,
    ) -> None:
        """Verifies that a record is deleted by its full or shortened ID."""
        before = cli_json(f"{kind} dump")
        assert isinstance(before, list)
        target = before[0]["id"]

        cli(f"{kind} delete {target[:8] if short else target} --yes")

        after = cli_json(f"{kind} dump")
        assert isinstance(after, list)
        assert target not in {r["id"] for r in after}
        assert len(after) == len(before) - 1
