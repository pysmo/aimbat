"""Unit tests for aimbat.io._sac."""

from pathlib import Path

import numpy as np
import pytest
from pandas import Timedelta, Timestamp

from pysmo.classes import SAC

from aimbat.io import (
    DataType,
    SeismogramReadContext,
    SourceRecordsRequest,
    read_picks,
    read_source_records,
)
from aimbat.io.sac import (
    create_event_from_sacfile,
    create_seismogram_from_sacfile,
    create_station_from_sacfile,
    read_picks_from_sacfile,
    read_records_from_sacfile,
    read_seismogram_data_from_sacfile,
    write_seismogram_data_to_sacfile,
)
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatStation


def _sac_context(path: Path) -> SeismogramReadContext:
    return SeismogramReadContext(str(path), DataType.SAC)


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
        data = read_seismogram_data_from_sacfile(_sac_context(sac_file_good))
        assert isinstance(data, np.ndarray)

    def test_matches_pysmo_data(self, sac_file_good: Path) -> None:
        """Verifies that the read data match data read by pysmo.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        expected = SAC.from_file(sac_file_good).seismogram.data
        data = read_seismogram_data_from_sacfile(_sac_context(sac_file_good))
        np.testing.assert_array_equal(data, expected)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that reading from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            read_seismogram_data_from_sacfile(_sac_context(tmp_path / "missing.sac"))


class TestWriteSeismogramData:
    """Tests for writing seismogram data to SAC files."""

    def test_overwrites_data_on_disk(self, sac_file_good: Path) -> None:
        """Verifies that writing data updates the file on disk.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        original = read_seismogram_data_from_sacfile(_sac_context(sac_file_good))
        new_data = np.ones_like(original) * 42.0

        write_seismogram_data_to_sacfile(sac_file_good, new_data)

        reread = read_seismogram_data_from_sacfile(_sac_context(sac_file_good))
        np.testing.assert_array_equal(reread, new_data)

    def test_preserves_length(self, sac_file_good: Path) -> None:
        """Verifies that writing data preserves the number of points.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        original = read_seismogram_data_from_sacfile(_sac_context(sac_file_good))
        write_seismogram_data_to_sacfile(sac_file_good, np.zeros_like(original))
        reread = read_seismogram_data_from_sacfile(_sac_context(sac_file_good))
        assert len(reread) == len(original)

    def test_round_trip(self, sac_file_good: Path) -> None:
        """Write then read should return the same array.

        Args:
            sac_file_good (Path): Path to a valid SAC file.
        """
        data = np.linspace(-1.0, 1.0, 100)
        # First overwrite with our data, then verify the round-trip.
        write_seismogram_data_to_sacfile(sac_file_good, data)
        result = read_seismogram_data_from_sacfile(_sac_context(sac_file_good))
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

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that creating an event from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            create_event_from_sacfile(tmp_path / "missing.sac")


# ===================================================================
# create_seismogram_from_sacfile
# ===================================================================


class TestCreateSeismogram:
    """Tests for creating AimbatSeismogram objects from SAC files."""

    def test_fields_match_sac(self, sac_file_good: Path) -> None:
        """The seismogram's times match the SAC file."""
        sac = SAC.from_file(sac_file_good)
        seis = create_seismogram_from_sacfile(sac_file_good)

        assert isinstance(seis, AimbatSeismogram)
        assert isinstance(seis.begin_time, Timestamp)
        assert seis.begin_time == sac.seismogram.begin_time
        assert isinstance(seis.delta, Timedelta)
        assert seis.delta == sac.seismogram.delta

    def test_file_without_picks(self, sac_file_good: Path) -> None:
        """A SAC file without picks still gives a seismogram."""
        sac = SAC.from_file(sac_file_good)
        sac.timestamps.t0 = None
        sac.timestamps.t1 = None
        sac.write(sac_file_good)

        assert isinstance(
            create_seismogram_from_sacfile(sac_file_good), AimbatSeismogram
        )

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            create_seismogram_from_sacfile(tmp_path / "missing.sac")


# ===================================================================
# picks
# ===================================================================


def _write_picks(
    path: Path, picks: dict[str, tuple[Timedelta | None, str | None]]
) -> SAC:
    """Clear every pick header of a SAC file, then set the given ones.

    Each value is an offset from the seismogram begin time (`None` leaves the
    time unset) and a label (`None` leaves the label unset).
    """
    sac = SAC.from_file(path)
    for header in ("a", *(f"t{i}" for i in range(10))):
        setattr(sac.timestamps, header, None)
        setattr(sac.native, f"k{header}", None)
    for header, (offset, label) in picks.items():
        if offset is not None:
            setattr(sac.timestamps, header, sac.seismogram.begin_time + offset)
        setattr(sac.native, f"k{header}", label)
    sac.write(path)
    return SAC.from_file(path)


class TestReadPicks:
    """Tests for reading picks from SAC files."""

    def test_labelled_pick(self, sac_file_good: Path) -> None:
        """A pick header with a label gives a labelled pick keyed by the header."""
        sac = _write_picks(sac_file_good, {"t3": (Timedelta(seconds=10), "PKP")})
        picks = read_picks_from_sacfile(sac_file_good)
        assert len(picks) == 1
        assert picks[0].key == "t3"
        assert picks[0].label == "PKP"
        assert picks[0].time == sac.timestamps.t3
        assert picks[0].target is None

    def test_undefined_label(self, sac_file_good: Path) -> None:
        """A pick header without a label gives an unlabelled pick."""
        _write_picks(sac_file_good, {"t0": (Timedelta(seconds=10), None)})
        (pick,) = read_picks_from_sacfile(sac_file_good)
        assert pick.label is None

    def test_blank_label(self, sac_file_good: Path) -> None:
        """A pick header with a blank label gives an unlabelled pick."""
        _write_picks(sac_file_good, {"t0": (Timedelta(seconds=10), "   ")})
        (pick,) = read_picks_from_sacfile(sac_file_good)
        assert pick.label is None

    def test_label_without_time(self, sac_file_good: Path) -> None:
        """A label whose pick header holds no time gives no pick."""
        _write_picks(sac_file_good, {"t5": (None, "S")})
        assert read_picks_from_sacfile(sac_file_good) == ()

    def test_a_header(self, sac_file_good: Path) -> None:
        """The `a` header is read with its `ka` label."""
        _write_picks(sac_file_good, {"a": (Timedelta(seconds=5), "P")})
        (pick,) = read_picks_from_sacfile(sac_file_good)
        assert (pick.key, pick.label) == ("a", "P")

    def test_several_picks_in_header_order(self, sac_file_good: Path) -> None:
        """Every set pick header gives one pick, in header order."""
        _write_picks(
            sac_file_good,
            {
                "t9": (Timedelta(seconds=30), "S"),
                "t0": (Timedelta(seconds=10), "P"),
                "a": (Timedelta(seconds=5), None),
            },
        )
        picks = read_picks_from_sacfile(sac_file_good)
        assert [p.key for p in picks] == ["a", "t0", "t9"]

    def test_fixture_picks(self, sac_file_good: Path) -> None:
        """The fixture's `t0` is read with its label, and `t1` without one."""
        sac = SAC.from_file(sac_file_good)
        picks = {p.key: p for p in read_picks_from_sacfile(sac_file_good)}
        assert picks["t0"].time == sac.timestamps.t0
        assert picks["t1"].time == sac.timestamps.t1
        assert picks["t0"].label == "P"
        assert picks["t1"].label is None

    def test_label_longer_than_eight_characters_refused_by_pysmo(self) -> None:
        """pysmo refuses a SAC label longer than eight characters on writing it."""
        sac = SAC()
        with pytest.raises(ValueError):
            sac.native.kt0 = "PKiKPPKP2"

    def test_registered_for_sac(self, sac_file_good: Path) -> None:
        """`read_picks` dispatches SAC to the SAC pick reader."""
        assert read_picks(sac_file_good, DataType.SAC) == read_picks_from_sacfile(
            sac_file_good
        )


class TestReadRecordsPicks:
    """Tests for picks in the SAC records reader."""

    def test_picks_and_end_time(self, sac_file_good: Path) -> None:
        """A request with picks gives the picks and the seismogram end time."""
        sac = SAC.from_file(sac_file_good)
        records = read_records_from_sacfile(
            SourceRecordsRequest(
                str(sac_file_good),
                DataType.SAC,
                station=True,
                event=True,
                seismogram=True,
                picks=True,
            )
        )
        assert records.picks == read_picks_from_sacfile(sac_file_good)
        assert records.seismogram_end_time == sac.seismogram.end_time

    def test_picks_only(self, sac_file_good: Path) -> None:
        """A picks-only request builds no station, event or seismogram."""
        records = read_source_records(
            sac_file_good,
            DataType.SAC,
            station=False,
            event=False,
            seismogram=False,
            picks=True,
        )
        assert records.picks
        assert records.station is None
        assert records.event is None
        assert records.seismogram is None
        assert records.seismogram_end_time is not None

    def test_no_picks_by_default(self, sac_file_good: Path) -> None:
        """Picks are not read unless they are asked for."""
        records = read_source_records(sac_file_good, DataType.SAC)
        assert records.picks == ()
        assert records.seismogram is not None
