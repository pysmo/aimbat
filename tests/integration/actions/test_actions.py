"""Integration tests for `aimbat.actions`.

Most rules of each operation are tested against `aimbat.core`. These tests
cover what the actions add (one transaction per call, lists of IDs, plain
results that outlive the session, the default engine) and the rules of a
user action as a whole.
"""

import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from pandas import Timedelta
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, col, select

from aimbat import actions, core
from aimbat.core import _iccs as core_iccs
from aimbat.io import DataType, SourcePick
from aimbat.models import (
    AimbatEvent,
    AimbatNote,
    AimbatPhase,
    AimbatPhaseParametersSnapshot,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersSnapshot,
    AimbatSeismogramQuality,
    AimbatSnapshot,
    AimbatStation,
)
from aimbat.types import PhaseParameter, SeismogramParameter

_NAMING = core.PickNaming(unlabelled_as="P")
"""The test data label no picks, so they are named here."""

_UNKNOWN = uuid.UUID(int=0)

type _Model = type[AimbatEvent] | type[AimbatStation] | type[AimbatSeismogram]
type _Delete = Callable[[Sequence[uuid.UUID]], None]


def _ids(engine: Engine, model: _Model) -> list[uuid.UUID]:
    with Session(engine) as session:
        return list(session.exec(select(model.id)).all())


def _phase_ids(engine: Engine) -> list[uuid.UUID]:
    with Session(engine) as session:
        return list(session.exec(select(AimbatPhase.id)).all())


def _phase_of(engine: Engine, seismogram_id: uuid.UUID) -> uuid.UUID:
    with Session(engine) as session:
        seismogram = session.get_one(AimbatSeismogram, seismogram_id)
        return seismogram.phase_rows[0].phase_id


def _seismogram_ids(engine: Engine) -> list[uuid.UUID]:
    with Session(engine) as session:
        return list(session.exec(select(AimbatSeismogram.id)).all())


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return len(session.exec(select(model)).all())


class TestDefaultEngine:
    def test_uses_the_project_engine(self, loaded_engine: Engine) -> None:
        """Without `engine`, an action writes to `aimbat.db.engine`."""
        phase_id = _phase_ids(loaded_engine)[0]

        completed = actions.toggle_phase_completed(phase_id)

        with Session(loaded_engine) as session:
            phase = session.get(AimbatPhase, phase_id)
            assert phase is not None
            assert phase.parameters.completed is completed


class TestListDeletes:
    @pytest.mark.parametrize(
        ("delete", "model"),
        [
            (actions.delete_events, AimbatEvent),
            (actions.delete_stations, AimbatStation),
            (actions.delete_seismograms, AimbatSeismogram),
        ],
    )
    def test_deletes_every_id(
        self, loaded_engine: Engine, delete: _Delete, model: _Model
    ) -> None:
        ids = _ids(loaded_engine, model)[:2]
        before = _count(loaded_engine, model)

        delete(ids)

        assert _count(loaded_engine, model) == before - 2

    @pytest.mark.parametrize(
        ("delete", "model", "label"),
        [
            (actions.delete_events, AimbatEvent, "event"),
            (actions.delete_stations, AimbatStation, "station"),
            (actions.delete_seismograms, AimbatSeismogram, "seismogram"),
        ],
    )
    def test_unknown_id_deletes_nothing(
        self, loaded_engine: Engine, delete: _Delete, model: _Model, label: str
    ) -> None:
        known = _ids(loaded_engine, model)[0]
        before = _count(loaded_engine, model)

        with pytest.raises(NoResultFound, match=f"No {label} found with ID {_UNKNOWN}"):
            delete([known, _UNKNOWN])

        assert _count(loaded_engine, model) == before

    def test_failure_part_way_deletes_nothing(
        self, loaded_engine: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An action is one transaction: a failure undoes what it already did."""
        ids = _ids(loaded_engine, AimbatEvent)[:2]
        real_delete = core.delete_event
        calls = 0

        def _fail_second(session: Session, event_id: uuid.UUID) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated failure")
            real_delete(session, event_id)

        monkeypatch.setattr(core, "delete_event", _fail_second)
        before = _count(loaded_engine, AimbatEvent)

        with pytest.raises(RuntimeError):
            actions.delete_events(ids)

        assert calls == 2
        assert _count(loaded_engine, AimbatEvent) == before

    def test_delete_events_evicts_cached_iccs(self, loaded_engine: Engine) -> None:
        """A deleted event's cached ICCS instances do not linger in the cache."""
        with Session(loaded_engine) as session:
            phase = session.exec(select(AimbatPhase)).first()
            assert phase is not None
            event_id, phase_id = phase.event_id, phase.id
        actions.prepare_iccs(phase_id)
        assert phase_id in core_iccs._iccs_cache

        actions.delete_events([event_id])

        assert phase_id not in core_iccs._iccs_cache

    def test_duplicates_and_empty_list(self, loaded_engine: Engine) -> None:
        seismogram_id = _seismogram_ids(loaded_engine)[0]
        before = _count(loaded_engine, AimbatSeismogram)

        actions.delete_seismograms([])
        actions.delete_seismograms([seismogram_id, seismogram_id])

        assert _count(loaded_engine, AimbatSeismogram) == before - 1

    def test_deleting_events_removes_their_seismograms(
        self, loaded_engine: Engine, multi_event_data: Sequence[Path]
    ) -> None:
        """Deleting every event empties the project, and re-adding restores it."""
        events = _count(loaded_engine, AimbatEvent)
        seismograms = _count(loaded_engine, AimbatSeismogram)

        actions.delete_events(_ids(loaded_engine, AimbatEvent))

        assert _count(loaded_engine, AimbatSeismogram) == 0
        actions.add_data(multi_event_data, DataType.SAC, naming=_NAMING)
        assert _count(loaded_engine, AimbatEvent) == events
        assert _count(loaded_engine, AimbatSeismogram) == seismograms

    def test_delete_snapshots(self, loaded_engine: Engine) -> None:
        phase_id = _phase_ids(loaded_engine)[0]
        actions.create_snapshot(phase_id, "one")
        actions.create_snapshot(phase_id, "two")
        with Session(loaded_engine) as session:
            ids = list(session.exec(select(AimbatSnapshot.id)).all())
        assert len(ids) >= 2

        with pytest.raises(NoResultFound, match="No snapshot found"):
            actions.delete_snapshots([*ids, _UNKNOWN])
        assert _count(loaded_engine, AimbatSnapshot) == len(ids)

        actions.delete_snapshots(ids)
        assert _count(loaded_engine, AimbatSnapshot) == 0

    def test_delete_snapshot_removes_only_its_parameters(
        self, loaded_engine: Engine
    ) -> None:
        phase_id = _phase_ids(loaded_engine)[0]
        actions.create_snapshot(phase_id, "keep")
        actions.create_snapshot(phase_id, "drop")
        with Session(loaded_engine) as session:
            snapshots = {
                s.comment: s.id for s in session.exec(select(AimbatSnapshot)).all()
            }
        per_snapshot = _count(loaded_engine, AimbatSeismogramParametersSnapshot) // 2

        actions.delete_snapshots([snapshots["drop"]])

        with Session(loaded_engine) as session:
            kept = session.get(AimbatSnapshot, snapshots["keep"])
            assert kept is not None
            assert kept.phase_parameters_snapshot is not None
            assert len(kept.seismogram_parameters_snapshots) == per_snapshot
        assert _count(loaded_engine, AimbatPhaseParametersSnapshot) == 1
        assert _count(loaded_engine, AimbatSeismogramParametersSnapshot) == per_snapshot


class TestSeismogramParameters:
    def test_set_on_several(self, loaded_engine: Engine) -> None:
        all_ids = _seismogram_ids(loaded_engine)
        phase_id = _phase_of(loaded_engine, all_ids[0])
        ids = [i for i in all_ids if _phase_of(loaded_engine, i) == phase_id][:3]

        actions.set_seismogram_parameters(
            phase_id, ids, {SeismogramParameter.FLIP: True}
        )

        with Session(loaded_engine) as session:
            for seismogram_id in all_ids:
                seismogram = session.get(AimbatSeismogram, seismogram_id)
                assert seismogram is not None
                assert seismogram.phase_rows[0].flip is (seismogram_id in ids)

    def test_reset_several(self, loaded_engine: Engine) -> None:
        all_ids = _seismogram_ids(loaded_engine)
        phase_id = _phase_of(loaded_engine, all_ids[0])
        ids = [i for i in all_ids if _phase_of(loaded_engine, i) == phase_id][:2]
        actions.set_seismogram_parameters(
            phase_id, ids, {SeismogramParameter.FLIP: True}
        )

        actions.reset_seismogram_parameters(phase_id, ids)

        with Session(loaded_engine) as session:
            flips = session.exec(
                select(AimbatSeismogram).where(col(AimbatSeismogram.id).in_(ids))
            ).all()
            assert all(not s.phase_rows[0].flip for s in flips)

    def test_reset_unknown_id_changes_nothing(self, loaded_engine: Engine) -> None:
        seismogram_id = _seismogram_ids(loaded_engine)[0]
        phase_id = _phase_of(loaded_engine, seismogram_id)
        actions.set_seismogram_parameters(
            phase_id, [seismogram_id], {SeismogramParameter.FLIP: True}
        )

        with pytest.raises(NoResultFound):
            actions.reset_seismogram_parameters(phase_id, [seismogram_id, _UNKNOWN])

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            assert seismogram.phase_rows[0].flip is True


class TestPhaseParameters:
    def test_invalid_value_changes_nothing(self, loaded_engine: Engine) -> None:
        phase_id = _phase_ids(loaded_engine)[0]
        with Session(loaded_engine) as session:
            before = session.get_one(AimbatPhase, phase_id).parameters.min_cc

        with pytest.raises(ValidationError):
            actions.set_phase_parameters(phase_id, {"min_cc": 2.0})  # type: ignore[dict-item]

        with Session(loaded_engine) as session:
            assert session.get_one(AimbatPhase, phase_id).parameters.min_cc == before

    def test_rejected_write_evicts_cached_iccs(self, loaded_engine: Engine) -> None:
        """A refused value an interactive tool applied does not stay cached.

        `min_cc` is unbounded on the pysmo instance but limited to [0, 1] in
        the database, so a tool can leave a value on the cached instance that
        storing then refuses.
        """
        phase_id = _phase_ids(loaded_engine)[0]
        bound = actions.prepare_iccs(phase_id)
        assert core_iccs._iccs_cache.get(phase_id) is bound
        bound.iccs.min_cc = 1.5

        with pytest.raises(ValidationError):
            actions.set_phase_parameters(phase_id, {PhaseParameter.MIN_CC: 1.5})

        assert phase_id not in core_iccs._iccs_cache


class TestPicks:
    def test_sets_each_pick(self, loaded_engine: Engine) -> None:
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            phase_id = event.phases[0].id
            picks = {
                s.id: s.phase_rows[0].initial_pick + Timedelta(seconds=i)
                for i, s in enumerate(event.seismograms)
            }

        actions.set_refined_picks(phase_id, picks)

        with Session(loaded_engine) as session:
            for seismogram_id, pick in picks.items():
                seismogram = session.get(AimbatSeismogram, seismogram_id)
                assert seismogram is not None
                assert seismogram.phase_rows[0].refined_pick == pick

    def test_seismogram_of_another_phase_changes_nothing(
        self, loaded_engine: Engine
    ) -> None:
        with Session(loaded_engine) as session:
            events = session.exec(select(AimbatEvent)).all()
            own, other = events[0].seismograms[0], events[1].seismograms[0]
            phase_id, own_id, other_id = events[0].phases[0].id, own.id, other.id
            picks = {
                own_id: own.phase_rows[0].initial_pick,
                other_id: other.phase_rows[0].initial_pick,
            }
            before = own.phase_rows[0].refined_pick

        with pytest.raises(NoResultFound, match=str(other_id)):
            actions.set_refined_picks(phase_id, picks)

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, own_id)
            assert seismogram is not None
            assert seismogram.phase_rows[0].refined_pick == before


class TestIccs:
    def test_prepare_keeps_the_cc_values(self, loaded_engine: Engine) -> None:
        bound = actions.prepare_iccs(_phase_ids(loaded_engine)[0])

        with Session(loaded_engine) as session:
            ccs = session.exec(
                select(AimbatSeismogramQuality.iccs_cc)
                .join(AimbatSeismogramParameters)
                .where(AimbatSeismogramParameters.phase_id == bound.phase_id)
            ).all()
        assert ccs
        assert all(cc is not None for cc in ccs)

    def test_run_iccs_returns_a_summary(self, loaded_engine: Engine) -> None:
        run = actions.run_iccs(_phase_ids(loaded_engine)[0])

        assert run.summary.message
        assert run.result is not None


def _add_unnamed_pick(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    """Store an unnamed pick on a seismogram of the first phase.

    Returns:
        The IDs of the phase and its event.
    """
    with Session(engine) as session:
        phase = session.get_one(AimbatPhase, _phase_ids(engine)[0])
        row = phase.seismogram_parameters[0]
        core.store_picks(
            session,
            [SourcePick(row.initial_pick + Timedelta(seconds=5), "extra")],
            source_name="extra.json",
            source_type=DataType.SAC,
            source_seismogram=row.seismogram,
        )
        session.commit()
        return phase.id, phase.event_id


_ALIGN_ACTIONS: dict[str, Callable[[uuid.UUID], object]] = {
    "prepare_iccs": actions.prepare_iccs,
    "run_iccs": actions.run_iccs,
    "run_mccc": actions.run_mccc,
}


class TestReadinessEnforced:
    @pytest.mark.parametrize("name", _ALIGN_ACTIONS)
    def test_refused_with_the_items(self, loaded_engine: Engine, name: str) -> None:
        phase_id, _ = _add_unnamed_pick(loaded_engine)

        with pytest.raises(core.NotReadyError) as exc_info:
            _ALIGN_ACTIONS[name](phase_id)

        assert [i.kind for i in exc_info.value.items] == [
            core.ReadinessKind.UNNAMED_PICK
        ]
        assert "aimbat pick name" in str(exc_info.value)

    def test_refused_writes_no_cc_values(self, loaded_engine: Engine) -> None:
        phase_id, _ = _add_unnamed_pick(loaded_engine)

        with pytest.raises(core.NotReadyError):
            actions.prepare_iccs(phase_id)

        with Session(loaded_engine) as session:
            ccs = session.exec(
                select(AimbatSeismogramQuality.iccs_cc)
                .join(AimbatSeismogramParameters)
                .where(AimbatSeismogramParameters.phase_id == phase_id)
            ).all()
        assert all(cc is None for cc in ccs)

    @pytest.mark.parametrize("name", _ALIGN_ACTIONS)
    def test_accepted_after_the_fix(self, loaded_engine: Engine, name: str) -> None:
        phase_id, event_id = _add_unnamed_pick(loaded_engine)
        actions.remove_picks(core.PickSelection(event_id=event_id, unnamed=True))

        _ALIGN_ACTIONS[name](phase_id)

    def test_core_does_not_check(self, loaded_engine: Engine) -> None:
        phase_id, _ = _add_unnamed_pick(loaded_engine)

        with Session(loaded_engine) as session:
            bound = core.create_iccs_instance(session, phase_id)

        assert bound.phase_id == phase_id


class TestAddData:
    def test_result_outlives_the_session(
        self, patched_engine: Engine, multi_event_data: Sequence[Path]
    ) -> None:
        result = actions.add_data(multi_event_data, DataType.SAC, naming=_NAMING)

        assert len(result.sources) == len(multi_event_data)
        assert all(s.new_seismogram for s in result.sources)
        assert set(result.snapshotted_phase_ids) == set(result.picks.phase_rows)
        assert {p.event_id for p in result.picks.phases_created} == {
            s.event_id for s in result.sources
        }
        assert _count(patched_engine, AimbatSeismogram) == len(multi_event_data)

    def test_dry_run_changes_nothing(
        self, patched_engine: Engine, multi_event_data: Sequence[Path]
    ) -> None:
        result = actions.add_data(
            multi_event_data, DataType.SAC, naming=_NAMING, dry_run=True
        )

        assert result.dry_run
        assert len(result.sources) == len(multi_event_data)
        assert result.picks.total_promoted == len(multi_event_data)
        assert {p.event_id for p in result.picks.phases_created} == {
            s.event_id for s in result.sources
        }
        assert result.snapshotted_phase_ids == []
        assert _count(patched_engine, AimbatSeismogram) == 0
        assert _count(patched_engine, AimbatPhase) == 0
        assert _count(patched_engine, AimbatSnapshot) == 0

    def test_readding_reports_nothing_new(
        self, loaded_engine: Engine, multi_event_data: Sequence[Path]
    ) -> None:
        result = actions.add_data(multi_event_data, DataType.SAC, naming=_NAMING)

        assert not any(s.new_seismogram for s in result.sources)
        assert result.snapshotted_phase_ids == []
        assert result.picks.stored == 0
        assert _count(loaded_engine, AimbatSnapshot) == 0

    def test_one_automatic_snapshot_per_phase(
        self, patched_engine: Engine, multi_event_data: Sequence[Path]
    ) -> None:
        """Each snapshot's comment counts the picks added to its own phase."""
        result = actions.add_data(multi_event_data, DataType.SAC, naming=_NAMING)

        added = Counter(s.event_id for s in result.sources)
        assert len(added) > 1
        with Session(patched_engine) as session:
            snapshots = session.exec(select(AimbatSnapshot)).all()
            assert {s.phase.event_id: s.comment for s in snapshots} == {
                event_id: f"Added {n} pick{'' if n == 1 else 's'}"
                for event_id, n in added.items()
            }
            assert all(s.automatic for s in snapshots)

    def test_snapshots_only_the_phases_that_gained_rows(
        self, patched_engine: Engine, multi_event_data: Sequence[Path]
    ) -> None:
        *first, last = multi_event_data
        actions.add_data(first, DataType.SAC, naming=_NAMING)
        before = _count(patched_engine, AimbatSnapshot)

        result = actions.add_data([last], DataType.SAC, naming=_NAMING)

        (source,) = result.sources
        with Session(patched_engine) as session:
            phase = session.exec(
                select(AimbatPhase).where(AimbatPhase.event_id == source.event_id)
            ).one()
            assert result.snapshotted_phase_ids == [phase.id]
            assert result.picks.phase_rows == {phase.id: 1}
            comments = session.exec(
                select(AimbatSnapshot.comment).where(
                    AimbatSnapshot.phase_id == phase.id
                )
            ).all()
            assert "Added 1 pick" in comments
        assert _count(patched_engine, AimbatSnapshot) == before + 1

    def test_without_automatic_snapshots(
        self, patched_engine: Engine, multi_event_data: Sequence[Path]
    ) -> None:
        result = actions.add_data(
            multi_event_data, DataType.SAC, naming=_NAMING, auto_snapshot=False
        )

        assert result.snapshotted_phase_ids == []
        assert _count(patched_engine, AimbatSnapshot) == 0


class TestPruneData:
    @staticmethod
    def _remove_one_source(engine: Engine) -> uuid.UUID:
        with Session(engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            Path(seismogram.datasource.sourcename).unlink()
            return seismogram.id

    def test_dry_run_result_outlives_the_session(self, loaded_engine: Engine) -> None:
        seismogram_id = self._remove_one_source(loaded_engine)

        result = actions.prune_data("all", dry_run=True)

        assert [o.seismogram_id for o in result.orphans] == [seismogram_id]
        assert result.orphans[0].station_name
        assert not result.pruned
        with Session(loaded_engine) as session:
            assert session.get(AimbatSeismogram, seismogram_id) is not None

    def test_confirm_sees_plain_result(self, loaded_engine: Engine) -> None:
        seismogram_id = self._remove_one_source(loaded_engine)
        seen: list[actions.PruneResult] = []

        def confirm(result: actions.PruneResult) -> bool:
            seen.append(result)
            return True

        result = actions.prune_data("all", auto_snapshot=False, confirm=confirm)

        assert [o.seismogram_id for o in seen[0].orphans] == [seismogram_id]
        assert result.pruned
        assert result.orphans[0].event_time is not None
        with Session(loaded_engine) as session:
            assert session.get(AimbatSeismogram, seismogram_id) is None

    def test_scoped_to_one_event(self, loaded_engine: Engine) -> None:
        with Session(loaded_engine) as session:
            events = session.exec(select(AimbatEvent)).all()
            kept, pruned = events[0].seismograms[0], events[1].seismograms[0]
            Path(kept.datasource.sourcename).unlink()
            Path(pruned.datasource.sourcename).unlink()
            kept_id, pruned_id, event_id = kept.id, pruned.id, events[1].id

        actions.prune_data(event_id, auto_snapshot=False, confirm=lambda _: True)

        with Session(loaded_engine) as session:
            assert session.get(AimbatSeismogram, kept_id) is not None
            assert session.get(AimbatSeismogram, pruned_id) is None


class TestNotesAndSnapshots:
    def test_save_note(self, loaded_engine: Engine) -> None:
        event_id = _ids(loaded_engine, AimbatEvent)[0]

        raced = actions.save_note("event", event_id, "hello", expected_previous="")

        assert raced is False
        with Session(loaded_engine) as session:
            note = session.exec(
                select(AimbatNote).where(AimbatNote.event_id == event_id)
            ).one()
            assert note.content == "hello"

    def test_create_and_roll_back(self, loaded_engine: Engine) -> None:
        seismogram_id = _seismogram_ids(loaded_engine)[0]
        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            phase_id = seismogram.phase_rows[0].phase_id
            flip = seismogram.phase_rows[0].flip

        actions.create_snapshot(phase_id, "before")
        actions.set_seismogram_parameters(
            phase_id, [seismogram_id], {SeismogramParameter.FLIP: not flip}
        )
        with Session(loaded_engine) as session:
            snapshot_id = session.exec(
                select(AimbatSnapshot.id).where(AimbatSnapshot.comment == "before")
            ).one()

        result = actions.rollback_to_snapshot(snapshot_id)

        assert result.added_since == ()
        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            assert seismogram.phase_rows[0].flip is flip
            assert session.get(AimbatSnapshot, snapshot_id) is not None
