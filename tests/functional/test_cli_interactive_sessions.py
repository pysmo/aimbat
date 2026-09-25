"""Functional tests for how long the interactive commands hold a connection.

Each command that opens a blocking matplotlib window used to do so inside
`with Session(engine) as session:`, pinning a database connection and a read
transaction for however long the user left the window open. These tests stand
in for the window and check that nothing is checked out of the pool while it
would be on screen.
"""

from collections.abc import Callable
from uuid import UUID

import pytest
from sqlalchemy import Engine, QueuePool
from sqlmodel import Session, select

import aimbat.plot
from aimbat.models import AimbatEvent, AimbatStation
from aimbat.plot import _iccs as plot_iccs


def _first_id[M: (AimbatEvent, AimbatStation)](engine: Engine, model: type[M]) -> UUID:
    """Return the ID of the first row of `model`."""
    with Session(engine) as session:
        record = session.exec(select(model)).first()
        assert record is not None
        return record.id


def _checked_out(engine: Engine) -> int:
    """Return how many connections are currently checked out of `engine`'s pool."""
    assert isinstance(engine.pool, QueuePool)
    return engine.pool.checkedout()


class TestInteractiveCommandsHoldNoConnection:
    """Tests that an open plot window pins no database connection."""

    @pytest.fixture
    def checked_out(
        self, loaded_engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> list[int]:
        """Record the pool's checked-out count from inside each blocking call.

        Args:
            loaded_engine_from_file: File-backed engine with data loaded. A file
                database is needed for a real connection pool; the in-memory
                engine's pool does not count checkouts the same way.
            monkeypatch: The pytest monkeypatch fixture.

        Returns:
            The list the stand-ins append to.
        """
        counts: list[int] = []

        def _record(*args: object, **kwargs: object) -> None:
            counts.append(_checked_out(loaded_engine_from_file))

        monkeypatch.setattr(plot_iccs, "_update_min_cc", _record)
        monkeypatch.setattr(plot_iccs, "_plot_stack", _record)
        monkeypatch.setattr(aimbat.plot, "show_figure", _record)
        return counts

    @pytest.mark.parametrize(
        "command",
        ["tool cc --event-id {event}", "plot stack --event-id {event}"],
        ids=["tool-cc", "plot-stack"],
    )
    def test_event_commands(
        self,
        command: str,
        checked_out: list[int],
        loaded_engine_from_file: Engine,
        cli: Callable[[str], None],
    ) -> None:
        """Commands that take an event open no connection while plotting.

        Args:
            command: Command template naming the event to work on.
            checked_out: Recorded pool checkouts from inside the blocking call.
            loaded_engine_from_file: File-backed engine with data loaded.
            cli: The CLI runner fixture.
        """
        event_id = _first_id(loaded_engine_from_file, AimbatEvent)
        cli(command.format(event=event_id))
        assert checked_out == [0]

    def test_station_seismograms_plot(
        self,
        checked_out: list[int],
        loaded_engine_from_file: Engine,
        cli: Callable[[str], None],
    ) -> None:
        """`station plotseis` closes its session before showing the figure.

        Args:
            checked_out: Recorded pool checkouts from inside the blocking call.
            loaded_engine_from_file: File-backed engine with data loaded.
            cli: The CLI runner fixture.
        """
        station_id = _first_id(loaded_engine_from_file, AimbatStation)
        cli(f"station plotseis {station_id}")
        assert checked_out == [0]
