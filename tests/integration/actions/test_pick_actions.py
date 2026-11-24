"""Integration tests for the actions that edit stored picks."""

import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
from pandas import Timedelta
from sqlalchemy import Engine, func
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from pysmo.classes import SAC

from aimbat import actions
from aimbat.core import PickNaming, PickSelection, store_picks
from aimbat.core._validity import compute_digests
from aimbat.io import DataType, SourcePick
from aimbat.logger import logger
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPick,
    AimbatSeismogramParameters,
    AimbatSnapshot,
)


def _add_picks(engine: Engine, label: str | None) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Store a pick 5 s after the initial pick of each seismogram of the first event."""
    with Session(engine) as session:
        event = session.exec(
            select(AimbatEvent).order_by(col(AimbatEvent.time))
        ).first()
        assert event is not None
        ids = []
        for seismogram in event.seismograms:
            ids += [
                pick.id
                for pick in store_picks(
                    session,
                    [
                        SourcePick(
                            seismogram.phase_rows[0].initial_pick
                            + Timedelta(seconds=5),
                            "extra",
                            label=label,
                        )
                    ],
                    source_name=f"extra-{seismogram.id}",
                    source_type=DataType.SAC,
                    source_seismogram=seismogram,
                ).stored
            ]
        session.commit()
        return event.id, ids


def _count(engine: Engine, model: type[AimbatSnapshot] | type[AimbatPhase]) -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(model)).one()


class TestNamePicks:
    """Tests for `actions.name_picks`."""

    def test_named_promoted_and_saved(self, loaded_engine: Engine) -> None:
        event_id, ids = _add_picks(loaded_engine, None)
        snapshots = _count(loaded_engine, AimbatSnapshot)
        result = actions.name_picks(
            PickSelection(event_id=event_id, unnamed=True), "S", engine=loaded_engine
        )
        assert sorted(result.picks) == sorted(ids)
        assert result.promoted == {"S": len(ids)}
        assert [phase.name for phase in result.phases_created] == ["S"]
        assert result.warnings == []
        assert result.snapshotted_phase_ids == [result.phases_created[0].phase_id]
        assert _count(loaded_engine, AimbatSnapshot) == snapshots + 1
        with Session(loaded_engine) as session:
            assert {session.get_one(AimbatPick, i).phase_name for i in ids} == {"S"}

    def test_no_snapshot(self, loaded_engine: Engine) -> None:
        event_id, _ = _add_picks(loaded_engine, None)
        snapshots = _count(loaded_engine, AimbatSnapshot)
        result = actions.name_picks(
            PickSelection(event_id=event_id, unnamed=True),
            "S",
            auto_snapshot=False,
            engine=loaded_engine,
        )
        assert result.promoted
        assert result.snapshotted_phase_ids == []
        assert _count(loaded_engine, AimbatSnapshot) == snapshots

    def test_dry_run_changes_nothing(self, loaded_engine: Engine) -> None:
        event_id, ids = _add_picks(loaded_engine, None)
        phases = _count(loaded_engine, AimbatPhase)
        result = actions.name_picks(
            PickSelection(event_id=event_id, unnamed=True),
            "S",
            dry_run=True,
            engine=loaded_engine,
        )
        assert result.dry_run
        assert result.promoted == {"S": len(ids)}
        assert _count(loaded_engine, AimbatPhase) == phases
        with Session(loaded_engine) as session:
            assert all(session.get_one(AimbatPick, i).phase_name is None for i in ids)

    def test_nonstandard_name_warned_once(self, loaded_engine: Engine) -> None:
        event_id, ids = _add_picks(loaded_engine, None)
        messages: list[str] = []
        sink = logger.add(messages.append, level="WARNING", format="{message}")
        try:
            result = actions.name_picks(
                PickSelection(event_id=event_id, unnamed=True),
                "Pdiff",
                engine=loaded_engine,
            )
        finally:
            logger.remove(sink)
        assert result.promoted == {"Pdiff": len(ids)}
        assert len(result.warnings) == 1
        assert "'Pdiff'" in result.warnings[0]
        assert [m.strip() for m in messages] == result.warnings

    def test_promoted_picks_refused(self, loaded_engine: Engine) -> None:
        event_id, _ = _add_picks(loaded_engine, None)
        with pytest.raises(ValueError, match="Promoted picks keep"):
            actions.name_picks(
                PickSelection(event_id=event_id), "S", engine=loaded_engine
            )


class TestPromote:
    """Tests for `actions.promote_phase_picks` and `actions.promote_picks`."""

    def test_phase_picks_of_all_events(self, loaded_engine: Engine) -> None:
        _, ids = _add_picks(loaded_engine, "S")
        result = actions.promote_phase_picks("all", "S", engine=loaded_engine)
        assert sorted(result.picks) == sorted(ids)
        assert len(result.phases_created) == 1
        assert result.snapshotted_phase_ids == [result.phases_created[0].phase_id]
        assert result.warnings == []

    def test_nonstandard_phase_warned(self, loaded_engine: Engine) -> None:
        _add_picks(loaded_engine, "Pdiff")
        result = actions.promote_phase_picks("all", "Pdiff", engine=loaded_engine)
        assert len(result.phases_created) == 1
        assert len(result.warnings) == 1
        assert "'Pdiff'" in result.warnings[0]

    def test_unknown_event_refused(self, loaded_engine: Engine) -> None:
        with pytest.raises(NoResultFound):
            actions.promote_phase_picks(uuid.uuid4(), "S", engine=loaded_engine)

    def test_replace(self, loaded_engine: Engine) -> None:
        _, ids = _add_picks(loaded_engine, "P")
        result = actions.promote_picks(ids, replace=True, engine=loaded_engine)
        assert len(result.replaced) == len(ids)
        assert result.promoted == {}
        assert result.snapshotted_phase_ids == []
        with Session(loaded_engine) as session:
            dismissed = [session.get_one(AimbatPick, i) for i in result.replaced]
        assert all(pick.dismissed for pick in dismissed)


def _first_row(engine: Engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seismogram, phase and pick of a row of the first event."""
    with Session(engine) as session:
        event = session.exec(
            select(AimbatEvent).order_by(col(AimbatEvent.time))
        ).first()
        assert event is not None
        seismogram = sorted(event.seismograms, key=lambda s: str(s.id))[0]
        row = seismogram.phase_rows[0]
        return seismogram.id, row.phase_id, row.pick_id


class TestSetRemoveRestore:
    """Tests for `actions.set_initial_pick`, `remove_picks` and `restore_picks`."""

    def test_set_refused_on_an_existing_row(self, loaded_engine: Engine) -> None:
        seismogram_id, _, pick_id = _first_row(loaded_engine)
        with Session(loaded_engine) as session:
            time = session.get_one(AimbatPick, pick_id).time + Timedelta(seconds=1)
        with pytest.raises(ValueError, match="already has a P pick"):
            actions.set_initial_pick(seismogram_id, "P", time, engine=loaded_engine)

    def test_remove_then_restore_snapshots(self, loaded_engine: Engine) -> None:
        _, phase_id, pick_id = _first_row(loaded_engine)
        snapshots = _count(loaded_engine, AimbatSnapshot)
        removed = actions.remove_picks(
            PickSelection(pick_ids=(pick_id,)), engine=loaded_engine
        )
        assert removed.picks == [pick_id]
        assert removed.rows_deleted == 1
        assert _count(loaded_engine, AimbatSnapshot) == snapshots
        restored = actions.restore_picks(
            PickSelection(pick_ids=(pick_id,)), engine=loaded_engine
        )
        assert restored.promoted == {"P": 1}
        assert restored.snapshotted_phase_ids == [phase_id]
        assert _count(loaded_engine, AimbatSnapshot) == snapshots + 1

    def test_purge_selects_dismissed_picks(self, loaded_engine: Engine) -> None:
        _, _, pick_id = _first_row(loaded_engine)
        selection = PickSelection(pick_ids=(pick_id,))
        actions.remove_picks(selection, engine=loaded_engine)
        purged = actions.remove_picks(selection, purge=True, engine=loaded_engine)
        assert purged.picks == [pick_id]
        with Session(loaded_engine) as session:
            assert session.get(AimbatPick, pick_id) is None


@dataclass(frozen=True)
class _Source:
    """A data source of the first event, with the pick of its first row."""

    path: Path
    key: str
    phase_id: uuid.UUID
    row_id: uuid.UUID
    pick_id: uuid.UUID


def _first_source(engine: Engine) -> _Source:
    with Session(engine) as session:
        event = session.exec(
            select(AimbatEvent).order_by(col(AimbatEvent.time))
        ).first()
        assert event is not None
        seismogram = sorted(event.seismograms, key=lambda s: str(s.id))[0]
        row = seismogram.phase_rows[0]
        key = row.pick.source_key
        assert key is not None
        return _Source(
            Path(seismogram.datasource.sourcename),
            key,
            row.phase_id,
            row.id,
            row.pick_id,
        )


def _edit_header(
    path: Path, key: str, *, shift: Timedelta | None = None, label: str | None = None
) -> None:
    """Shift the time of a SAC pick header, or set its label."""
    sac = SAC.from_file(path)
    if shift is not None:
        setattr(sac.timestamps, key, getattr(sac.timestamps, key) + shift)
    if label is not None:
        setattr(sac.native, f"k{key}", label)
    sac.write(path)


def _add_header(path: Path, key: str, offset: Timedelta, label: str | None) -> None:
    """Set an empty SAC pick header to a time after the begin time."""
    sac = SAC.from_file(path)
    setattr(sac.timestamps, key, sac.seismogram.begin_time + offset)
    if label is not None:
        setattr(sac.native, f"k{key}", label)
    sac.write(path)


def _pick(engine: Engine, pick_id: uuid.UUID) -> AimbatPick:
    with Session(engine) as session:
        return session.get_one(AimbatPick, pick_id)


def _instance_digest(engine: Engine, phase_id: uuid.UUID) -> str:
    with Session(engine) as session:
        return compute_digests(session, phase_id)[phase_id].instance


class TestAddPicks:
    """Tests for `actions.add_picks`."""

    def test_unchanged_source_skipped(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        result = actions.add_picks([source.path], engine=loaded_engine)
        assert result.picks.stored == 0
        assert result.picks.changed == 0
        assert result.picks.already_present >= 1
        assert result.snapshotted_phase_ids == []

    def test_new_key_stored_and_promoted(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _add_header(source.path, "t5", Timedelta(seconds=40), "S")
        result = actions.add_picks([source.path], engine=loaded_engine)
        assert result.picks.stored == 1
        assert result.picks.promoted == {"S": 1}
        assert [phase.name for phase in result.picks.phases_created] == ["S"]
        assert len(result.snapshotted_phase_ids) == 1
        assert result.picks.warnings == []

    def test_nonstandard_phase_warned(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _add_header(source.path, "t5", Timedelta(seconds=40), "Pdiff")
        result = actions.add_picks([source.path], engine=loaded_engine)
        assert result.picks.promoted == {"Pdiff": 1}
        assert len(result.picks.warnings) == 1
        assert "'Pdiff'" in result.picks.warnings[0]

    def test_dry_run_changes_nothing(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _add_header(source.path, "t5", Timedelta(seconds=40), "S")
        phases = _count(loaded_engine, AimbatPhase)
        result = actions.add_picks([source.path], dry_run=True, engine=loaded_engine)
        assert result.dry_run
        assert result.picks.promoted == {"S": 1}
        assert _count(loaded_engine, AimbatPhase) == phases

    def test_changed_time_reported_without_update(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        before = _pick(loaded_engine, source.pick_id).time
        _edit_header(source.path, source.key, shift=Timedelta(seconds=1))
        result = actions.add_picks([source.path], engine=loaded_engine)
        assert result.picks.changed == 1
        assert result.picks.updated == 0
        assert _pick(loaded_engine, source.pick_id).time == before

    @pytest.mark.parametrize("refined", [False, True], ids=["unrefined", "refined"])
    def test_promoted_time_updated(self, loaded_engine: Engine, refined: bool) -> None:
        source = _first_source(loaded_engine)
        before = _pick(loaded_engine, source.pick_id).time
        if refined:
            with Session(loaded_engine) as session:
                row = session.get_one(AimbatSeismogramParameters, source.row_id)
                row.refined_pick = before + Timedelta(seconds=0.5)
                session.add(row)
                session.commit()
        digest = _instance_digest(loaded_engine, source.phase_id)
        _edit_header(source.path, source.key, shift=Timedelta(seconds=1))
        result = actions.add_picks([source.path], update=True, engine=loaded_engine)
        assert result.picks.updated == 1
        assert result.picks.rows_deleted == 0
        after = _pick(loaded_engine, source.pick_id).time
        assert abs(after - before - Timedelta(seconds=1)) < Timedelta(milliseconds=1)
        with Session(loaded_engine) as session:
            row = session.get_one(AimbatSeismogramParameters, source.row_id)
            assert row.pick_id == source.pick_id
        changed = _instance_digest(loaded_engine, source.phase_id) != digest
        assert changed is not refined

    def test_unpromoted_time_updated(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _add_header(source.path, "t6", Timedelta(seconds=40), None)
        assert actions.add_picks([source.path], engine=loaded_engine).picks.unnamed == 1
        with Session(loaded_engine) as session:
            pick = session.exec(
                select(AimbatPick)
                .where(col(AimbatPick.source_name) == str(source.path))
                .where(col(AimbatPick.source_key) == "t6")
            ).one()
        _edit_header(source.path, "t6", shift=Timedelta(seconds=2))
        result = actions.add_picks([source.path], update=True, engine=loaded_engine)
        assert result.picks.updated == 1
        assert result.picks.promoted == {}
        after = _pick(loaded_engine, pick.id)
        assert after.phase_name is None
        assert abs(after.time - pick.time - Timedelta(seconds=2)) < Timedelta(
            milliseconds=1
        )

    def test_changed_label_moves_the_pick(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _edit_header(source.path, source.key, label="PP")
        result = actions.add_picks([source.path], update=True, engine=loaded_engine)
        assert result.picks.renamed == 1
        assert result.picks.rows_deleted == 1
        assert result.picks.promoted == {"PP": 1}
        pick = _pick(loaded_engine, source.pick_id)
        assert (pick.label, pick.phase_name) == ("PP", "PP")
        with Session(loaded_engine) as session:
            assert session.get(AimbatSeismogramParameters, source.row_id) is None

    def test_dismissed_pick_stays_dismissed(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        selection = PickSelection(pick_ids=(source.pick_id,))
        actions.remove_picks(selection, engine=loaded_engine)
        before = _pick(loaded_engine, source.pick_id).time
        _edit_header(source.path, source.key, shift=Timedelta(seconds=1))
        result = actions.add_picks([source.path], update=True, engine=loaded_engine)
        assert result.picks.changed == 0
        assert result.picks.stored == 0
        pick = _pick(loaded_engine, source.pick_id)
        assert pick.dismissed
        assert pick.time == before

    def test_purged_pick_stored_again(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        selection = PickSelection(pick_ids=(source.pick_id,))
        actions.remove_picks(selection, purge=True, engine=loaded_engine)
        naming = PickNaming(unlabelled_as="P")
        result = actions.add_picks([source.path], naming=naming, engine=loaded_engine)
        assert result.picks.stored == 1
        assert result.picks.promoted == {"P": 1}

    def test_data_add_does_not_read_again(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        before = _pick(loaded_engine, source.pick_id).time
        _edit_header(source.path, source.key, shift=Timedelta(seconds=1))
        result = actions.add_data([source.path], DataType.SAC, engine=loaded_engine)
        assert result.picks.changed == 0
        assert _pick(loaded_engine, source.pick_id).time == before

    def test_update_before_begin_time_refused(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _edit_header(source.path, source.key, shift=Timedelta(hours=-1))
        with pytest.raises(ValueError, match="before the begin time"):
            actions.add_picks([source.path], update=True, engine=loaded_engine)

    def test_update_after_end_time_refused(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _edit_header(source.path, source.key, shift=Timedelta(hours=10))
        with pytest.raises(ValueError, match="after the end time"):
            actions.add_picks([source.path], update=True, engine=loaded_engine)

    def test_new_pick_after_end_time_refused(self, loaded_engine: Engine) -> None:
        source = _first_source(loaded_engine)
        _add_header(source.path, "t5", Timedelta(hours=10), "S")
        with pytest.raises(ValueError, match="after the end time"):
            actions.add_picks([source.path], engine=loaded_engine)

    def test_source_not_in_project_refused(
        self, loaded_engine: Engine, sac_file_good: Path
    ) -> None:
        with pytest.raises(ValueError, match="not in the project"):
            actions.add_picks([sac_file_good], engine=loaded_engine)

    def test_type_without_picks_refused(
        self, loaded_engine: Engine, sac_file_good: Path
    ) -> None:
        with pytest.raises(ValueError, match="hold no picks"):
            actions.add_picks(
                [sac_file_good], DataType.JSON_EVENT, engine=loaded_engine
            )


class TestRemovePhase:
    """Tests for `actions.remove_phase`."""

    def test_declined_keeps_the_phase(self, loaded_engine: Engine) -> None:
        _, phase_id, _ = _first_row(loaded_engine)
        seen: list[actions.RemovePhaseResult] = []

        def decline(pending: actions.RemovePhaseResult) -> bool:
            seen.append(pending)
            return False

        result = actions.remove_phase(phase_id, confirm=decline, engine=loaded_engine)
        assert not result.removed
        assert seen == [result]
        with Session(loaded_engine) as session:
            assert session.get(AimbatPhase, phase_id) is not None

    def test_removed_with_counts(self, loaded_engine: Engine) -> None:
        _, phase_id, pick_id = _first_row(loaded_engine)
        with Session(loaded_engine) as session:
            rows = len(session.get_one(AimbatPhase, phase_id).seismogram_parameters)
        result = actions.remove_phase(phase_id, engine=loaded_engine)
        assert result.removed
        assert result.rows == rows
        assert result.dismissed_picks == rows
        with Session(loaded_engine) as session:
            assert session.get(AimbatPhase, phase_id) is None
            assert session.get_one(AimbatPick, pick_id).dismissed
