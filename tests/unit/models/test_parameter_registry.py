"""The parameter specs, and the hand-written names that must agree with them."""

from types import UnionType
from typing import Annotated, Any, TypeAliasType, Union, get_args, get_origin

import attrs
import pytest
from pandas import Timedelta, Timestamp
from sqlmodel import SQLModel

from pysmo.tools.iccs import ICCS, MiniIccsSeismogram

from aimbat.core._event import (
    EventParameterBool,
    EventParameterFloat,
    EventParameterInt,
    EventParameterTimedelta,
)
from aimbat.core._seismogram import (
    SeismogramParameterBool,
    SeismogramParameterTimestamp,
)
from aimbat.models._parameters import (
    EVENT_PARAMETER_SPECS,
    SEISMOGRAM_PARAMETER_SPECS,
    AimbatEventParametersBase,
    AimbatSeismogramParametersBase,
    ParameterSpec,
    Reach,
    _parameter_specs,
)
from aimbat.types import EventParameter, SeismogramParameter


def _plain_type(annotation: Any) -> Any:
    """Strip aliases, `Annotated` and `| None` from a field annotation."""
    while True:
        if isinstance(annotation, TypeAliasType):
            annotation = annotation.__value__
        elif get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
        elif get_origin(annotation) in (Union, UnionType):
            (annotation,) = (a for a in get_args(annotation) if a is not type(None))
        else:
            return annotation


def _fields_of_type(model: type[SQLModel], plain_type: type) -> set[str]:
    return {
        name
        for name, field in model.model_fields.items()
        if _plain_type(field.annotation) is plain_type
    }


def _members(literal_alias: TypeAliasType) -> set[str]:
    return {str(member) for member in get_args(literal_alias.__value__)}


class TestSpecs:
    def test_every_event_parameter_has_a_spec(self) -> None:
        assert set(EVENT_PARAMETER_SPECS) == set(AimbatEventParametersBase.model_fields)

    def test_every_seismogram_parameter_has_a_spec(self) -> None:
        assert set(SEISMOGRAM_PARAMETER_SPECS) == set(
            AimbatSeismogramParametersBase.model_fields
        )

    def test_field_without_a_spec_is_rejected(self) -> None:
        class Incomplete(SQLModel):
            new_parameter: float = 0.0

        with pytest.raises(TypeError, match="Incomplete.new_parameter"):
            _parameter_specs(Incomplete)

    @pytest.mark.parametrize("reach", [Reach.EVENT, Reach.CONDITIONAL])
    def test_stack_input_must_name_an_iccs_attribute(self, reach: Reach) -> None:
        with pytest.raises(ValueError, match="iccs_attribute"):
            ParameterSpec(stack=reach)

    @pytest.mark.parametrize(
        "inputs",
        [
            {"stack": Reach.EVENT, "iccs_attribute": "select"},
            {"mccc": Reach.EVENT},
            {"iccs_attribute": "min_cc"},
        ],
        ids=["stack", "mccc", "iccs-attribute"],
    )
    def test_bookkeeping_parameter_cannot_be_an_input(
        self, inputs: dict[str, Any]
    ) -> None:
        with pytest.raises(ValueError, match="bookkeeping"):
            ParameterSpec(bookkeeping=True, **inputs)


class TestIccsAttributes:
    """The ICCS calls are built from the specs, so mypy does not see the names."""

    def test_event_parameters_name_iccs_attributes(self) -> None:
        iccs_fields = {field.name for field in attrs.fields(ICCS)}
        named = {spec.iccs_attribute for spec in EVENT_PARAMETER_SPECS.values()}
        assert named - {None} <= iccs_fields

    def test_seismogram_parameters_name_iccs_seismogram_attributes(self) -> None:
        seismogram_fields = {field.name for field in attrs.fields(MiniIccsSeismogram)}
        named = {spec.iccs_attribute for spec in SEISMOGRAM_PARAMETER_SPECS.values()}
        assert named - {None} <= seismogram_fields


class TestEnumsFollowTheModels:
    def test_event_parameter_enum(self) -> None:
        assert {str(member) for member in EventParameter} == set(
            AimbatEventParametersBase.model_fields
        )

    def test_seismogram_parameter_enum(self) -> None:
        assert {str(member) for member in SeismogramParameter} == set(
            AimbatSeismogramParametersBase.model_fields
        )

    @pytest.mark.parametrize(
        ("literal_alias", "plain_type"),
        [
            (EventParameterBool, bool),
            (EventParameterFloat, float),
            (EventParameterInt, int),
            (EventParameterTimedelta, Timedelta),
        ],
        ids=lambda value: getattr(value, "__name__", None),
    )
    def test_event_setter_overload_groups(
        self, literal_alias: TypeAliasType, plain_type: type
    ) -> None:
        assert _members(literal_alias) == _fields_of_type(
            AimbatEventParametersBase, plain_type
        )

    @pytest.mark.parametrize(
        ("literal_alias", "plain_type"),
        [
            (SeismogramParameterBool, bool),
            (SeismogramParameterTimestamp, Timestamp),
        ],
        ids=lambda value: getattr(value, "__name__", None),
    )
    def test_seismogram_setter_overload_groups(
        self, literal_alias: TypeAliasType, plain_type: type
    ) -> None:
        assert _members(literal_alias) == _fields_of_type(
            AimbatSeismogramParametersBase, plain_type
        )
