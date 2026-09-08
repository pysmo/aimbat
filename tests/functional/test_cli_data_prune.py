"""Functional tests for the `aimbat data prune` CLI command.

Commands are invoked in-process via `app()` with `aimbat.db.engine`
monkeypatched to the test fixture's database.
"""

from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.io import SourceUnavailableError
from aimbat.models import AimbatDataSource, AimbatEvent, AimbatSeismogram


def _sourcenames(engine: Engine) -> list[str]:
    with Session(engine) as session:
        return list(session.exec(select(AimbatDataSource.sourcename)).all())


def _seismogram_count(engine: Engine) -> int:
    with Session(engine) as session:
        return len(session.exec(select(AimbatSeismogram)).all())


@pytest.mark.cli
class TestDataPrune:
    def test_dry_run_lists_orphans_and_keeps_them(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        before = _seismogram_count(loaded_engine)
        Path(_sourcenames(loaded_engine)[0]).unlink()

        cli("data prune all --dry-run")

        out = capsys.readouterr().out
        assert "Data sources to prune" in out
        assert _seismogram_count(loaded_engine) == before

    def test_prune_with_yes_deletes_orphan(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
    ) -> None:
        before = _seismogram_count(loaded_engine)
        gone = Path(_sourcenames(loaded_engine)[0])
        gone.unlink()

        cli("data prune all --yes --no-snapshot")

        assert _seismogram_count(loaded_engine) == before - 1
        assert gone.name not in [Path(s).name for s in _sourcenames(loaded_engine)]

    def test_prune_declined_keeps_everything(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        before = _seismogram_count(loaded_engine)
        Path(_sourcenames(loaded_engine)[0]).unlink()
        monkeypatch.setattr("rich.prompt.Confirm.ask", lambda *a, **k: False)

        cli("data prune all --no-snapshot")

        assert _seismogram_count(loaded_engine) == before

    def test_prune_nothing_to_do(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        cli("data prune all --dry-run")
        assert "No vanished data sources found." in capsys.readouterr().out

    def test_missing_parent_directory_needs_force(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        tmp_path: Path,
    ) -> None:
        with Session(loaded_engine) as session:
            datasource = session.exec(select(AimbatDataSource)).first()
            assert datasource is not None
            datasource.sourcename = str(tmp_path / "vanished" / "x.sac")
            session.add(datasource)
            session.commit()

        before = _seismogram_count(loaded_engine)
        # Debug log level is on in tests, so handle_issues re-raises instead of
        # exiting; a real terminal would see a red panel and exit 1.
        with pytest.raises((SystemExit, SourceUnavailableError)):
            cli("data prune all --yes --no-snapshot")

        cli("data prune all --yes --no-snapshot --force")
        assert _seismogram_count(loaded_engine) == before - 1

    def test_unknown_event_id_errors(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
    ) -> None:
        from uuid import uuid4

        before = _seismogram_count(loaded_engine)
        with pytest.raises((SystemExit, NoResultFound)):
            cli(f"data prune {uuid4()} --yes --no-snapshot")
        assert _seismogram_count(loaded_engine) == before

    def test_scoped_to_single_event(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
    ) -> None:
        with Session(loaded_engine) as session:
            events = session.exec(select(AimbatEvent)).all()
            target = events[0]
            other = events[1]
            target_source = Path(target.seismograms[0].datasource.sourcename)
            other_source = Path(other.seismograms[0].datasource.sourcename)
            other_event_id = other.id
        target_source.unlink()
        other_source.unlink()

        before = _seismogram_count(loaded_engine)
        cli(f"data prune {other_event_id} --yes --no-snapshot")

        # Only the other event's orphan was removed; the target event's stays.
        assert _seismogram_count(loaded_engine) == before - 1
        assert not target_source.exists()
        assert str(target_source) in _sourcenames(loaded_engine)
