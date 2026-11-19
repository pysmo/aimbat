"""Unit tests for the pick contract in aimbat.io."""

from os import PathLike
from uuid import uuid4

import pytest
from pandas import Timestamp

from aimbat.io import (
    DataType,
    SeismogramTarget,
    SourcePick,
    SourceRecords,
    SourceRecordsRequest,
    StationEventTarget,
    pick_reader,
    read_picks,
    read_source_records,
    supports_pick_reading,
)
from aimbat.io._base import _pick_readers, _source_records_readers

_TIME = Timestamp("2020-01-01T00:00:00", tz="UTC")


class TestSourcePick:
    """Tests for `SourcePick` validation and normalisation."""

    def test_valid_pick(self) -> None:
        """A timezone-aware time and a key make a pick with no label or target."""
        pick = SourcePick(time=_TIME, key="t0")
        assert pick.label is None
        assert pick.target is None

    def test_naive_time_rejected(self) -> None:
        """A time without a timezone is rejected."""
        with pytest.raises(ValueError, match="timezone-aware"):
            SourcePick(time=Timestamp("2020-01-01T00:00:00"), key="t0")

    @pytest.mark.parametrize("key", ["", "   "])
    def test_blank_key_rejected(self, key: str) -> None:
        """An empty or blank key is rejected."""
        with pytest.raises(ValueError, match="key"):
            SourcePick(time=_TIME, key=key)

    def test_key_stripped(self) -> None:
        """Surrounding blanks are removed from the key."""
        assert SourcePick(time=_TIME, key=" t0 ").key == "t0"

    def test_label_stripped(self) -> None:
        """Surrounding blanks are removed from the label."""
        assert SourcePick(time=_TIME, key="t0", label="  P ").label == "P"

    def test_blank_label_is_none(self) -> None:
        """A blank label is stored as `None`."""
        assert SourcePick(time=_TIME, key="t0", label="   ").label is None

    def test_targets(self) -> None:
        """Both target kinds are accepted."""
        by_id = SeismogramTarget(seismogram_id=uuid4())
        by_codes = StationEventTarget(network="XX", station="ABC")
        assert SourcePick(time=_TIME, key="1", target=by_id).target == by_id
        assert SourcePick(time=_TIME, key="2", target=by_codes).target == by_codes


class TestStationEventTarget:
    """Tests for `StationEventTarget` normalisation."""

    def test_double_dash_location_normalised(self) -> None:
        """A location of `--` is the blank location."""
        assert StationEventTarget(location="--").location == ""

    def test_other_locations_kept(self) -> None:
        """Other locations, including `None`, are kept as given."""
        assert StationEventTarget(location="00").location == "00"
        assert StationEventTarget().location is None

    def test_naive_event_time_rejected(self) -> None:
        """An event time without a timezone is rejected."""
        with pytest.raises(ValueError, match="timezone-aware"):
            StationEventTarget(event_time=Timestamp("2020-01-01T00:00:00"))


@pytest.fixture
def fake_pick_reader(monkeypatch: pytest.MonkeyPatch) -> tuple[SourcePick, ...]:
    """Registers a pick reader for miniSEED, which has no records reader."""
    monkeypatch.setattr("aimbat.io._base._pick_readers", dict(_pick_readers))
    picks = (SourcePick(time=_TIME, key="only", label="P"),)

    @pick_reader(DataType.MSEED)
    def _read(_source: str | PathLike[str]) -> tuple[SourcePick, ...]:
        return picks

    return picks


class TestPickReaderRegistry:
    """Tests for registering and dispatching pick readers."""

    def test_sac_registered(self) -> None:
        """SAC registers a pick reader on import."""
        assert supports_pick_reading(DataType.SAC)

    def test_unregistered_type_raises(self) -> None:
        """A data type without a pick reader raises `NotImplementedError`."""
        assert not supports_pick_reading(DataType.JSON_EVENT)
        with pytest.raises(NotImplementedError):
            read_picks("whatever.json", DataType.JSON_EVENT)

    def test_registered_reader_dispatched(
        self, fake_pick_reader: tuple[SourcePick, ...]
    ) -> None:
        """`read_picks` returns what the registered reader returns."""
        assert supports_pick_reading(DataType.MSEED)
        assert read_picks("x.mseed", DataType.MSEED) == fake_pick_reader


class TestReadSourceRecordsPicks:
    """Tests for picks in `read_source_records`."""

    def test_picks_only_request_falls_back_to_pick_reader(
        self, fake_pick_reader: tuple[SourcePick, ...]
    ) -> None:
        """A picks-only request is served by the pick reader alone."""
        records = read_source_records(
            "x.mseed",
            DataType.MSEED,
            station=False,
            event=False,
            seismogram=False,
            picks=True,
        )
        assert records.picks == fake_pick_reader
        assert records.station is None
        assert records.seismogram is None

    def test_picks_not_read_by_default(
        self, fake_pick_reader: tuple[SourcePick, ...]
    ) -> None:
        """Picks are left out unless they are asked for."""
        records = read_source_records(
            "x.mseed", DataType.MSEED, station=False, event=False, seismogram=False
        )
        assert records == SourceRecords()

    def test_records_reader_receives_picks_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A records reader is asked for picks through its request."""
        seen: list[SourceRecordsRequest] = []

        def _reader(request: SourceRecordsRequest) -> SourceRecords:
            seen.append(request)
            return SourceRecords()

        monkeypatch.setitem(_source_records_readers, DataType.MSEED, _reader)
        read_source_records(
            "x.mseed",
            DataType.MSEED,
            station=False,
            event=False,
            seismogram=False,
            picks=True,
        )
        assert len(seen) == 1
        assert seen[0].picks is True
