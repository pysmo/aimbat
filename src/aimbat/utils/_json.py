from aimbat.models import AimbatTypes
from typing import Sequence, Any
from pandas import Timestamp, Timedelta
import json
import uuid

__all__ = ["dump_to_json"]


def dump_to_json(aimbat_data: Sequence[AimbatTypes]) -> None:
    """Dump a sequence of AimbatTypes to a JSON string and print it.

    Args:
        aimbat_data: A sequence of AimbatTypes to dump to JSON.
    """

    class CustomEncoder(json.JSONEncoder):
        def default(self, o: Any) -> str | Any:
            if isinstance(o, uuid.UUID):
                return str(o)
            if isinstance(o, Timestamp):
                return o.isoformat()
            if isinstance(o, Timedelta):
                return o.total_seconds()
            return super().default(o)

    json_str = json.dumps(
        [r.model_dump(mode="python") for r in aimbat_data],
        cls=CustomEncoder,
        indent=4,
    )
    print(json_str)
