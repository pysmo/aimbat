"""Functional tests for selecting a phase in the CLI and for the `phase` group.

All commands are invoked in-process via `app()` with `aimbat.db.engine`
monkeypatched to the test fixture's in-memory database. Behaviour is tested
against `aimbat.actions` and `aimbat.core`. These tests check that `--phase`
and `DEFAULT_PHASE` reach them and that the results are shown.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from pandas import Timedelta
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from aimbat import settings
from aimbat.core import promote_picks, store_picks
from aimbat.io import DataType, SourcePick
from aimbat.models import AimbatEvent, AimbatPhase, AimbatPick, AimbatSnapshot

type _Cli = Callable[[str | list[str]], None]
type _CliJson = Callable[[str], list[Any] | dict[str, Any]]


@pytest.fixture
def two_phases(loaded_engine: Engine, event_id: str) -> str:
    """Add a PKP phase on all but one seismogram of the first event.

    Returns:
        The ID of the event.
    """
    with Session(loaded_engine) as session:
        event = session.get_one(AimbatEvent, uuid.UUID(event_id))
        seismograms = sorted(event.seismograms, key=lambda s: str(s.id))[1:]
        picks = []
        for seismogram in seismograms:
            picks += store_picks(
                session,
                [
                    SourcePick(
                        seismogram.phase_rows[0].initial_pick + Timedelta(seconds=1),
                        "t9",
                        label="PKP",
                    )
                ],
                source_name=f"PKP-{seismogram.id}",
                source_type=DataType.SAC,
                source_seismogram=seismogram,
            ).stored
        promote_picks(session, picks)
        session.commit()
    return event_id


def _min_cc(engine: Engine, event_id: str, name: str) -> float:
    with Session(engine) as session:
        phase = session.exec(
            select(AimbatPhase)
            .where(col(AimbatPhase.event_id) == uuid.UUID(event_id))
            .where(col(AimbatPhase.name) == name)
        ).one()
        return phase.parameters.min_cc


def _fails(
    cli: _Cli,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> str:
    """Run a command that fails and return its error output."""
    # At INFO, handle_issues prints the panel and exits instead of raising.
    monkeypatch.setattr(settings, "log_level", "INFO")
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc_info:
        cli(command)
    assert exc_info.value.code == 1
    return " ".join(capsys.readouterr().err.split())


@pytest.mark.cli
class TestPhaseSelection:
    """Tests for `--phase`, `DEFAULT_PHASE` and the single-phase fallback."""

    def test_only_phase_needs_no_name(
        self, loaded_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        cli(f"phase parameter set min_cc 0.42 --event-id {event_id}")
        assert _min_cc(loaded_engine, event_id, "P") == pytest.approx(0.42)

    def test_several_phases_need_a_name(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        two_phases: str,
    ) -> None:
        error = _fails(
            cli,
            capsys,
            monkeypatch,
            f"phase parameter set min_cc 0.42 --event-id {two_phases}",
        )
        assert "has phases P, PKP" in error

    def test_option_selects_the_phase(
        self, loaded_engine: Engine, cli: _Cli, two_phases: str
    ) -> None:
        cli(f"phase parameter set min_cc 0.42 --event-id {two_phases} --phase PKP")
        assert _min_cc(loaded_engine, two_phases, "PKP") == pytest.approx(0.42)
        assert _min_cc(loaded_engine, two_phases, "P") != pytest.approx(0.42)

    def test_environment_selects_the_phase(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        monkeypatch: pytest.MonkeyPatch,
        two_phases: str,
    ) -> None:
        monkeypatch.setenv("DEFAULT_PHASE", "PKP")
        cli(f"phase parameter set min_cc 0.42 --event-id {two_phases}")
        assert _min_cc(loaded_engine, two_phases, "PKP") == pytest.approx(0.42)

    def test_unknown_name_lists_the_phases(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        two_phases: str,
    ) -> None:
        error = _fails(
            cli, capsys, monkeypatch, f"align iccs --event-id {two_phases} --phase S"
        )
        assert "Its phases: P, PKP" in error

    def test_snapshot_of_the_named_phase(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        two_phases: str,
    ) -> None:
        cli(f"snapshot create --event-id {two_phases} --phase PKP")
        with Session(loaded_engine) as session:
            (snapshot,) = session.exec(select(AimbatSnapshot)).all()
            assert snapshot.phase.name == "PKP"
        capsys.readouterr()
        cli(f"snapshot list --event-id {two_phases} --phase P")
        assert "PKP" not in capsys.readouterr().out
        cli(f"snapshot list --event-id {two_phases}")
        assert "PKP" in capsys.readouterr().out

    def test_seismogram_parameter_of_the_named_phase(
        self, loaded_engine: Engine, cli: _Cli, two_phases: str
    ) -> None:
        with Session(loaded_engine) as session:
            pkp = session.exec(
                select(AimbatPhase).where(col(AimbatPhase.name) == "PKP")
            ).one()
            row = pkp.seismogram_parameters[0]
            seismogram_id = row.seismogram_id
        cli(f"seismogram parameter set flip true --id {seismogram_id} --phase PKP")
        with Session(loaded_engine) as session:
            rows = session.get_one(AimbatEvent, uuid.UUID(two_phases)).seismograms
            flips = {
                r.phase.name: r.flip
                for s in rows
                if s.id == seismogram_id
                for r in s.phase_rows
            }
        assert flips == {"P": False, "PKP": True}


@pytest.mark.cli
class TestPhaseCommands:
    """Tests for `phase list`, `dump`, `completed`, `rename` and `quality`."""

    def test_list(
        self, cli: _Cli, capsys: pytest.CaptureFixture[str], two_phases: str
    ) -> None:
        capsys.readouterr()
        cli(f"phase list --event-id {two_phases}")
        output = capsys.readouterr().out
        assert "PKP" in output
        cli("phase list --event-id all --phase PKP")
        output = capsys.readouterr().out
        assert "PKP" in output
        assert " P " not in output

    def test_list_ignores_default_phase(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        two_phases: str,
    ) -> None:
        monkeypatch.setenv("DEFAULT_PHASE", "P")
        capsys.readouterr()
        cli(f"phase list --event-id {two_phases}")
        assert "PKP" in capsys.readouterr().out

    def test_dump(self, cli_json: _CliJson, two_phases: str) -> None:
        dump = cli_json("phase dump")
        assert isinstance(dump, list)
        assert {p["name"] for p in dump if p["event_id"] == two_phases} == {
            "P",
            "PKP",
        }

    def test_completed(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        two_phases: str,
    ) -> None:
        capsys.readouterr()
        cli(f"phase completed --event-id {two_phases} --phase PKP")
        assert "marked as completed" in capsys.readouterr().out
        with Session(loaded_engine) as session:
            completed = {
                p.name: p.parameters.completed
                for p in session.get_one(AimbatEvent, uuid.UUID(two_phases)).phases
            }
        assert completed == {"P": False, "PKP": True}

    def test_rename(self, loaded_engine: Engine, cli: _Cli, two_phases: str) -> None:
        cli(f"phase rename PKPdf --event-id {two_phases} --phase PKP")
        with Session(loaded_engine) as session:
            event = session.get_one(AimbatEvent, uuid.UUID(two_phases))
            assert sorted(p.name for p in event.phases) == ["P", "PKPdf"]
            names = {
                pick.phase_name
                for pick in session.exec(select(AimbatPick)).all()
                if pick.label == "PKP"
            }
        assert names == {"PKPdf"}

    def test_remove(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        two_phases: str,
    ) -> None:
        capsys.readouterr()
        cli(f"phase remove --event-id {two_phases} --phase PKP --yes")
        output = " ".join(capsys.readouterr().out.split())
        assert "Removed phase PKP" in output
        with Session(loaded_engine) as session:
            event = session.get_one(AimbatEvent, uuid.UUID(two_phases))
            rows = len(event.seismograms) - 1
            assert [p.name for p in event.phases] == ["P"]
        assert f"{rows} initial pick(s)" in output
        assert f"{rows} pick(s) dismissed" in output

    def test_quality_list(
        self, cli: _Cli, capsys: pytest.CaptureFixture[str], two_phases: str
    ) -> None:
        capsys.readouterr()
        cli(f"phase quality list --event-id {two_phases}")
        assert "PKP" in capsys.readouterr().out

    def test_quality_dump(self, cli_json: _CliJson, two_phases: str) -> None:
        dump = cli_json("phase quality dump")
        assert isinstance(dump, list)
        assert {"P", "PKP"} <= {row["phase_name"] for row in dump}


@pytest.mark.cli
class TestListings:
    """Tests for the phase columns of other listings."""

    def test_event_list_names_the_phases(
        self, cli: _Cli, capsys: pytest.CaptureFixture[str], two_phases: str
    ) -> None:
        capsys.readouterr()
        cli("event list")
        assert "P, PKP" in capsys.readouterr().out

    def test_seismogram_list_of_a_phase(
        self, cli: _Cli, capsys: pytest.CaptureFixture[str], two_phases: str
    ) -> None:
        capsys.readouterr()
        cli(f"seismogram list --event-id {two_phases} --phase PKP --raw")
        assert "True" in capsys.readouterr().out

    def test_seismogram_parameter_list_names_the_phase(
        self, cli: _Cli, capsys: pytest.CaptureFixture[str], two_phases: str
    ) -> None:
        capsys.readouterr()
        cli(f"seismogram parameter list --event-id {two_phases} --phase PKP")
        output = capsys.readouterr().out
        assert "PKP" in output
