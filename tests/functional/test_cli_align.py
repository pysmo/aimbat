"""Functional tests for `aimbat align`."""

import warnings
from collections.abc import Callable

import numpy as np
import pytest
from pandas import Timedelta, Timestamp
from sqlalchemy import Engine
from sqlmodel import Session, select

from pysmo.tools.iccs import ICCS, IccsResult, IccsStatus, McccResult

from aimbat.models import AimbatEvent


def _event_id(engine: Engine) -> str:
    with Session(engine) as session:
        event = session.exec(select(AimbatEvent)).first()
        assert event is not None
        return str(event.id)


def _run(cli: Callable[[str], None], command: str) -> None:
    """Run a CLI command, failing if a pysmo warning gets past the summary."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cli(command)
    assert not [w for w in caught if "refused" in str(w.message)]


def _fake_iccs_call(status: IccsStatus) -> Callable[..., IccsResult]:
    """Replace `ICCS.__call__` with one returning a fixed result and warning."""

    def call(self: ICCS, **kwargs: object) -> IccsResult:
        warnings.warn("ICCS refused the final-iteration shift", UserWarning)
        return IccsResult(
            convergence=np.zeros(2),
            status=status,
            refused=frozenset(),
            flipped=frozenset(),
            deselected=frozenset(),
            reselected=frozenset(),
            fallback=None,
        )

    return call


def _fake_run_mccc(refused: bool) -> Callable[..., McccResult]:
    """Replace `ICCS.run_mccc` with one refusing the first pick if asked."""

    def run_mccc(self: ICCS, **kwargs: object) -> McccResult:
        warnings.warn("MCCC refused the shift", UserWarning)
        indices = [i for i, s in enumerate(self.seismograms) if s.select]
        n = len(indices)
        return McccResult(
            indices=indices,
            picks=[Timestamp("2010-02-27T06:40:00", tz="UTC")] * n,
            errors=[Timedelta(seconds=0.1)] * n,
            rmse=Timedelta(seconds=0.2),
            cc_means=[0.8] * n,
            cc_stds=[0.05] * n,
            refused=frozenset(indices[:1] if refused else ()),
        )

    return run_mccc


class TestAlign:
    """Tests for the summary printed after an alignment run."""

    def test_iccs_success_goes_to_stdout(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies a converged run is reported on stdout.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """
        monkeypatch.setattr(ICCS, "__call__", _fake_iccs_call(IccsStatus.converged))
        _run(cli, f"align iccs {_event_id(loaded_engine)}")
        captured = capsys.readouterr()
        assert "ICCS converged after 2 iterations." in captured.out

    def test_iccs_nothing_applied_is_a_warning(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verifies a run that moved no picks is reported on stderr.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
        """
        monkeypatch.setattr(
            ICCS, "__call__", _fake_iccs_call(IccsStatus.nothing_applied)
        )
        _run(cli, f"align iccs {_event_id(loaded_engine)}")
        captured = capsys.readouterr()
        assert "ICCS moved no picks" in captured.err
        assert "ICCS" not in captured.out

    @pytest.mark.parametrize(
        ("refused", "stream", "message"),
        [
            (False, "out", "MCCC refined "),
            (True, "err", "1 was left unchanged"),
        ],
    )
    def test_mccc_summary(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        refused: bool,
        stream: str,
        message: str,
    ) -> None:
        """Verifies the MCCC summary, and that refusals go to stderr.

        Args:
            loaded_engine: The patched engine with multi-event data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
            monkeypatch: The pytest monkeypatch fixture.
            refused: Whether the fake run refuses a pick.
            stream: The stream the summary is expected on.
            message: Text the summary is expected to contain.
        """
        monkeypatch.setattr(ICCS, "run_mccc", _fake_run_mccc(refused))
        _run(cli, f"align mccc {_event_id(loaded_engine)}")
        captured = capsys.readouterr()
        assert message in getattr(captured, stream)
