"""Unit tests for aimbat.io._sac."""

from aimbat.io.sac import (
    create_event_from_sacfile,
    create_seismogram_from_sacfile_and_pick_header,
    create_station_from_sacfile,
    read_seismogram_data_from_sacfile,
    write_seismogram_data_to_sacfile,
)
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatStation
from pathlib import Path
from pandas import Timedelta, Timestamp
from pydantic import ValidationError
from pysmo.classes import SAC
import numpy as np
import pytest

# ===================================================================
# read / write seismogram data
# ===================================================================


class TestReadSeismogramData:
    """Tests for reading seismogram data from SAC files."""

    def test_returns_ndarray(self, sac_file_good: Path) -> None:
        """Verifies that reading data returns a numpy ndarray.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        data = read_seismogram_data_from_sacfile(sac_file_good)
        assert isinstance(data, np.ndarray)

    def test_matches_pysmo_data(self, sac_file_good: Path) -> None:
        """Verifies that the read data matches data read by pysmo.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        expected = SAC.from_file(sac_file_good).seismogram.data
        data = read_seismogram_data_from_sacfile(sac_file_good)
        np.testing.assert_array_equal(data, expected)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that reading from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            read_seismogram_data_from_sacfile(tmp_path / "missing.sac")


class TestWriteSeismogramData:
    """Tests for writing seismogram data to SAC files."""

    def test_overwrites_data_on_disk(self, sac_file_good: Path) -> None:
        """Verifies that writing data updates the file on disk.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        original = read_seismogram_data_from_sacfile(sac_file_good)
        new_data = np.ones_like(original) * 42.0

        write_seismogram_data_to_sacfile(sac_file_good, new_data)

        reread = read_seismogram_data_from_sacfile(sac_file_good)
        np.testing.assert_array_equal(reread, new_data)

    def test_preserves_length(self, sac_file_good: Path) -> None:
        """Verifies that writing data preserves the number of points.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        original = read_seismogram_data_from_sacfile(sac_file_good)
        write_seismogram_data_to_sacfile(sac_file_good, np.zeros_like(original))
        reread = read_seismogram_data_from_sacfile(sac_file_good)
        assert len(reread) == len(original)

    def test_round_trip(self, sac_file_good: Path) -> None:
        """Write then read should return the same array.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        data = np.linspace(-1.0, 1.0, 100)
        # First overwrite with our data, then verify the round-trip.
        write_seismogram_data_to_sacfile(sac_file_good, data)
        result = read_seismogram_data_from_sacfile(sac_file_good)
        np.testing.assert_allclose(result, data)


# ===================================================================
# create_station_from_sacfile
# ===================================================================


class TestCreateStation:
    """Tests for creating AimbatStation objects from SAC files."""

    def test_returns_aimbat_station(self, sac_file_good: Path) -> None:
        """Verifies that the function returns an AimbatStation instance.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        station = create_station_from_sacfile(sac_file_good)
        assert isinstance(station, AimbatStation)

    def test_fields_match_sac(self, sac_file_good: Path) -> None:
        """Verifies that station fields match the SAC header values.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        sac = SAC.from_file(sac_file_good)
        station = create_station_from_sacfile(sac_file_good)

        assert station.name == sac.station.name
        assert station.network == sac.station.network
        assert station.location == sac.station.location
        assert station.channel == sac.station.channel
        assert station.latitude == sac.station.latitude
        assert station.longitude == sac.station.longitude
        assert station.elevation == sac.station.elevation

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that creating a station from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            create_station_from_sacfile(tmp_path / "missing.sac")


# ===================================================================
# create_event_from_sacfile
# ===================================================================


class TestCreateEvent:
    """Tests for creating AimbatEvent objects from SAC files."""

    def test_returns_aimbat_event(self, sac_file_good: Path) -> None:
        """Verifies that the function returns an AimbatEvent instance.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        event = create_event_from_sacfile(sac_file_good)
        assert isinstance(event, AimbatEvent)

    def test_fields_match_sac(self, sac_file_good: Path) -> None:
        """Verifies that event fields match the SAC header values.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        sac = SAC.from_file(sac_file_good)
        event = create_event_from_sacfile(sac_file_good)

        assert isinstance(event.time, Timestamp)
        assert event.time == sac.event.time
        assert event.latitude == sac.event.latitude
        assert event.longitude == sac.event.longitude
        assert event.depth == sac.event.depth

    def test_has_parameters(self, sac_file_good: Path) -> None:
        """Verifies that the created event has initialized parameters.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        event = create_event_from_sacfile(sac_file_good)
        assert event.parameters is not None

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that creating an event from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            create_event_from_sacfile(tmp_path / "missing.sac")


# ===================================================================
# create_seismogram_from_sacfile_and_pick_header
# ===================================================================


class TestCreateSeismogram:
    """Tests for creating AimbatSeismogram objects from SAC files."""

    def test_returns_aimbat_seismogram(self, sac_file_good: Path) -> None:
        """Verifies that the function returns an AimbatSeismogram instance.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        seis = create_seismogram_from_sacfile_and_pick_header(sac_file_good, "t0")
        assert isinstance(seis, AimbatSeismogram)

    def test_fields_match_sac(self, sac_file_good: Path) -> None:
        """Verifies that seismogram fields match the SAC header values.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        sac = SAC.from_file(sac_file_good)
        seis = create_seismogram_from_sacfile_and_pick_header(sac_file_good, "t0")

        assert isinstance(seis.begin_time, Timestamp)
        assert seis.begin_time == sac.seismogram.begin_time
        assert isinstance(seis.delta, Timedelta)
        assert seis.delta == sac.seismogram.delta

    def test_t0_uses_requested_pick_header(self, sac_file_good: Path) -> None:
        """Verifies that t0 is populated from the specified pick header.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        sac = SAC.from_file(sac_file_good)

        seis_t0 = create_seismogram_from_sacfile_and_pick_header(sac_file_good, "t0")
        assert seis_t0.t0 == sac.timestamps.t0

        seis_t1 = create_seismogram_from_sacfile_and_pick_header(sac_file_good, "t1")
        assert seis_t1.t0 == sac.timestamps.t1

    def test_has_parameters(self, sac_file_good: Path) -> None:
        """Verifies that the created seismogram has initialized parameters.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        seis = create_seismogram_from_sacfile_and_pick_header(sac_file_good, "t0")
        assert seis.parameters is not None

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that creating a seismogram from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            create_seismogram_from_sacfile_and_pick_header(
                tmp_path / "missing.sac", "t0"
            )

    def test_invalid_pick_header_raises(self, sac_file_good: Path) -> None:
        """Verifies that requesting an invalid pick header raises AttributeError.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        with pytest.raises(AttributeError):
            create_seismogram_from_sacfile_and_pick_header(
                sac_file_good, "nonexistent_header"
            )

    def test_none_pick_raises(self, sac_file_good: Path) -> None:
        """Verifies that if the pick header exists but is None, ValidationError is raised.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        sac = SAC.from_file(sac_file_good)
        # Find a timestamp header that is None.
        none_header = None
        for name in ["t4", "t5", "t6", "t7", "t8", "t9"]:
            if getattr(sac.timestamps, name) is None:
                none_header = name
                break
        assert none_header is not None, "expected at least one None timestamp header"

        with pytest.raises(ValidationError):
            create_seismogram_from_sacfile_and_pick_header(sac_file_good, none_header)
