"""Functional tests exercising the AIMBAT CLI.

All commands are invoked in-process via ``app()`` with ``aimbat.db.engine``
monkeypatched to the test fixture's in-memory database.
"""

import pytest
from pathlib import Path
from collections.abc import Callable, Sequence
from sqlalchemy import Engine

# ===================================================================
# Project lifecycle (in-memory)
# ===================================================================


@pytest.mark.cli
class TestProjectLifecycle:
    """Tests for project commands against an in-memory database."""

    def test_create_project_twice_fails(
        self,
        patched_engine: Engine,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that creating a project when one already exists fails.

        Args:
            patched_engine: The monkeypatched in-memory engine (project already created).
            cli: The in-process CLI callable.
        """
        with pytest.raises((SystemExit, RuntimeError)):
            cli("project create")

    def test_project_info(
        self,
        patched_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that project info displays a panel for an in-memory database.

        Args:
            patched_engine: The monkeypatched in-memory engine (project already created).
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("project info")
        output = capsys.readouterr().out
        assert (
            "Project Info" in output
        ), "Output should contain the 'Project Info' panel title"
        assert (
            "in-memory database" in output
        ), "Output should indicate this is an in-memory database"

    def test_delete_project_succeeds_for_in_memory(
        self,
        patched_engine: Engine,
        cli: Callable[[str], None],
    ) -> None:
        """Verifies that project delete completes without error for an in-memory database.

        Args:
            patched_engine: The monkeypatched in-memory engine (project already created).
            cli: The in-process CLI callable.
        """
        cli("project delete")  # should not raise for in-memory


# ===================================================================
# Data management
# ===================================================================


@pytest.mark.cli
class TestDataManagement:
    """Tests for adding and managing data."""

    def test_add_data(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that data can be added to the project."""
        files = " ".join(str(f) for f in multi_event_data)
        cli(f"data add {files} --no-progress")
        events = cli_json("event dump")
        assert len(events) > 0

    def test_add_data_idempotent(
        self,
        loaded_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Adding the same files twice does not duplicate data."""
        events_before = cli_json("event dump")

        files = " ".join(str(f) for f in multi_event_data)
        cli(f"data add {files} --no-progress")

        events_after = cli_json("event dump")
        assert len(events_after) == len(events_before)

    def test_data_list(self, loaded_engine: Engine, cli: Callable[[str], None]) -> None:
        """Verifies that data list command runs successfully."""
        cli("data list --all")

    def test_data_dump(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that data dump returns a list of data items."""
        data = cli_json("data dump")
        assert isinstance(data, list)
        assert len(data) > 0

    def test_dry_run_does_not_add(
        self,
        patched_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that dry-run mode does not modify the database."""
        files = " ".join(str(f) for f in multi_event_data)
        cli(f"data add {files} --no-progress --dry-run")
        events = cli_json("event dump")
        assert len(events) == 0


# ===================================================================
# Event operations
# ===================================================================


@pytest.mark.cli
class TestEventOperations:
    """Tests for event-related CLI commands."""

    def test_event_list(
        self, loaded_engine: Engine, cli: Callable[[str], None]
    ) -> None:
        """Verifies that event list command runs successfully."""
        cli("event list")

    def test_event_dump(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that event dump returns a list of events."""
        events = cli_json("event dump")
        assert len(events) > 1

    def test_activate_event(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that an event can be activated."""
        events = cli_json("event dump")

        inactive = [e for e in events if e["active"] is None]
        assert len(inactive) > 0
        target_id = inactive[0]["id"]

        cli(f"event activate {target_id}")

        events_after = cli_json("event dump")
        active = [e for e in events_after if e["active"] is True]
        assert len(active) == 1
        assert active[0]["id"] == target_id

    def test_activate_switches_active(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Activating a different event deactivates the previous one."""
        events = cli_json("event dump")
        ids = [e["id"] for e in events]

        cli(f"event activate {ids[0]}")
        cli(f"event activate {ids[1]}")

        events_after = cli_json("event dump")
        active = [e for e in events_after if e["active"] is True]
        assert len(active) == 1
        assert active[0]["id"] == ids[1]

    def test_delete_event(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that an event can be deleted."""
        events_before = cli_json("event dump")
        target_id = events_before[0]["id"]

        cli(f"event delete {target_id}")

        events_after = cli_json("event dump")
        remaining_ids = [e["id"] for e in events_after]
        assert target_id not in remaining_ids
        assert len(events_after) == len(events_before) - 1

    def test_activate_event_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that an event can be activated using a shortened ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        events = cli_json("event dump")
        inactive = [e for e in events if e["active"] is None]
        assert len(inactive) > 0
        target_id = inactive[0]["id"]
        short_id = target_id[:8]

        cli(f"event activate {short_id}")

        events_after = cli_json("event dump")
        active = [e for e in events_after if e["active"] is True]
        assert len(active) == 1
        assert active[0]["id"] == target_id

    def test_delete_event_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that an event can be deleted using a shortened ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        events_before = cli_json("event dump")
        target_id = events_before[0]["id"]
        short_id = target_id[:8]

        cli(f"event delete {short_id}")

        events_after = cli_json("event dump")
        remaining_ids = [e["id"] for e in events_after]
        assert target_id not in remaining_ids
        assert len(events_after) == len(events_before) - 1

    def test_delete_event_removes_seismograms(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that deleting an event also deletes its seismograms."""
        seis_before = cli_json("seismogram dump")
        events = cli_json("event dump")
        target_id = events[0]["id"]

        cli(f"event delete {target_id}")

        seis_after = cli_json("seismogram dump")
        assert len(seis_after) < len(seis_before)


# ===================================================================
# Event parameters
# ===================================================================


@pytest.mark.cli
class TestEventParameters:
    """Tests for event parameter CLI commands."""

    def test_parameter_list(
        self, loaded_engine: Engine, cli: Callable[[str], None]
    ) -> None:
        """Verifies that parameter list command runs successfully."""
        cli("event parameter list")

    def test_parameter_get_and_set(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies getting and setting event parameters."""
        cli("event parameter get completed")
        assert "False" in capsys.readouterr().out

        cli("event parameter set completed true")

        cli("event parameter get completed")
        assert "True" in capsys.readouterr().out

    def test_parameter_dump(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that parameter dump returns parameter data."""
        data = cli_json("event parameter dump")
        assert "completed" in data


# ===================================================================
# Station operations
# ===================================================================


@pytest.mark.cli
class TestStationOperations:
    """Tests for station-related CLI commands."""

    def test_station_list(
        self, loaded_engine: Engine, cli: Callable[[str], None]
    ) -> None:
        """Verifies that station list command runs successfully."""
        cli("station list --all")

    def test_station_dump(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that station dump returns a list of stations."""
        stations = cli_json("station dump")
        assert len(stations) > 0

    def test_delete_station(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a station can be deleted."""
        stations = cli_json("station dump")
        target_id = stations[0]["id"]

        cli(f"station delete {target_id}")

        stations_after = cli_json("station dump")
        assert len(stations_after) == len(stations) - 1

    def test_delete_station_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a station can be deleted using a shortened ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        stations = cli_json("station dump")
        target_id = stations[0]["id"]
        short_id = target_id[:8]

        cli(f"station delete {short_id}")

        stations_after = cli_json("station dump")
        assert len(stations_after) == len(stations) - 1


# ===================================================================
# Seismogram operations
# ===================================================================


@pytest.mark.cli
class TestSeismogramOperations:
    """Tests for seismogram-related CLI commands."""

    def test_seismogram_list(
        self, loaded_engine: Engine, cli: Callable[[str], None]
    ) -> None:
        """Verifies that seismogram list command runs successfully."""
        cli("seismogram list")

    def test_seismogram_dump(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that seismogram dump returns a list of seismograms."""
        data = cli_json("seismogram dump")
        assert len(data) > 0

    def test_delete_seismogram(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a seismogram can be deleted."""
        seis = cli_json("seismogram dump")
        target_id = seis[0]["id"]

        cli(f"seismogram delete {target_id}")

        seis_after = cli_json("seismogram dump")
        assert len(seis_after) == len(seis) - 1

    def test_delete_seismogram_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a seismogram can be deleted using a shortened ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        seis = cli_json("seismogram dump")
        target_id = seis[0]["id"]
        short_id = target_id[:8]

        cli(f"seismogram delete {short_id}")

        seis_after = cli_json("seismogram dump")
        assert len(seis_after) == len(seis) - 1


# ===================================================================
# Snapshot lifecycle
# ===================================================================


@pytest.mark.cli
class TestSnapshotLifecycle:
    """Tests for snapshot creation, deletion, and rollback."""

    def test_create_snapshot(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a snapshot can be created."""
        cli("snapshot create initial")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        snapshots = data["snapshots"]
        assert len(snapshots) == 1
        assert snapshots[0]["comment"] == "initial"
        assert len(data["event_parameters"]) == 1
        assert len(data["seismogram_parameters"]) > 0

    def test_create_multiple_snapshots(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that multiple snapshots can be created."""
        cli("snapshot create first")
        cli("snapshot create second")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        snapshots = data["snapshots"]
        assert len(snapshots) == 2
        comments = {s["comment"] for s in snapshots}
        assert comments == {"first", "second"}

    def test_delete_snapshot(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a snapshot can be deleted."""
        cli("snapshot create to-delete")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        snapshots = data["snapshots"]
        assert len(snapshots) == 1

        cli(f"snapshot delete {snapshots[0]['id']}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict)
        assert len(data_after["snapshots"]) == 0

    def test_delete_snapshot_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a snapshot can be deleted using a shortened ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("snapshot create to-delete")
        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        snapshots = data["snapshots"]
        assert len(snapshots) == 1
        short_id = snapshots[0]["id"][:8]

        cli(f"snapshot delete {short_id}")

        data_after = cli_json("snapshot dump")
        assert isinstance(data_after, dict)
        assert len(data_after["snapshots"]) == 0

    def test_snapshot_list(
        self, loaded_engine: Engine, cli: Callable[[str], None]
    ) -> None:
        """Verifies that snapshot list command runs successfully."""
        cli("snapshot create")
        cli("snapshot list")

    def test_rollback_snapshot(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Rollback restores parameter values from a snapshot."""
        cli("snapshot create before-change")

        cli("event parameter set completed true")
        cli("event parameter get completed")
        assert "True" in capsys.readouterr().out

        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        cli(f"snapshot rollback {data['snapshots'][0]['id']}")

        cli("event parameter get completed")
        assert "False" in capsys.readouterr().out

    def test_rollback_snapshot_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that rollback works with a shortened snapshot ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        cli("snapshot create before-change")

        cli("event parameter set completed true")
        cli("event parameter get completed")
        assert "True" in capsys.readouterr().out

        data = cli_json("snapshot dump")
        assert isinstance(data, dict)
        short_id = data["snapshots"][0]["id"][:8]
        cli(f"snapshot rollback {short_id}")

        cli("event parameter get completed")
        assert "False" in capsys.readouterr().out


# ===================================================================
# Full workflow: add → delete → re-add
# ===================================================================


@pytest.mark.cli
class TestDataReaddWorkflow:
    """Delete all data then add it back."""

    def test_delete_all_events_and_readd(
        self,
        loaded_engine: Engine,
        multi_event_data: Sequence[Path],
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that data can be re-added after deletion."""
        events_before = cli_json("event dump")
        assert len(events_before) > 0

        for event in events_before:
            cli(f"event delete {event['id']}")

        events_empty = cli_json("event dump")
        assert len(events_empty) == 0

        seis_empty = cli_json("seismogram dump")
        assert len(seis_empty) == 0

        files = " ".join(str(f) for f in multi_event_data)
        cli(f"data add {files} --no-progress")

        events_after = cli_json("event dump")
        assert len(events_after) == len(events_before)
