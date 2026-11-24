"""Tests for the shared project test helpers."""

import uuid

import pytest
from pandas import Timedelta
from sqlalchemy import Engine
from sqlmodel import Session, select

from aimbat.models import (
    AimbatEvent,
    AimbatPick,
    AimbatSeismogramQuality,
    AimbatStation,
)

from testsupport.project import (
    BEGIN,
    ORIGIN,
    add_event,
    add_seismogram,
    add_station,
    add_unpromoted_pick,
    first,
    stamp_quality,
    store_pick,
)


class TestFirst:
    def test_returns_a_row(self, engine: Engine) -> None:
        with Session(engine) as session:
            event = add_event(session)
            assert first(session, AimbatEvent) is event

    def test_fails_without_rows(self, engine: Engine) -> None:
        with (
            Session(engine) as session,
            pytest.raises(AssertionError, match="no AimbatEvent"),
        ):
            first(session, AimbatEvent)


class TestAddSeismogram:
    def test_builds_a_station_from_name_and_channel(self, engine: Engine) -> None:
        with Session(engine) as session:
            seismogram = add_seismogram(
                session, add_event(session), name="DEF", channel="BHN"
            )
            assert (seismogram.station.name, seismogram.station.channel) == (
                "DEF",
                "BHN",
            )
            assert seismogram.begin_time == BEGIN

    def test_uses_a_given_station(self, engine: Engine) -> None:
        with Session(engine) as session:
            station = add_station(session)
            one = add_seismogram(session, add_event(session), station=station)
            two = add_seismogram(
                session, add_event(session, ORIGIN + Timedelta(days=1)), station=station
            )
            assert one.station_id == two.station_id == station.id
            assert one.datasource.sourcename != two.datasource.sourcename
            assert len(session.exec(select(AimbatStation)).all()) == 1


class TestStorePick:
    def test_defaults(self, engine: Engine) -> None:
        with Session(engine) as session:
            seismogram = add_seismogram(session, add_event(session))
            pick = store_pick(session, seismogram, "t0")
            assert (pick.source_name, pick.source_key, pick.label) == (
                "/data/picks.json",
                "t0",
                "P",
            )
            assert pick.time == BEGIN + Timedelta(seconds=30)

    def test_source(self, engine: Engine) -> None:
        with Session(engine) as session:
            seismogram = add_seismogram(session, add_event(session))
            pick = store_pick(session, seismogram, "a", source="/data/a.json")
            assert pick.source_name == "/data/a.json"


class TestAddUnpromotedPick:
    def test_commits_an_unpromoted_pick(self, loaded_engine: Engine) -> None:
        with Session(loaded_engine) as session:
            event_id = str(first(session, AimbatEvent).id)
        pick_id = add_unpromoted_pick(loaded_engine, event_id, "S")
        with Session(loaded_engine) as session:
            pick = session.get_one(AimbatPick, uuid.UUID(pick_id))
            assert pick.label == "S"
            assert pick.seismogram_id is not None
            event = session.get_one(AimbatEvent, uuid.UUID(event_id))
            assert "S" not in {phase.name for phase in event.phases}


class TestStampQuality:
    @staticmethod
    def _unstamped(session: Session) -> list[AimbatEvent]:
        """Give every row a CC value without a fingerprint; return the events."""
        events = list(session.exec(select(AimbatEvent)).all())
        for event in events:
            for row in event.phases[0].seismogram_parameters:
                session.add(AimbatSeismogramQuality(parameters=row, iccs_cc=0.75))
        session.flush()
        return events

    @staticmethod
    def _stamped(event: AimbatEvent) -> bool:
        rows = event.phases[0].seismogram_parameters
        return all(
            row.quality is not None and row.quality.iccs_fingerprint is not None
            for row in rows
        )

    def test_one_event(self, loaded_session: Session) -> None:
        events = self._unstamped(loaded_session)
        stamp_quality(loaded_session, events[0].id)
        assert [self._stamped(e) for e in events] == [True] + [False] * (
            len(events) - 1
        )

    def test_every_event(self, loaded_session: Session) -> None:
        events = self._unstamped(loaded_session)
        stamp_quality(loaded_session)
        assert all(self._stamped(e) for e in events)
