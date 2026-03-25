"""Functional tests for the AIMBAT snapshot CLI commands.

All commands are invoked in-process via `app()` with `aimbat.db.engine`
monkeypatched to the test fixture's in-memory database.  The `snapshot dump`
JSON output is used as the ground truth for ID verification after mutations.
"""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from aimbat import settings
from aimbat.models import AimbatSeismogram

# ===================================================================
# Snapshot creation
# ===================================================================


@pytest.mark.cli
class TestSnapshotCreate:
    """Tests for the `snapshot create` CLI command."""

    def test_create_without_comment(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that a snapshot is created with a null comment by default.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert len(data["snapshots"]) == 1, "Expected exactly one snapshot"
        assert data["snapshots"][0]["comment"] is None, (
            "Comment should be None when not provided"
        )

    def test_create_with_comment(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that the comment is stored when provided.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id} --comment my-comment")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert data["snapshots"][0]["comment"] == "my-comment", (
            "Comment should match the value passed to create"
        )

    def test_create_captures_event_parameters(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that one event parameter snapshot is created per snapshot.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert len(data["event_parameters"]) == 1, (
            "Expected one event parameter snapshot per snapshot"
        )

    def test_create_captures_seismogram_parameters(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that seismogram parameter snapshots are created.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert len(data["seismogram_parameters"]) > 0, (
            "Expected at least one seismogram parameter snapshot"
        )

    def test_create_multiple_snapshots(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that multiple snapshots accumulate correctly.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id} --comment first")
        cli(f"snapshot create --event-id {event_id} --comment second")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert len(data["snapshots"]) == 2, "Expected two snapshots"
        assert len(data["event_parameters"]) == 2, (
            "Expected two event parameter snapshots"
        )
        comments = {s["comment"] for s in data["snapshots"]}
        assert comments == {
            "first",
            "second",
        }, "Both comments should be present in the dump"


# ===================================================================
# Snapshot deletion
# ===================================================================


@pytest.mark.cli
class TestSnapshotDelete:
    """Tests for the `snapshot delete` CLI command.

    Uses IDs obtained from `snapshot dump` to verify complete removal of
    the snapshot and all related child records.
    """

    def test_delete_removes_snapshot(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that the snapshot ID is absent from the dump after deletion.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data_before = cli_json("snapshot dump")
        assert isinstance(data_before, dict), "Dump should return a dict"
        snapshot_id = data_before["snapshots"][0]["id"]

        cli(f"snapshot delete {snapshot_id}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict), "Dump should return a dict"
        remaining_ids = [s["id"] for s in data_after["snapshots"]]
        assert snapshot_id not in remaining_ids, (
            f"Snapshot {snapshot_id} should be absent after deletion"
        )

    def test_delete_removes_event_parameter_snapshot(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that the related event parameter snapshot is removed after deletion.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data_before = cli_json("snapshot dump")
        assert isinstance(data_before, dict), "Dump should return a dict"
        snapshot_id = data_before["snapshots"][0]["id"]
        event_param_ids = {ep["id"] for ep in data_before["event_parameters"]}

        cli(f"snapshot delete {snapshot_id}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict), "Dump should return a dict"
        remaining_event_param_ids = {ep["id"] for ep in data_after["event_parameters"]}
        assert event_param_ids.isdisjoint(remaining_event_param_ids), (
            f"Event parameter snapshot IDs {event_param_ids} should all be absent after deletion"
        )

    def test_delete_removes_seismogram_parameter_snapshots(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that all related seismogram parameter snapshots are removed after deletion.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data_before = cli_json("snapshot dump")
        assert isinstance(data_before, dict), "Dump should return a dict"
        snapshot_id = data_before["snapshots"][0]["id"]
        seis_param_ids = {sp["id"] for sp in data_before["seismogram_parameters"]}
        assert len(seis_param_ids) > 0, (
            "There should be seismogram parameter snapshots before deletion"
        )

        cli(f"snapshot delete {snapshot_id}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict), "Dump should return a dict"
        remaining_seis_param_ids = {
            sp["id"] for sp in data_after["seismogram_parameters"]
        }
        assert seis_param_ids.isdisjoint(remaining_seis_param_ids), (
            f"Seismogram parameter snapshot IDs {seis_param_ids} should all be absent after deletion"
        )

    def test_delete_one_of_two_snapshots_leaves_other_intact(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that deleting one snapshot does not affect the other.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id} --comment first")
        cli(f"snapshot create --event-id {event_id} --comment second")
        data_before = cli_json("snapshot dump")
        assert isinstance(data_before, dict), "Dump should return a dict"
        first_id = next(
            s["id"] for s in data_before["snapshots"] if s["comment"] == "first"
        )
        second_id = next(
            s["id"] for s in data_before["snapshots"] if s["comment"] == "second"
        )

        cli(f"snapshot delete {first_id}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict), "Dump should return a dict"
        remaining_ids = [s["id"] for s in data_after["snapshots"]]
        assert first_id not in remaining_ids, (
            f"Deleted snapshot {first_id} should be absent"
        )
        assert second_id in remaining_ids, (
            f"Surviving snapshot {second_id} should still be present"
        )

    def test_delete_snapshot_with_short_id_removes_all_related(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies deletion via short ID removes the snapshot and all related records.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data_before = cli_json("snapshot dump")
        assert isinstance(data_before, dict), "Dump should return a dict"
        snapshot_id = data_before["snapshots"][0]["id"]
        short_id = snapshot_id[:8]
        event_param_ids = {ep["id"] for ep in data_before["event_parameters"]}
        seis_param_ids = {sp["id"] for sp in data_before["seismogram_parameters"]}

        cli(f"snapshot delete {short_id}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict), "Dump should return a dict"
        remaining_snapshot_ids = [s["id"] for s in data_after["snapshots"]]
        remaining_event_param_ids = {ep["id"] for ep in data_after["event_parameters"]}
        remaining_seis_param_ids = {
            sp["id"] for sp in data_after["seismogram_parameters"]
        }
        assert snapshot_id not in remaining_snapshot_ids, (
            f"Snapshot {snapshot_id} should be absent after deletion via short ID"
        )
        assert event_param_ids.isdisjoint(remaining_event_param_ids), (
            f"Event parameter snapshot IDs {event_param_ids} should all be absent"
        )
        assert seis_param_ids.isdisjoint(remaining_seis_param_ids), (
            f"Seismogram parameter snapshot IDs {seis_param_ids} should all be absent"
        )

    def test_delete_non_existent_id_fails(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies that deleting a non-existent snapshot ID fails gracefully.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """
        # Set log level to INFO so simple_exception catches and exits
        monkeypatch.setattr(settings, "log_level", "INFO")
        with pytest.raises(SystemExit) as exc_info:
            cli("snapshot delete 00000000-0000-0000-0000-000000000000")
        assert exc_info.value.code == 1
        output = capsys.readouterr().err
        assert "Error" in output, "Expected error panel in stderr"
        assert "Unable to find" in output, (
            "Error message should mention it was not found"
        )


# ===================================================================
# Snapshot rollback
# ===================================================================


@pytest.mark.cli
class TestSnapshotRollback:
    """Tests for the `snapshot rollback` CLI command."""

    def test_rollback_restores_event_parameter(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that rollback restores a previously changed event parameter.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id} --comment before-change")

        cli(f"event parameter set completed true --event-id {event_id}")
        cli(f"event parameter get completed --event-id {event_id}")
        assert "True" in capsys.readouterr().out, (
            "Parameter should read True after being set"
        )

        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot rollback {snapshot_id}")

        cli(f"event parameter get completed --event-id {event_id}")
        assert "False" in capsys.readouterr().out, (
            "Parameter should be restored to False after rollback"
        )

    def test_rollback_restores_seismogram_parameter(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that rollback restores a previously changed seismogram parameter.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        # Get a seismogram ID
        with Session(loaded_engine) as session:
            seis = session.exec(select(AimbatSeismogram)).first()
            assert seis is not None
            seis_id = seis.id

        cli(f"snapshot create --event-id {event_id} --comment before-seis-change")

        # Flip the seismogram
        cli(f"seismogram parameter set flip true --id {seis_id}")
        cli(f"seismogram parameter get flip --id {seis_id}")
        assert "True" in capsys.readouterr().out, "Seismogram should be flipped"

        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot rollback {snapshot_id}")

        cli(f"seismogram parameter get flip --id {seis_id}")
        assert "False" in capsys.readouterr().out, (
            "Seismogram flip should be restored to False after rollback"
        )

    def test_rollback_restores_event_parameter_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that rollback restores a parameter when given a shortened snapshot ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id} --comment before-change")

        cli(f"event parameter set completed true --event-id {event_id}")
        cli(f"event parameter get completed --event-id {event_id}")
        assert "True" in capsys.readouterr().out, (
            "Parameter should read True after being set"
        )

        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        short_id = data["snapshots"][0]["id"][:8]

        cli(f"snapshot rollback {short_id}")

        cli(f"event parameter get completed --event-id {event_id}")
        assert "False" in capsys.readouterr().out, (
            "Parameter should be restored to False after rollback via short ID"
        )

    def test_rollback_does_not_delete_snapshot(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that rolling back leaves the snapshot itself in place.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data_before = cli_json("snapshot dump")
        assert isinstance(data_before, dict), "Dump should return a dict"
        snapshot_id = data_before["snapshots"][0]["id"]

        cli(f"snapshot rollback {snapshot_id}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict), "Dump should return a dict"
        remaining_ids = [s["id"] for s in data_after["snapshots"]]
        assert snapshot_id in remaining_ids, (
            "Snapshot should still exist after rollback"
        )


# ===================================================================
# Snapshot dump
# ===================================================================


@pytest.mark.cli
class TestSnapshotDump:
    """Tests for the `snapshot dump` CLI command."""

    def test_dump_empty_returns_empty_lists(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that the dump is empty when no snapshots have been created.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert data["snapshots"] == [], "Snapshots list should be empty"
        assert data["event_parameters"] == [], "Event parameters list should be empty"
        assert data["seismogram_parameters"] == [], (
            "Seismogram parameters list should be empty"
        )

    def test_dump_contains_expected_keys(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that the dump dict contains the three expected top-level keys.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert "snapshots" in data, "Dump should contain 'snapshots' key"
        assert "event_parameters" in data, "Dump should contain 'event_parameters' key"
        assert "seismogram_parameters" in data, (
            "Dump should contain 'seismogram_parameters' key"
        )

    def test_dump_all_events_includes_default(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that dump returns snapshots for all events by default.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        assert len(data["snapshots"]) >= 1, (
            "Dump should return at least one snapshot for the default event"
        )

    def test_dump_snapshot_ids_are_consistent(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that snapshot IDs referenced in event/seismogram params match the snapshots list.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        snapshot_ids = {s["id"] for s in data["snapshots"]}
        for ep in data["event_parameters"]:
            assert ep["snapshot_id"] in snapshot_ids, (
                f"Event parameter snapshot_id {ep['snapshot_id']} not in snapshots list"
            )
        for sp in data["seismogram_parameters"]:
            assert sp["snapshot_id"] in snapshot_ids, (
                f"Seismogram parameter snapshot_id {sp['snapshot_id']} not in snapshots list"
            )


# ===================================================================
# Snapshot list
# ===================================================================


@pytest.mark.cli
class TestSnapshotList:
    """Tests for the `snapshot list` CLI command."""

    def test_list_default_event(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that the list command produces output for the default event.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id} --comment test-comment")
        cli(f"snapshot list --event-id {event_id}")
        output = capsys.readouterr().out
        assert "AIMBAT snapshots for event" in output
        assert "test-comment" in output

    def test_list_all_events(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that `--event-id all` produces output for all events.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id} --comment test-comment-all")
        cli("snapshot list --event-id all")
        output = capsys.readouterr().out
        assert "AIMBAT snapshots for all events" in output
        assert "test-comment-all" in output

    def test_list_raw(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that `--raw` produces output.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id}")
        cli(f"snapshot list --raw --event-id {event_id}")
        output = capsys.readouterr().out
        assert "ID" in output


# ===================================================================
# Snapshot details
# ===================================================================


@pytest.mark.cli
class TestSnapshotDetails:
    """Tests for the `snapshot details` CLI command."""

    def test_details_produces_output(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that the details command produces output for a valid snapshot ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot details {snapshot_id}")
        output = capsys.readouterr().out
        assert "Saved event parameters" in output
        assert "Window pre" in output

    def test_details_produces_output_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that the details command works with a shortened snapshot ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        short_id = data["snapshots"][0]["id"][:8]

        cli(f"snapshot details {short_id}")
        output = capsys.readouterr().out
        assert "Saved event parameters" in output

    def test_details_raw_flag(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that `--raw` produces output.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot details {snapshot_id} --raw")
        assert "Saved event parameters" in capsys.readouterr().out


# ===================================================================
# Snapshot preview
# ===================================================================


@pytest.mark.cli
class TestSnapshotPreview:
    """Tests for the `snapshot preview` CLI command."""

    @patch("aimbat.plot.plot_stack")
    def test_preview_stack_is_called(
        self,
        mock_plot: MagicMock,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that plot_stack is called when previewing without --matrix.

        Args:
            mock_plot: The mocked plot_stack function.
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot preview {snapshot_id}")
        mock_plot.assert_called_once()

    @patch("aimbat.plot.plot_matrix_image")
    def test_preview_matrix_is_called(
        self,
        mock_plot: MagicMock,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
    ) -> None:
        """Verifies that plot_matrix_image is called when previewing with --matrix.

        Args:
            mock_plot: The mocked plot_matrix_image function.
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict), "Dump should return a dict"
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot preview {snapshot_id} --matrix")
        mock_plot.assert_called_once()


# ===================================================================
# Snapshot results
# ===================================================================


@pytest.mark.cli
class TestSnapshotResults:
    """Tests for the `snapshot results` CLI command."""

    def test_results_stdout_contains_expected_fields(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that stdout JSON output contains the expected envelope and seismogram fields.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            event_id: The default event ID fixture.
            capsys: The pytest capsys fixture.
        """
        import json

        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot results {snapshot_id}")
        output = capsys.readouterr().out
        result = json.loads(output)
        assert isinstance(result, dict)
        for field in (
            "snapshot_id",
            "event_id",
            "event_time",
            "mccc_rmse",
            "seismograms",
        ):
            assert field in result, f"Expected field '{field}' in results envelope"
        assert len(result["seismograms"]) > 0
        for field in ("seismogram_id", "name", "flip", "t1"):
            assert field in result["seismograms"][0], (
                f"Expected field '{field}' in seismogram row"
            )

    def test_results_output_to_file(
        self,
        loaded_engine: Engine,
        cli: Callable[[str | list[str]], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
        tmp_path: Path,
    ) -> None:
        """Verifies that --output writes a valid JSON file.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            event_id: The default event ID fixture.
            tmp_path: Pytest temporary directory.
        """
        import json

        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        snapshot_id: str = data["snapshots"][0]["id"]

        out_file = tmp_path / "results.json"
        cli(["snapshot", "results", snapshot_id, "--output", str(out_file)])

        assert out_file.exists(), "Output file should be created"
        result = json.loads(out_file.read_text())
        assert isinstance(result, dict)
        assert len(result["seismograms"]) > 0

    def test_results_by_alias(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        event_id: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that --alias produces camelCase keys in the output.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            event_id: The default event ID fixture.
            capsys: The pytest capsys fixture.
        """
        import json

        cli(f"snapshot create --event-id {event_id}")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        snapshot_id = data["snapshots"][0]["id"]

        cli(f"snapshot results {snapshot_id} --alias")
        output = capsys.readouterr().out
        result = json.loads(output)
        assert "snapshotId" in result
        assert "snapshot_id" not in result
        assert "seismogramId" in result["seismograms"][0]
        assert "seismogram_id" not in result["seismograms"][0]
