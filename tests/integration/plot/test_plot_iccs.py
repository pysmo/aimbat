"""Integration tests for aimbat.plot._iccs."""

from typing import Any

import pytest
from pydantic import ValidationError
from sqlmodel import Session, select

import aimbat.plot._iccs as plot_iccs
from aimbat.core import _iccs as core_iccs
from aimbat.core import clear_iccs_cache, create_iccs_instance
from aimbat.models import AimbatEvent
from aimbat.plot import update_min_cc


class TestRejectedWriteEvictsCachedIccs:
    """Tests that a refused parameter write does not leave a diverged cache."""

    def test_cached_iccs_is_evicted_when_the_write_is_rejected(
        self, loaded_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies a rejected `min_cc` write drops the cached ICCS instance.

        `min_cc` is unbounded on the pysmo instance but constrained to
        `0 <= min_cc <= 1` in the database, so the widget can leave a value
        on the shared instance that the write then refuses. Nothing else
        marks that instance stale, so it must not survive in the cache.

        Args:
            loaded_session: The database session.
            monkeypatch: The pytest monkeypatch fixture.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None

        clear_iccs_cache()
        iccs = create_iccs_instance(loaded_session, event).iccs
        assert event.id in core_iccs._iccs_cache

        # Stands in for the interactive widget: it mutates the instance in
        # place, which is what leaves the cache diverged once the write fails.
        def _reject(iccs_arg: Any, *args: object, **kwargs: object) -> None:
            iccs_arg.min_cc = 1.5

        monkeypatch.setattr(plot_iccs, "_update_min_cc", _reject)

        with pytest.raises(ValidationError):
            update_min_cc(
                event.id,
                iccs,
                context=False,
                all_seismograms=False,
                causal=False,
                return_fig=False,
            )

        assert event.id not in core_iccs._iccs_cache
