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
from os import PathLike
from typing import TYPE_CHECKING

from aimbat.logger import logger

from ._base import event_creator, station_creator
from ._data import DataType

if TYPE_CHECKING:
    from aimbat.models import AimbatEvent, AimbatStation

__all__ = [
    "create_station_from_json",
    "create_event_from_json",
]


def _load_json(path: str | PathLike[str]) -> object:
    """Read and parse a UTF-8 JSON file, naming the file on a parse error."""
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not valid JSON: {exc}") from exc


@station_creator(DataType.JSON_STATION)
def create_station_from_json(path: str | PathLike[str]) -> AimbatStation:
    """Create an `AimbatStation` from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        A new `AimbatStation` instance.
    """
    from aimbat.models import AimbatStation

    logger.debug(f"Reading station data from {path}.")

    return AimbatStation.model_validate(_load_json(path))


@event_creator(DataType.JSON_EVENT)
def create_event_from_json(path: str | PathLike[str]) -> AimbatEvent:
    """Create an `AimbatEvent` from a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        A new `AimbatEvent` instance.
    """
    from aimbat.models import AimbatEvent, AimbatEventParameters

    logger.debug(f"Reading event data from {path}.")

    event = AimbatEvent.model_validate(_load_json(path))
    event.parameters = AimbatEventParameters()
    return event
