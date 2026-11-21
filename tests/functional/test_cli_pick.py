"""Functional tests for the `aimbat pick` commands.

Selection, naming and promotion are tested against `aimbat.core` and
`aimbat.actions`. These tests check the wiring of the options.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from pandas import Timedelta
from sqlalchemy import Engine
from sqlmodel import Session

from pysmo.classes import SAC

from aimbat.app import app
from aimbat.models import AimbatEvent

from testsupport.cli import exit_code
from testsupport.project import add_unpromoted_pick

type _CliJson = Callable[[str], list[Any] | dict[str, Any]]


@pytest.mark.cli
class TestPick:
    """Tests for `pick list`, `pick dump`, `pick name` and `pick promote`."""

    def test_list_unnamed(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        add_unpromoted_pick(loaded_engine, event_id, None)
        capsys.readouterr()
        assert exit_code(f"pick list {event_id} --unnamed") == 0
        output = capsys.readouterr().out
        assert "unnamed" in output
        assert "extra.json" in output

    def test_dump_has_state(
        self, loaded_engine: Engine, cli_json: _CliJson, event_id: str
    ) -> None:
        pick_id = add_unpromoted_pick(loaded_engine, event_id, None)
        records = cli_json("pick dump")
        assert isinstance(records, list)
        (record,) = [r for r in records if r["id"] == pick_id]
        assert record["state"] == "unnamed"

    def test_name(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        cli_json: _CliJson,
        event_id: str,
    ) -> None:
        pick_id = add_unpromoted_pick(loaded_engine, event_id, None)
        capsys.readouterr()
        assert exit_code(f"pick name S --event {event_id} --unnamed --from 0") == 0
        output = capsys.readouterr().out
        assert "Named 1 pick(s) S." in output
        assert "Promoted 1 pick(s) (S: 1)." in output
        assert "Snapshotted 1 phase(s)." in output
        records = cli_json("pick dump")
        assert isinstance(records, list)
        (record,) = [r for r in records if r["id"] == pick_id]
        assert record["state"] == "promoted"

    def test_name_no_snapshot(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        add_unpromoted_pick(loaded_engine, event_id, None)
        capsys.readouterr()
        command = f"pick name S --event {event_id} --unnamed --no-snapshot"
        assert exit_code(command) == 0
        output = capsys.readouterr().out
        assert "Promoted 1 pick(s) (S: 1)." in output
        assert "Snapshotted" not in output

    def test_name_refuses_time_without_offset(
        self, loaded_engine: Engine, event_id: str
    ) -> None:
        command = f"pick name S --event {event_id} --from 2011-03-11T05:56:00"
        with pytest.raises(ValueError, match="has no offset"):
            app(command)

    def test_promote_by_pick(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        pick_id = add_unpromoted_pick(loaded_engine, event_id, "S")
        capsys.readouterr()
        assert exit_code(f"pick promote --pick {pick_id}") == 0
        output = capsys.readouterr().out
        assert "Promoted 1 pick(s) (S: 1)." in output
        assert "Phase S created" in output

    def test_promote_replace(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        pick_id = add_unpromoted_pick(loaded_engine, event_id, "P")
        capsys.readouterr()
        assert exit_code(f"pick promote --pick {pick_id} --replace") == 0
        output = capsys.readouterr().out
        assert "Replaced the pick of 1 row(s)." in output
        assert "No picks promoted." not in output

    def test_promote_by_phase(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        add_unpromoted_pick(loaded_engine, event_id, "S")
        capsys.readouterr()
        assert exit_code(f"pick promote --event {event_id} --phase S") == 0
        assert "Promoted 1 pick(s) (S: 1)." in capsys.readouterr().out

    def test_promote_needs_phase_or_pick(self, loaded_engine: Engine) -> None:
        with pytest.raises(ValueError, match="either `--phase` or `--pick`"):
            app("pick promote")


@pytest.mark.cli
class TestPickAdd:
    """Tests for `pick add`."""

    def test_changed_time_needs_update(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        with Session(loaded_engine) as session:
            event = session.get_one(AimbatEvent, uuid.UUID(event_id))
            seismogram = sorted(event.seismograms, key=lambda s: str(s.id))[0]
            path = seismogram.datasource.sourcename
            key = seismogram.phase_rows[0].pick.source_key
        assert key is not None
        sac = SAC.from_file(path)
        setattr(sac.timestamps, key, getattr(sac.timestamps, key) + Timedelta(1, "s"))
        sac.write(path)
        capsys.readouterr()
        assert exit_code(["pick", "add", str(path), "--no-progress"]) == 0
        assert "1 stored pick(s) differ from their data source." in (
            " ".join(capsys.readouterr().out.split())
        )
        assert exit_code(["pick", "add", str(path), "--update", "--no-progress"]) == 0
        assert "Updated 1 pick(s)." in capsys.readouterr().out

    def test_dry_run(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        with Session(loaded_engine) as session:
            event = session.get_one(AimbatEvent, uuid.UUID(event_id))
            path = event.seismograms[0].datasource.sourcename
        capsys.readouterr()
        assert exit_code(["pick", "add", str(path), "--dry-run", "--no-progress"]) == 0
        output = capsys.readouterr().out
        assert "already present" in output
        assert "Dry run: nothing was changed." in output


@pytest.mark.cli
class TestPickFixes:
    """Tests for `pick match`, `pick set`, `pick remove` and `pick restore`."""

    def test_match_needs_pick_and_seismogram(self, loaded_engine: Engine) -> None:
        with pytest.raises(ValueError, match="pick and a seismogram"):
            app("pick match")

    def test_retry_takes_no_pick(self, loaded_engine: Engine, event_id: str) -> None:
        pick_id = add_unpromoted_pick(loaded_engine, event_id, None)
        with pytest.raises(ValueError, match="takes no pick"):
            app(f"pick match {pick_id} --retry")

    def test_retry(
        self, loaded_engine: Engine, capsys: pytest.CaptureFixture[str]
    ) -> None:
        capsys.readouterr()
        assert exit_code("pick match --retry") == 0
        assert "Matched 0 pick(s)." in capsys.readouterr().out

    def test_set_replace(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        with Session(loaded_engine) as session:
            event = session.get_one(AimbatEvent, uuid.UUID(event_id))
            seismogram = sorted(event.seismograms, key=lambda s: str(s.id))[0]
            seismogram_id = seismogram.id
            time = seismogram.phase_rows[0].initial_pick + Timedelta(seconds=2)
        capsys.readouterr()
        command = f"pick set {seismogram_id} P {time.isoformat()} --replace"
        assert exit_code(command) == 0
        assert "Replaced the pick of 1 row(s)." in capsys.readouterr().out

    def test_set_refuses_time_without_offset(
        self, loaded_engine: Engine, event_id: str
    ) -> None:
        with Session(loaded_engine) as session:
            event = session.get_one(AimbatEvent, uuid.UUID(event_id))
            seismogram_id = event.seismograms[0].id
        with pytest.raises(ValueError, match="has no offset"):
            app(f"pick set {seismogram_id} P 2011-03-11T05:56:00")

    def test_remove_and_restore(
        self,
        loaded_engine: Engine,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        pick_id = add_unpromoted_pick(loaded_engine, event_id, None)
        capsys.readouterr()
        assert exit_code(f"pick remove --event {event_id} --unnamed") == 0
        assert "Dismissed 1 pick(s). Deleted 0 row(s)." in capsys.readouterr().out
        assert exit_code(f"pick restore {pick_id}") == 0
        assert "Restored 1 pick(s)." in capsys.readouterr().out
        assert exit_code(f"pick remove {pick_id} --purge") == 0
        assert "Deleted 1 pick(s)." in capsys.readouterr().out
