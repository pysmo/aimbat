"""Integration tests for seismogram management functions in aimbat.core._seismogram."""

import json
import uuid
import pytest
from aimbat.core import (
    delete_seismogram,
    delete_seismogram_by_id,
    get_seismogram_parameter,
    get_seismogram_parameter_by_id,
    set_seismogram_parameter,
    set_seismogram_parameter_by_id,
    reset_seismogram_parameters,
    reset_seismogram_parameters_by_id,
    get_selected_seismograms,
    dump_seismogram_table_to_json,
    dump_seismogram_parameter_table_to_json,
    plot_all_seismograms,
    get_default_event,
)
from aimbat.models._parameters import AimbatSeismogramParametersBase
from aimbat._types import SeismogramParameter
from aimbat.models import AimbatSeismogram
from matplotlib.figure import Figure
from pandas import Timestamp
from sqlmodel import Session, select
from sqlalchemy.exc import NoResultFound


@pytest.fixture
def session(loaded_session: Session) -> Session:
    """Provides a session with multi-event data and an default event pre-loaded.

    Args:
        loaded_session: A SQLModel Session with data populated.

    Returns:
        The database session.
    """
    return loaded_session


@pytest.fixture
def seismogram(session: Session) -> AimbatSeismogram:
    """Provides the first seismogram from the default event.

    Args:
        session: The database session.

    Returns:
        An AimbatSeismogram from the default event.
    """
    return session.exec(select(AimbatSeismogram)).first()  # type: ignore[return-value]


class TestDeleteSeismogram:
    """Tests for deleting seismograms from the database."""

    def test_delete_seismogram(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a seismogram is removed from the database after deletion.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram to delete.
        """
        count_before = len(session.exec(select(AimbatSeismogram)).all())
        delete_seismogram(session, seismogram)
        assert len(session.exec(select(AimbatSeismogram)).all()) == count_before - 1

    def test_delete_seismogram_by_id(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a seismogram is removed from the database when deleted by ID.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram whose ID is used for deletion.
        """
        count_before = len(session.exec(select(AimbatSeismogram)).all())
        delete_seismogram_by_id(session, seismogram.id)
        assert len(session.exec(select(AimbatSeismogram)).all()) == count_before - 1

    def test_delete_seismogram_by_id_not_found(self, session: Session) -> None:
        """Verifies that deleting a non-existent seismogram ID raises NoResultFound.

        Args:
            session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_seismogram_by_id(session, uuid.uuid4())


class TestGetSeismogramParameter:
    """Tests for reading parameter values from a seismogram instance."""

    def test_get_bool_parameter(self, seismogram: AimbatSeismogram) -> None:
        """Verifies that a bool parameter is returned as a bool.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        value = get_seismogram_parameter(seismogram, SeismogramParameter.SELECT)
        assert isinstance(value, bool)

    def test_get_timestamp_parameter_default_none(
        self, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that the t1 parameter returns None when not set.

        Args:
            seismogram: An AimbatSeismogram instance.
        """
        value = get_seismogram_parameter(seismogram, SeismogramParameter.T1)
        assert value is None

    def test_get_timestamp_parameter_after_set(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that t1 is returned as a Timestamp after being set.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram instance.
        """
        t1 = seismogram.t0
        set_seismogram_parameter(session, seismogram, SeismogramParameter.T1, t1)
        value = get_seismogram_parameter(seismogram, SeismogramParameter.T1)
        assert isinstance(value, Timestamp)


class TestGetSeismogramParameterById:
    """Tests for reading parameter values from a seismogram by ID."""

    def test_get_by_id(self, session: Session, seismogram: AimbatSeismogram) -> None:
        """Verifies that a bool parameter is returned correctly when looked up by ID.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram whose ID is used for lookup.
        """
        value = get_seismogram_parameter_by_id(
            session, seismogram.id, SeismogramParameter.SELECT
        )
        assert isinstance(value, bool)

    def test_get_by_id_not_found(self, session: Session) -> None:
        """Verifies that a ValueError is raised for an unknown seismogram ID.

        Args:
            session: The database session.
        """
        with pytest.raises(ValueError):
            get_seismogram_parameter_by_id(
                session, uuid.uuid4(), SeismogramParameter.SELECT
            )


class TestSetSeismogramParameter:
    """Tests for writing parameter values to a seismogram instance."""

    def test_set_bool_parameter(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a bool parameter is persisted correctly.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram instance.
        """
        original = get_seismogram_parameter(seismogram, SeismogramParameter.SELECT)
        set_seismogram_parameter(
            session, seismogram, SeismogramParameter.SELECT, not original
        )
        assert (
            get_seismogram_parameter(seismogram, SeismogramParameter.SELECT)
            is not original
        )

    def test_set_timestamp_parameter(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a Timestamp parameter is persisted correctly.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram instance.
        """
        t1 = seismogram.t0
        set_seismogram_parameter(session, seismogram, SeismogramParameter.T1, t1)
        assert get_seismogram_parameter(seismogram, SeismogramParameter.T1) == t1


class TestSetSeismogramParameterById:
    """Tests for writing parameter values to a seismogram by ID."""

    def test_set_by_id(self, session: Session, seismogram: AimbatSeismogram) -> None:
        """Verifies that a bool parameter is persisted when set by seismogram ID.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram whose ID is used for lookup.
        """
        set_seismogram_parameter_by_id(
            session, seismogram.id, SeismogramParameter.FLIP, True
        )
        assert get_seismogram_parameter(seismogram, SeismogramParameter.FLIP) is True

    def test_set_by_id_not_found(self, session: Session) -> None:
        """Verifies that a ValueError is raised for an unknown seismogram ID.

        Args:
            session: The database session.
        """
        with pytest.raises(ValueError):
            set_seismogram_parameter_by_id(
                session, uuid.uuid4(), SeismogramParameter.FLIP, True
            )


class TestResetSeismogramParameters:
    """Tests for resetting seismogram parameters to their defaults."""

    def test_reset_parameters(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that all parameters are restored to their default values after reset.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram whose parameters are modified then reset.
        """
        set_seismogram_parameter(session, seismogram, SeismogramParameter.FLIP, True)
        set_seismogram_parameter(session, seismogram, SeismogramParameter.SELECT, False)
        set_seismogram_parameter(
            session, seismogram, SeismogramParameter.T1, seismogram.t0
        )
        reset_seismogram_parameters(session, seismogram)
        defaults = AimbatSeismogramParametersBase()
        for field_name in AimbatSeismogramParametersBase.model_fields:
            assert getattr(seismogram.parameters, field_name) == getattr(
                defaults, field_name
            )

    def test_reset_parameters_by_id(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that reset via ID produces the same result as reset by instance.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram whose parameters are modified then reset.
        """
        set_seismogram_parameter(session, seismogram, SeismogramParameter.FLIP, True)
        reset_seismogram_parameters_by_id(session, seismogram.id)
        assert seismogram.parameters.flip is False

    def test_reset_parameters_by_id_not_found(self, session: Session) -> None:
        """Verifies that resetting a non-existent seismogram ID raises NoResultFound.

        Args:
            session: The database session.
        """
        with pytest.raises(NoResultFound):
            reset_seismogram_parameters_by_id(session, uuid.uuid4())


class TestGetSelectedSeismograms:
    """Tests for retrieving selected seismograms."""

    def test_all_selected_by_default(self, session: Session) -> None:
        """Verifies that all seismograms in the default event are selected by default.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        selected = get_selected_seismograms(session, event=default_event)
        assert len(selected) > 0

    def test_after_deselecting_one(
        self, session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that deselecting a seismogram removes it from the selected set.

        Args:
            session: The database session.
            seismogram: An AimbatSeismogram to deselect.
        """
        default_event = get_default_event(session)
        count_before = len(get_selected_seismograms(session, event=default_event))
        set_seismogram_parameter(session, seismogram, SeismogramParameter.SELECT, False)
        assert (
            len(get_selected_seismograms(session, event=default_event))
            == count_before - 1
        )

    def test_all_events(self, session: Session) -> None:
        """Verifies that get_selected_seismograms returns seismograms across all events.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        selected_default = get_selected_seismograms(
            session, event=default_event, all_events=False
        )
        selected_all = get_selected_seismograms(session, all_events=True)
        assert len(selected_all) >= len(selected_default)


class TestDumpSeismogramTableToJson:
    """Tests for serialising the seismogram table to JSON."""

    def test_returns_json_string(self, session: Session) -> None:
        """Verifies that the seismogram table is returned as a valid JSON string.

        Args:
            session: The database session.
        """
        result = dump_seismogram_table_to_json(session)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) > 0


class TestDumpSeismogramParameterTableToJson:
    """Tests for serialising the seismogram parameter table to JSON."""

    def test_default_event_as_string(self, session: Session) -> None:
        """Verifies that a JSON string of the default event's parameters is returned.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        result = dump_seismogram_parameter_table_to_json(
            session, all_events=False, as_string=True, event=default_event
        )
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) > 0

    def test_default_event_as_list(self, session: Session) -> None:
        """Verifies that a list of dicts of the default event's parameters is returned.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        result = dump_seismogram_parameter_table_to_json(
            session, all_events=False, as_string=False, event=default_event
        )
        assert isinstance(result, list)
        assert len(result) > 0
        assert "select" in result[0]

    def test_all_events_as_string(self, session: Session) -> None:
        """Verifies that a JSON string of all events' parameters is returned.

        Args:
            session: The database session.
        """
        result = dump_seismogram_parameter_table_to_json(
            session, all_events=True, as_string=True
        )
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) > 0

    def test_all_events_as_list(self, session: Session) -> None:
        """Verifies that a list of dicts of all events' parameters is returned.

        Args:
            session: The database session.
        """
        result = dump_seismogram_parameter_table_to_json(
            session, all_events=True, as_string=False
        )
        assert isinstance(result, list)
        assert len(result) > 0
        assert "select" in result[0]

    def test_all_events_returns_more_than_default_only(self, session: Session) -> None:
        """Verifies that all_events=True returns more rows than default event only.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        default_only = dump_seismogram_parameter_table_to_json(
            session, all_events=False, as_string=False, event=default_event
        )
        all_events = dump_seismogram_parameter_table_to_json(
            session, all_events=True, as_string=False
        )
        assert len(all_events) >= len(default_only)


class TestPlotAllSeismograms:
    """Tests for plotting seismograms."""

    def test_returns_figure(self, session: Session) -> None:
        """Verifies that plot_all_seismograms returns a matplotlib Figure.

        Args:
            session: The database session.
        """
        default_event = get_default_event(session)
        fig, _ = plot_all_seismograms(session, event=default_event, return_fig=True)
        assert isinstance(fig, Figure)
