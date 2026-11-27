"""Functional tests for selecting and removing phases by component in the CLI.

The data are testkit's prepared Solomon Islands event, with every pick on Z
and on T, so each phase name has a phase on both components. Resolution
itself is tested against `aimbat.core`. These tests check that
`--component`, `DEFAULT_COMPONENT` and the selectors reach it.
"""

import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from aimbat import settings
from aimbat.core import default_phase_parameters
from aimbat.models import AimbatEvent, AimbatPhase, AimbatPick, AimbatSeismogram

from testsupport.cli import error_text

type _Cli = Callable[[str | list[str]], None]


@pytest.fixture
def event_id(
    patched_engine: Engine, cli: _Cli, three_component_data: dict[str, list[Path]]
) -> str:
    """Add the prepared Solomon Islands event, and return its ID."""
    files = three_component_data["prepared/solomon_islands"]
    cli(["data", "add", "--no-progress", *map(str, files)])
    with Session(patched_engine) as session:
        (event,) = session.exec(select(AimbatEvent)).all()
        return str(event.id)


def _phases(engine: Engine) -> dict[tuple[str, str], AimbatPhase]:
    with Session(engine) as session:
        return {
            (p.name, p.component): p for p in session.exec(select(AimbatPhase)).all()
        }


def _min_cc(engine: Engine, name: str, component: str) -> float:
    with Session(engine) as session:
        phase = session.exec(
            select(AimbatPhase)
            .where(col(AimbatPhase.name) == name)
            .where(col(AimbatPhase.component) == component)
        ).one()
        return phase.parameters.min_cc


def _fails(
    cli: _Cli,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> str:
    """Run a command that fails and return its error output."""
    monkeypatch.setattr(settings, "log_level", "INFO")
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc_info:
        cli(command)
    assert exc_info.value.code == 1
    return error_text(capsys.readouterr().err)


@pytest.mark.cli
class TestComponentSelection:
    """Tests for `--component` and `DEFAULT_COMPONENT`."""

    def test_both_components_exist(self, patched_engine: Engine, event_id: str) -> None:
        assert {("S", "T"), ("S", "Z")} <= set(_phases(patched_engine))

    def test_name_on_two_components_fails(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        error = _fails(
            cli,
            capsys,
            monkeypatch,
            f"phase parameter set min_cc 0.42 --event {event_id} --phase S",
        )
        assert "S (T), S (Z)" in error
        assert "by component" in error

    def test_option_selects_the_component(
        self, patched_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        cli(
            f"phase parameter set min_cc 0.42 --event {event_id} --phase S "
            + "--component t"
        )
        assert _min_cc(patched_engine, "S", "T") == pytest.approx(0.42)
        assert _min_cc(patched_engine, "S", "Z") != pytest.approx(0.42)

    def test_environment_selects_the_component(
        self,
        patched_engine: Engine,
        cli: _Cli,
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        monkeypatch.setenv("DEFAULT_PHASE", "S")
        monkeypatch.setenv("DEFAULT_COMPONENT", "Z")
        cli(f"phase parameter set min_cc 0.42 --event {event_id}")
        assert _min_cc(patched_engine, "S", "Z") == pytest.approx(0.42)

    def test_get_reads_the_component(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        cli(
            f"phase parameter set min_cc 0.42 --event {event_id} --phase S "
            + "--component T"
        )
        capsys.readouterr()
        cli(f"phase parameter get min_cc --event {event_id} --phase S --component T")
        assert capsys.readouterr().out.strip() == "0.42"
        cli(f"phase parameter get min_cc --event {event_id} --phase S --component Z")
        assert capsys.readouterr().out.strip() != "0.42"

    def test_get_with_two_components_fails(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        error = _fails(
            cli,
            capsys,
            monkeypatch,
            f"phase parameter get min_cc --event {event_id}" + " --phase S",
        )
        assert "S (T), S (Z)" in error

    def test_empty_component_selects_the_phase_without_one(
        self, patched_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        with Session(patched_engine) as session:
            session.add(
                AimbatPhase(
                    event_id=uuid.UUID(event_id),
                    name="S",
                    parameters=default_phase_parameters("S"),
                )
            )
            session.commit()
        cli(
            ["phase", "parameter", "set", "min_cc", "0.42", "--event", event_id]
            + ["--phase", "S", "--component", ""]
        )
        assert _min_cc(patched_engine, "S", "") == pytest.approx(0.42)
        assert _min_cc(patched_engine, "S", "T") != pytest.approx(0.42)

    def test_environment_component_stays_with_its_name(
        self,
        patched_engine: Engine,
        cli: _Cli,
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        """`--phase P` does not take the component exported for S."""
        cli(f"phase remove --event {event_id} --phase P --component T --yes")
        monkeypatch.setenv("DEFAULT_PHASE", "S")
        monkeypatch.setenv("DEFAULT_COMPONENT", "T")
        cli(f"phase parameter set min_cc 0.42 --event {event_id} --phase P")
        assert _min_cc(patched_engine, "P", "Z") == pytest.approx(0.42)

    def test_rename_needs_no_component(
        self, patched_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        cli(f"phase rename SKS --event {event_id} --phase S")
        phases = set(_phases(patched_engine))
        assert {("SKS", "T"), ("SKS", "Z")} <= phases
        assert not {("S", "T"), ("S", "Z")} & phases

    def test_seismogram_parameter_on_its_component(
        self, patched_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        transverse = _phases(patched_engine)[("S", "T")]
        with Session(patched_engine) as session:
            row = session.get_one(AimbatPhase, transverse.id).seismogram_parameters[0]
            seismogram_id = row.seismogram_id
        cli(f"seismogram parameter set flip true --id {seismogram_id} --phase S")
        with Session(patched_engine) as session:
            seismogram = session.get_one(AimbatSeismogram, seismogram_id)
            flips = {
                (r.phase.name, r.phase.component): r.flip for r in seismogram.phase_rows
            }
        assert flips[("S", "T")] is True


@pytest.mark.cli
class TestPhaseRemoveAll:
    """Tests for `phase remove --event all`."""

    def test_removes_the_pair_only(
        self, patched_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        cli("phase remove --event all --phase S --component Z --yes")
        phases = _phases(patched_engine)
        assert ("S", "Z") not in phases
        assert ("S", "T") in phases

    def test_dry_run_changes_nothing(
        self,
        patched_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        before = set(_phases(patched_engine))
        capsys.readouterr()
        cli("phase remove --event all --phase S --component Z --dry-run")
        assert "Would remove phase S (Z)" in " ".join(capsys.readouterr().out.split())
        assert set(_phases(patched_engine)) == before

    def test_needs_the_component(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        error = _fails(cli, capsys, monkeypatch, "phase remove --event all --phase S")
        assert "--component" in error

    def test_no_event_has_the_pair(
        self,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        event_id: str,
    ) -> None:
        error = _fails(
            cli,
            capsys,
            monkeypatch,
            "phase remove --event all --phase S --component Q --yes",
        )
        assert "No event has a phase S (Q)" in error


@pytest.mark.cli
class TestPickRemoveSelectors:
    """Tests for `pick remove --station` and `--phase`."""

    def test_station_and_phase(
        self, patched_engine: Engine, cli: _Cli, event_id: str
    ) -> None:
        transverse = _phases(patched_engine)[("S", "T")]
        with Session(patched_engine) as session:
            row = session.get_one(AimbatPhase, transverse.id).seismogram_parameters[0]
            station_id = row.seismogram.station_id
            seismogram_id = row.seismogram_id
        cli(f"pick remove --station {station_id} --phase S")
        with Session(patched_engine) as session:
            picks = session.exec(
                select(AimbatPick).where(col(AimbatPick.seismogram_id) == seismogram_id)
            ).all()
            dismissed = {p.phase_name: p.dismissed for p in picks}
            others = session.exec(
                select(AimbatPick)
                .where(col(AimbatPick.seismogram_id) != seismogram_id)
                .where(col(AimbatPick.phase_name) == "S")
            ).all()
        assert dismissed["S"] is True
        assert all(not v for k, v in dismissed.items() if k != "S")
        assert others and not any(p.dismissed for p in others)
