"""Unit tests for aimbat.io.json."""

import json
from pathlib import Path

import pytest
from pandas import Timestamp
from pydantic import ValidationError

from aimbat.io.json import create_event_from_json, create_station_from_json
from aimbat.models import AimbatEvent, AimbatStation

from testsupport.sources import EVENT_DATA, STATION_DATA

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
        assert station.name == STATION_DATA["name"]
        assert station.network == STATION_DATA["network"]
        assert station.location == STATION_DATA["location"]
        assert station.channel == STATION_DATA["channel"]
        assert station.latitude == STATION_DATA["latitude"]
        assert station.longitude == STATION_DATA["longitude"]
        assert station.elevation == STATION_DATA["elevation"]

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

    def test_malformed_json_names_the_file(self, tmp_path: Path) -> None:
        """A parse error is wrapped with the offending path, not raised raw."""
        path = tmp_path / "broken.json"
        path.write_text("{not json")
        with pytest.raises(ValueError, match="broken.json is not valid JSON"):
            create_station_from_json(path)

    def test_utf8_content_is_read(self, tmp_path: Path) -> None:
        """Non-ASCII station names round-trip regardless of platform encoding."""
        path = tmp_path / "utf8_station.json"
        data = {**STATION_DATA, "name": "ÑOÑÓ"}
        path.write_text(json.dumps(data), encoding="utf-8")
        assert create_station_from_json(path).name == "ÑOÑÓ"


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
        assert event.latitude == EVENT_DATA["latitude"]
        assert event.longitude == EVENT_DATA["longitude"]
        assert event.depth == EVENT_DATA["depth"]

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
