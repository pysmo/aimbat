"""Integration tests for seismogram management functions in aimbat.core._seismogram."""

import uuid

import pytest
from matplotlib.figure import Figure
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat._types import SeismogramParameter
from aimbat.core import (
    delete_seismogram,
    dump_seismogram_parameter_table,
    dump_seismogram_table,
    get_default_event,
    get_selected_seismograms,
    reset_seismogram_parameters,
    set_seismogram_parameter,
)
from aimbat.models import AimbatSeismogram, AimbatStation
from aimbat.models._parameters import AimbatSeismogramParametersBase
from aimbat.plot import plot_seismograms


@pytest.fixture
def seismogram(loaded_session: Session) -> AimbatSeismogram:
    """Provides the first seismogram from the default event.

    Args:
        loaded_session: The database session.

    Returns:
        An AimbatSeismogram from the default event.
    """
    seismogram = loaded_session.exec(select(AimbatSeismogram)).first()
    assert seismogram is not None
    return seismogram


@pytest.fixture
def station(loaded_session: Session) -> AimbatStation:
    """Provides the first station in the database.

    Args:
        loaded_session: The database session.

    Returns:
        An AimbatStation instance.
    """
    station = loaded_session.exec(select(AimbatStation)).first()
    assert station is not None
    return station


class TestDeleteSeismogram:
    """Tests for deleting seismograms from the database."""

    def test_delete_seismogram(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a seismogram is removed from the database after deletion.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram to delete.
        """
        count_before = len(loaded_session.exec(select(AimbatSeismogram)).all())
        delete_seismogram(loaded_session, seismogram.id)
        assert (
            len(loaded_session.exec(select(AimbatSeismogram)).all()) == count_before - 1
        )

    def test_delete_seismogram_by_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that deleting a non-existent seismogram ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            delete_seismogram(loaded_session, uuid.uuid4())


class TestSetSeismogramParameter:
    """Tests for writing parameter values to a seismogram instance."""

    def test_set_bool_parameter(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a bool parameter is persisted correctly.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram instance.
        """
        original = getattr(seismogram.parameters, SeismogramParameter.SELECT)
        set_seismogram_parameter(
            loaded_session, seismogram.id, SeismogramParameter.SELECT, not original
        )
        assert (
            getattr(seismogram.parameters, SeismogramParameter.SELECT) is not original
        )

    def test_set_timestamp_parameter(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a Timestamp parameter is persisted correctly.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram instance.
        """
        t1 = seismogram.t0
        set_seismogram_parameter(
            loaded_session, seismogram.id, SeismogramParameter.T1, t1
        )
        assert getattr(seismogram.parameters, SeismogramParameter.T1) == t1

    def test_set_by_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that a ValueError is raised for an unknown seismogram ID.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(ValueError):
            set_seismogram_parameter(
                loaded_session, uuid.uuid4(), SeismogramParameter.FLIP, True
            )


class TestResetSeismogramParameters:
    """Tests for resetting seismogram parameters to their defaults."""

    def test_reset_parameters(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that all parameters are restored to their default values after reset.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram whose parameters are modified then reset.
        """
        set_seismogram_parameter(
            loaded_session, seismogram.id, SeismogramParameter.FLIP, True
        )
        set_seismogram_parameter(
            loaded_session, seismogram.id, SeismogramParameter.SELECT, False
        )
        set_seismogram_parameter(
            loaded_session, seismogram.id, SeismogramParameter.T1, seismogram.t0
        )
        reset_seismogram_parameters(loaded_session, seismogram.id)
        defaults = AimbatSeismogramParametersBase()
        for field_name in AimbatSeismogramParametersBase.model_fields:
            assert getattr(seismogram.parameters, field_name) == getattr(
                defaults, field_name
            )

    def test_reset_parameters_by_id_not_found(self, loaded_session: Session) -> None:
        """Verifies that resetting a non-existent seismogram ID raises NoResultFound.

        Args:
            loaded_session: The database session.
        """
        with pytest.raises(NoResultFound):
            reset_seismogram_parameters(loaded_session, uuid.uuid4())


class TestGetSelectedSeismograms:
    """Tests for retrieving selected seismograms."""

    def test_all_selected_by_default(self, loaded_session: Session) -> None:
        """Verifies that all seismograms in the default event are selected by default.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None, (
            "expected a default event to be present in the database"
        )
        selected = get_selected_seismograms(loaded_session, event_id=default_event.id)
        assert len(selected) > 0

    def test_after_deselecting_one(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that deselecting a seismogram removes it from the selected set.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram to deselect.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None, (
            "expected a default event to be present in the database"
        )
        count_before = len(
            get_selected_seismograms(loaded_session, event_id=default_event.id)
        )
        set_seismogram_parameter(
            loaded_session, seismogram.id, SeismogramParameter.SELECT, False
        )
        assert (
            len(get_selected_seismograms(loaded_session, event_id=default_event.id))
            == count_before - 1
        )

    def test_all_events(self, loaded_session: Session) -> None:
        """Verifies that get_selected_seismograms returns seismograms across all events.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None, (
            "expected a default event to be present in the database"
        )
        selected_default = get_selected_seismograms(
            loaded_session, event_id=default_event.id, all_events=False
        )
        selected_all = get_selected_seismograms(loaded_session, all_events=True)
        assert len(selected_all) >= len(selected_default)


class TestDumpSeismogramTableToJson:
    """Tests for serialising the seismogram table to JSON."""

    def test_returns_list(self, loaded_session: Session) -> None:
        """Verifies that the seismogram table is returned as a list.

        Args:
            loaded_session: The database session.
        """
        result = dump_seismogram_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) > 0


class TestDumpSeismogramParameterTableToJson:
    """Tests for serialising the seismogram parameter table to JSON."""

    def test_default_event_as_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts of the default event's parameters is returned.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        result = dump_seismogram_parameter_table(
            loaded_session, event_id=default_event.id
        )
        assert isinstance(result, list)
        assert len(result) > 0
        assert "select" in result[0]

    def test_all_events_as_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts of all events' parameters is returned.

        Args:
            loaded_session: The database session.
        """
        result = dump_seismogram_parameter_table(loaded_session)
        assert isinstance(result, list)
        assert len(result) > 0
        assert "select" in result[0]


class TestPlotSeismograms:
    """Tests for plotting seismograms."""

    def test_plot_event_returns_figure(self, loaded_session: Session) -> None:
        """Verifies that plot_seismograms for an event returns a matplotlib Figure.

        Args:
            loaded_session: The database session.
        """
        default_event = get_default_event(loaded_session)
        assert default_event is not None
        fig, _ = plot_seismograms(
            loaded_session, plot_for=default_event, return_fig=True
        )
        assert isinstance(fig, Figure)

    def test_plot_station_returns_figure(
        self, loaded_session: Session, station: AimbatStation
    ) -> None:
        """Verifies that plot_seismograms for a station returns a matplotlib Figure.

        Args:
            loaded_session: The database session.
            station: An AimbatStation instance.
        """
        fig, _ = plot_seismograms(loaded_session, plot_for=station, return_fig=True)
        assert isinstance(fig, Figure)
