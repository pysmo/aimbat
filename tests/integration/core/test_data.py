"""Integration tests for adding data to the project (aimbat.core._data)."""

import json
import shutil
import uuid
from pathlib import Path

import numpy as np
import pytest
from pandas import Timedelta, Timestamp
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from pysmo import MiniEvent, MiniStation
from pysmo.classes import SAC
from pysmo.tools.iccs import MiniIccsSeismogram

import aimbat
from aimbat.core import (
    add_data_to_project,
    add_seismograms_to_project,
    dump_data_table,
    get_data_for_event,
)
from aimbat.io import DataType
from aimbat.models import (
    AimbatDataSource,
    AimbatEvent,
    AimbatEventParameters,
    AimbatSeismogram,
    AimbatStation,
)

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


_STATION_DATA: dict[str, str | float] = {
    "name": "ANMO",
    "network": "IU",
    "location": "00",
    "channel": "BHZ",
    "latitude": 34.9459,
    "longitude": -106.4572,
    "elevation": 1820.0,
}

_EVENT_DATA: dict[str, str | float] = {
    "time": "2020-01-01T00:00:00Z",
    "latitude": 35.0,
    "longitude": -120.0,
    "depth": 10.0,
}


@pytest.fixture()
def station_json(tmp_path: Path) -> Path:
    """Path to a temporary JSON file containing a station record.

    Args:
        tmp_path: The pytest tmp_path fixture.

    Returns:
        Path to the JSON station file.
    """
    path = tmp_path / "station.json"
    path.write_text(json.dumps(_STATION_DATA))
    return path


@pytest.fixture()
def event_json(tmp_path: Path) -> Path:
    """Path to a temporary JSON file containing an event record.

    Args:
        tmp_path: The pytest tmp_path fixture.

    Returns:
        Path to the JSON event file.
    """
    path = tmp_path / "event.json"
    path.write_text(json.dumps(_EVENT_DATA))
    return path


# ===================================================================
# Session-level tests (patched_session / loaded_session)
# ===================================================================


class TestAddDataToProject:
    def test_add_single_sac_file(
        self, sac_file_good: Path, patched_session: Session
    ) -> None:
        """Verifies adding a single valid SAC file to the project.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            patched_session (Session): Database session.
        """
        datasource = patched_session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == 0, "Expected no data sources before adding files."

        # do this 2 times to verify we can only add the same file once and that nothing changes on the second attempt
        for _ in range(2):
            add_data_to_project(
                patched_session,
                [sac_file_good],
                data_type=DataType.SAC,
            )
            seismogram_filename = patched_session.exec(
                select(AimbatDataSource.sourcename)
            ).one()
            assert seismogram_filename == str(sac_file_good)

    def test_add_multiple_sac_files(
        self, multi_event_data: list[Path], patched_session: Session
    ) -> None:
        """Verifies adding multiple SAC files to the project at once.

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            patched_session (Session): Database session.
        """
        datasource = patched_session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == 0, "Expected no data sources before adding files."

        add_data_to_project(
            patched_session,
            multi_event_data,
            data_type=DataType.SAC,
        )

        seismogram_filenames = patched_session.exec(
            select(AimbatDataSource.sourcename)
        ).all()
        assert sorted(seismogram_filenames) == sorted(
            [str(path) for path in multi_event_data]
        ), "Expected all files from multi_event to be added as data sources."

    def test_add_nonexistent_file(self, patched_session: Session) -> None:
        """Verifies that adding a non-existent file raises FileNotFoundError.

        Args:
            patched_session (Session): Database session.
        """
        non_existent_file = Path("this_file_does_not_exist.sac")
        with pytest.raises(FileNotFoundError):
            add_data_to_project(
                patched_session,
                [non_existent_file],
                data_type=DataType.SAC,
            )

    def test_add_mixed_valid_and_invalid_files(
        self, sac_file_good: Path, patched_session: Session
    ) -> None:
        """Verifies that adding a mix of valid and invalid files raises an error and adds nothing.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            patched_session (Session): Database session.
        """
        non_existent_file = Path("this_file_does_not_exist.sac")
        with pytest.raises(FileNotFoundError):
            add_data_to_project(
                patched_session,
                [sac_file_good, non_existent_file],
                data_type=DataType.SAC,
            )

        datasource = patched_session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == 0, (
            "Expected no data sources to be added when an error occurs."
        )

    def test_add_sac_file_with_missing_pick(
        self, sac_file_good: Path, patched_session: Session
    ) -> None:
        """Verifies that adding a SAC file missing required pick information raises ValidationError.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
            patched_session (Session): Database session.
        """
        sac = SAC.from_file(sac_file_good)
        sac.timestamps.t0 = None
        sac.write(sac_file_good)
        with pytest.raises(ValidationError):
            add_data_to_project(
                patched_session,
                [sac_file_good],
                data_type=DataType.SAC,
            )

    def test_dry_run_all_new(
        self,
        multi_event_data: list[Path],
        patched_session: Session,
    ) -> None:
        """Verifies dry run behaviour when all data are new.

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            patched_session (Session): Database session.
        """
        result = add_data_to_project(
            patched_session,
            multi_event_data,
            data_type=DataType.SAC,
            dry_run=True,
        )

        datasource = patched_session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == 0, "Expected no data sources after dry run."

        assert result is not None
        (
            added_datasources,
            existing_station_ids,
            existing_event_ids,
            existing_seismogram_ids,
            duplicate_warnings,
        ) = result
        n = len(multi_event_data)
        assert len(added_datasources) == n
        assert all(
            ds.seismogram.station_id not in existing_station_ids
            for ds in added_datasources
        )
        assert all(
            ds.seismogram.event_id not in existing_event_ids for ds in added_datasources
        )
        assert all(
            ds.seismogram_id not in existing_seismogram_ids for ds in added_datasources
        )
        assert duplicate_warnings == []

    def test_dry_run_all_skipped(
        self,
        multi_event_data: list[Path],
        patched_session: Session,
    ) -> None:
        """Verifies dry run behaviour when all data already exists (should be skipped).

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            patched_session (Session): Database session.
        """
        add_data_to_project(
            patched_session,
            multi_event_data,
            data_type=DataType.SAC,
        )

        result = add_data_to_project(
            patched_session,
            multi_event_data,
            data_type=DataType.SAC,
            dry_run=True,
        )

        assert result is not None
        (
            added_datasources,
            existing_station_ids,
            existing_event_ids,
            existing_seismogram_ids,
            duplicate_warnings,
        ) = result
        n = len(multi_event_data)
        assert len(added_datasources) == n
        assert all(
            ds.seismogram.station_id in existing_station_ids for ds in added_datasources
        )
        assert all(
            ds.seismogram.event_id in existing_event_ids for ds in added_datasources
        )
        assert all(
            ds.seismogram_id in existing_seismogram_ids for ds in added_datasources
        )
        assert duplicate_warnings == []

    def test_real_run_all_new(
        self,
        multi_event_data: list[Path],
        patched_session: Session,
    ) -> None:
        """Verifies the real-run (dry_run=False) return value when all data are new.

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            patched_session (Session): Database session.
        """
        (
            added_datasources,
            existing_station_ids,
            existing_event_ids,
            existing_seismogram_ids,
            duplicate_warnings,
        ) = add_data_to_project(
            patched_session,
            multi_event_data,
            data_type=DataType.SAC,
        )

        n = len(multi_event_data)
        assert len(added_datasources) == n
        assert all(
            ds.seismogram_id not in existing_seismogram_ids for ds in added_datasources
        )
        assert duplicate_warnings == []

        datasource = patched_session.exec(select(AimbatDataSource.sourcename)).all()
        assert len(datasource) == n, "Expected data to actually be committed."

    def test_real_run_idempotent_second_call(
        self,
        multi_event_data: list[Path],
        patched_session: Session,
    ) -> None:
        """A second, idempotent real-run call reports all entries as already existing.

        Args:
            multi_event_data (list[Path]): List of paths to SAC files.
            patched_session (Session): Database session.
        """
        add_data_to_project(
            patched_session,
            multi_event_data,
            data_type=DataType.SAC,
        )

        (
            added_datasources,
            _existing_station_ids,
            _existing_event_ids,
            existing_seismogram_ids,
            duplicate_warnings,
        ) = add_data_to_project(
            patched_session,
            multi_event_data,
            data_type=DataType.SAC,
        )

        assert len(added_datasources) == len(multi_event_data)
        assert all(
            ds.seismogram_id in existing_seismogram_ids for ds in added_datasources
        )
        assert duplicate_warnings == []


class TestNearDuplicateEventDetection:
    """Tests for near-duplicate event detection in add_data_to_project."""

    @staticmethod
    def _shifted_copy(
        source: Path, tmp_path: Path, shift_seconds: float, name: str
    ) -> Path:
        """Copy `source` to `tmp_path/name`, shifting its event time.

        Args:
            source: Path to the SAC file to copy.
            tmp_path: Directory to copy into.
            shift_seconds: Seconds to shift the copy's event time by.
            name: Filename for the copy.

        Returns:
            Path to the shifted copy.
        """
        new_path = tmp_path / name
        shutil.copy(source, new_path)
        sac = SAC.from_file(new_path)
        sac.event.time = sac.event.time + Timedelta(seconds=shift_seconds)
        sac.write(new_path)
        return new_path

    @staticmethod
    def _seed_event(session: Session, time: Timestamp) -> AimbatEvent:
        """Insert an event directly via the ORM, bypassing add_data_to_project.

        Args:
            session: Database session.
            time: Event origin time.

        Returns:
            The inserted AimbatEvent.
        """
        event = AimbatEvent(time=time, latitude=35.0, longitude=-120.0, depth=10.0)
        session.add(event)
        session.flush()
        session.add(AimbatEventParameters(event=event))
        session.flush()
        return event

    # -- Noise band (within event_duplicate_tolerance) --------------------

    def test_near_duplicate_event_reused_on_real_add(
        self, sac_file_good: Path, patched_session: Session, tmp_path: Path
    ) -> None:
        """A real add reuses the existing event within event_duplicate_tolerance.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
        """
        add_data_to_project(patched_session, [sac_file_good], data_type=DataType.SAC)
        existing = patched_session.exec(select(AimbatEvent)).one()
        near_dup = self._shifted_copy(sac_file_good, tmp_path, 0.02, "near_dup.sac")

        added_datasources, _, _, _, duplicate_warnings = add_data_to_project(
            patched_session, [near_dup], data_type=DataType.SAC
        )

        assert len(patched_session.exec(select(AimbatEvent)).all()) == 1
        assert added_datasources[0].seismogram.event_id == existing.id
        # A real add logs the reuse warning rather than returning it.
        assert duplicate_warnings == []

    def test_near_duplicate_event_previews_reuse_on_dry_run(
        self, sac_file_good: Path, patched_session: Session, tmp_path: Path
    ) -> None:
        """A dry run previews the near-duplicate as a reused, pre-existing event.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
        """
        add_data_to_project(patched_session, [sac_file_good], data_type=DataType.SAC)
        existing = patched_session.exec(select(AimbatEvent)).one()
        near_dup = self._shifted_copy(sac_file_good, tmp_path, 0.02, "near_dup.sac")

        (
            added_datasources,
            _existing_station_ids,
            existing_event_ids,
            _existing_seismogram_ids,
            duplicate_warnings,
        ) = add_data_to_project(
            patched_session, [near_dup], data_type=DataType.SAC, dry_run=True
        )

        assert len(duplicate_warnings) == 1
        assert str(near_dup) in duplicate_warnings[0]
        assert str(existing.id) in duplicate_warnings[0]

        # The near-duplicate previews as a reused (pre-existing) event.
        assert len(added_datasources) == 1
        assert added_datasources[0].seismogram.event_id == existing.id
        assert added_datasources[0].seismogram.event_id in existing_event_ids

    # -- Ambiguous-gap band (between the two tolerances) -------------------

    def test_ambiguous_gap_raises_on_real_add(
        self, sac_file_good: Path, patched_session: Session, tmp_path: Path
    ) -> None:
        """A real add raises with a data-problem message in the ambiguous-gap band.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
        """
        add_data_to_project(patched_session, [sac_file_good], data_type=DataType.SAC)
        ambiguous = self._shifted_copy(sac_file_good, tmp_path, 1.0, "ambiguous.sac")

        with pytest.raises(ValueError) as excinfo:
            add_data_to_project(patched_session, [ambiguous], data_type=DataType.SAC)

        assert "--use-event" not in str(excinfo.value)
        assert "timing problem" in str(excinfo.value)
        assert len(patched_session.exec(select(AimbatEvent)).all()) == 1

    def test_ambiguous_gap_raises_even_on_dry_run(
        self, sac_file_good: Path, patched_session: Session, tmp_path: Path
    ) -> None:
        """A dry run still raises in the ambiguous-gap band, unlike the noise band.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
        """
        add_data_to_project(patched_session, [sac_file_good], data_type=DataType.SAC)
        ambiguous = self._shifted_copy(sac_file_good, tmp_path, 1.0, "ambiguous.sac")

        with pytest.raises(ValueError):
            add_data_to_project(
                patched_session, [ambiguous], data_type=DataType.SAC, dry_run=True
            )

    # -- Independent events and edge cases ---------------------------------

    def test_events_beyond_raise_tolerance_are_independent(
        self, sac_file_good: Path, patched_session: Session, tmp_path: Path
    ) -> None:
        """A real add beyond event_duplicate_raise_tolerance is not flagged.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
        """
        add_data_to_project(patched_session, [sac_file_good], data_type=DataType.SAC)
        independent = self._shifted_copy(
            sac_file_good, tmp_path, 3.0, "independent.sac"
        )

        add_data_to_project(patched_session, [independent], data_type=DataType.SAC)

        assert len(patched_session.exec(select(AimbatEvent)).all()) == 2

    def test_same_batch_near_duplicates_are_merged(
        self, sac_file_good: Path, patched_session: Session, tmp_path: Path
    ) -> None:
        """Near-duplicates within the same batch merge onto the first file's event.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
        """
        near_dup = self._shifted_copy(sac_file_good, tmp_path, 0.02, "near_dup.sac")

        added_datasources, _, _, _, _ = add_data_to_project(
            patched_session, [sac_file_good, near_dup], data_type=DataType.SAC
        )

        events = patched_session.exec(select(AimbatEvent)).all()
        assert len(events) == 1
        assert {ds.seismogram.event_id for ds in added_datasources} == {events[0].id}

    def test_gap_exactly_at_raise_tolerance_is_independent(
        self, event_json: Path, patched_session: Session
    ) -> None:
        """A gap exactly equal to event_duplicate_raise_tolerance is not flagged.

        Uses a JSON event rather than a SAC file so both origin times are
        exact to the microsecond: SAC's 32-bit float header leaves the new
        event's time with sub-microsecond noise that a DB round trip (which
        floors to microsecond precision) would not reproduce on the seeded
        side, masking the exact boundary this test targets.

        Args:
            event_json: Path to a JSON event file.
            patched_session: Database session.
        """
        new_time = Timestamp(_EVENT_DATA["time"])
        self._seed_event(patched_session, new_time + Timedelta(seconds=2))

        add_data_to_project(
            patched_session, [event_json], data_type=DataType.JSON_EVENT
        )

        assert len(patched_session.exec(select(AimbatEvent)).all()) == 2

    def test_multiple_near_duplicates_picks_closest(
        self, sac_file_good: Path, patched_session: Session
    ) -> None:
        """The closest pre-existing near-duplicate is the one reused.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
        """
        new_time = SAC.from_file(sac_file_good).event.time
        far = self._seed_event(patched_session, new_time - Timedelta(seconds=0.09))
        close = self._seed_event(patched_session, new_time + Timedelta(seconds=0.04))

        added_datasources, _, _, _, _ = add_data_to_project(
            patched_session, [sac_file_good], data_type=DataType.SAC
        )

        assert len(patched_session.exec(select(AimbatEvent)).all()) == 2
        assert added_datasources[0].seismogram.event_id == close.id
        assert added_datasources[0].seismogram.event_id != far.id

    def test_closest_match_determines_band(
        self, sac_file_good: Path, patched_session: Session
    ) -> None:
        """Band classification is based on the closest match, not the query window.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
        """
        new_time = SAC.from_file(sac_file_good).event.time
        noise_band_event = self._seed_event(
            patched_session, new_time + Timedelta(seconds=0.05)
        )
        self._seed_event(patched_session, new_time - Timedelta(seconds=1))

        # Closest match is in the noise band, so the event is reused rather
        # than raising, despite an ambiguous-gap match also being in range.
        added_datasources, _, _, _, _ = add_data_to_project(
            patched_session, [sac_file_good], data_type=DataType.SAC
        )

        assert added_datasources[0].seismogram.event_id == noise_band_event.id

    # -- strict mode ---------------------------------------------------

    def test_strict_skips_noise_band(
        self,
        sac_file_good: Path,
        patched_session: Session,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """event_duplicate_strict=True skips the noise-band check.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
            monkeypatch: Fixture to mock objects/attributes.
        """
        monkeypatch.setattr(aimbat.settings, "event_duplicate_strict", True)
        add_data_to_project(patched_session, [sac_file_good], data_type=DataType.SAC)
        near_dup = self._shifted_copy(sac_file_good, tmp_path, 0.02, "near_dup.sac")

        add_data_to_project(patched_session, [near_dup], data_type=DataType.SAC)

        assert len(patched_session.exec(select(AimbatEvent)).all()) == 2

    def test_strict_skips_ambiguous_gap_band(
        self,
        sac_file_good: Path,
        patched_session: Session,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """event_duplicate_strict=True also skips the ambiguous-gap-band check.

        Args:
            sac_file_good: Path to a valid SAC file.
            patched_session: Database session.
            tmp_path: Temporary directory for the shifted copy.
            monkeypatch: Fixture to mock objects/attributes.
        """
        monkeypatch.setattr(aimbat.settings, "event_duplicate_strict", True)
        add_data_to_project(patched_session, [sac_file_good], data_type=DataType.SAC)
        ambiguous = self._shifted_copy(sac_file_good, tmp_path, 1.0, "ambiguous.sac")

        add_data_to_project(patched_session, [ambiguous], data_type=DataType.SAC)

        assert len(patched_session.exec(select(AimbatEvent)).all()) == 2


class TestGetDataSources:
    def test_get_data_sources_for_event(self, loaded_session: Session) -> None:
        """Verifies that get_data_sources returns the expected data sources.

        Args:
            loaded_session (Session): Database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        data_sources = get_data_for_event(loaded_session, event.id)
        assert len(data_sources) != 0, "Expected data sources for the event."
        assert all(isinstance(ds, AimbatDataSource) for ds in data_sources), (
            "expected all items to be AimbatDataSource instances"
        )

    def test_dump_data_table_to_json(self, loaded_session: Session) -> None:
        """Verifies that dump_data_table_to_json returns expected content.

        Args:
            loaded_session (Session): Database session.
        """
        json_data = dump_data_table(loaded_session)
        expected_ids = map(str, loaded_session.exec(select(AimbatDataSource.id)).all())
        returned_ids = [item["id"] for item in json_data]
        assert set(expected_ids) == set(returned_ids), "Expected IDs to match."


# ===================================================================
# Engine-level tests (add_data_to_project with engine fixture)
# ===================================================================


class TestAddDataSac:
    """Tests for add_data_to_project with SAC data."""

    def test_creates_station_event_seismogram_and_datasource(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a SAC import creates all four entity types.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [sac_file_good], DataType.SAC)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1
            assert len(session.exec(select(AimbatEvent)).all()) == 1
            assert len(session.exec(select(AimbatSeismogram)).all()) == 1
            assert len(session.exec(select(AimbatDataSource)).all()) == 1

    def test_duplicate_import_does_not_create_duplicates(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that importing the same SAC file twice does not duplicate records.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [sac_file_good], DataType.SAC)
            add_data_to_project(session, [sac_file_good], DataType.SAC)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1
            assert len(session.exec(select(AimbatEvent)).all()) == 1
            assert len(session.exec(select(AimbatSeismogram)).all()) == 1
            assert len(session.exec(select(AimbatDataSource)).all()) == 1


class TestAddDataJsonStation:
    """Tests for add_data_to_project with JSON_STATION data."""

    def test_creates_station_only(self, engine: Engine, station_json: Path) -> None:
        """Verifies that a JSON_STATION import creates only a station record.

        Args:
            engine: In-memory SQLAlchemy Engine.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1
            assert len(session.exec(select(AimbatEvent)).all()) == 0
            assert len(session.exec(select(AimbatSeismogram)).all()) == 0
            assert len(session.exec(select(AimbatDataSource)).all()) == 0

    def test_station_fields_match_json(
        self, engine: Engine, station_json: Path
    ) -> None:
        """Verifies that imported station fields match the JSON values.

        Args:
            engine: In-memory SQLAlchemy Engine.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)

        with Session(engine) as session:
            station = session.exec(select(AimbatStation)).one()
            assert station.name == _STATION_DATA["name"]
            assert station.network == _STATION_DATA["network"]
            assert station.location == _STATION_DATA["location"]
            assert station.channel == _STATION_DATA["channel"]
            assert station.latitude == _STATION_DATA["latitude"]


class TestAddDataJsonEvent:
    """Tests for add_data_to_project with JSON_EVENT data."""

    def test_creates_event_only(self, engine: Engine, event_json: Path) -> None:
        """Verifies that a JSON_EVENT import creates only an event record.

        Args:
            engine: In-memory SQLAlchemy Engine.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 0
            assert len(session.exec(select(AimbatEvent)).all()) == 1
            assert len(session.exec(select(AimbatSeismogram)).all()) == 0
            assert len(session.exec(select(AimbatDataSource)).all()) == 0

    def test_event_fields_match_json(self, engine: Engine, event_json: Path) -> None:
        """Verifies that imported event fields match the JSON values.

        Args:
            engine: In-memory SQLAlchemy Engine.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)

        with Session(engine) as session:
            event = session.exec(select(AimbatEvent)).one()
            assert event.time == Timestamp("2020-01-01T00:00:00Z")
            assert event.latitude == _EVENT_DATA["latitude"]
            assert event.longitude == _EVENT_DATA["longitude"]
            assert event.depth == _EVENT_DATA["depth"]

    def test_event_has_parameters(self, engine: Engine, event_json: Path) -> None:
        """Verifies that the imported event has initialised parameters.

        Args:
            engine: In-memory SQLAlchemy Engine.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)

        with Session(engine) as session:
            event = session.exec(select(AimbatEvent)).one()
            assert event.parameters is not None


class TestUuidValidation:
    """Tests for early UUID validation in add_data_to_project."""

    def test_invalid_station_id_raises_value_error(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a non-existent station UUID raises ValueError before the import loop.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            with pytest.raises(NoResultFound, match="No station found"):
                add_data_to_project(
                    session,
                    [sac_file_good],
                    DataType.SAC,
                    station_id=uuid.uuid4(),
                )

    def test_invalid_event_id_raises_value_error(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a non-existent event UUID raises ValueError before the import loop.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            with pytest.raises(NoResultFound, match="No event found"):
                add_data_to_project(
                    session,
                    [sac_file_good],
                    DataType.SAC,
                    event_id=uuid.uuid4(),
                )

    def test_invalid_uuid_does_not_modify_database(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that a failed UUID check leaves the database unchanged.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            with pytest.raises(NoResultFound):
                add_data_to_project(
                    session,
                    [sac_file_good],
                    DataType.SAC,
                    station_id=uuid.uuid4(),
                )

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 0
            assert len(session.exec(select(AimbatEvent)).all()) == 0


class TestCombinedSacAndJsonStation:
    """Tests for combining SAC seismogram data with a JSON-imported station."""

    def test_sac_with_station_id_links_to_json_station(
        self, engine: Engine, sac_file_good: Path, station_json: Path
    ) -> None:
        """Verifies that a SAC import with station_id links to the pre-existing station.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)
            station = session.exec(select(AimbatStation)).one()
            station_id = station.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, station_id=station_id
            )

        with Session(engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).one()
            assert seismogram.station_id == station_id

    def test_sac_with_station_id_does_not_create_extra_station(
        self, engine: Engine, sac_file_good: Path, station_json: Path
    ) -> None:
        """Verifies that the SAC file's embedded station data are ignored when station_id is provided.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            station_json: Path to a valid JSON station file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [station_json], DataType.JSON_STATION)
            station = session.exec(select(AimbatStation)).one()
            station_id = station.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, station_id=station_id
            )

        with Session(engine) as session:
            assert len(session.exec(select(AimbatStation)).all()) == 1


class TestCombinedSacAndJsonEvent:
    """Tests for combining SAC seismogram data with a JSON-imported event."""

    def test_sac_with_event_id_links_to_json_event(
        self, engine: Engine, sac_file_good: Path, event_json: Path
    ) -> None:
        """Verifies that a SAC import with event_id links to the pre-existing event.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)
            event = session.exec(select(AimbatEvent)).one()
            event_id = event.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, event_id=event_id
            )

        with Session(engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).one()
            assert seismogram.event_id == event_id

    def test_sac_with_event_id_does_not_create_extra_event(
        self, engine: Engine, sac_file_good: Path, event_json: Path
    ) -> None:
        """Verifies that the SAC file's embedded event data are ignored when event_id is provided.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
            event_json: Path to a valid JSON event file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [event_json], DataType.JSON_EVENT)
            event = session.exec(select(AimbatEvent)).one()
            event_id = event.id

        with Session(engine) as session:
            add_data_to_project(
                session, [sac_file_good], DataType.SAC, event_id=event_id
            )

        with Session(engine) as session:
            assert len(session.exec(select(AimbatEvent)).all()) == 1


class TestDryRun:
    """Tests for the dry_run option."""

    def test_dry_run_does_not_persist_changes(
        self, engine: Engine, sac_file_good: Path
    ) -> None:
        """Verifies that dry_run=True rolls back all changes.

        Args:
            engine: In-memory SQLAlchemy Engine.
            sac_file_good: Path to a valid SAC file.
        """
        with Session(engine) as session:
            add_data_to_project(session, [sac_file_good], DataType.SAC, dry_run=True)

        with Session(engine) as session:
            assert len(session.exec(select(AimbatDataSource)).all()) == 0
            assert len(session.exec(select(AimbatSeismogram)).all()) == 0
            assert len(session.exec(select(AimbatStation)).all()) == 0
            assert len(session.exec(select(AimbatEvent)).all()) == 0


# ===================================================================
# add_seismograms_to_project (direct triple ingestion)
# ===================================================================


class TestAddSeismogramsToProject:
    """Tests for add_seismograms_to_project (direct triple ingestion)."""

    @staticmethod
    def _triple(
        *,
        station_name: str = "ANMO",
        begin_time: Timestamp = Timestamp("2020-01-01T00:00:00Z"),
        event: MiniEvent | None = None,
    ) -> tuple[MiniIccsSeismogram, MiniStation, MiniEvent]:
        """Build a valid (seismogram, station, event) triple for ingestion."""
        station = MiniStation(
            name=station_name,
            network="IU",
            location="00",
            channel="BHZ",
            latitude=34.9459,
            longitude=-106.4572,
            elevation=1820.0,
        )
        if event is None:
            event = MiniEvent(
                time=Timestamp("2020-06-01T00:00:00Z"),
                latitude=35.0,
                longitude=-120.0,
                depth=10.0,
            )
        seismogram = MiniIccsSeismogram(
            begin_time=begin_time,
            delta=Timedelta(seconds=0.05),
            data=np.arange(100.0),
            t0=begin_time + Timedelta(seconds=10),
        )
        return seismogram, station, event

    def test_add_single_triple(self, patched_session: Session, tmp_path: Path) -> None:
        """A single triple is linked to a new station, event, and seismogram."""
        seismogram, station, event = self._triple()

        added, _, _, _, _ = add_seismograms_to_project(
            patched_session, [(seismogram, station, event)], data_dir=tmp_path
        )

        assert len(added) == 1
        aimbat_seismogram = added[0].seismogram
        assert aimbat_seismogram.t0 == seismogram.t0
        assert aimbat_seismogram.station.name == station.name
        assert aimbat_seismogram.event.time == event.time

    def test_files_land_under_data_dir(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """The persisted waveform is written under the given data_dir."""
        seismogram, station, event = self._triple()

        add_seismograms_to_project(
            patched_session, [(seismogram, station, event)], data_dir=tmp_path
        )

        assert len(list(tmp_path.glob("*.mseed"))) == 1

    def test_creates_missing_data_dir(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """data_dir is created (with any missing parents) if it doesn't exist yet."""
        seismogram, station, event = self._triple()
        missing_dir = tmp_path / "nested" / "waveforms"
        assert not missing_dir.exists()

        add_seismograms_to_project(
            patched_session, [(seismogram, station, event)], data_dir=missing_dir
        )

        assert len(list(missing_dir.glob("*.mseed"))) == 1

    def test_reingesting_same_triple_dedups(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """Re-running the same ingestion resolves to one seismogram, not two."""
        seismogram, station, event = self._triple()

        for _ in range(2):
            add_seismograms_to_project(
                patched_session, [(seismogram, station, event)], data_dir=tmp_path
            )

        assert len(patched_session.exec(select(AimbatSeismogram)).all()) == 1
        assert len(patched_session.exec(select(AimbatStation)).all()) == 1
        assert len(patched_session.exec(select(AimbatEvent)).all()) == 1

    def test_dedups_station_across_triples(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """Two triples for the same station reuse one AimbatStation row."""
        first = self._triple(begin_time=Timestamp("2020-01-01T00:00:00Z"))
        second = self._triple(begin_time=Timestamp("2020-01-01T01:00:00Z"))

        add_seismograms_to_project(patched_session, [first, second], data_dir=tmp_path)

        assert len(patched_session.exec(select(AimbatStation)).all()) == 1
        assert len(patched_session.exec(select(AimbatSeismogram)).all()) == 2

    def test_two_triples_sharing_event_link_to_one_event(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """Reusing the same Event across triples links them to one AimbatEvent."""
        shared_event = MiniEvent(
            time=Timestamp("2020-06-01T00:00:00Z"),
            latitude=35.0,
            longitude=-120.0,
            depth=10.0,
        )
        first = self._triple(station_name="ANMO", event=shared_event)
        second = self._triple(
            station_name="COLA",
            begin_time=Timestamp("2020-01-01T01:00:00Z"),
            event=shared_event,
        )

        add_seismograms_to_project(patched_session, [first, second], data_dir=tmp_path)

        events = patched_session.exec(select(AimbatEvent)).all()
        assert len(events) == 1
        seismograms = patched_session.exec(select(AimbatSeismogram)).all()
        assert {s.event_id for s in seismograms} == {events[0].id}

    def test_near_duplicate_event_reused(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """A near-duplicate origin time (within tolerance) reuses the existing event."""
        seismogram1, station1, event1 = self._triple()
        add_seismograms_to_project(
            patched_session, [(seismogram1, station1, event1)], data_dir=tmp_path
        )
        existing = patched_session.exec(select(AimbatEvent)).one()

        near_dup_event = MiniEvent(
            time=event1.time + Timedelta(seconds=0.02),
            latitude=event1.latitude,
            longitude=event1.longitude,
            depth=event1.depth,
        )
        seismogram2, station2, _ = self._triple(
            station_name="COLA", begin_time=Timestamp("2020-01-01T02:00:00Z")
        )

        added, *_ = add_seismograms_to_project(
            patched_session,
            [(seismogram2, station2, near_dup_event)],
            data_dir=tmp_path,
        )

        assert len(patched_session.exec(select(AimbatEvent)).all()) == 1
        assert added[0].seismogram.event_id == existing.id

    def test_dry_run_does_not_persist_changes(
        self, engine: Engine, tmp_path: Path
    ) -> None:
        """dry_run=True rolls back all changes, including the persisted file."""
        seismogram, station, event = self._triple()

        with Session(engine) as session:
            add_seismograms_to_project(
                session, [(seismogram, station, event)], data_dir=tmp_path, dry_run=True
            )

        with Session(engine) as session:
            assert len(session.exec(select(AimbatDataSource)).all()) == 0
            assert len(session.exec(select(AimbatSeismogram)).all()) == 0
            assert len(session.exec(select(AimbatStation)).all()) == 0
            assert len(session.exec(select(AimbatEvent)).all()) == 0
        assert list(tmp_path.glob("*.mseed")) == []

    def test_reingesting_different_seismogram_does_not_overwrite_file(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """Re-ingesting a different seismogram for the same (station, begin_time)
        keeps the first-ingested file and DB row in sync, rather than
        overwriting the file while keeping the old DB row."""
        from pysmo.classes import MSeed

        seismogram, station, event = self._triple()
        add_seismograms_to_project(
            patched_session, [(seismogram, station, event)], data_dir=tmp_path
        )
        first_t0 = patched_session.exec(select(AimbatSeismogram)).one().t0

        other_seismogram, _, _ = self._triple()
        other_seismogram.data = other_seismogram.data + 1000.0
        add_seismograms_to_project(
            patched_session, [(other_seismogram, station, event)], data_dir=tmp_path
        )

        assert len(patched_session.exec(select(AimbatSeismogram)).all()) == 1
        aimbat_seismogram = patched_session.exec(select(AimbatSeismogram)).one()
        assert aimbat_seismogram.t0 == first_t0

        [mseed_file] = tmp_path.glob("*.mseed")
        on_disk = MSeed.from_file(mseed_file)
        np.testing.assert_array_equal(on_disk.data, seismogram.data)

    def test_collision_warns_on_dry_run(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """A dry-run re-ingest colliding on the deterministic path surfaces a
        warning, rather than silently discarding the colliding triple's data."""
        seismogram, station, event = self._triple()
        add_seismograms_to_project(
            patched_session, [(seismogram, station, event)], data_dir=tmp_path
        )

        other_seismogram, _, _ = self._triple()
        other_seismogram.data = other_seismogram.data + 1000.0
        *_, duplicate_warnings = add_seismograms_to_project(
            patched_session,
            [(other_seismogram, station, event)],
            data_dir=tmp_path,
            dry_run=True,
        )

        assert len(duplicate_warnings) == 1
        assert "collision" in duplicate_warnings[0].lower()

    def test_dry_run_does_not_create_data_dir(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """A dry run must not create data_dir as a filesystem side effect."""
        seismogram, station, event = self._triple()
        missing_dir = tmp_path / "nested" / "waveforms"
        assert not missing_dir.exists()

        add_seismograms_to_project(
            patched_session,
            [(seismogram, station, event)],
            data_dir=missing_dir,
            dry_run=True,
        )

        assert not missing_dir.exists()

    def test_mid_batch_failure_does_not_orphan_files(
        self, patched_session: Session, tmp_path: Path
    ) -> None:
        """A later triple's ambiguous-gap failure must not leave an earlier
        triple's waveform file orphaned on disk with no committed DB row."""
        seismogram1, station1, event1 = self._triple()
        ambiguous_event = MiniEvent(
            time=event1.time + Timedelta(seconds=1),
            latitude=event1.latitude,
            longitude=event1.longitude,
            depth=event1.depth,
        )
        seismogram2, station2, _ = self._triple(
            station_name="COLA", begin_time=Timestamp("2020-01-01T02:00:00Z")
        )

        with pytest.raises(ValueError, match="Event time conflict"):
            add_seismograms_to_project(
                patched_session,
                [
                    (seismogram1, station1, event1),
                    (seismogram2, station2, ambiguous_event),
                ],
                data_dir=tmp_path,
            )

        assert list(tmp_path.glob("*.mseed")) == []
        assert len(patched_session.exec(select(AimbatSeismogram)).all()) == 0
