"""Contents of data sources written by tests."""

__all__ = ["EVENT_DATA", "STATION_DATA"]

STATION_DATA: dict[str, str | float] = {
    "name": "ANMO",
    "network": "IU",
    "location": "00",
    "channel": "BHZ",
    "latitude": 34.9459,
    "longitude": -106.4572,
    "elevation": 1820.0,
}
"""A station as stored in a JSON station source."""

EVENT_DATA: dict[str, str | float] = {
    "time": "2020-01-01T00:00:00Z",
    "latitude": 35.0,
    "longitude": -120.0,
    "depth": 10.0,
}
"""An event as stored in a JSON event source."""
