"""Functional tests for `aimbat utils lookup`."""

import re
from collections.abc import Callable

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from aimbat.core import create_snapshot
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatSnapshot, AimbatStation

_ROW = re.compile(r"\W*(Event|Station|Seismogram|Snapshot)\s")


def _lookup(
    cli: Callable[[str], None], capsys: pytest.CaptureFixture[str], id: str
) -> list[str]:
    """Run the lookup and return the table's body rows."""
    capsys.readouterr()
    cli(f"utils lookup {id}")
    # Match rows by their first cell: box characters differ by platform.
    return [line for line in capsys.readouterr().out.splitlines() if _ROW.match(line)]


class TestLookup:
    """Tests for which records a lookup finds and how they are described."""

    def test_event(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies an event ID is shown as an event with its time.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            (row,) = _lookup(cli, capsys, str(event.id))
            assert "Event" in row
            assert f"{event.time:%Y-%m-%d %H:%M:%S}" in row

    def test_station(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a station ID is shown as `NET.STA`.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        with Session(loaded_engine) as session:
            station = session.exec(select(AimbatStation)).first()
            assert station is not None
            (row,) = _lookup(cli, capsys, str(station.id))
            assert "Station" in row
            assert f"{station.network}.{station.name}" in row

    def test_seismogram(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a seismogram ID is shown with its station and event time.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        with Session(loaded_engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            station, event = seismogram.station, seismogram.event
            (row,) = _lookup(cli, capsys, str(seismogram.id))
            assert "Seismogram" in row
            assert f"{station.network}.{station.name}" in row
            assert f"{event.time:%Y-%m-%d %H:%M:%S}" in row

    def test_snapshot(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a snapshot ID is shown with its comment.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            create_snapshot(session, event.phases[0].id, comment="before ICCS")
            snapshot = session.exec(select(AimbatSnapshot)).one()
            (row,) = _lookup(cli, capsys, str(snapshot.id))
            assert "Snapshot" in row
            assert "before ICCS" in row

    def test_prefix_without_dashes(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a prefix spanning a dash matches with the dash left out.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        with Session(loaded_engine) as session:
            station = session.exec(select(AimbatStation)).first()
            assert station is not None
            prefix = str(station.id).replace("-", "")[:12]
            rows = _lookup(cli, capsys, prefix)
            assert any(f"{station.network}.{station.name}" in row for row in rows)

    def test_prefix_matching_several_kinds(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a short prefix lists matches of every kind.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        with Session(loaded_engine) as session:
            stations = {str(s.id)[0] for s in session.exec(select(AimbatStation))}
            seismograms = {str(s.id)[0] for s in session.exec(select(AimbatSeismogram))}
        shared = sorted(stations & seismograms)
        assert shared, "no first character shared by a station and a seismogram"
        rows = _lookup(cli, capsys, shared[0])
        assert any("Station" in row for row in rows)
        assert any("Seismogram" in row for row in rows)

    def test_brackets_in_comment_shown_literally(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies a snapshot comment is not parsed as Rich markup.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        comment = "before [/red] ICCS [pre]"
        with Session(loaded_engine) as session:
            event = session.exec(select(AimbatEvent)).first()
            assert event is not None
            create_snapshot(session, event.phases[0].id, comment=comment)
            snapshot = session.exec(select(AimbatSnapshot)).one()
            (row,) = _lookup(cli, capsys, str(snapshot.id))
            assert comment in row

    @pytest.mark.parametrize("id", ["", "--"])
    def test_empty_prefix(
        self,
        loaded_engine: Engine,
        cli: Callable[[list[str]], None],
        id: str,
    ) -> None:
        """Verifies a prefix without any ID characters is an error.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            id: A prefix with no ID characters.
        """
        with pytest.raises(ValueError, match="at least the first character"):
            cli(["utils", "lookup", "--", id])

    def test_no_match(self, loaded_engine: Engine, cli: Callable[[str], None]) -> None:
        """Verifies an ID matching nothing is an error.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
        """
        with pytest.raises(ValueError, match="has ID zz"):
            cli("utils lookup zz")
