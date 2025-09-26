from aimbat.lib.models import AimbatTypes
from typing import Sequence, Any
import json
import uuid
import datetime


def dump_to_json(aimbat_data: Sequence[AimbatTypes]) -> None:
    class CustomEncoder(json.JSONEncoder):
        def default(self, o: Any) -> str | Any:
            if isinstance(o, uuid.UUID):
                return str(o)
            if isinstance(o, datetime.datetime):
                return o.isoformat()
            if isinstance(o, datetime.timedelta):
                return str(o)
            return super().default(o)

    json_str = json.dumps(
        [r.model_dump() for r in aimbat_data],
        cls=CustomEncoder,
        indent=4,
    )
    print(json_str)
