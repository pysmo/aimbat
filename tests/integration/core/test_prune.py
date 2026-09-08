"""Integration tests for `aimbat.core.prune_project`."""

from pathlib import Path

import pytest
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.core import (
    create_iccs_instance,
    create_snapshot,
    prune_project,
    run_mccc,
)
from aimbat.io import DataType, SourceUnavailableError
from aimbat.io._base import _source_probes
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatSeismogramParametersSnapshot,
    AimbatSeismogramQuality,
    AimbatSnapshot,
    AimbatStation,
)


def _first_event(session: Session) -> AimbatEvent:
    event = session.exec(select(AimbatEvent)).first()
    assert event is not None
    return event


def _unlink_seismogram_source(session: Session, seismogram: AimbatSeismogram) -> Path:
    """Delete the file backing `seismogram` and return its path."""
    path = Path(seismogram.datasource.sourcename)
    path.unlink()
    return path


class TestPruneProject:
    def test_dry_run_reports_but_keeps_everything(
        self, loaded_session: Session
    ) -> None:
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        _unlink_seismogram_source(loaded_session, seismogram)

        report = prune_project(loaded_session, "all", dry_run=True)

        assert [s.id for s in report.orphan_seismograms] == [seismogram.id]
        assert not report.pruned
        assert loaded_session.get(AimbatSeismogram, seismogram.id) is not None

    def test_prune_deletes_seismogram_and_cascades(
        self, loaded_session: Session
    ) -> None:
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        seismogram_id = seismogram.id
        datasource_id = seismogram.datasource.id
        parameters_id = seismogram.parameters.id
        _unlink_seismogram_source(loaded_session, seismogram)

        report = prune_project(loaded_session, "all", auto_snapshot=False)

        assert report.pruned
        assert loaded_session.get(AimbatSeismogram, seismogram_id) is None
        assert loaded_session.get(AimbatDataSource, datasource_id) is None
        assert loaded_session.get(AimbatSeismogramParameters, parameters_id) is None

    def test_report_graph_is_usable_after_auto_snapshot(
        self, loaded_session: Session
    ) -> None:
        """The returned report's relationships must not be detached.

        Regression: `create_snapshot`'s commit expired the report instances
        and the later `expunge_all()` detached them, so
        `orphan_seismograms[0].station` raised `DetachedInstanceError`.
        """
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        station_name = seismogram.station.name
        _unlink_seismogram_source(loaded_session, seismogram)

        report = prune_project(loaded_session, "all", auto_snapshot=True)

        assert report.pruned
        assert report.orphan_seismograms[0].station.name == station_name
        assert report.orphan_seismograms[0].event.id == event.id

    def test_frozen_snapshot_rows_survive_prune(self, loaded_session: Session) -> None:
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        seismogram_id = seismogram.id
        create_snapshot(loaded_session, event, comment="baseline")
        snapshot = loaded_session.exec(select(AimbatSnapshot)).one()
        snapshot_id = snapshot.id
        count_before = snapshot.seismogram_count

        _unlink_seismogram_source(loaded_session, seismogram)
        prune_project(loaded_session, "all", auto_snapshot=False)

        frozen = loaded_session.exec(
            select(AimbatSeismogramParametersSnapshot).where(
                AimbatSeismogramParametersSnapshot.seismogram_id == seismogram_id
            )
        ).one()
        assert frozen.seismogram_parameters_id is None
        refreshed = loaded_session.get(AimbatSnapshot, snapshot_id)
        assert refreshed is not None
        assert refreshed.seismogram_count == count_before

    def test_live_quality_is_nulled_for_affected_event(
        self, loaded_session: Session
    ) -> None:
        event = _first_event(loaded_session)
        event_id = event.id
        iccs_bound = create_iccs_instance(loaded_session, event)
        run_mccc(loaded_session, event, iccs_bound.iccs, all_seismograms=False)
        loaded_session.refresh(event)
        assert event.quality is not None and event.quality.mccc_rmse is not None
        stack_modified_before = event.stack_modified

        surviving_id = event.seismograms[1].id
        pruned = event.seismograms[0]
        _unlink_seismogram_source(loaded_session, pruned)

        prune_project(loaded_session, "all", auto_snapshot=False)

        refreshed = loaded_session.get(AimbatEvent, event_id)
        assert refreshed is not None
        assert refreshed.quality is not None
        assert refreshed.quality.mccc_rmse is None
        assert refreshed.stack_modified != stack_modified_before
        surviving_quality = loaded_session.exec(
            select(AimbatSeismogramQuality).where(
                AimbatSeismogramQuality.seismogram_id == surviving_id
            )
        ).one_or_none()
        assert surviving_quality is not None
        assert surviving_quality.iccs_cc is None
        assert surviving_quality.mccc_cc_mean is None

    def test_auto_snapshot_runs_before_delete(self, loaded_session: Session) -> None:
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        _unlink_seismogram_source(loaded_session, seismogram)

        seismograms_before = len(event.seismograms)
        prune_project(loaded_session, "all", auto_snapshot=True)

        snapshots = loaded_session.exec(
            select(AimbatSnapshot).where(AimbatSnapshot.event_id == event.id)
        ).all()
        auto = [s for s in snapshots if s.comment == "Automatic snapshot before prune"]
        assert len(auto) == 1
        # The snapshot froze the pre-prune seismogram set.
        assert auto[0].seismogram_count == seismograms_before

    def test_snapshot_failure_aborts_without_deleting(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        seismogram_id = seismogram.id
        _unlink_seismogram_source(loaded_session, seismogram)

        def boom(*args: object, **kwargs: object) -> None:
            raise RuntimeError("snapshot exploded")

        monkeypatch.setattr("aimbat.core._snapshot.create_snapshot", boom)

        with pytest.raises(RuntimeError, match="Aborting prune"):
            prune_project(loaded_session, "all", auto_snapshot=True)

        loaded_session.rollback()
        assert loaded_session.get(AimbatSeismogram, seismogram_id) is not None

    def test_no_snapshot_flag_suppresses_it(self, loaded_session: Session) -> None:
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        _unlink_seismogram_source(loaded_session, seismogram)

        prune_project(loaded_session, "all", auto_snapshot=False)

        assert (
            loaded_session.exec(
                select(AimbatSnapshot).where(AimbatSnapshot.event_id == event.id)
            ).first()
            is None
        )

    def test_emptied_station_is_removed(self, loaded_session: Session) -> None:
        station = loaded_session.exec(select(AimbatStation)).first()
        assert station is not None
        station_id = station.id
        for seismogram in list(station.seismograms):
            path = Path(seismogram.datasource.sourcename)
            if path.exists():
                path.unlink()

        report = prune_project(
            loaded_session, "all", prune_empty_stations=True, auto_snapshot=False
        )

        assert station_id in {s.id for s in report.emptied_stations}
        assert loaded_session.get(AimbatStation, station_id) is None

    def test_emptied_event_kept_without_flag(self, loaded_session: Session) -> None:
        event = _first_event(loaded_session)
        event_id = event.id
        for seismogram in list(event.seismograms):
            _unlink_seismogram_source(loaded_session, seismogram)

        report = prune_project(loaded_session, event_id, auto_snapshot=False)

        assert event_id in {e.id for e in report.emptied_events}
        kept = loaded_session.get(AimbatEvent, event_id)
        assert kept is not None
        assert kept.seismograms == []

    def test_emptied_event_pruned_with_flag_reports_snapshot_loss(
        self, loaded_session: Session
    ) -> None:
        event = _first_event(loaded_session)
        event_id = event.id
        create_snapshot(loaded_session, event, comment="baseline")
        for seismogram in list(event.seismograms):
            _unlink_seismogram_source(loaded_session, seismogram)

        report = prune_project(
            loaded_session, event_id, prune_empty_events=True, auto_snapshot=False
        )

        assert loaded_session.get(AimbatEvent, event_id) is None
        assert report.deleted_snapshots.get(event_id, 0) >= 1
        assert (
            loaded_session.exec(
                select(AimbatSnapshot).where(AimbatSnapshot.event_id == event_id)
            ).first()
            is None
        )

    def test_unprobeable_datatype_warns_and_keeps_rows(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delitem(_source_probes, DataType.SAC)
        total = len(loaded_session.exec(select(AimbatSeismogram)).all())

        report = prune_project(loaded_session, "all", auto_snapshot=False)

        assert report.unprobeable.get(DataType.SAC) == total
        assert not report.orphan_seismograms
        assert len(loaded_session.exec(select(AimbatSeismogram)).all()) == total

    def test_source_unavailable_aborts_without_deleting(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(_context: object) -> bool:
            raise SourceUnavailableError("cannot stat")

        monkeypatch.setitem(_source_probes, DataType.SAC, _boom)
        event = _first_event(loaded_session)
        count_before = len(event.seismograms)

        with pytest.raises(SourceUnavailableError):
            prune_project(loaded_session, "all", auto_snapshot=False)

        loaded_session.refresh(event)
        assert len(event.seismograms) == count_before

    def test_missing_parent_directory_requires_force(
        self, loaded_session: Session, tmp_path: Path
    ) -> None:
        event = _first_event(loaded_session)
        seismogram = event.seismograms[0]
        # Point the source at a path whose parent does not exist.
        seismogram.datasource.sourcename = str(tmp_path / "gone" / "x.sac")
        loaded_session.add(seismogram.datasource)
        loaded_session.commit()

        with pytest.raises(SourceUnavailableError, match="parent directory"):
            prune_project(loaded_session, "all", auto_snapshot=False)

        report = prune_project(loaded_session, "all", auto_snapshot=False, force=True)
        assert report.pruned

    def test_unknown_event_id_raises(self, loaded_session: Session) -> None:
        from uuid import uuid4

        with pytest.raises(NoResultFound):
            prune_project(loaded_session, uuid4(), auto_snapshot=False)
