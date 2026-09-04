"""Unit tests for aimbat.io.mseed."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pymseed.exceptions import MiniSEEDError  # type: ignore[import-untyped]

from pysmo import MiniSeismogram, MiniStationCode
from pysmo.classes import MSeed
from pysmo.lib.io import write_mseed

from aimbat.io import (
    DataType,
    supports_event_creation,
    supports_seismogram_creation,
    supports_station_creation,
)
from aimbat.io.mseed import (
    read_seismogram_data_from_mseedfile,
    write_seismogram_data_to_mseedfile,
)


@pytest.fixture
def mseed_file_good(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A miniSEED file with exactly one clean, contiguous segment."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    path = tmpdir / "good.mseed"
    identity = MiniStationCode(network="IU", name="ANMO", location="00", channel="BHZ")
    seismogram = MiniSeismogram(
        begin_time=pd.Timestamp("2020-01-01T00:00:00Z"),
        delta=pd.Timedelta(seconds=0.05),
        data=np.arange(100.0),
    )
    write_mseed([(identity, seismogram)], path)
    return path


@pytest.fixture
def mseed_file_multichannel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A miniSEED file multiplexing two channels - not round-trippable by this module."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    path = tmpdir / "multichannel.mseed"
    seismogram = MiniSeismogram(
        begin_time=pd.Timestamp("2020-01-01T00:00:00Z"),
        delta=pd.Timedelta(seconds=0.05),
        data=np.arange(100.0),
    )
    write_mseed(
        [
            (
                MiniStationCode(
                    network="IU", name="ANMO", location="00", channel="BHZ"
                ),
                seismogram,
            ),
            (
                MiniStationCode(
                    network="IU", name="ANMO", location="00", channel="BHN"
                ),
                seismogram,
            ),
        ],
        path,
    )
    return path


@pytest.fixture
def mseed_file_gappy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A miniSEED file with two segments on the same channel, separated by a gap."""
    tmpdir = tmp_path_factory.mktemp("aimbat")
    path = tmpdir / "gappy.mseed"
    identity = MiniStationCode(network="IU", name="ANMO", location="00", channel="BHZ")
    first = MiniSeismogram(
        begin_time=pd.Timestamp("2020-01-01T00:00:00Z"),
        delta=pd.Timedelta(seconds=0.05),
        data=np.arange(100.0),
    )
    second = MiniSeismogram(
        begin_time=pd.Timestamp("2020-01-01T01:00:00Z"),
        delta=pd.Timedelta(seconds=0.05),
        data=np.arange(100.0),
    )
    write_mseed([(identity, first), (identity, second)], path)
    return path


# ===================================================================
# read / write seismogram data
# ===================================================================


class TestReadSeismogramData:
    """Tests for reading seismogram data from miniSEED files."""

    def test_returns_ndarray(self, mseed_file_good: Path) -> None:
        data = read_seismogram_data_from_mseedfile(mseed_file_good)
        assert isinstance(data, np.ndarray)

    def test_matches_pysmo_data(self, mseed_file_good: Path) -> None:
        expected = MSeed.from_file(mseed_file_good).data
        data = read_seismogram_data_from_mseedfile(mseed_file_good)
        np.testing.assert_array_equal(data, expected)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(MiniSEEDError):
            read_seismogram_data_from_mseedfile(tmp_path / "missing.mseed")

    def test_multichannel_file_raises_value_error(
        self, mseed_file_multichannel: Path
    ) -> None:
        """A multiplexed archival-style file is out of scope - see the module docstring."""
        with pytest.raises(ValueError):
            read_seismogram_data_from_mseedfile(mseed_file_multichannel)

    def test_gappy_file_raises_value_error(self, mseed_file_gappy: Path) -> None:
        """A gappy archival-style file is out of scope - see the module docstring."""
        with pytest.raises(ValueError):
            read_seismogram_data_from_mseedfile(mseed_file_gappy)


class TestWriteSeismogramData:
    """Tests for writing seismogram data to miniSEED files."""

    def test_overwrites_data_on_disk(self, mseed_file_good: Path) -> None:
        original = read_seismogram_data_from_mseedfile(mseed_file_good)
        new_data = np.ones_like(original) * 42.0

        write_seismogram_data_to_mseedfile(mseed_file_good, new_data)

        reread = read_seismogram_data_from_mseedfile(mseed_file_good)
        np.testing.assert_array_equal(reread, new_data)

    def test_preserves_other_fields(self, mseed_file_good: Path) -> None:
        before = MSeed.from_file(mseed_file_good)
        write_seismogram_data_to_mseedfile(mseed_file_good, np.zeros(len(before.data)))
        after = MSeed.from_file(mseed_file_good)

        assert after.begin_time == before.begin_time
        assert after.delta == before.delta
        assert after.sourceid == before.sourceid

    def test_round_trip(self, mseed_file_good: Path) -> None:
        data = np.linspace(-1.0, 1.0, 100)
        write_seismogram_data_to_mseedfile(mseed_file_good, data)
        result = read_seismogram_data_from_mseedfile(mseed_file_good)
        np.testing.assert_allclose(result, data)


# ===================================================================
# capability registration
# ===================================================================


class TestCapabilities:
    """MSEED registers a reader/writer only - no station, event, or seismogram creator."""

    def test_no_station_creation(self) -> None:
        assert supports_station_creation(DataType.MSEED) is False

    def test_no_event_creation(self) -> None:
        assert supports_event_creation(DataType.MSEED) is False

    def test_no_seismogram_creation(self) -> None:
        assert supports_seismogram_creation(DataType.MSEED) is False
