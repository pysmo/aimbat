"""Functional tests for CLI commands that read and write phase and seismogram parameters.

All commands are invoked in-process via `app()` with `aimbat.db.engine`
monkeypatched to the test fixture's in-memory database. The `dump`
sub-commands are used as the source of truth for verifying parameter changes.
The rules for changing parameters are tested against `aimbat.actions` and
`aimbat.core`. These tests check how values are parsed and shown.
"""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from aimbat.core import resolve_phase

type _Cli = Callable[[str | list[str]], None]
type _CliJson = Callable[[str], list[Any] | dict[str, Any]]

_PHASE_PARAMETERS = (
    "completed",
    "min_cc",
    "window_pre",
    "window_post",
    "bandpass_apply",
    "bandpass_fmin",
    "bandpass_fmax",
)


def _phase_parameters(
    engine: Engine, cli_json: _CliJson, event_id: str
) -> dict[str, Any]:
    with Session(engine) as session:
        phase_id = str(resolve_phase(session, uuid.UUID(event_id)).id)
    dump = cli_json("phase parameter dump")
    assert isinstance(dump, list)
    return next(p for p in dump if p["phase_id"] == phase_id)


def _seismogram_parameters(cli_json: _CliJson, seismogram_id: str) -> dict[str, Any]:
    dump = cli_json("seismogram parameter dump")
    assert isinstance(dump, list)
    return next(p for p in dump if p["seismogram_id"] == seismogram_id)


def _first_seismogram_id(cli_json: _CliJson) -> str:
    seismograms = cli_json("seismogram dump")
    assert isinstance(seismograms, list) and seismograms
    return seismograms[0]["id"]


@pytest.mark.cli
class TestPhaseParameters:
    """Tests for `phase parameter get`, `set`, `dump` and `list`."""

    def test_get_bool(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that a bool parameter is printed as `True` or `False`."""
        cli(f"phase parameter get --event-id {event_id} completed")
        assert capsys.readouterr().out.strip() == "False"

    def test_get_float(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that a float parameter is printed as a number."""
        cli(f"phase parameter get --event-id {event_id} min_cc")
        assert float(capsys.readouterr().out.strip()) >= 0.0

    def test_get_timedelta(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
    ) -> None:
        """Verifies that a timedelta parameter is printed in seconds."""
        cli(f"phase parameter get --event-id {event_id} window_pre")
        assert float(capsys.readouterr().out.strip()) <= 0.0

    @pytest.mark.parametrize(
        ("name", "value", "expected"),
        [
            ("completed", "true", True),
            ("bandpass_apply", "false", False),
            ("min_cc", "0.42", 0.42),
            ("window_pre", "-20", -20.0),
            ("window_post", "20s", 20.0),
        ],
        ids=["bool-true", "bool-false", "float", "timedelta-bare", "timedelta-unit"],
    )
    def test_set(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        cli_json: _CliJson,
        event_id: str,
        name: str,
        value: str,
        expected: object,
    ) -> None:
        """Verifies that a value given on the command line is parsed and stored."""
        cli(f"phase parameter set --event-id {event_id} {name} {value}")

        assert _phase_parameters(loaded_engine, cli_json, event_id)[
            name
        ] == pytest.approx(expected)

    def test_dump(self, loaded_engine: Engine, cli_json: _CliJson) -> None:
        """Verifies that the dump has every parameter for every phase."""
        dump = cli_json("phase parameter dump")
        phases = cli_json("phase dump")
        assert isinstance(dump, list)
        assert len(dump) == len(phases) > 1
        for entry in dump:
            assert set(_PHASE_PARAMETERS) | {"phase_id", "phase_name"} <= entry.keys()

    @pytest.mark.parametrize("flags", ["", "--raw"])
    def test_list(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
        flags: str,
    ) -> None:
        """Verifies that the list command prints a table for one event."""
        cli(f"phase parameter list {flags} --event-id {event_id}")
        assert capsys.readouterr().out

    def test_list_all_events(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that `--event-id all` prints a table for every event."""
        cli("phase parameter list --event-id all")
        assert capsys.readouterr().out


@pytest.mark.cli
class TestSeismogramParameters:
    """Tests for `seismogram parameter get`, `set`, `dump` and `list`."""

    @pytest.mark.parametrize(
        ("name", "default"), [("select", "True"), ("flip", "False")]
    )
    @pytest.mark.parametrize("short", [False, True], ids=["full-id", "short-id"])
    def test_get(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        cli_json: _CliJson,
        capsys: pytest.CaptureFixture[str],
        name: str,
        default: str,
        short: bool,
    ) -> None:
        """Verifies that a parameter is read by full or shortened ID."""
        seismogram_id = _first_seismogram_id(cli_json)
        capsys.readouterr()

        cli(
            f"seismogram parameter get {name} "
            f"--id {seismogram_id[:8] if short else seismogram_id}"
        )

        assert capsys.readouterr().out.strip() == default

    @pytest.mark.parametrize(
        ("name", "value", "expected"),
        [("select", "false", False), ("flip", "true", True)],
    )
    @pytest.mark.parametrize("short", [False, True], ids=["full-id", "short-id"])
    def test_set(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        cli_json: _CliJson,
        name: str,
        value: str,
        expected: bool,
        short: bool,
    ) -> None:
        """Verifies that a parameter is set by full or shortened ID."""
        seismogram_id = _first_seismogram_id(cli_json)

        cli(
            f"seismogram parameter set {name} {value} "
            f"--id {seismogram_id[:8] if short else seismogram_id}"
        )

        assert _seismogram_parameters(cli_json, seismogram_id)[name] is expected

    def test_dump(self, loaded_engine: Engine, cli_json: _CliJson) -> None:
        """Verifies that the dump has one entry per seismogram."""
        dump = cli_json("seismogram parameter dump")
        seismograms = cli_json("seismogram dump")
        assert isinstance(dump, list)
        assert len(dump) == len(seismograms) > 0
        for entry in dump:
            assert {"select", "flip", "refined_pick", "seismogram_id"} <= entry.keys()

    @pytest.mark.parametrize("flags", ["", "--raw"])
    def test_list(
        self,
        loaded_engine: Engine,
        cli: _Cli,
        capsys: pytest.CaptureFixture[str],
        event_id: str,
        flags: str,
    ) -> None:
        """Verifies that the list command prints a table."""
        cli(f"seismogram parameter list {flags} --event-id {event_id}")
        assert capsys.readouterr().out
