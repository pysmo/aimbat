"""Integration tests for aimbat.plot._iccs."""

from typing import Any

import pytest
from pandas import Timedelta
from sqlmodel import Session, select

import aimbat.plot._iccs as plot_iccs
from aimbat.core import clear_iccs_cache, create_iccs_instance
from aimbat.models import AimbatEvent
from aimbat.plot import update_min_cc, update_pick
from aimbat.types import PhaseParameter


class TestUpdateReturnsChanges:
    """Tests that the `update_*` tools return the new values and store nothing."""

    def test_min_cc_is_returned_not_stored(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The new threshold is returned and the stored parameter is unchanged.

        Args:
            loaded_session: The database session.
            monkeypatch: The pytest monkeypatch fixture.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        before = event.phases[0].parameters.min_cc
        clear_iccs_cache()
        iccs = create_iccs_instance(loaded_session, event.phases[0].id).iccs

        # Stands in for the interactive widget, which mutates the instance.
        def _set(iccs_arg: Any, *args: object, **kwargs: object) -> None:
            iccs_arg.min_cc = 0.25

        monkeypatch.setattr(plot_iccs, "_update_min_cc", _set)

        changes = update_min_cc(
            iccs, context=False, all_seismograms=False, causal=False, return_fig=False
        )

        assert changes == {PhaseParameter.MIN_CC: 0.25}
        loaded_session.expire_all()
        assert event.phases[0].parameters.min_cc == before

    def test_picks_are_keyed_by_seismogram_id(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each seismogram's new pick is returned under its ID.

        Args:
            loaded_session: The database session.
            monkeypatch: The pytest monkeypatch fixture.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        clear_iccs_cache()
        iccs = create_iccs_instance(loaded_session, event.phases[0].id).iccs
        shift = Timedelta(seconds=1)

        def _shift(iccs_arg: Any, *args: object, **kwargs: object) -> None:
            for seis in iccs_arg.seismograms:
                seis.refined_pick = seis.initial_pick + shift

        monkeypatch.setattr(plot_iccs, "_update_pick", _shift)

        picks = update_pick(
            iccs,
            context=False,
            all_seismograms=False,
            use_matrix_image=False,
            causal=False,
            return_fig=False,
        )

        assert picks == {
            seis.id: seis.phase_rows[0].initial_pick + shift
            for seis in event.seismograms
        }
