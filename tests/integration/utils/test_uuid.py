"""Integration tests for aimbat.utils._uuid."""

import uuid

import pandas as pd
import pytest
from sqlalchemy import event
from sqlmodel import Session

import aimbat
from aimbat.models import AimbatEvent
from aimbat.utils._uuid import string_to_uuid, uuid_shortener


def _make_event(uid: uuid.UUID, offset_seconds: int = 0) -> AimbatEvent:
    """Helper to create an AimbatEvent with a specific UUID and time offset.

    Args:
        uid: The UUID for the event.
        offset_seconds: Time offset in seconds.

    Returns:
        The created event.
    """
    return AimbatEvent(
        id=uid,
        time=pd.Timestamp("2000-01-01") + pd.Timedelta(seconds=offset_seconds),
        latitude=0.0,
        longitude=0.0,
        depth=0.0,
    )


class TestStringToUuid:
    """Tests for the string_to_uuid function."""

    def test_resolves_full_uuid(self, patched_session: Session) -> None:
        """Verifies resolving a full UUID string.

        Args:
            patched_session: The database session.
        """
        uid = uuid.uuid4()
        patched_session.add(_make_event(uid))
        patched_session.commit()
        result = string_to_uuid(patched_session, str(uid), AimbatEvent)
        assert result == uid

    def test_resolves_short_prefix(self, patched_session: Session) -> None:
        """Verifies resolving a UUID from a short prefix.

        Args:
            patched_session: The database session.
        """
        uid = uuid.uuid4()
        patched_session.add(_make_event(uid))
        patched_session.commit()
        prefix = str(uid).replace("-", "")[:6]
        result = string_to_uuid(patched_session, prefix, AimbatEvent)
        assert result == uid

    def test_raises_on_no_match(self, patched_session: Session) -> None:
        """Verifies that ValueError is raised when no match is found.

        Args:
            patched_session: The database session.
        """
        with pytest.raises(ValueError, match="Unable to find"):
            string_to_uuid(patched_session, "000000", AimbatEvent)

    def test_raises_on_ambiguous_match(self, patched_session: Session) -> None:
        """Verifies that ValueError is raised when multiple matches are found.

        Args:
            patched_session: The database session.
        """
        uid1 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        uid2 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000002")
        patched_session.add(_make_event(uid1, offset_seconds=0))
        patched_session.add(_make_event(uid2, offset_seconds=1))
        patched_session.commit()
        with pytest.raises(ValueError, match="more than one"):
            string_to_uuid(patched_session, "aaaaaaaa", AimbatEvent)

    def test_custom_error_message(self, patched_session: Session) -> None:
        """Verifies that a custom error message is used when provided.

        Args:
            patched_session: The database session.
        """
        with pytest.raises(ValueError, match="custom error"):
            string_to_uuid(
                patched_session, "000000", AimbatEvent, custom_error="custom error"
            )

    def test_ignores_dashes_in_input(self, patched_session: Session) -> None:
        """Verifies that dashes in the input string are ignored.

        Args:
            patched_session: The database session.
        """
        uid = uuid.UUID("abcdef12-1234-4000-8000-000000000001")
        patched_session.add(_make_event(uid))
        patched_session.commit()
        result = string_to_uuid(patched_session, "abcdef12-1234", AimbatEvent)
        assert result == uid

    def test_escapes_like_wildcards_in_input(self, patched_session: Session) -> None:
        """Verifies that `%`/`_` in the input are treated literally, not as wildcards.

        Args:
            patched_session: The database session.
        """
        uid = uuid.uuid4()
        patched_session.add(_make_event(uid))
        patched_session.commit()
        with pytest.raises(ValueError, match="Unable to find"):
            string_to_uuid(patched_session, "%", AimbatEvent)


class TestUuidShortener:
    """Tests for the uuid_shortener function."""

    def test_returns_unique_prefix_for_single_entry(
        self, patched_session: Session
    ) -> None:
        """Verifies getting a unique prefix for a single event.

        Args:
            patched_session: The database session.
        """
        uid = uuid.uuid4()
        event = _make_event(uid)
        patched_session.add(event)
        patched_session.commit()
        short = uuid_shortener(patched_session, event)
        assert str(uid).startswith(short)

    def test_prefix_is_shortest_unique(self, patched_session: Session) -> None:
        """Verifies that the returned prefix is the shortest possible unique prefix.

        Args:
            patched_session: The database session.
        """
        uid1 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        uid2 = uuid.UUID("bbbbbbbb-0000-4000-8000-000000000002")
        e1 = _make_event(uid1, offset_seconds=0)
        e2 = _make_event(uid2, offset_seconds=1)
        patched_session.add(e1)
        patched_session.add(e2)
        patched_session.commit()
        short1 = uuid_shortener(patched_session, e1)
        short2 = uuid_shortener(patched_session, e2)
        assert str(uid1).startswith(short1), "prefix should match uid1"
        assert str(uid2).startswith(short2), "prefix should match uid2"
        assert not str(uid2).startswith(short1), "short1 should not match uid2"
        assert not str(uid1).startswith(short2), "short2 should not match uid1"

    def test_disambiguates_shared_prefix(self, patched_session: Session) -> None:
        """Verifies disambiguation when two UUIDs share a long common prefix.

        Args:
            patched_session: The database session.
        """
        uid1 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        uid2 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000002")
        e1 = _make_event(uid1, offset_seconds=0)
        e2 = _make_event(uid2, offset_seconds=1)
        patched_session.add(e1)
        patched_session.add(e2)
        patched_session.commit()
        short1 = uuid_shortener(patched_session, e1)
        short2 = uuid_shortener(patched_session, e2)
        assert short1 != short2, "disambiguated prefixes should differ"
        assert str(uid1).startswith(short1), "short1 should match uid1"
        assert str(uid2).startswith(short2), "short2 should match uid2"

    def test_class_form_with_str_uuid(self, patched_session: Session) -> None:
        """Verifies calling with a class and string UUID instead of a model instance.

        Args:
            patched_session: The database session.
        """
        uid = uuid.uuid4()
        patched_session.add(_make_event(uid))
        patched_session.commit()
        short = uuid_shortener(patched_session, AimbatEvent, str_uuid=str(uid))
        assert str(uid).startswith(short)

    def test_class_form_requires_str_uuid(self, patched_session: Session) -> None:
        """Verifies that str_uuid is required when calling with a class.

        Args:
            patched_session: The database session.
        """
        with pytest.raises(ValueError, match="str_uuid must be provided"):
            uuid_shortener(patched_session, AimbatEvent)

    def test_raises_if_id_not_in_table(self, patched_session: Session) -> None:
        """Verifies that ValueError is raised if the UUID is not in the table.

        Args:
            patched_session: The database session.
        """
        uid = uuid.uuid4()
        with pytest.raises(ValueError, match="not found in table"):
            uuid_shortener(patched_session, AimbatEvent, str_uuid=str(uid))

    def test_min_length_crossing_a_dash_boundary(
        self, patched_session: Session
    ) -> None:
        """Verifies a min_length that lands just past a hyphen in the UUID.

        Regression test: the internal length bookkeeping used to mix a
        dash-free count (for the SQL query) with a dashed-string count (for
        the candidate loop); this exercises a min_length that only makes
        sense counted on the dash-free string.
        """
        uid1 = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
        uid2 = uuid.UUID("aaaaaaab-0000-4000-8000-000000000002")
        e1 = _make_event(uid1, offset_seconds=0)
        e2 = _make_event(uid2, offset_seconds=1)
        patched_session.add(e1)
        patched_session.add(e2)
        patched_session.commit()
        # 9 dash-free characters reaches just past the first hyphen (index 8).
        short1 = uuid_shortener(patched_session, e1, min_length=9)
        short2 = uuid_shortener(patched_session, e2, min_length=9)
        assert str(uid1).startswith(short1)
        assert str(uid2).startswith(short2)
        assert short1 != short2
        assert len(short1.replace("-", "")) >= 9

    def test_min_length_respected(self, patched_session: Session) -> None:
        """Verifies that the minimum length constraint is respected.

        Args:
            patched_session: The database session.
        """
        uid = uuid.uuid4()
        patched_session.add(_make_event(uid))
        patched_session.commit()
        event = patched_session.get(AimbatEvent, uid)
        assert event is not None, "expected event to exist in database"
        short = uuid_shortener(patched_session, event, min_length=4)
        assert len(short.replace("-", "")) >= 4, (
            "result should be at least 4 characters excluding dashes"
        )

    def test_one_query_covers_a_whole_table_of_rows(
        self, patched_session: Session
    ) -> None:
        """Verifies that shortening N ids costs one query, not N.

        Regression test: the prefix lookup used to run its own
        non-sargable `LIKE` per call, so rendering a table scanned the
        table once per row (twice per seismogram row, and again per cell
        for the CLI's column formatters).
        """
        events = [_make_event(uuid.uuid4(), offset_seconds=i) for i in range(20)]
        patched_session.add_all(events)
        patched_session.commit()
        # Read the ids before recording: `commit` expired the instances, and
        # the resulting refresh is not what this test is counting.
        uids = [str(e.id) for e in events]

        statements: list[str] = []
        bind = patched_session.get_bind()

        def record(
            conn: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(bind, "before_cursor_execute", record)
        try:
            shortened = [
                uuid_shortener(patched_session, AimbatEvent, str_uuid=uid)
                for uid in uids
            ]
        finally:
            event.remove(bind, "before_cursor_execute", record)

        assert len(statements) == 1, "the id pool should be fetched once per table"
        assert len(set(shortened)) == len(uids), "prefixes should still be unique"

    def test_pool_is_refetched_for_a_row_added_later_in_the_session(
        self, patched_session: Session
    ) -> None:
        """Verifies that a row added after the pool was cached is still found.

        The cached pool would otherwise report the new id as absent from
        its own table.
        """
        first = _make_event(uuid.uuid4(), offset_seconds=0)
        patched_session.add(first)
        patched_session.commit()
        uuid_shortener(patched_session, first)

        second = _make_event(uuid.uuid4(), offset_seconds=1)
        patched_session.add(second)
        patched_session.commit()
        assert str(second.id).startswith(uuid_shortener(patched_session, second))

    def test_min_length_defaults_to_setting(
        self, patched_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies that `min_id_length` is used when `min_length` is omitted.

        Args:
            patched_session: The database session.
            monkeypatch: The pytest monkeypatch fixture.
        """
        uid = uuid.uuid4()
        event = _make_event(uid)
        patched_session.add(event)
        patched_session.commit()
        monkeypatch.setattr(aimbat.settings, "min_id_length", 7)
        short = uuid_shortener(patched_session, event)
        assert len(short.replace("-", "")) >= 7, (
            "result should honour the min_id_length setting"
        )
