"""Integration tests for the readiness of phases for processing."""

import uuid
from collections.abc import Generator

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session

from aimbat import settings
from aimbat.core import (
    NotReadyError,
    ReadinessItem,
    ReadinessKind,
    ReadinessSeverity,
    default_phase_parameters,
    promote_picks,
    readiness,
    require_ready,
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
_END = _BEGIN + Timedelta(seconds=100)
_SOURCE = "/data/picks.json"


@pytest.fixture
def session(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Generator[Session]:
    """A session on an empty project whose seismograms end at `_END`."""
    monkeypatch.setattr(settings, "event_duplicate_strict", False)
    monkeypatch.setattr(settings, "event_duplicate_tolerance", Timedelta(seconds=1))
    monkeypatch.setattr(
        settings, "event_duplicate_raise_tolerance", Timedelta(seconds=60)
    )
    monkeypatch.setattr(AimbatSeismogram, "end_time", property(lambda _: _END))
    with Session(engine) as session:
        yield session


def _event(session: Session, time: Timestamp = _ORIGIN) -> AimbatEvent:
    event = AimbatEvent(time=time, latitude=0.0, longitude=0.0)
    session.add(event)
    session.flush()
    return event


def _seismogram(
    session: Session, event: AimbatEvent, *, name: str = "ABC", channel: str = "BHZ"
) -> AimbatSeismogram:
    station = AimbatStation(
        name=name,
        network="XX",
        location="00",
        channel=channel,
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


def _at(seconds: float) -> Timestamp:
    return _BEGIN + Timedelta(seconds=seconds)


def _pick(
    session: Session,
    seismogram: AimbatSeismogram | None,
    key: str,
    *,
    label: str | None = "P",
    seconds: float = 30,
    target: StationEventTarget | None = None,
) -> AimbatPick:
    (pick,) = store_picks(
        session,
        [SourcePick(_at(seconds), key, label=label, target=target)],
        source_name=_SOURCE,
        source_type=DataType.SAC,
        source_seismogram=seismogram,
    ).stored
    return pick


def _by_codes(station: str = "XYZ") -> StationEventTarget:
    return StationEventTarget(
        network="XX", station=station, location="00", event_time=_ORIGIN
    )


def _promoted(session: Session, seismogram: AimbatSeismogram, key: str) -> AimbatPick:
    pick = _pick(session, seismogram, key)
    assert promote_picks(session, [pick]).rows
    return pick


def _phase(session: Session, event: AimbatEvent, name: str) -> AimbatPhase:
    phase = AimbatPhase(
        event_id=event.id, name=name, parameters=default_phase_parameters(name)
    )
    session.add(phase)
    session.flush()
    return phase


def _only(items: list[ReadinessItem], kind: ReadinessKind) -> ReadinessItem:
    (item,) = [i for i in items if i.kind is kind]
    return item


class TestRules:
    """One test for each readiness rule."""

    def test_ready(self, session: Session) -> None:
        _promoted(session, _seismogram(session, _event(session)), "t0")
        assert readiness(session) == []

    def test_r1_unnamed_pick_blocks_every_phase(self, session: Session) -> None:
        event = _event(session)
        seismogram = _seismogram(session, event)
        _promoted(session, seismogram, "t0")
        pick = _pick(session, seismogram, "t1", label=None, seconds=40)
        item = _only(readiness(session), ReadinessKind.UNNAMED_PICK)
        assert item.blocking
        assert (item.phase_id, item.phase_name) == (None, None)
        assert item.pick_ids == (pick.id,)
        assert item.fixes[0] == f"aimbat pick name PHASE --event {event.id} --unnamed"
        assert all(item.covers(phase) for phase in event.phases)

    def test_r2_unmatched_blocks_existing_phase(self, session: Session) -> None:
        event = _event(session)
        _promoted(session, _seismogram(session, event), "t0")
        pick = _pick(session, None, "lost", target=_by_codes())
        item = _only(readiness(session), ReadinessKind.UNMATCHED_PICK)
        assert item.blocking
        assert item.phase_id == event.phases[0].id
        assert item.fixes[0] == f"aimbat pick match {pick.id} SEISMOGRAM"

    def test_r2_unmatched_notice_without_phase(self, session: Session) -> None:
        event = _event(session)
        _seismogram(session, event)
        _pick(session, None, "lost", label="S", target=_by_codes())
        item = _only(readiness(session), ReadinessKind.UNMATCHED_PICK)
        assert item.severity is ReadinessSeverity.NOTICE
        assert (item.phase_id, item.phase_name) == (None, "S")

    def test_r2_names_the_reason(self, session: Session) -> None:
        event = _event(session)
        _seismogram(session, event)
        pick = AimbatPick(
            time=_at(-30),
            phase_name="P",
            origin=PickOrigin.MANUAL,
            target_network="XX",
            target_station="ABC",
            target_location="00",
            target_event_time=_ORIGIN,
            event_id=event.id,
        )
        session.add(pick)
        session.flush()
        item = _only(readiness(session), ReadinessKind.UNMATCHED_PICK)
        assert "before the begin time" in item.message

    def test_r3_ambiguous_unnamed_blocks_every_phase(self, session: Session) -> None:
        event = _event(session)
        _seismogram(session, event, name="AMB", channel="BHZ")
        _seismogram(session, event, name="AMB", channel="BHN")
        pick = AimbatPick(
            time=_at(10),
            origin=PickOrigin.MANUAL,
            target_network="XX",
            target_station="AMB",
            target_location="00",
            target_event_time=_ORIGIN,
            event_id=event.id,
        )
        session.add(pick)
        session.flush()
        item = _only(readiness(session), ReadinessKind.AMBIGUOUS_PICK)
        assert item.blocking
        assert item.phase_name is None
        assert item.pick_ids == (pick.id,)

    def test_r4_empty_phase(self, session: Session) -> None:
        event = _event(session)
        _promoted(session, _seismogram(session, event), "t0")
        empty = _phase(session, event, "PKP")
        item = _only(readiness(session), ReadinessKind.EMPTY_PHASE)
        assert item.blocking
        assert item.phase_id == empty.id
        assert item.fixes[1] == f"aimbat phase remove --event {event.id} --phase PKP"

    def test_r5_unpromoted_notice(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session))
        pick = _pick(session, seismogram, "t0")
        promote_picks(session, [pick], phases=False)
        item = _only(readiness(session), ReadinessKind.UNPROMOTED_PICKS)
        assert item.severity is ReadinessSeverity.NOTICE
        assert (item.phase_id, item.phase_name) == (None, "P")

    def test_r6_conflict_notice(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session))
        _promoted(session, seismogram, "t0")
        other = AimbatPick(
            time=_at(40),
            phase_name="P",
            origin=PickOrigin.MANUAL,
            seismogram_id=seismogram.id,
        )
        session.add(other)
        session.flush()
        item = _only(readiness(session), ReadinessKind.CONFLICTING_PICK)
        assert item.severity is ReadinessSeverity.NOTICE
        assert item.pick_ids == (other.id,)
        assert item.fixes[0] == f"aimbat pick promote --pick {other.id} --replace"

    def test_r7_unresolved_belongs_to_the_project(self, session: Session) -> None:
        event = _event(session)
        _promoted(session, _seismogram(session, event), "t0")
        target = StationEventTarget(
            network="XX",
            station="ABC",
            location="00",
            event_time=_ORIGIN + Timedelta(days=9),
        )
        _pick(session, None, "far", target=target)
        item = _only(readiness(session), ReadinessKind.UNRESOLVED_EVENT)
        assert item.severity is ReadinessSeverity.NOTICE
        assert item.event_id is None
        assert readiness(session, event_id=event.id) == []

    def test_r8_seismogram_without_picks(self, session: Session) -> None:
        event = _event(session)
        _promoted(session, _seismogram(session, event), "t0")
        bare = _seismogram(session, event, name="DEF")
        item = _only(readiness(session), ReadinessKind.SEISMOGRAM_WITHOUT_PICKS)
        assert item.severity is ReadinessSeverity.NOTICE
        assert item.seismogram_ids == (bare.id,)

    def test_r9_pick_after_end(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session))
        pick = _promoted(session, seismogram, "t0")
        pick.time = _END + Timedelta(seconds=1)
        session.flush()
        item = _only(readiness(session), ReadinessKind.PICK_AFTER_END)
        assert item.blocking
        assert item.pick_ids == (pick.id,)
        assert item.seismogram_ids == (seismogram.id,)
        assert readiness(session, read_data=False) == []


class TestScope:
    """Tests for narrowing the check to an event or a phase."""

    def test_phase_leaves_out_other_phases(self, session: Session) -> None:
        event = _event(session)
        _promoted(session, _seismogram(session, event), "t0")
        _phase(session, event, "PKP")
        (p,) = [phase for phase in event.phases if phase.name == "P"]
        assert readiness(session, phase_id=p.id) == []

    def test_phase_of_another_event_refused(self, session: Session) -> None:
        event = _event(session)
        other = _event(session, _ORIGIN + Timedelta(days=1))
        phase = _phase(session, other, "P")
        with pytest.raises(ValueError, match="does not belong"):
            readiness(session, event_id=event.id, phase_id=phase.id)


class TestRequireReady:
    """Tests for refusing phases that are not ready."""

    def test_refused_with_the_items(self, session: Session) -> None:
        event = _event(session)
        seismogram = _seismogram(session, event)
        _promoted(session, seismogram, "t0")
        _pick(session, seismogram, "t1", label=None, seconds=40)
        with pytest.raises(NotReadyError, match="aimbat pick name") as exc_info:
            require_ready(session, event.phases[0].id)
        assert [i.kind for i in exc_info.value.items] == [ReadinessKind.UNNAMED_PICK]

    def test_notices_accepted(self, session: Session) -> None:
        event = _event(session)
        _promoted(session, _seismogram(session, event), "t0")
        _seismogram(session, event, name="DEF")
        require_ready(session, event.phases[0].id)
