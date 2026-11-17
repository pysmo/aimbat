"""Functional tests for the AIMBAT snapshot CLI commands.

All commands are invoked in-process via `app()` with `aimbat.db.engine`
monkeypatched to the test fixture's in-memory database. The `snapshot dump`
JSON output is used as the ground truth for ID verification after mutations.
The rules for snapshots are tested against `aimbat.actions` and
`aimbat.core`. These tests check that arguments reach them and that results
are shown.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine

from aimbat import settings

type _Cli = Callable[[str | list[str]], None]
type _CliJson = Callable[[str], list[Any] | dict[str, Any]]


def _dump(cli_json: _CliJson) -> dict[str, Any]:
    data = cli_json("snapshot dump")
    assert isinstance(data, dict)
    return data


@pytest.fixture
def snapshot_id(
    loaded_engine: Engine, cli: _Cli, cli_json: _CliJson, event_id: str
) -> str:
    """Creates a snapshot of the first event through the CLI.

    Returns:
        The ID of the snapshot.
    """
    cli(f"snapshot create --event-id {event_id} --comment fixture")
    return _dump(cli_json)["snapshots"][0]["id"]


@pytest.mark.cli
class TestSnapshotCreate:
    """Tests for `snapshot create`."""

    @pytest.mark.parametrize(
        ("flags", "comment"), [("", None), ("--comment my-comment", "my-comment")]
    )
    def test_create(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        cli_json: _CliJson,
        event_id: str,
        flags: str,
        comment: str | None,
    ) -> None:
        """Verifies that a snapshot is created with the comment given, if any."""
        cli(f"snapshot create --event-id {event_id} {flags}")

        data = _dump(cli_json)
        (snapshot,) = data["snapshots"]
        assert snapshot["comment"] == comment
        assert snapshot["event_id"] == event_id
        assert len(data["event_parameters"]) == 1
        assert data["seismogram_parameters"]


@pytest.mark.cli
class TestSnapshotDelete:
    """Tests for `snapshot delete`."""

    @pytest.mark.parametrize("short", [False, True], ids=["full-id", "short-id"])
    def test_delete(
        self, cli: _Cli, cli_json: _CliJson, snapshot_id: str, short: bool
    ) -> None:
        """Verifies that a snapshot is deleted by its full or shortened ID."""
        cli(f"snapshot delete {snapshot_id[:8] if short else snapshot_id} --yes")

        assert _dump(cli_json)["snapshots"] == []

    def test_unknown_id_is_reported(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that an unknown ID exits with an error panel."""
        # At INFO, handle_issues prints the panel and exits instead of raising.
        monkeypatch.setattr(settings, "log_level", "INFO")
        with pytest.raises(SystemExit) as exc_info:
            cli("snapshot delete 00000000-0000-0000-0000-000000000000 --yes")
        assert exc_info.value.code == 1
        output = capsys.readouterr().err
        assert "Error" in output
        assert "No snapshot found" in output


@pytest.mark.cli
class TestSnapshotRollback:
    """Tests for `snapshot rollback`."""

    @pytest.mark.parametrize("short", [False, True], ids=["full-id", "short-id"])
    def test_rollback(
        self,
        cli: _Cli,
        cli_json: _CliJson,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
        snapshot_id: str,
        short: bool,
    ) -> None:
        """Verifies that a rollback by full or shortened ID restores parameters."""
        cli(f"event parameter set completed true --event-id {event_id}")

        cli(f"snapshot rollback {snapshot_id[:8] if short else snapshot_id} --yes")

        capsys.readouterr()
        cli(f"event parameter get completed --event-id {event_id}")
        assert capsys.readouterr().out.strip() == "False"


@pytest.mark.cli
class TestSnapshotReads:
    """Tests for `snapshot dump`, `list` and `details`."""

    def test_dump_empty(self, loaded_engine: Engine, cli_json: _CliJson) -> None:
        """Verifies that every list in the dump is empty without snapshots."""
        data = _dump(cli_json)
        assert {"snapshots", "event_parameters", "seismogram_parameters"} <= data.keys()
        assert all(entries == [] for entries in data.values())

    def test_dump_ids_are_consistent(
        self, cli_json: _CliJson, snapshot_id: str
    ) -> None:
        """Verifies that parameter entries refer to the snapshots listed."""
        data = _dump(cli_json)
        assert [s["id"] for s in data["snapshots"]] == [snapshot_id]
        for entry in data["event_parameters"] + data["seismogram_parameters"]:
            assert entry["snapshot_id"] == snapshot_id

    @pytest.mark.parametrize(
        ("flags", "expected"),
        [
            ("--event-id {event_id}", "AIMBAT snapshots for event"),
            ("--event-id all", "AIMBAT snapshots for all events"),
            ("--raw --event-id {event_id}", "ID"),
        ],
        ids=["one-event", "all-events", "raw"],
    )
    def test_list(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
        snapshot_id: str,
        flags: str,
        expected: str,
    ) -> None:
        """Verifies that the list command shows the snapshot."""
        capsys.readouterr()
        cli(f"snapshot list {flags.format(event_id=event_id)}")
        output = capsys.readouterr().out
        assert expected in output
        assert "fixture" in output

    @pytest.mark.parametrize(
        ("short", "flags"),
        [(False, ""), (True, ""), (False, "--raw")],
        ids=["full-id", "short-id", "raw"],
    )
    def test_details(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        snapshot_id: str,
        short: bool,
        flags: str,
    ) -> None:
        """Verifies that the details command shows the saved parameters."""
        capsys.readouterr()
        cli(f"snapshot details {snapshot_id[:8] if short else snapshot_id} {flags}")
        assert "Saved event parameters" in capsys.readouterr().out


@pytest.mark.cli
class TestSnapshotPreview:
    """Tests for `snapshot preview`."""

    @patch("aimbat.plot.plot_stack")
    def test_stack(self, mock_plot: MagicMock, cli: _Cli, snapshot_id: str) -> None:
        """Verifies that the stack is plotted without `--matrix`."""
        cli(f"snapshot preview {snapshot_id}")
        mock_plot.assert_called_once()

    @patch("aimbat.plot.plot_matrix_image")
    def test_matrix(self, mock_plot: MagicMock, cli: _Cli, snapshot_id: str) -> None:
        """Verifies that the matrix image is plotted with `--matrix`."""
        cli(f"snapshot preview {snapshot_id} --matrix")
        mock_plot.assert_called_once()


@pytest.mark.cli
class TestSnapshotResults:
    """Tests for `snapshot results`."""

    def test_stdout(
        self, cli: _Cli, capsys: pytest.CaptureFixture[str], snapshot_id: str
    ) -> None:
        """Verifies that the results are printed as JSON with the expected fields."""
        capsys.readouterr()
        cli(f"snapshot results {snapshot_id}")
        result = json.loads(capsys.readouterr().out)
        assert {
            "snapshot_id",
            "event_id",
            "event_time",
            "mccc_rmse",
            "seismograms",
        } <= result.keys()
        assert result["seismograms"]
        assert {"seismogram_id", "name", "flip", "t1"} <= result["seismograms"][
            0
        ].keys()

    def test_by_alias(
        self, cli: _Cli, capsys: pytest.CaptureFixture[str], snapshot_id: str
    ) -> None:
        """Verifies that `--alias` produces camelCase keys."""
        capsys.readouterr()
        cli(f"snapshot results {snapshot_id} --alias")
        result = json.loads(capsys.readouterr().out)
        assert "snapshotId" in result
        assert "snapshot_id" not in result
        assert "seismogramId" in result["seismograms"][0]
        assert "seismogram_id" not in result["seismograms"][0]

    def test_output_to_file(self, cli: _Cli, snapshot_id: str, tmp_path: Path) -> None:
        """Verifies that `--output` writes a JSON file."""
        out_file = tmp_path / "results.json"

        cli(["snapshot", "results", snapshot_id, "--output", str(out_file)])

        assert json.loads(out_file.read_text())["seismograms"]

    def test_output_rejects_directory(
        self, cli: _Cli, snapshot_id: str, tmp_path: Path
    ) -> None:
        """Verifies that a directory given as `--output` is rejected."""
        with pytest.raises(SystemExit):
            cli(["snapshot", "results", snapshot_id, "--output", str(tmp_path)])

    def test_output_refuses_to_overwrite_without_force(
        self, cli: _Cli, snapshot_id: str, tmp_path: Path
    ) -> None:
        """Verifies that `--output` overwrites an existing file only with `--force`."""
        out_file = tmp_path / "results.json"
        out_file.write_text("pre-existing content")

        with pytest.raises(FileExistsError):
            cli(["snapshot", "results", snapshot_id, "--output", str(out_file)])
        assert out_file.read_text() == "pre-existing content"

        cli(["snapshot", "results", snapshot_id, "--output", str(out_file), "--force"])
        assert out_file.read_text() != "pre-existing content"
