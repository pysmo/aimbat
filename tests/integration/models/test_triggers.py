"""Integration tests for database triggers in AIMBAT."""

from pandas import Timedelta, Timestamp
from sqlmodel import Session, select

from aimbat.models import (
    AimbatEventQuality,
    AimbatSeismogram,
    AimbatSeismogramQuality,
)


def _populate_quality_metrics(
    session: Session,
) -> tuple[
    AimbatSeismogram,
    AimbatSeismogram,
    AimbatSeismogramQuality,
    AimbatSeismogramQuality,
    AimbatEventQuality,
]:
    """Helper function to populate quality metrics for testing."""
    seismograms = session.exec(select(AimbatSeismogram)).all()
    target_seis = seismograms[0]
    event_id = target_seis.event_id
    other_seis = next(
        s for s in seismograms if s.event_id == event_id and s.id != target_seis.id
    )

    target_quality = AimbatSeismogramQuality(
        seismogram_id=target_seis.id, iccs_cc=0.9, mccc_cc_mean=0.8
    )
    other_quality = AimbatSeismogramQuality(
        seismogram_id=other_seis.id, iccs_cc=0.95, mccc_cc_mean=0.85
    )
    event_quality = AimbatEventQuality(
        event_id=event_id, mccc_rmse=Timedelta(seconds=2.0)
    )

    session.add_all([target_quality, other_quality, event_quality])
    session.commit()

    for q in [target_quality, other_quality, event_quality]:
        session.refresh(q)

    return target_seis, other_seis, target_quality, other_quality, event_quality


def test_trigger_null_event_quality_on_flip_change(loaded_session: Session) -> None:
    """Verifies changing 'flip' nulls quality metrics for all seismograms in the event."""
    target_seis, other_seis, target_quality, other_quality, event_quality = (
        _populate_quality_metrics(loaded_session)
    )

    # Pre-check
    assert target_quality.iccs_cc is not None
    assert other_quality.iccs_cc is not None
    assert event_quality.mccc_rmse is not None

    # Act
    target_seis.parameters.flip = not target_seis.parameters.flip
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Assert: flip changes the stack, so iccs_cc is nulled for ALL seismograms in the event
    loaded_session.refresh(target_quality)
    loaded_session.refresh(other_quality)
    loaded_session.refresh(event_quality)
    assert target_quality.iccs_cc is None
    assert other_quality.iccs_cc is None
    assert event_quality.mccc_rmse is None


def test_trigger_flip_change_deselected_nulls_local_iccs_only(
    loaded_session: Session,
) -> None:
    """Verifies flipping a deselected seismogram nulls only its own iccs_cc."""
    target_seis, other_seis, target_quality, other_quality, event_quality = (
        _populate_quality_metrics(loaded_session)
    )

    # Deselect target, then re-populate so we have a clean baseline
    target_seis.parameters.select = False
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    target_quality.iccs_cc = 0.9
    other_quality.iccs_cc = 0.95
    other_quality.mccc_cc_mean = 0.85
    event_quality.mccc_rmse = Timedelta(seconds=2.0)
    loaded_session.add_all([target_quality, other_quality, event_quality])
    loaded_session.commit()
    for q in [target_quality, other_quality, event_quality]:
        loaded_session.refresh(q)

    # Act
    target_seis.parameters.flip = not target_seis.parameters.flip
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Assert: deselected flip does not change the stack, so only the flipped
    # seismogram's own iccs_cc is stale; other quality is unaffected
    loaded_session.refresh(target_quality)
    loaded_session.refresh(other_quality)
    loaded_session.refresh(event_quality)
    assert target_quality.iccs_cc is None
    assert other_quality.iccs_cc is not None
    assert other_quality.mccc_cc_mean is not None
    assert event_quality.mccc_rmse is not None


def test_trigger_t1_change_selected_nulls_all(loaded_session: Session) -> None:
    """Verifies changing t1 on a selected seismogram nulls quality for the whole event."""
    target_seis, other_seis, target_quality, other_quality, event_quality = (
        _populate_quality_metrics(loaded_session)
    )

    assert target_seis.parameters.select is True

    # Act
    target_seis.parameters.t1 = Timestamp("2000-01-01", tz="UTC")
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Assert: selected seismogram is in the stack, so all iccs_cc and MCCC stats are nulled
    loaded_session.refresh(target_quality)
    loaded_session.refresh(other_quality)
    loaded_session.refresh(event_quality)
    assert target_quality.iccs_cc is None
    assert other_quality.iccs_cc is None
    assert target_quality.mccc_cc_mean is None
    assert other_quality.mccc_cc_mean is None
    assert event_quality.mccc_rmse is None


def test_trigger_t1_change_deselected_not_in_mccc_nulls_local_only(
    loaded_session: Session,
) -> None:
    """Verifies changing t1 on a deselected seismogram with no live MCCC stats only nulls its own iccs_cc."""
    target_seis, other_seis, target_quality, other_quality, event_quality = (
        _populate_quality_metrics(loaded_session)
    )

    # Deselect the target seismogram first
    target_seis.parameters.select = False
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Re-populate quality after deselect, but leave target's MCCC stats absent to
    # simulate the case where MCCC was run in selected-only mode (target was excluded).
    target_quality.iccs_cc = 0.9
    other_quality.iccs_cc = 0.95
    other_quality.mccc_cc_mean = 0.85
    event_quality.mccc_rmse = Timedelta(seconds=2.0)
    loaded_session.add_all([target_quality, other_quality, event_quality])
    loaded_session.commit()
    for q in [target_quality, other_quality, event_quality]:
        loaded_session.refresh(q)

    # Act
    target_seis.parameters.t1 = Timestamp("2000-01-01", tz="UTC")
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Assert: target was not in MCCC run, so only its own iccs_cc is nulled
    loaded_session.refresh(target_quality)
    loaded_session.refresh(other_quality)
    loaded_session.refresh(event_quality)
    assert target_quality.iccs_cc is None
    assert other_quality.iccs_cc is not None
    assert other_quality.mccc_cc_mean is not None
    assert event_quality.mccc_rmse is not None


def test_trigger_t1_change_deselected_in_mccc_nulls_all(
    loaded_session: Session,
) -> None:
    """Verifies changing t1 on a deselected seismogram with live MCCC stats nulls all MCCC quality."""
    target_seis, other_seis, target_quality, other_quality, event_quality = (
        _populate_quality_metrics(loaded_session)
    )

    # Deselect the target seismogram first
    target_seis.parameters.select = False
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Re-populate quality after deselect, including MCCC stats for target to simulate
    # the case where MCCC was run with --all (target was included despite being deselected).
    target_quality.iccs_cc = 0.9
    target_quality.mccc_cc_mean = 0.8
    other_quality.iccs_cc = 0.95
    other_quality.mccc_cc_mean = 0.85
    event_quality.mccc_rmse = Timedelta(seconds=2.0)
    loaded_session.add_all([target_quality, other_quality, event_quality])
    loaded_session.commit()
    for q in [target_quality, other_quality, event_quality]:
        loaded_session.refresh(q)

    # Act
    target_seis.parameters.t1 = Timestamp("2000-01-01", tz="UTC")
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Assert: target was in MCCC run (--all), so MCCC stats are nulled for the whole event
    loaded_session.refresh(target_quality)
    loaded_session.refresh(other_quality)
    loaded_session.refresh(event_quality)
    assert target_quality.iccs_cc is None
    assert other_quality.iccs_cc is not None
    assert target_quality.mccc_cc_mean is None
    assert other_quality.mccc_cc_mean is None
    assert event_quality.mccc_rmse is None


def test_trigger_null_event_quality_on_select_change(loaded_session: Session) -> None:
    """Verifies changing 'select' nulls event quality metrics."""
    target_seis, _, _, _, event_quality = _populate_quality_metrics(loaded_session)

    # Pre-check
    assert event_quality.mccc_rmse is not None

    # Act
    target_seis.parameters.select = not target_seis.parameters.select
    loaded_session.add(target_seis.parameters)
    loaded_session.commit()

    # Assert
    loaded_session.refresh(event_quality)
    assert event_quality.mccc_rmse is None

    # TODO: Add application-level logic to null seismogram quality metrics
