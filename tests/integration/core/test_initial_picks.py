"""Integration tests for storing, matching and promoting initial picks."""

import uuid
from collections.abc import Generator

import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from aimbat import settings
from aimbat.core import (
    MatchStatus,
    PickNaming,
    PickState,
    find_event,
    match_target,
    pick_states,
    promote_picks,
    rematch_picks,
    store_picks,
    validate_phase_name,
    validate_pick,
)
from aimbat.io import DataType, SeismogramTarget, SourcePick, StationEventTarget
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatPhase,
    AimbatPick,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
    PickOrigin,
)

_ORIGIN = Timestamp("2020-01-01T00:00:00", tz="UTC")
_BEGIN = _ORIGIN + Timedelta(minutes=5)
_SOURCE = "/data/picks.json"


@pytest.fixture
def session(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Generator[Session]:
    """A session on an empty project, with known event-matching tolerances."""
    monkeypatch.setattr(settings, "event_duplicate_strict", False)
    monkeypatch.setattr(settings, "event_duplicate_tolerance", Timedelta(seconds=1))
    monkeypatch.setattr(
        settings, "event_duplicate_raise_tolerance", Timedelta(seconds=60)
    )
    with Session(engine) as session:
        yield session


def _event(session: Session, time: Timestamp = _ORIGIN) -> AimbatEvent:
    event = AimbatEvent(time=time, latitude=0.0, longitude=0.0)
    session.add(event)
    session.flush()
    return event


def _station(
    session: Session, *, name: str = "ABC", channel: str = "BHZ"
) -> AimbatStation:
    station = AimbatStation(
        name=name,
        network="XX",
        location="00",
        channel=channel,
        latitude=10.0,
        longitude=10.0,
    )
    session.add(station)
    session.flush()
    return station


def _seismogram(
    session: Session,
    event: AimbatEvent,
    station: AimbatStation,
    *,
    source: str | None = None,
) -> AimbatSeismogram:
    seismogram = AimbatSeismogram(
        begin_time=_BEGIN,
        delta=Timedelta(seconds=0.05),
        event=event,
        station=station,
    )
    seismogram.datasource = AimbatDataSource(
        sourcename=source or f"/data/{uuid.uuid4().hex}.sac", datatype=DataType.SAC
    )
    session.add(seismogram)
    session.flush()
    return seismogram


def _at(seconds: float) -> Timestamp:
    """A time `seconds` after the begin time of the test seismograms."""
    return _BEGIN + Timedelta(seconds=seconds)


def _by_codes(
    *,
    station: str | None = "ABC",
    channel: str | None = None,
    event_time: Timestamp | None = _ORIGIN,
) -> StationEventTarget:
    return StationEventTarget(
        network="XX",
        station=station,
        location="00",
        channel=channel,
        event_time=event_time,
    )


def _store(session: Session, *picks: SourcePick, **kwargs: object) -> list[AimbatPick]:
    return store_picks(
        session,
        list(picks),
        source_name=_SOURCE,
        source_type=DataType.SAC,
        **kwargs,  # type: ignore[arg-type]
    ).stored


class TestValidatePhaseName:
    """Tests for `validate_phase_name`."""

    def test_strips_blanks(self) -> None:
        assert validate_phase_name("  PKiKP ") == "PKiKP"

    @pytest.mark.parametrize("name", ["", "   ", "P S", "P\tS", "P\x07", "x" * 33])
    def test_rejects(self, name: str) -> None:
        with pytest.raises(ValueError):
            validate_phase_name(name)

    def test_accepts_32_characters(self) -> None:
        assert validate_phase_name("x" * 32) == "x" * 32


class TestPickNaming:
    """Tests for how ingestion names picks."""

    def test_label_wins(self) -> None:
        naming = PickNaming(unlabelled_as="P")
        assert naming.name_for(SourcePick(_ORIGIN, "t0", label="S")) == "S"

    def test_unlabelled_takes_default(self) -> None:
        naming = PickNaming(unlabelled_as="P")
        assert naming.name_for(SourcePick(_ORIGIN, "t0")) == "P"

    def test_invalid_label_stays_unnamed(self) -> None:
        naming = PickNaming(unlabelled_as="P")
        assert naming.name_for(SourcePick(_ORIGIN, "t0", label="x" * 33)) is None

    def test_invalid_default_rejected(self) -> None:
        with pytest.raises(ValueError):
            PickNaming(unlabelled_as="P S")


class TestFindEvent:
    """Tests for looking up an event by origin time."""

    def test_exact(self, session: Session) -> None:
        event = _event(session)
        assert find_event(session, _ORIGIN, label="x") is event

    def test_within_tolerance(self, session: Session) -> None:
        event = _event(session)
        found = find_event(session, _ORIGIN + Timedelta(seconds=0.5), label="x")
        assert found is event

    def test_in_gap_band_raises(self, session: Session) -> None:
        _event(session)
        with pytest.raises(ValueError, match="Event time conflict"):
            find_event(session, _ORIGIN + Timedelta(seconds=10), label="x")

    def test_beyond_raise_tolerance(self, session: Session) -> None:
        _event(session)
        assert find_event(session, _ORIGIN + Timedelta(minutes=5), label="x") is None

    def test_strict_matches_exactly_only(
        self, session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _event(session)
        monkeypatch.setattr(settings, "event_duplicate_strict", True)
        assert find_event(session, _ORIGIN + Timedelta(seconds=10), label="x") is None

    def test_never_creates(self, session: Session) -> None:
        assert find_event(session, _ORIGIN, label="x") is None
        assert session.exec(select(AimbatEvent)).all() == []


class TestMatchTarget:
    """Tests for resolving a pick target to a seismogram."""

    def test_same_source(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        match = match_target(session, None, source_seismogram=seismogram, label="x")
        assert match.status is MatchStatus.MATCHED
        assert match.seismogram is seismogram

    def test_same_source_without_seismogram(self, session: Session) -> None:
        with pytest.raises(ValueError, match="names no seismogram"):
            match_target(session, None, label="x")

    def test_seismogram_id(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        target = SeismogramTarget(seismogram.id)
        match = match_target(session, target, label="x")
        assert match.status is MatchStatus.MATCHED
        assert match.seismogram is seismogram

    def test_unknown_seismogram_id(self, session: Session) -> None:
        with pytest.raises(ValueError, match="No seismogram"):
            match_target(session, SeismogramTarget(uuid.uuid4()), label="x")

    def test_seismogram_id_outside_given_event(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        other = _event(session, _ORIGIN + Timedelta(days=1))
        with pytest.raises(ValueError, match="does not belong"):
            match_target(
                session, SeismogramTarget(seismogram.id), event=other, label="x"
            )

    def test_station_code_matched(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        match = match_target(session, _by_codes(), label="x")
        assert match.status is MatchStatus.MATCHED
        assert match.seismogram is seismogram

    def test_station_code_unmatched(self, session: Session) -> None:
        event = _event(session)
        _seismogram(session, event, _station(session))
        match = match_target(session, _by_codes(station="XYZ"), label="x")
        assert match.status is MatchStatus.UNMATCHED
        assert match.event is event

    def test_station_code_ambiguous(self, session: Session) -> None:
        event = _event(session)
        one = _seismogram(session, event, _station(session, channel="BHZ"))
        two = _seismogram(session, event, _station(session, channel="BHN"))
        match = match_target(session, _by_codes(), label="x")
        assert match.status is MatchStatus.AMBIGUOUS
        assert set(match.candidates) == {one.id, two.id}

    def test_channel_resolves_ambiguity(self, session: Session) -> None:
        event = _event(session)
        _seismogram(session, event, _station(session, channel="BHZ"))
        north = _seismogram(session, event, _station(session, channel="BHN"))
        match = match_target(session, _by_codes(channel="BHN"), label="x")
        assert match.seismogram is north

    def test_unresolved_event(self, session: Session) -> None:
        match = match_target(session, _by_codes(), label="x")
        assert match.status is MatchStatus.UNRESOLVED

    def test_incomplete_code_rejected(self, session: Session) -> None:
        _event(session)
        with pytest.raises(ValueError, match="no station code"):
            match_target(session, _by_codes(station=None), label="x")

    def test_missing_event_time_rejected(self, session: Session) -> None:
        with pytest.raises(ValueError, match="no event time"):
            match_target(session, _by_codes(event_time=None), label="x")

    def test_given_event_replaces_event_time(self, session: Session) -> None:
        event = _event(session)
        seismogram = _seismogram(session, event, _station(session))
        match = match_target(
            session, _by_codes(event_time=None), event=event, label="x"
        )
        assert match.seismogram is seismogram

    def test_given_event_contradicted_by_event_time(self, session: Session) -> None:
        _event(session)
        other = _event(session, _ORIGIN + Timedelta(days=1))
        with pytest.raises(ValueError, match="does not belong"):
            match_target(session, _by_codes(), event=other, label="x")

    def test_given_station_contradicted_by_code(self, session: Session) -> None:
        station = _station(session)
        _seismogram(session, _event(session), station)
        with pytest.raises(ValueError, match="station code"):
            match_target(session, _by_codes(station="XYZ"), station=station, label="x")

    def test_given_station_completes_code(self, session: Session) -> None:
        station = _station(session)
        seismogram = _seismogram(session, _event(session), station)
        match = match_target(
            session, _by_codes(station=None), station=station, label="x"
        )
        assert match.seismogram is seismogram


class TestStorePicks:
    """Tests for writing the raw picks of one source."""

    def test_stores_matched_pick(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        (pick,) = _store(
            session,
            SourcePick(_at(30), "t0", label="P"),
            source_seismogram=seismogram,
        )
        assert pick.seismogram_id == seismogram.id
        assert pick.event_id is None
        assert pick.phase_name == "P"
        assert pick.origin is PickOrigin.SOURCE
        assert (pick.source_name, pick.source_key) == (_SOURCE, "t0")

    def test_keeps_target_as_read(self, session: Session) -> None:
        event = _event(session)
        (pick,) = _store(session, SourcePick(_at(30), "1", target=_by_codes()))
        assert pick.seismogram_id is None
        assert pick.event_id == event.id
        assert (pick.target_network, pick.target_station) == ("XX", "ABC")
        assert pick.target_event_time == _ORIGIN

    def test_unresolved_stores_neither_id(self, session: Session) -> None:
        (pick,) = _store(session, SourcePick(_at(30), "1", target=_by_codes()))
        assert pick.seismogram_id is None
        assert pick.event_id is None

    def test_duplicate_key_rejected(self, session: Session) -> None:
        with pytest.raises(ValueError, match="more than one pick"):
            _store(
                session,
                SourcePick(_at(1), "k", target=_by_codes()),
                SourcePick(_at(2), "k", target=_by_codes()),
            )

    def test_already_present_skipped(self, session: Session) -> None:
        pick = SourcePick(_at(30), "1", target=_by_codes())
        _store(session, pick)
        report = store_picks(
            session, [pick], source_name=_SOURCE, source_type=DataType.SAC
        )
        assert report.stored == []
        assert report.already_present == 1

    def test_skip_unnamed(self, session: Session) -> None:
        report = store_picks(
            session,
            [SourcePick(_at(30), "1", target=_by_codes())],
            source_name=_SOURCE,
            source_type=DataType.SAC,
            naming=PickNaming(skip_unnamed=True),
        )
        assert report.stored == []
        assert report.skipped_unnamed == 1

    def test_ambiguous_rejected_with_every_pick(self, session: Session) -> None:
        event = _event(session)
        _seismogram(session, event, _station(session, channel="BHZ"))
        _seismogram(session, event, _station(session, channel="BHN"))
        with pytest.raises(ValueError) as raised:
            _store(
                session,
                SourcePick(_at(1), "first", target=_by_codes()),
                SourcePick(_at(2), "second", target=_by_codes()),
            )
        assert "'first'" in str(raised.value)
        assert "'second'" in str(raised.value)
        assert session.exec(select(AimbatPick)).all() == []

    def test_before_begin_rejected(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        with pytest.raises(ValueError, match="before the begin time"):
            _store(session, SourcePick(_at(-1), "t0"), source_seismogram=seismogram)

    def test_after_source_end_rejected(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        with pytest.raises(ValueError, match="after the end time"):
            _store(
                session,
                SourcePick(_at(100), "t0"),
                source_seismogram=seismogram,
                source_end_time=_at(50),
            )

    def test_same_source_conflict_rejected(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        with pytest.raises(ValueError, match="two different P picks"):
            _store(
                session,
                SourcePick(_at(10), "t0", label="P"),
                SourcePick(_at(20), "t1", label="P"),
                source_seismogram=seismogram,
            )

    def test_same_source_same_time_accepted(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        stored = _store(
            session,
            SourcePick(_at(10), "t0", label="P"),
            SourcePick(_at(10), "t1", label="P"),
            source_seismogram=seismogram,
        )
        assert len(stored) == 2


class TestRematchPicks:
    """Tests for retrying unmatched picks."""

    def test_unresolved_pick_matched_after_data_added(self, session: Session) -> None:
        (pick,) = _store(session, SourcePick(_at(30), "1", target=_by_codes()))
        seismogram = _seismogram(session, _event(session), _station(session))
        assert rematch_picks(session) == [pick]
        assert pick.seismogram_id == seismogram.id
        assert pick.event_id is None

    def test_unmatched_pick_matched_after_seismogram_added(
        self, session: Session
    ) -> None:
        event = _event(session)
        (pick,) = _store(session, SourcePick(_at(30), "1", target=_by_codes()))
        seismogram = _seismogram(session, event, _station(session))
        assert rematch_picks(session, event_ids=[event.id]) == [pick]
        assert pick.seismogram_id == seismogram.id

    def test_event_resolved_without_candidates(self, session: Session) -> None:
        (pick,) = _store(session, SourcePick(_at(30), "1", target=_by_codes()))
        event = _event(session)
        assert rematch_picks(session) == []
        assert pick.event_id == event.id

    def test_pick_before_begin_stays_unmatched(self, session: Session) -> None:
        (pick,) = _store(session, SourcePick(_at(-30), "1", target=_by_codes()))
        _seismogram(session, _event(session), _station(session))
        assert rematch_picks(session) == []
        assert pick.seismogram_id is None

    def test_ambiguity_does_not_raise(self, session: Session) -> None:
        (pick,) = _store(session, SourcePick(_at(30), "1", target=_by_codes()))
        event = _event(session)
        _seismogram(session, event, _station(session, channel="BHZ"))
        _seismogram(session, event, _station(session, channel="BHN"))
        assert rematch_picks(session) == []
        assert pick.seismogram_id is None

    def test_other_events_left_alone(self, session: Session) -> None:
        event = _event(session)
        other = _event(session, _ORIGIN + Timedelta(days=1))
        (pick,) = _store(session, SourcePick(_at(30), "1", target=_by_codes()))
        _seismogram(session, event, _station(session))
        assert rematch_picks(session, event_ids=[other.id]) == []
        assert pick.seismogram_id is None


def _named_pick(
    session: Session, seismogram: AimbatSeismogram, seconds: float, key: str
) -> AimbatPick:
    (pick,) = _store(
        session,
        SourcePick(_at(seconds), key, label="P"),
        source_seismogram=seismogram,
    )
    return pick


class TestPromotePicks:
    """Tests for creating rows from named, matched picks."""

    def test_creates_phase_and_row(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        pick = _named_pick(session, seismogram, 30, "t0")
        report = promote_picks(session, [pick])
        (phase,) = report.phases_created
        (row,) = report.rows
        assert (phase.name, phase.event_id) == ("P", seismogram.event_id)
        assert phase.parameters is not None
        assert row.pick is pick
        assert row.initial_pick == pick.time
        assert row.refined_pick is None

    def test_reuses_existing_phase(self, session: Session) -> None:
        event = _event(session)
        first = _seismogram(session, event, _station(session))
        second = _seismogram(session, event, _station(session, name="DEF"))
        promote_picks(session, [_named_pick(session, first, 30, "a")])
        report = promote_picks(session, [_named_pick(session, second, 30, "b")])
        assert report.phases_created == []
        assert len(report.rows) == 1
        assert len(event.phases) == 1

    @pytest.mark.parametrize(
        ("allowed", "promoted"), [(True, 1), (False, 1), (["S"], 0)]
    )
    def test_existing_phase_filled_only_if_allowed(
        self, session: Session, allowed: bool | list[str], promoted: int
    ) -> None:
        event = _event(session)
        first = _seismogram(session, event, _station(session))
        second = _seismogram(session, event, _station(session, name="DEF"))
        promote_picks(session, [_named_pick(session, first, 30, "a")])
        pick = _named_pick(session, second, 30, "b")
        report = promote_picks(session, [pick], phases=allowed)
        assert len(report.rows) == promoted
        assert report.unpromoted == ([] if promoted else [pick])
        assert report.phases_created == []

    @pytest.mark.parametrize("allowed", [False, ["S"]])
    def test_phase_creation_refused(
        self, session: Session, allowed: bool | list[str]
    ) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        pick = _named_pick(session, seismogram, 30, "t0")
        report = promote_picks(session, [pick], phases=allowed)
        assert report.unpromoted == [pick]
        assert report.rows == []

    def test_phase_creation_allowed_by_name(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        pick = _named_pick(session, seismogram, 30, "t0")
        report = promote_picks(session, [pick], phases=["P"])
        assert len(report.rows) == 1

    def test_redundant_pick_reports_nothing(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        promote_picks(session, [_named_pick(session, seismogram, 30, "a")])
        report = promote_picks(session, [_named_pick(session, seismogram, 30, "b")])
        assert (report.rows, report.conflicts) == ([], [])

    def test_conflicting_pick_reported(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        kept = _named_pick(session, seismogram, 30, "a")
        promote_picks(session, [kept])
        other = _named_pick(session, seismogram, 40, "b")
        report = promote_picks(session, [other])
        assert report.conflicts == [other]
        assert seismogram.phase_rows[0].pick is kept

    def test_ignores_picks_that_cannot_be_promoted(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        unnamed, unmatched = _store(
            session,
            SourcePick(_at(10), "a"),
            SourcePick(_at(20), "b", label="P", target=_by_codes(station="XYZ")),
            source_seismogram=seismogram,
        )
        dismissed = _named_pick(session, seismogram, 30, "c")
        dismissed.dismissed = True
        report = promote_picks(session, [unnamed, unmatched, dismissed])
        assert report.rows == []
        assert report.phases_created == []

    def test_invalid_pick_not_promoted(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        early = AimbatPick(
            time=_at(-1),
            phase_name="P",
            origin=PickOrigin.MANUAL,
            seismogram=seismogram,
        )
        session.add(early)
        session.flush()
        report = promote_picks(session, [early])
        assert report.invalid == [early]
        assert report.rows == []
        assert report.phases_created == []

    def test_promoted_pick_ignored(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        pick = _named_pick(session, seismogram, 30, "t0")
        promote_picks(session, [pick])
        assert promote_picks(session, [pick]).rows == []

    def test_in_source_then_key_order(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        later = _named_pick(session, seismogram, 40, "t1")
        earlier = _named_pick(session, seismogram, 30, "t0")
        report = promote_picks(session, [later, earlier])
        assert report.rows[0].pick is earlier
        assert report.conflicts == [later]


class TestValidatePick:
    """Tests for checking a pick against a seismogram."""

    def test_valid(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        check = validate_pick(
            session, _named_pick(session, seismogram, 30, "t0"), seismogram
        )
        assert check.errors == ()
        assert check.conflict is None
        assert not check.redundant

    def test_errors(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        other = _event(session, _ORIGIN + Timedelta(days=1))
        pick = AimbatPick(time=_at(100), origin=PickOrigin.MANUAL, event_id=other.id)
        check = validate_pick(session, pick, seismogram, end_time=_at(50))
        assert len(check.errors) == 2

    def test_before_begin(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        pick = AimbatPick(time=_at(-1), origin=PickOrigin.MANUAL)
        assert validate_pick(session, pick, seismogram).errors

    def test_conflict_and_redundant(self, session: Session) -> None:
        seismogram = _seismogram(session, _event(session), _station(session))
        promote_picks(session, [_named_pick(session, seismogram, 30, "a")])
        same = _named_pick(session, seismogram, 30, "b")
        different = _named_pick(session, seismogram, 40, "c")
        assert validate_pick(session, same, seismogram).redundant
        conflict = validate_pick(session, different, seismogram).conflict
        assert conflict is seismogram.phase_rows[0]


class TestPickStates:
    """Tests for deriving the state of each pick."""

    def test_every_state(self, session: Session) -> None:
        event = _event(session)
        seismogram = _seismogram(session, event, _station(session))
        _seismogram(session, event, _station(session, name="AMB", channel="BHZ"))
        _seismogram(session, event, _station(session, name="AMB", channel="BHN"))
        promoted = _named_pick(session, seismogram, 30, "a")
        promote_picks(session, [promoted])
        redundant = _named_pick(session, seismogram, 30, "b")
        conflict = _named_pick(session, seismogram, 40, "c")
        unnamed, unmatched, other_phase = _store(
            session,
            SourcePick(_at(10), "d"),
            SourcePick(_at(10), "e", label="P", target=_by_codes(station="XYZ")),
            SourcePick(_at(10), "f", label="S"),
            source_seismogram=seismogram,
        )
        dismissed = _named_pick(session, seismogram, 50, "g")
        dismissed.dismissed = True
        unresolved = AimbatPick(
            time=_at(10),
            origin=PickOrigin.MANUAL,
            target_network="XX",
            target_station="ABC",
            target_location="00",
            target_event_time=_ORIGIN + Timedelta(days=9),
        )
        ambiguous = AimbatPick(
            time=_at(10),
            origin=PickOrigin.MANUAL,
            target_network="XX",
            target_station="AMB",
            target_location="00",
            target_event_time=_ORIGIN,
            event_id=event.id,
        )
        session.add_all([unresolved, ambiguous])
        session.flush()

        states = pick_states(session)
        assert states == {
            promoted.id: PickState.PROMOTED,
            redundant.id: PickState.REDUNDANT,
            conflict.id: PickState.CONFLICT,
            unnamed.id: PickState.UNNAMED,
            unmatched.id: PickState.UNMATCHED,
            other_phase.id: PickState.UNPROMOTED,
            dismissed.id: PickState.DISMISSED,
            unresolved.id: PickState.UNRESOLVED,
            ambiguous.id: PickState.AMBIGUOUS,
        }

    def test_filtered_by_event(self, session: Session) -> None:
        event = _event(session)
        other = _event(session, _ORIGIN + Timedelta(days=1))
        mine = _named_pick(
            session, _seismogram(session, event, _station(session)), 30, "a"
        )
        _named_pick(session, _seismogram(session, other, _station(session)), 30, "b")
        assert set(pick_states(session, event_id=event.id)) == {mine.id}


class TestDeletion:
    """Picks, rows and phases when a record they depend on is deleted."""

    def _promoted(self, session: Session) -> tuple[AimbatSeismogram, AimbatPick]:
        seismogram = _seismogram(session, _event(session), _station(session))
        pick = _named_pick(session, seismogram, 30, "t0")
        promote_picks(session, [pick])
        session.commit()
        return seismogram, pick

    def test_seismogram(self, session: Session) -> None:
        seismogram, pick = self._promoted(session)
        event_id, pick_id = seismogram.event_id, pick.id
        session.delete(seismogram)
        session.commit()
        assert session.get(AimbatPick, pick_id) is None
        assert session.exec(select(AimbatSeismogramParameters)).all() == []
        assert len(session.exec(select(AimbatPhase)).all()) == 1
        assert session.get(AimbatEvent, event_id) is not None

    def test_event(self, session: Session) -> None:
        seismogram, pick = self._promoted(session)
        (unmatched,) = _store(
            session, SourcePick(_at(30), "x", target=_by_codes(station="XYZ"))
        )
        (unresolved,) = _store(
            session,
            SourcePick(
                _at(30), "y", target=_by_codes(event_time=_ORIGIN + Timedelta(days=9))
            ),
        )
        unmatched_id, unresolved_id = unmatched.id, unresolved.id
        session.delete(seismogram.event)
        session.commit()
        assert session.exec(select(AimbatPhase)).all() == []
        assert session.exec(select(AimbatSeismogramParameters)).all() == []
        assert session.get(AimbatPick, unmatched_id) is None
        assert session.get(AimbatPick, unresolved_id) is not None

    def test_phase(self, session: Session) -> None:
        seismogram, pick = self._promoted(session)
        pick_id = pick.id
        session.delete(seismogram.event.phases[0])
        session.commit()
        assert session.exec(select(AimbatSeismogramParameters)).all() == []
        assert session.get(AimbatPick, pick_id) is not None
        assert session.get(AimbatSeismogram, seismogram.id) is not None

    def test_purged_pick(self, session: Session) -> None:
        seismogram, pick = self._promoted(session)
        session.delete(pick)
        session.commit()
        assert (
            session.exec(
                select(AimbatSeismogramParameters).where(
                    col(AimbatSeismogramParameters.seismogram_id) == seismogram.id
                )
            ).all()
            == []
        )
        assert len(session.exec(select(AimbatPhase)).all()) == 1
