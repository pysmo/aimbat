"""Integration tests for quality view functions in aimbat.core._quality."""

import uuid

import pandas as pd
import pytest
from sqlmodel import Session, col, select

from aimbat.core import get_default_event
from aimbat.core._quality import get_quality_event, get_quality_seismogram
from aimbat.core._snapshot import create_snapshot


def _write_mock_mccc_quality(
    session: Session,
    event_id: uuid.UUID,
    seismogram_ids: list[uuid.UUID],
    select_flags: list[bool],
    all_seismograms: bool,
) -> None:
    """Simulate an MCCC run by writing mock quality data to the live DB tables.

    Upserts `AimbatEventQuality` and per-seismogram `AimbatSeismogramQuality`
    entries. Only seismograms indicated by `all_seismograms` / `select_flags`
    receive MCCC metric values; the rest have their MCCC fields cleared.

    Args:
        session: Database session.
        event_id: UUID of the event.
        seismogram_ids: UUIDs of the seismograms in order.
        select_flags: Per-seismogram select flag, same order as seismogram_ids.
        all_seismograms: If True, all seismograms receive MCCC data.
    """
    from aimbat.models import AimbatEventQuality, AimbatSeismogramQuality

    used_ids = {
        sid for sid, sel in zip(seismogram_ids, select_flags) if all_seismograms or sel
    }

    # Event quality
    eq = session.exec(
        select(AimbatEventQuality).where(col(AimbatEventQuality.event_id) == event_id)
    ).first()
    if eq is None:
        eq = AimbatEventQuality(
            id=uuid.uuid4(),
            event_id=event_id,
            mccc_rmse=pd.Timedelta(milliseconds=1),
        )
        session.add(eq)
    else:
        eq.mccc_rmse = pd.Timedelta(milliseconds=1)
        session.add(eq)

    # Per-seismogram quality
    for seis_id in seismogram_ids:
        sq = session.exec(
            select(AimbatSeismogramQuality).where(
                col(AimbatSeismogramQuality.seismogram_id) == seis_id
            )
        ).first()
        if sq is None:
            sq = AimbatSeismogramQuality(id=uuid.uuid4(), seismogram_id=seis_id)
            session.add(sq)
        if seis_id in used_ids:
            sq.mccc_error = pd.Timedelta(microseconds=100)
            sq.mccc_cc_mean = 0.9
            sq.mccc_cc_std = 0.05
        else:
            sq.mccc_error = None
            sq.mccc_cc_mean = None
            sq.mccc_cc_std = None
        session.add(sq)

    session.commit()


class TestGetQualitySeismogram:
    """Tests for get_quality_seismogram staleness fix."""

    def test_returns_none_when_no_mccc_run(self, loaded_session: Session) -> None:
        """Verifies that None is returned when no MCCC snapshot exists.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        seis = default_event.seismograms[0]
        assert get_quality_seismogram(loaded_session, seis.id) is None

    def test_returns_quality_for_selected_seismogram(
        self, loaded_session: Session
    ) -> None:
        """Verifies that quality data is returned for a selected seismogram.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [True] * len(seis_ids)
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=False,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)

        result = get_quality_seismogram(loaded_session, seis_ids[0])
        assert result is not None
        assert result.mccc_cc_mean == pytest.approx(0.9)

    def test_returns_none_for_deselected_seismogram_when_selected_only(
        self, loaded_session: Session
    ) -> None:
        """Verifies that None is returned for a deselected seismogram when MCCC ran on selected only.

        The most recent MCCC snapshot excluded the deselected seismogram.
        Returning its quality from an older snapshot would be misleading.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        seis_ids = [s.id for s in default_event.seismograms]
        # Snapshot 1: all_seismograms=True — deselected seismogram gets quality data.
        select_flags_all_deselected = [False] + [True] * (len(seis_ids) - 1)
        for i, seis in enumerate(default_event.seismograms):
            seis.parameters.select = select_flags_all_deselected[i]
        loaded_session.commit()
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags_all_deselected,
            all_seismograms=True,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)

        # Snapshot 2 (most recent): all_seismograms=False — deselected seismogram is excluded.
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags_all_deselected,
            all_seismograms=False,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)

        # The deselected seismogram should return None despite having data in snapshot 1.
        deselected_id = seis_ids[0]
        assert get_quality_seismogram(loaded_session, deselected_id) is None

    def test_returns_quality_for_deselected_seismogram_when_all_seismograms(
        self, loaded_session: Session
    ) -> None:
        """Verifies that quality data is returned for a deselected seismogram when MCCC ran on all.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [False] + [True] * (len(seis_ids) - 1)
        for i, seis in enumerate(default_event.seismograms):
            seis.parameters.select = select_flags[i]
        loaded_session.commit()

        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)

        deselected_id = seis_ids[0]
        result = get_quality_seismogram(loaded_session, deselected_id)
        assert result is not None
        assert result.mccc_cc_mean == pytest.approx(0.9)


class TestGetQualityEvent:
    """Tests for get_quality_event returning quality data from the most recent snapshot."""

    def test_returns_none_when_no_mccc(self, loaded_session: Session) -> None:
        """Verifies that the event quality snapshot is None when no MCCC has been run.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        event_quality, stats = get_quality_event(loaded_session, default_event.id)
        assert event_quality is None
        assert stats.count == 0

    def test_includes_all_quality_records_from_snapshot(
        self, loaded_session: Session
    ) -> None:
        """Verifies that stats aggregate all seismogram quality records in the snapshot.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [s.select for s in default_event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=False,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)

        _, stats = get_quality_event(loaded_session, default_event.id)
        assert stats.count == sum(select_flags)

    def test_includes_deselected_seismograms_when_present_in_snapshot(
        self, loaded_session: Session
    ) -> None:
        """Verifies that deselected seismograms with quality data are included in stats.

        When MCCC ran with all_seismograms=True, quality records exist for
        deselected seismograms too, and they should be counted.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None

        default_event.seismograms[0].parameters.select = False
        loaded_session.commit()

        seis_ids = [s.id for s in default_event.seismograms]
        select_flags = [s.select for s in default_event.seismograms]
        _write_mock_mccc_quality(
            loaded_session,
            default_event.id,
            seis_ids,
            select_flags,
            all_seismograms=True,
        )
        loaded_session.refresh(default_event)
        create_snapshot(loaded_session, default_event)

        _, stats = get_quality_event(loaded_session, default_event.id)
        assert stats.count == len(seis_ids)
