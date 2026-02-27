"""JSON data source support for AIMBAT.

Provides station and event creation from JSON files:

- `JSON_STATION` (`DataType.JSON_STATION`): a JSON file containing a single
  station record. Field names match `AimbatStation`:

    ```json
    {
        "name": "ANMO",
        "network": "IU",
        "location": "00",
        "channel": "BHZ",
        "latitude": 34.9459,
        "longitude": -106.4572,
        "elevation": 1820.0
    }
    ```

- `JSON_EVENT` (`DataType.JSON_EVENT`): a JSON file containing a single event
  record. Field names match `AimbatEvent`:

    ```json
    {
        "time": "2020-01-01T00:00:00Z",
        "latitude": 35.0,
        "longitude": -120.0,
        "depth": 10.0
    }
    ```
"""

from __future__ import annotations
import json
from ._data import DataType
from aimbat.logger import logger
from os import PathLike
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aimbat.models import AimbatEvent, AimbatStation

__all__ = [
    "create_station_from_json",
    "create_event_from_json",
]


def create_station_from_json(path: str | PathLike) -> AimbatStation:
    """Create an `AimbatStation` from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        A new `AimbatStation` instance.
    """
    from aimbat.models import AimbatStation

    logger.debug(f"Reading station data from {path}.")

    with open(path) as f:
        data = json.load(f)
    return AimbatStation.model_validate(data)


def create_event_from_json(path: str | PathLike) -> AimbatEvent:
    """Create an `AimbatEvent` from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        A new `AimbatEvent` instance.
    """
    from aimbat.models import AimbatEvent, AimbatEventParameters

    logger.debug(f"Reading event data from {path}.")

    with open(path) as f:
        data = json.load(f)
    event = AimbatEvent.model_validate(data)
    event.parameters = AimbatEventParameters()
    return event


# Register JSON capabilities with the io dispatch layer
from ._base import register_station_creator, register_event_creator  # noqa: E402

register_station_creator(DataType.JSON_STATION, create_station_from_json)
register_event_creator(DataType.JSON_EVENT, create_event_from_json)
