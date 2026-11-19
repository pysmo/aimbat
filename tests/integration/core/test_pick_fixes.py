"""Integration tests for selecting and fixing stored picks."""

import uuid
from collections.abc import Callable, Generator
from dataclasses import dataclass

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session

from aimbat.core import (
    PickSelection,
    create_snapshot,
    dump_pick_table,
    match_pick,
    name_picks,
    promote_existing_picks,
    promote_phase_picks,
    promote_picks,
    remove_phase,
    remove_picks,
    restore_picks,
    retry_pick_matching,
    select_picks,
    set_initial_pick,
    store_picks,
)
from aimbat.io import DataType, SourcePick, StationEventTarget
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatPhase,
    AimbatPick,
    AimbatSeismogram,
    AimbatStation,
    PickOrigin,
)

_ORIGIN = Timestamp("2020-01-01T00:00:00", tz="UTC")
_BEGIN = _ORIGIN + Timedelta(minutes=5)


def _at(seconds: float) -> Timestamp:
    return _BEGIN + Timedelta(seconds=seconds)


def _seismogram(session: Session, event: AimbatEvent, name: str) -> AimbatSeismogram:
    station = AimbatStation(
        name=name,
        network="XX",
        location="00",
        channel="BHZ",
        latitude=10.0,
        longitude=10.0,
    )
    seismogram = AimbatSeismogram(
        begin_time=_BEGIN,
        delta=Timedelta(seconds=0.05),
        event=event,
        station=station,
    )
    seismogram.datasource = AimbatDataSource(
        sourcename=f"/data/{uuid.uuid4().hex}.sac", datatype=DataType.SAC
    )
    session.add(seismogram)
    session.flush()
    return seismogram


def _pick(
    session: Session,
    seismogram: AimbatSeismogram,
    key: str,
    seconds: float,
    label: str | None,
) -> AimbatPick:
    (pick,) = store_picks(
        session,
        [SourcePick(_at(seconds), key, label=label)],
        source_name=f"/data/{key}.json",
        source_type=DataType.SAC,
        source_seismogram=seismogram,
    ).stored
    return pick


@dataclass
class _Project:
    session: Session
    event: AimbatEvent
    abc: AimbatSeismogram
    def_: AimbatSeismogram
    unnamed: AimbatPick
    """Unnamed and unlabelled, on ABC at 30 s."""
    labelled: AimbatPick
    """Unnamed, labelled "first arrival", on DEF at 60 s."""
    promoted: AimbatPick
    """Promoted P, on ABC at 20 s."""


@pytest.fixture
def project(engine: Engine) -> Generator[_Project]:
    """One event with two seismograms and three picks."""
    with Session(engine) as session:
        event = AimbatEvent(time=_ORIGIN, latitude=0.0, longitude=0.0)
        session.add(event)
        abc = _seismogram(session, event, "ABC")
        def_ = _seismogram(session, event, "DEF")
        unnamed = _pick(session, abc, "a", 30, None)
        labelled = _pick(session, def_, "b", 60, "first arrival")
        promoted = _pick(session, abc, "c", 20, "P")
        promote_picks(session, [promoted])
        yield _Project(session, event, abc, def_, unnamed, labelled, promoted)


def _ids(picks: list[AimbatPick]) -> set[uuid.UUID]:
    return {pick.id for pick in picks}


class TestSelectPicks:
    """Tests for `select_picks`."""

    @pytest.mark.parametrize(
        ("make", "expected"),
        [
            pytest.param(
                lambda p: PickSelection(event_id=p.event.id),
                ("unnamed", "labelled", "promoted"),
                id="event",
            ),
            pytest.param(
                lambda p: PickSelection(seismogram_ids=(p.abc.id,)),
                ("unnamed", "promoted"),
                id="seismogram",
            ),
            pytest.param(
                lambda p: PickSelection(station_ids=(p.def_.station_id,)),
                ("labelled",),
                id="station",
            ),
            pytest.param(
                lambda p: PickSelection(label="first arrival"),
                ("labelled",),
                id="label",
            ),
            pytest.param(
                lambda p: PickSelection(event_id=p.event.id, unnamed=True),
                ("unnamed", "labelled"),
                id="unnamed",
            ),
            pytest.param(
                lambda p: PickSelection(phase_name="P"),
                ("promoted",),
                id="phase",
            ),
            pytest.param(
                lambda p: PickSelection(time_from=_at(25), time_to=_at(40)),
                ("unnamed",),
                id="absolute-window",
            ),
            pytest.param(
                lambda p: PickSelection(time_to=Timedelta(seconds=325)),
                ("promoted",),
                id="relative-window",
            ),
        ],
    )
    def test_criteria(
        self,
        project: _Project,
        make: Callable[[_Project], PickSelection],
        expected: tuple[str, ...],
    ) -> None:
        picks = select_picks(project.session, make(project))
        assert _ids(picks) == {getattr(project, name).id for name in expected}

    def test_ordered_by_time(self, project: _Project) -> None:
        picks = select_picks(project.session, PickSelection(event_id=project.event.id))
        assert [p.time for p in picks] == sorted(p.time for p in picks)

    def test_no_criteria_refused(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="at least one criterion"):
            select_picks(project.session, PickSelection())

    def test_unknown_pick_refused(self, project: _Project) -> None:
        with pytest.raises(NoResultFound, match="No pick found"):
            select_picks(project.session, PickSelection(pick_ids=(uuid.uuid4(),)))

    def test_dismissed_pick_refused(self, project: _Project) -> None:
        project.unnamed.dismissed = True
        project.session.flush()
        selection = PickSelection(pick_ids=(project.unnamed.id,))
        with pytest.raises(ValueError, match="dismissed"):
            select_picks(project.session, selection)

    def test_naive_time_refused(self) -> None:
        with pytest.raises(ValueError, match="no time zone"):
            PickSelection(time_from=Timestamp("2020-01-01T00:00:00"))

    def test_relative_bound_leaves_out_unresolved_picks(
        self, project: _Project
    ) -> None:
        stray = AimbatPick(time=_at(0), origin=PickOrigin.MANUAL, target_station="XYZ")
        project.session.add(stray)
        project.session.flush()
        picks = select_picks(
            project.session, PickSelection(time_from=Timedelta(seconds=0))
        )
        assert stray.id not in _ids(picks)


class TestDumpPickTable:
    """Tests for `dump_pick_table`."""

    def test_every_pick_with_its_state(self, project: _Project) -> None:
        project.unnamed.dismissed = True
        project.session.flush()
        states = {
            record["id"]: record["state"] for record in dump_pick_table(project.session)
        }
        assert states == {
            str(project.unnamed.id): "dismissed",
            str(project.labelled.id): "unnamed",
            str(project.promoted.id): "promoted",
        }


class TestNamePicks:
    """Tests for `name_picks`."""

    def test_named_picks_promoted_into_a_new_phase(self, project: _Project) -> None:
        picks = [project.unnamed, project.labelled]
        report = name_picks(project.session, picks, "PKP")
        assert [phase.name for phase in report.phases_created] == ["PKP"]
        assert {row.pick_id for row in report.rows} == _ids(picks)
        assert project.labelled.label == "first arrival"

    def test_promoted_pick_refused(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="Promoted picks keep"):
            name_picks(project.session, [project.unnamed, project.promoted], "S")
        assert project.unnamed.phase_name is None
        assert project.promoted.phase_name == "P"

    def test_invalid_name_refused(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            name_picks(project.session, [project.unnamed], "P P")

    def test_existing_row_is_a_conflict(self, project: _Project) -> None:
        report = name_picks(project.session, [project.unnamed], "P")
        assert report.rows == []
        assert report.conflicts == [project.unnamed]


class TestPromote:
    """Tests for `promote_phase_picks` and `promote_existing_picks`."""

    def test_phase_created_for_named_picks(self, project: _Project) -> None:
        pick = _pick(project.session, project.def_, "d", 70, "S")
        report = promote_phase_picks(project.session, "S", event_id=project.event.id)
        assert [phase.name for phase in report.phases_created] == ["S"]
        assert [row.pick_id for row in report.rows] == [pick.id]

    def test_unnamed_pick_refused(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="no phase name"):
            promote_existing_picks(project.session, [project.unnamed.id])

    def test_conflict_kept_without_replace(self, project: _Project) -> None:
        other = _pick(project.session, project.abc, "d", 40, "P")
        report = promote_existing_picks(project.session, [other.id])
        assert report.conflicts == [other]
        assert not project.promoted.dismissed

    def test_replace_takes_over_the_row(self, project: _Project) -> None:
        (row,) = project.abc.phase_rows
        row.select = False
        other = _pick(project.session, project.abc, "d", 40, "P")
        report = promote_existing_picks(project.session, [other.id], replace_rows=True)
        assert report.replaced == [project.promoted]
        assert project.promoted.dismissed
        assert row.pick_id == other.id
        assert row.select is False

    def test_replace_refuses_two_picks_for_one_row(self, project: _Project) -> None:
        first = _pick(project.session, project.abc, "d", 40, "P")
        second = _pick(project.session, project.abc, "e", 45, "P")
        with pytest.raises(ValueError, match="same seismogram and phase"):
            promote_existing_picks(
                project.session, [first.id, second.id], replace_rows=True
            )


def _coded_pick(
    session: Session,
    key: str,
    station: str,
    *,
    event_time: Timestamp = _ORIGIN,
    label: str | None = "S",
    seconds: float = 50,
) -> AimbatPick:
    """Store a pick read with a station code of network XX, location 00."""
    target = StationEventTarget(
        network="XX", station=station, location="00", event_time=event_time
    )
    (pick,) = store_picks(
        session,
        [SourcePick(_at(seconds), key, label=label, target=target)],
        source_name=f"/data/{key}.json",
        source_type=DataType.SAC,
    ).stored
    return pick


class TestMatchPick:
    """Tests for `match_pick` and `retry_pick_matching`."""

    def test_matched_and_promoted_with_a_code_warning(self, project: _Project) -> None:
        pick = _coded_pick(project.session, "m", "GHI")
        assert pick.seismogram_id is None and pick.event_id == project.event.id
        report = match_pick(project.session, pick.id, project.def_.id)
        assert pick.seismogram_id == project.def_.id
        assert pick.event_id is None
        assert [row.pick_id for row in report.rows] == [pick.id]
        (warning,) = report.warnings
        assert "'GHI'" in warning and "'DEF'" in warning

    def test_seismogram_of_another_event_refused(self, project: _Project) -> None:
        other = AimbatEvent(
            time=_ORIGIN + Timedelta(days=1), latitude=0.0, longitude=0.0
        )
        project.session.add(other)
        seismogram = _seismogram(project.session, other, "XYZ")
        pick = _coded_pick(project.session, "m", "GHI")
        with pytest.raises(ValueError, match="belongs to event"):
            match_pick(project.session, pick.id, seismogram.id)
        assert pick.seismogram_id is None

    def test_pick_whose_event_is_unknown_refused(self, project: _Project) -> None:
        pick = _coded_pick(
            project.session, "m", "GHI", event_time=_ORIGIN + Timedelta(days=3)
        )
        with pytest.raises(ValueError, match="not in the project"):
            match_pick(project.session, pick.id, project.def_.id)

    def test_matched_pick_refused(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="already matched"):
            match_pick(project.session, project.unnamed.id, project.def_.id)

    def test_pick_before_the_seismogram_refused(self, project: _Project) -> None:
        pick = _coded_pick(project.session, "m", "GHI", seconds=-10)
        with pytest.raises(ValueError, match="before the begin time"):
            match_pick(project.session, pick.id, project.def_.id)
        assert pick.seismogram_id is None
        assert pick.event_id == project.event.id

    def test_retry_matches_once_the_seismogram_exists(self, project: _Project) -> None:
        pick = _coded_pick(project.session, "m", "JKL")
        jkl = _seismogram(project.session, project.event, "JKL")
        matched, report = retry_pick_matching(
            project.session, event_id=project.event.id
        )
        assert matched == [pick]
        assert pick.seismogram_id == jkl.id
        assert [row.pick_id for row in report.rows] == [pick.id]


class TestSetInitialPick:
    """Tests for `set_initial_pick`."""

    def test_manual_pick_in_a_new_phase(self, project: _Project) -> None:
        pick, report = set_initial_pick(project.session, project.def_.id, "S", _at(80))
        assert pick.origin is PickOrigin.MANUAL
        assert [phase.name for phase in report.phases_created] == ["S"]
        assert [row.pick_id for row in report.rows] == [pick.id]

    def test_existing_row_refused_without_replace(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="already has a P pick"):
            set_initial_pick(project.session, project.abc.id, "P", _at(25))
        assert project.abc.phase_rows[0].pick_id == project.promoted.id

    def test_replace_takes_over_the_row(self, project: _Project) -> None:
        pick, report = set_initial_pick(
            project.session, project.abc.id, "P", _at(25), replace_row=True
        )
        assert report.replaced == [project.promoted]
        assert project.promoted.dismissed
        assert project.abc.phase_rows[0].pick_id == pick.id

    def test_naive_time_refused(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="no time zone"):
            set_initial_pick(
                project.session, project.def_.id, "S", Timestamp("2020-01-01")
            )


class TestRemoveAndRestore:
    """Tests for `remove_picks` and `restore_picks`."""

    def test_dismiss_deletes_the_row(self, project: _Project) -> None:
        report = remove_picks(project.session, [project.promoted])
        assert report.dismissed == [project.promoted.id]
        assert report.rows_deleted == 1
        assert project.promoted.dismissed
        assert project.abc.phase_rows == []

    def test_restore_promotes_again(self, project: _Project) -> None:
        remove_picks(project.session, [project.promoted])
        report = restore_picks(project.session, [project.promoted])
        assert not project.promoted.dismissed
        assert [row.pick_id for row in report.rows] == [project.promoted.id]

    def test_restore_refuses_picks_not_dismissed(self, project: _Project) -> None:
        with pytest.raises(ValueError, match="not dismissed"):
            restore_picks(project.session, [project.unnamed])

    def test_dismissed_pick_not_stored_again(self, project: _Project) -> None:
        remove_picks(project.session, [project.unnamed])
        again = store_picks(
            project.session,
            [SourcePick(_at(30), "a")],
            source_name="/data/a.json",
            source_type=DataType.SAC,
            source_seismogram=project.abc,
        )
        assert again.stored == [] and again.already_present == 1
        assert project.session.get_one(AimbatPick, project.unnamed.id).dismissed

    def test_purged_pick_stored_again(self, project: _Project) -> None:
        pick_id = project.unnamed.id
        report = remove_picks(project.session, [project.unnamed], purge=True)
        assert report.purged == [pick_id]
        assert project.session.get(AimbatPick, pick_id) is None
        again = store_picks(
            project.session,
            [SourcePick(_at(30), "a")],
            source_name="/data/a.json",
            source_type=DataType.SAC,
            source_seismogram=project.abc,
        )
        assert len(again.stored) == 1


class TestRemovePhase:
    """Tests for `remove_phase`."""

    def test_counts_and_dismissed_picks(self, project: _Project) -> None:
        conflict = _pick(project.session, project.abc, "d", 40, "P")
        (row,) = project.abc.phase_rows
        phase_id = row.phase_id
        create_snapshot(project.session, phase_id)
        report = remove_phase(project.session, phase_id)
        assert (report.rows, report.snapshots, report.dismissed_picks) == (1, 1, 2)
        assert project.session.get(AimbatPhase, phase_id) is None
        assert project.session.get_one(AimbatPick, project.promoted.id).dismissed
        assert project.session.get_one(AimbatPick, conflict.id).dismissed
        assert not project.session.get_one(AimbatPick, project.unnamed.id).dismissed
