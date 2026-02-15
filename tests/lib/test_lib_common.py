from sqlmodel import Session
from aimbat.lib.models import AimbatStation
from collections.abc import Iterator
import pytest
import uuid

UUID1 = uuid.UUID("11e6ca37-e03b-42b6-acc4-e9eaba5c1587")
UUID2 = uuid.UUID("12e6ca37-e03b-42b6-acc4-e9eaba5c1587")


class TestUuidFunctions:
    @pytest.fixture
    def session_with_stations(
        self, fixture_session_with_project: Session
    ) -> Iterator[Session]:
        station_1 = AimbatStation(
            id=UUID1,
            name="TEST1",
            network="TE",
            channel="BHZ",
            location="",
            latitude=12,
            longitude=12,
            elevation=12,
        )
        station_2 = AimbatStation(
            id=UUID2,
            name="TEST2",
            network="TE",
            channel="BHZ",
            location="",
            latitude=12,
            longitude=12,
            elevation=12,
        )
        session = fixture_session_with_project
        session.add_all([station_1, station_2])
        session.commit()
        yield session

    @pytest.mark.parametrize(
        "uuid_str,expected",
        [
            (str(UUID1)[:2], UUID1),
            (str(UUID2)[:2], UUID2),
            (str(UUID1), UUID1),
            (str(UUID1)[:1], ValueError),
            (str(UUID2)[:1], ValueError),
            (str(uuid.uuid4()), ValueError),
        ],
    )
    def test_string_to_uuid(
        self,
        session_with_stations: Session,
        uuid_str: str,
        expected: uuid.UUID | Exception,
    ) -> None:
        from aimbat.lib.common import string_to_uuid

        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                string_to_uuid(session_with_stations, uuid_str, AimbatStation)
        else:
            assert (
                string_to_uuid(session_with_stations, uuid_str, AimbatStation)
                == expected
            )

    @pytest.mark.parametrize("test_uuid", [UUID1, UUID2])
    def test_uuid_shortener(
        self, session_with_stations: Session, test_uuid: uuid.UUID
    ) -> None:
        from aimbat.lib.common import uuid_shortener

        aimbat_station = session_with_stations.get(AimbatStation, test_uuid)
        assert aimbat_station is not None
        assert (
            uuid_shortener(session_with_stations, aimbat_station) == str(test_uuid)[:2]
        )
