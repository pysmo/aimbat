"""Unit tests for aimbat.io.json."""

import json
from pathlib import Path

import pytest
from pandas import Timestamp
from pydantic import ValidationError

from aimbat.io.json import create_event_from_json, create_station_from_json
from aimbat.models import AimbatEvent, AimbatStation

_STATION_DATA: dict = {
    "name": "ANMO",
    "network": "IU",
    "location": "00",
    "channel": "BHZ",
    "latitude": 34.9459,
    "longitude": -106.4572,
    "elevation": 1820.0,
}

_EVENT_DATA: dict = {
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
# create_station_from_json
# ===================================================================


class TestCreateStationFromJson:
    """Tests for create_station_from_json."""

    def test_returns_aimbat_station(self, station_json: Path) -> None:
        """Verifies that the function returns an AimbatStation instance.

        Args:
            station_json: Path to a valid JSON station file.
        """
        station = create_station_from_json(station_json)
        assert isinstance(station, AimbatStation)

    def test_fields_match_json(self, station_json: Path) -> None:
        """Verifies that station fields match the JSON values.

        Args:
            station_json: Path to a valid JSON station file.
        """
        station = create_station_from_json(station_json)
        assert station.name == _STATION_DATA["name"]
        assert station.network == _STATION_DATA["network"]
        assert station.location == _STATION_DATA["location"]
        assert station.channel == _STATION_DATA["channel"]
        assert station.latitude == _STATION_DATA["latitude"]
        assert station.longitude == _STATION_DATA["longitude"]
        assert station.elevation == _STATION_DATA["elevation"]

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        """Verifies that a JSON file missing required fields raises ValidationError.

        Args:
            tmp_path: Temporary directory path.
        """
        path = tmp_path / "bad_station.json"
        path.write_text(json.dumps({"name": "ANMO"}))
        with pytest.raises(ValidationError):
            create_station_from_json(path)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that reading from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path: Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            create_station_from_json(tmp_path / "missing.json")


# ===================================================================
# create_event_from_json
# ===================================================================


class TestCreateEventFromJson:
    """Tests for create_event_from_json."""

    def test_returns_aimbat_event(self, event_json: Path) -> None:
        """Verifies that the function returns an AimbatEvent instance.

        Args:
            event_json: Path to a valid JSON event file.
        """
        event = create_event_from_json(event_json)
        assert isinstance(event, AimbatEvent)

    def test_fields_match_json(self, event_json: Path) -> None:
        """Verifies that event fields match the JSON values.

        Args:
            event_json: Path to a valid JSON event file.
        """
        event = create_event_from_json(event_json)
        assert event.time == Timestamp("2020-01-01T00:00:00Z")
        assert event.latitude == _EVENT_DATA["latitude"]
        assert event.longitude == _EVENT_DATA["longitude"]
        assert event.depth == _EVENT_DATA["depth"]

    def test_has_parameters(self, event_json: Path) -> None:
        """Verifies that the created event has initialised parameters.

        Args:
            event_json: Path to a valid JSON event file.
        """
        event = create_event_from_json(event_json)
        assert event.parameters is not None

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        """Verifies that a JSON file missing required fields raises ValidationError.

        Args:
            tmp_path: Temporary directory path.
        """
        path = tmp_path / "bad_event.json"
        path.write_text(json.dumps({"latitude": 35.0}))
        with pytest.raises(ValidationError):
            create_event_from_json(path)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Verifies that reading from a non-existent file raises FileNotFoundError.

        Args:
            tmp_path: Temporary directory path.
        """
        with pytest.raises(FileNotFoundError):
            create_event_from_json(tmp_path / "missing.json")
