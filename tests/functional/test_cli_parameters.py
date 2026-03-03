"""Functional tests for CLI commands that read and write event and seismogram parameters.

All commands are invoked in-process via ``app()`` with ``aimbat.db.engine``
monkeypatched to the test fixture's in-memory database.  The ``dump``
sub-commands are used as the source of truth for verifying parameter changes.
"""

import pytest
from collections.abc import Callable
from sqlalchemy import Engine

# ===================================================================
# Event parameter — get
# ===================================================================


@pytest.mark.cli
class TestEventParameterGet:
    """Tests for ``event parameter get``."""

    def test_get_bool_parameter(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that getting a bool parameter prints its current value.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("event parameter get completed")
        assert "False" in capsys.readouterr().out, "'completed' should default to False"

    def test_get_float_parameter(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that getting a float parameter prints a numeric value.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("event parameter get min_ccnorm")
        output = capsys.readouterr().out.strip()
        assert output, "Expected a non-empty output for min_ccnorm"
        assert float(output) >= 0.0, "min_ccnorm should be a non-negative float"

    def test_get_timedelta_parameter(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that getting a timedelta parameter prints a value ending in 's'.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("event parameter get window_pre")
        output = capsys.readouterr().out.strip()
        assert output.endswith(
            "s"
        ), f"window_pre should be printed in seconds (got '{output}')"

    def test_get_bandpass_bool_parameter(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that getting bandpass_apply prints a bool value.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("event parameter get bandpass_apply")
        output = capsys.readouterr().out.strip()
        assert output in (
            "True",
            "False",
        ), f"bandpass_apply should be True or False, got '{output}'"


# ===================================================================
# Event parameter — set + verify via dump
# ===================================================================


@pytest.mark.cli
class TestEventParameterSetBool:
    """Tests for setting boolean event parameters and verifying via dump."""

    def test_set_completed_true(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting completed=true is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        before = cli_json("event parameter dump")
        assert isinstance(before, dict), "Dump should return a dict for active event"
        assert before["completed"] is False, "'completed' should default to False"

        cli("event parameter set completed true")

        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert after["completed"] is True, "'completed' should be True after being set"

    def test_set_completed_false(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting completed=false is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set completed true")
        cli("event parameter set completed false")
        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert (
            after["completed"] is False
        ), "'completed' should be False after being set back"

    def test_set_bandpass_apply(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting bandpass_apply is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        before = cli_json("event parameter dump")
        assert isinstance(before, dict), "Dump should return a dict for active event"
        original = before["bandpass_apply"]

        cli(f"event parameter set bandpass_apply {not original}".lower())

        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert (
            after["bandpass_apply"] is not original
        ), "'bandpass_apply' should have toggled after set"


@pytest.mark.cli
class TestEventParameterSetFloat:
    """Tests for setting float event parameters and verifying via dump."""

    def test_set_min_ccnorm(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting min_ccnorm is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set min_ccnorm 0.42")
        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert after["min_ccnorm"] == pytest.approx(
            0.42
        ), "'min_ccnorm' should be 0.42 after being set"

    def test_set_bandpass_fmin(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting bandpass_fmin is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set bandpass_fmin 0.1")
        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert after["bandpass_fmin"] == pytest.approx(
            0.1
        ), "'bandpass_fmin' should be 0.1 after being set"

    def test_set_bandpass_fmax(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting bandpass_fmax is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set bandpass_fmax 2.0")
        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert after["bandpass_fmax"] == pytest.approx(
            2.0
        ), "'bandpass_fmax' should be 2.0 after being set"


# ===================================================================
# Event parameter — set timedelta
# ===================================================================


@pytest.mark.cli
class TestEventParameterSetTimedelta:
    """Tests for setting timedelta event parameters and verifying via dump."""

    def test_set_window_pre_as_bare_number(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a bare number is interpreted as seconds for window_pre.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set window_pre -20")
        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert after["window_pre"] == pytest.approx(
            -20.0
        ), "'window_pre' should be -20.0 seconds after being set with a bare number"

    def test_set_window_post_as_bare_number(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a bare number is interpreted as seconds for window_post.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set window_post 30")
        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert after["window_post"] == pytest.approx(
            30.0
        ), "'window_post' should be 30.0 seconds after being set with a bare number"

    def test_set_window_pre_with_unit_string(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a pandas-style unit string (e.g. '10s') is accepted for window_post.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set window_post 20s")
        after = cli_json("event parameter dump")
        assert isinstance(after, dict), "Dump should return a dict for active event"
        assert after["window_post"] == pytest.approx(
            20.0
        ), "'window_post' should be 20.0 seconds after being set with '20s'"


# ===================================================================
# Event parameter — dump
# ===================================================================


@pytest.mark.cli
class TestEventParameterDump:
    """Tests for ``event parameter dump``."""

    def test_active_event_returns_dict(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that the active-event dump returns a dict.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        data = cli_json("event parameter dump")
        assert isinstance(data, dict), "Active-event dump should be a dict"

    def test_active_event_contains_all_parameter_keys(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that all expected parameter keys are present in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        data = cli_json("event parameter dump")
        assert isinstance(data, dict), "Active-event dump should be a dict"
        for key in (
            "completed",
            "min_ccnorm",
            "window_pre",
            "window_post",
            "bandpass_apply",
            "bandpass_fmin",
            "bandpass_fmax",
        ):
            assert key in data, f"Expected key '{key}' in event parameter dump"

    def test_all_events_returns_list(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that ``--all`` returns a list of parameter dicts.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        data = cli_json("event parameter dump --all")
        assert isinstance(data, list), "All-events dump should be a list"
        assert len(data) > 1, "Expected parameters for more than one event"

    def test_all_events_entries_contain_parameter_keys(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that each entry in the all-events dump has the expected keys.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        data = cli_json("event parameter dump --all")
        assert isinstance(data, list), "All-events dump should be a list"
        for entry in data:
            assert "completed" in entry, "Each entry should have 'completed' key"
            assert "min_ccnorm" in entry, "Each entry should have 'min_ccnorm' key"

    def test_set_visible_in_all_events_dump(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that a parameter change to the active event appears in the all-events dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        cli("event parameter set completed true")
        all_data = cli_json("event parameter dump --all")
        assert isinstance(all_data, list), "All-events dump should be a list"
        active_entries = [e for e in all_data if e.get("completed") is True]
        assert (
            len(active_entries) == 1
        ), "Exactly one event should have completed=True after setting it"


# ===================================================================
# Event parameter — list
# ===================================================================


@pytest.mark.cli
class TestEventParameterList:
    """Tests for ``event parameter list``."""

    def test_list_produces_output(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that the list command produces output.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("event parameter list")
        assert (
            len(capsys.readouterr().out) > 0
        ), "Expected output from event parameter list"

    def test_list_short_produces_output(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that ``--short`` produces output.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("event parameter list --short")
        assert (
            len(capsys.readouterr().out) > 0
        ), "Expected output from event parameter list --short"

    def test_list_all_events_produces_output(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that ``--all`` produces output covering all events.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("event parameter list --all")
        assert (
            len(capsys.readouterr().out) > 0
        ), "Expected output from event parameter list --all"


# ===================================================================
# Seismogram parameter — get
# ===================================================================


@pytest.mark.cli
class TestSeismogramParameterGet:
    """Tests for ``seismogram parameter get``."""

    def test_get_select_with_full_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that 'select' can be retrieved using the full seismogram ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        seis = cli_json("seismogram dump")
        assert (
            isinstance(seis, list) and len(seis) > 0
        ), "Expected at least one seismogram in the dump"
        target_id = seis[0]["id"]

        cli(f"seismogram parameter get {target_id} select")
        output = capsys.readouterr().out.strip()
        assert output in (
            "True",
            "False",
        ), f"'select' should be True or False, got '{output}'"

    def test_get_select_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that 'select' can be retrieved using a shortened seismogram ID.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        seis = cli_json("seismogram dump")
        assert (
            isinstance(seis, list) and len(seis) > 0
        ), "Expected at least one seismogram in the dump"
        short_id = seis[0]["id"][:8]

        cli(f"seismogram parameter get {short_id} select")
        output = capsys.readouterr().out.strip()
        assert output in (
            "True",
            "False",
        ), f"'select' should be True or False, got '{output}'"

    def test_get_flip_default_is_false(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that 'flip' defaults to False.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        seis = cli_json("seismogram dump")
        target_id = seis[0]["id"]

        cli(f"seismogram parameter get {target_id} flip")
        assert "False" in capsys.readouterr().out, "'flip' should default to False"

    def test_get_select_default_is_true(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that 'select' defaults to True.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
            capsys: The pytest capsys fixture.
        """
        seis = cli_json("seismogram dump")
        target_id = seis[0]["id"]

        cli(f"seismogram parameter get {target_id} select")
        assert "True" in capsys.readouterr().out, "'select' should default to True"


# ===================================================================
# Seismogram parameter — set + verify via dump
# ===================================================================


@pytest.mark.cli
class TestSeismogramParameterSet:
    """Tests for setting seismogram parameters and verifying via dump."""

    def test_set_select_false_with_full_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting select=false is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        seis = cli_json("seismogram dump")
        assert (
            isinstance(seis, list) and len(seis) > 0
        ), "Expected at least one seismogram in the dump"
        target_id = seis[0]["id"]

        cli(f"seismogram parameter set {target_id} select false")

        params = cli_json("seismogram parameter dump")
        assert isinstance(params, list), "Seismogram parameter dump should be a list"
        target_params = next(p for p in params if p["seismogram_id"] == target_id)
        assert (
            target_params["select"] is False
        ), f"'select' should be False for seismogram {target_id} after being set"

    def test_set_select_false_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting select=false via a shortened ID is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        seis = cli_json("seismogram dump")
        target_id = seis[0]["id"]
        short_id = target_id[:8]

        cli(f"seismogram parameter set {short_id} select false")

        params = cli_json("seismogram parameter dump")
        assert isinstance(params, list), "Seismogram parameter dump should be a list"
        target_params = next(p for p in params if p["seismogram_id"] == target_id)
        assert (
            target_params["select"] is False
        ), f"'select' should be False for seismogram {target_id} after being set via short ID"

    def test_set_flip_true_with_full_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting flip=true is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        seis = cli_json("seismogram dump")
        target_id = seis[0]["id"]

        cli(f"seismogram parameter set {target_id} flip true")

        params = cli_json("seismogram parameter dump")
        assert isinstance(params, list), "Seismogram parameter dump should be a list"
        target_params = next(p for p in params if p["seismogram_id"] == target_id)
        assert (
            target_params["flip"] is True
        ), f"'flip' should be True for seismogram {target_id} after being set"

    def test_set_flip_true_with_short_id(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that setting flip=true via a shortened ID is reflected in the dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        seis = cli_json("seismogram dump")
        target_id = seis[0]["id"]
        short_id = target_id[:8]

        cli(f"seismogram parameter set {short_id} flip true")

        params = cli_json("seismogram parameter dump")
        assert isinstance(params, list), "Seismogram parameter dump should be a list"
        target_params = next(p for p in params if p["seismogram_id"] == target_id)
        assert (
            target_params["flip"] is True
        ), f"'flip' should be True for seismogram {target_id} after being set via short ID"

    def test_set_does_not_affect_other_seismograms(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that changing one seismogram's parameter does not affect others.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            cli_json: The in-process CLI JSON dump callable.
        """
        params_before = cli_json("seismogram parameter dump")
        assert isinstance(
            params_before, list
        ), "Seismogram parameter dump should be a list"
        assert (
            len(params_before) > 1
        ), "Need at least two seismograms in the active event for this test"
        target_id = params_before[0]["seismogram_id"]
        other_id = params_before[1]["seismogram_id"]
        other_select_before = params_before[1]["select"]

        cli(f"seismogram parameter set {target_id} select false")

        params_after = cli_json("seismogram parameter dump")
        assert isinstance(
            params_after, list
        ), "Seismogram parameter dump should be a list"
        other_select_after = next(
            p["select"] for p in params_after if p["seismogram_id"] == other_id
        )
        assert (
            other_select_after == other_select_before
        ), "Changing one seismogram's 'select' should not affect another's"


# ===================================================================
# Seismogram parameter — dump
# ===================================================================


@pytest.mark.cli
class TestSeismogramParameterDump:
    """Tests for ``seismogram parameter dump``."""

    def test_returns_list(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that the dump returns a list of parameter dicts.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        data = cli_json("seismogram parameter dump")
        assert isinstance(data, list), "Seismogram parameter dump should be a list"
        assert len(data) > 0, "Expected at least one entry in the parameter dump"

    def test_entries_contain_expected_keys(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that each entry contains the expected parameter keys.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        data = cli_json("seismogram parameter dump")
        assert isinstance(data, list), "Seismogram parameter dump should be a list"
        for entry in data:
            for key in ("select", "flip", "t1", "seismogram_id"):
                assert (
                    key in entry
                ), f"Expected key '{key}' in seismogram parameter dump entry"

    def test_all_events_returns_more_entries(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that ``--all`` returns at least as many entries as the active-event dump.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        active_data = cli_json("seismogram parameter dump")
        all_data = cli_json("seismogram parameter dump --all")
        assert isinstance(
            active_data, list
        ), "Active-event seismogram parameter dump should be a list"
        assert isinstance(
            all_data, list
        ), "All-events seismogram parameter dump should be a list"
        assert len(all_data) >= len(
            active_data
        ), "--all should return at least as many entries as the active-event dump"

    def test_count_matches_seismogram_dump(
        self,
        loaded_engine: Engine,
        cli_json: Callable[[str], list | dict],
    ) -> None:
        """Verifies that the parameter dump entry count matches the seismogram count.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli_json: The in-process CLI JSON dump callable.
        """
        seis = cli_json("seismogram dump")
        params = cli_json("seismogram parameter dump --all")
        assert isinstance(seis, list), "Seismogram dump should be a list"
        assert isinstance(params, list), "Parameter dump should be a list"
        assert len(params) == len(
            seis
        ), "One parameter entry should exist per seismogram"


# ===================================================================
# Seismogram parameter — list
# ===================================================================


@pytest.mark.cli
class TestSeismogramParameterList:
    """Tests for ``seismogram parameter list``."""

    def test_list_produces_output(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that the list command produces output.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("seismogram parameter list")
        assert (
            len(capsys.readouterr().out) > 0
        ), "Expected output from seismogram parameter list"

    def test_list_short_produces_output(
        self,
        loaded_engine: Engine,
        cli: Callable[[str], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Verifies that ``--short`` produces output.

        Args:
            loaded_engine: The monkeypatched engine with data loaded.
            cli: The in-process CLI callable.
            capsys: The pytest capsys fixture.
        """
        cli("seismogram parameter list --short")
        assert (
            len(capsys.readouterr().out) > 0
        ), "Expected output from seismogram parameter list --short"
