"""Integration tests for the AIMBAT TUI application."""

from aimbat.models._parameters import AimbatEventParametersBase


def test_event_parameters_have_titles() -> None:
    """Verify all AimbatEventParametersBase fields have a title set.

    This guards against parameters being added to the model without also setting
    the title metadata used by the TUI.
    """
    missing = [
        name
        for name, field_info in AimbatEventParametersBase.model_fields.items()
        if not field_info.title
    ]
    assert not missing, f"Fields missing title in AimbatEventParametersBase: {missing}"
