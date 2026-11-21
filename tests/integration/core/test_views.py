"""Integration tests for SeismogramQualityStats in aimbat.models."""

import uuid

import pandas as pd
import pytest
from sqlmodel import Session, col, select

from aimbat.core import resolve_phase
from aimbat.core._snapshot import create_snapshot
from aimbat.core._validity import Validity
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPhaseQuality,
    AimbatSeismogramParameters,
    AimbatSeismogramQuality,
    AimbatSnapshot,
    AimbatStation,
    SeismogramQualityStats,
)

from testsupport.project import first, stamp_quality


def _write_seismogram_quality(
    session: Session,
    seismogram_ids: list[uuid.UUID],
    *,
    with_mccc: bool = True,
) -> None:
    """Write mock seismogram quality records to live DB tables.

    Args:
        session: Database session.
        seismogram_ids: UUIDs of the seismograms to populate.
        with_mccc: If True, write MCCC fields alongside ICCS CC.
    """
    for seis_id in seismogram_ids:
        sq = session.exec(
            select(AimbatSeismogramQuality)
            .join(AimbatSeismogramParameters)
            .where(col(AimbatSeismogramParameters.seismogram_id) == seis_id)
        ).first()
        if sq is None:
            sq = AimbatSeismogramQuality(
                id=uuid.uuid4(),
                parameters=session.exec(
                    select(AimbatSeismogramParameters).where(
                        col(AimbatSeismogramParameters.seismogram_id) == seis_id
                    )
                ).one(),
            )
        sq.iccs_cc = 0.8
        if with_mccc:
            sq.mccc_error = pd.Timedelta(microseconds=100)
            sq.mccc_cc_mean = 0.9
            sq.mccc_cc_std = 0.05
        else:
            sq.mccc_error = None
            sq.mccc_cc_mean = None
            sq.mccc_cc_std = None
        session.add(sq)
    session.flush()
    stamp_quality(session)
    session.commit()


def _write_event_quality(session: Session, event_id: uuid.UUID) -> None:
    """Write a mock event-level quality record to the live DB table.

    Args:
        session: Database session.
        event_id: UUID of the event.
    """
    eq = session.exec(
        select(AimbatPhaseQuality)
        .join(AimbatPhase)
        .where(col(AimbatPhase.event_id) == event_id)
    ).first()
    if eq is None:
        eq = AimbatPhaseQuality(
            id=uuid.uuid4(),
            phase_id=resolve_phase(session, event_id).id,
            mccc_rmse=pd.Timedelta(milliseconds=1),
        )
    else:
        eq.mccc_rmse = pd.Timedelta(milliseconds=1)
    session.add(eq)
    session.flush()
    stamp_quality(session)
    session.commit()


class TestSeismogramQualityStatsFromPhase:
    """Tests for SeismogramQualityStats.from_phase."""

    def test_all_none_when_no_quality(self, loaded_session: Session) -> None:
        """Aggregate fields are None and count equals total seismograms when no quality exists."""
        event = first(loaded_session, AimbatEvent)
        phase = event.phases[0]
        total = len(event.seismograms)

        stats = SeismogramQualityStats.from_phase(phase, Validity.read(loaded_session))

        assert stats.count == total
        assert (stats.phase_id, stats.phase_name) == (phase.id, phase.name)
        assert stats.cc_mean is None
        assert stats.mccc_cc_mean is None
        assert stats.mccc_rmse is None

    def test_aggregates_iccs_cc(self, loaded_session: Session) -> None:
        """cc_mean is computed from seismograms with iccs_cc set."""
        event = first(loaded_session, AimbatEvent)
        seis_ids = [s.id for s in event.seismograms]

        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=False)
        loaded_session.refresh(event)

        stats = SeismogramQualityStats.from_phase(
            event.phases[0], Validity.read(loaded_session)
        )

        assert stats.count == len(seis_ids)
        assert stats.cc_mean == pytest.approx(0.8)
        assert stats.mccc_cc_mean is None
        assert stats.mccc_rmse is None

    def test_aggregates_mccc_fields(self, loaded_session: Session) -> None:
        """MCCC aggregate fields are populated after an MCCC run."""
        event = first(loaded_session, AimbatEvent)
        seis_ids = [s.id for s in event.seismograms]

        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=True)
        _write_event_quality(loaded_session, event.id)
        loaded_session.refresh(event)

        stats = SeismogramQualityStats.from_phase(
            event.phases[0], Validity.read(loaded_session)
        )

        assert stats.mccc_cc_mean == pytest.approx(0.9)
        assert stats.mccc_cc_std == pytest.approx(0.05)

    def test_mccc_rmse_from_phase_quality(self, loaded_session: Session) -> None:
        """mccc_rmse is taken from the phase quality record."""
        event = first(loaded_session, AimbatEvent)
        seis_ids = [s.id for s in event.seismograms]

        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=True)
        _write_event_quality(loaded_session, event.id)
        loaded_session.refresh(event)

        stats = SeismogramQualityStats.from_phase(
            event.phases[0], Validity.read(loaded_session)
        )

        assert stats.mccc_rmse == pd.Timedelta(milliseconds=1)

    def test_count_is_total_not_just_with_quality(
        self, loaded_session: Session
    ) -> None:
        """Count reflects all seismograms of the phase, not just those with quality data."""
        event = first(loaded_session, AimbatEvent)
        total = len(event.seismograms)
        partial_ids = [s.id for s in event.seismograms][: total // 2]

        _write_seismogram_quality(loaded_session, partial_ids, with_mccc=False)
        loaded_session.refresh(event)

        stats = SeismogramQualityStats.from_phase(
            event.phases[0], Validity.read(loaded_session)
        )

        assert stats.count == total


class TestSeismogramQualityStatsFromStation:
    """Tests for SeismogramQualityStats.from_station."""

    def test_all_none_when_no_quality(self, loaded_session: Session) -> None:
        """Aggregate fields are None when no seismograms have quality records."""
        station = first(loaded_session, AimbatStation)

        stats = SeismogramQualityStats.from_station(
            station, Validity.read(loaded_session)
        )

        assert stats.count == len(station.seismograms)
        assert stats.cc_mean is None
        assert stats.mccc_cc_mean is None

    def test_aggregates_quality(self, loaded_session: Session) -> None:
        """ICCS and MCCC fields are aggregated across all seismograms at the station."""
        station = first(loaded_session, AimbatStation)
        seis_ids = [s.id for s in station.seismograms]

        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=True)
        for event_id in {s.event_id for s in station.seismograms}:
            _write_event_quality(loaded_session, event_id)
        loaded_session.refresh(station)

        stats = SeismogramQualityStats.from_station(
            station, Validity.read(loaded_session)
        )

        assert stats.cc_mean == pytest.approx(0.8)
        assert stats.mccc_cc_mean == pytest.approx(0.9)

    def test_mccc_rmse_is_always_none(self, loaded_session: Session) -> None:
        """mccc_rmse is None for station stats — it is an event-level metric."""
        station = first(loaded_session, AimbatStation)
        seis_ids = [s.id for s in station.seismograms]

        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=True)
        loaded_session.refresh(station)

        stats = SeismogramQualityStats.from_station(
            station, Validity.read(loaded_session)
        )

        assert stats.mccc_rmse is None


class TestSeismogramQualityStatsFromSnapshot:
    """Tests for SeismogramQualityStats.from_snapshot."""

    def test_all_none_when_no_quality_in_snapshot(
        self, loaded_session: Session
    ) -> None:
        """Aggregate fields are None when the snapshot has no quality records."""
        event = first(loaded_session, AimbatEvent)
        create_snapshot(loaded_session, event.phases[0].id)

        snapshot = first(loaded_session, AimbatSnapshot)

        stats = SeismogramQualityStats.from_snapshot(snapshot)

        assert stats.count == snapshot.seismogram_count
        assert stats.cc_mean is None
        assert stats.mccc_cc_mean is None
        assert stats.mccc_rmse is None

    def test_aggregates_frozen_quality(self, loaded_session: Session) -> None:
        """Quality fields reflect values frozen at snapshot time, not live changes."""
        event = first(loaded_session, AimbatEvent)
        seis_ids = [s.id for s in event.seismograms]

        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=True)
        _write_event_quality(loaded_session, event.id)
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)

        snapshot = first(loaded_session, AimbatSnapshot)
        stats = SeismogramQualityStats.from_snapshot(snapshot)

        assert stats.count == snapshot.seismogram_count
        assert stats.cc_mean == pytest.approx(0.8)
        assert stats.mccc_cc_mean == pytest.approx(0.9)
        assert stats.mccc_rmse == pd.Timedelta(milliseconds=1)

    def test_is_independent_of_live_quality_changes(
        self, loaded_session: Session
    ) -> None:
        """Snapshot stats are unaffected by live quality changes made after snapshotting."""
        event = first(loaded_session, AimbatEvent)
        seis_ids = [s.id for s in event.seismograms]

        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=True)
        _write_event_quality(loaded_session, event.id)
        loaded_session.refresh(event)
        create_snapshot(loaded_session, event.phases[0].id)

        # Overwrite live quality after snapshotting.
        _write_seismogram_quality(loaded_session, seis_ids, with_mccc=False)

        snapshot = first(loaded_session, AimbatSnapshot)
        stats = SeismogramQualityStats.from_snapshot(snapshot)

        assert stats.mccc_cc_mean == pytest.approx(0.9)
