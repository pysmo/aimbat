"""Integration tests for seismogram management functions in aimbat.core._seismogram."""

import uuid

import matplotlib.dates as mdates
import pytest
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from pandas import Timedelta
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select

from aimbat.core import (
    delete_seismogram,
    dump_seismogram_parameter_table,
    dump_seismogram_table,
    get_selected_seismograms,
    reset_seismogram_parameters,
    set_seismogram_parameter,
    set_seismogram_parameters,
    set_seismogram_picks,
)
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatStation
from aimbat.models._parameters import AimbatSeismogramParametersBase
from aimbat.plot import plot_seismograms
from aimbat.types import SeismogramParameter


@pytest.fixture
def seismogram(loaded_session: Session) -> AimbatSeismogram:
    """Provides the first seismogram from the database.

    Args:
        loaded_session: The database session.

    Returns:
        An AimbatSeismogram.
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

    def test_delete_seismogram_with_preloaded_event_and_live_quality(
        self, loaded_session: Session
    ) -> None:
        """Deleting works with the event's seismograms already loaded, and
        leaves the survivors' `iccs_cc` out of date."""
        from aimbat.core import create_iccs_instance
        from aimbat.core._validity import Validity

        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        create_iccs_instance(loaded_session, event)  # writes live iccs_cc

        seismograms = list(event.seismograms)  # preload the collection
        assert len(seismograms) > 1
        victim_id, survivor_id = seismograms[0].id, seismograms[1].id
        assert seismograms[0].quality is not None

        delete_seismogram(loaded_session, victim_id)

        assert loaded_session.get(AimbatSeismogram, victim_id) is None
        assert not Validity.read(loaded_session, event.id).iccs_cc(survivor_id)


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

    @pytest.mark.parametrize("commit", [False, True])
    def test_change_is_kept_only_if_the_caller_commits(
        self, loaded_engine: Engine, commit: bool
    ) -> None:
        """`set_seismogram_parameter` leaves committing to the caller."""
        with Session(loaded_engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            seismogram_id = seismogram.id
            original = getattr(seismogram.parameters, SeismogramParameter.SELECT)
            set_seismogram_parameter(
                session, seismogram_id, SeismogramParameter.SELECT, not original
            )
            if commit:
                session.commit()

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            expected = (not original) if commit else original
            assert (
                getattr(seismogram.parameters, SeismogramParameter.SELECT) is expected
            )


class TestSetSeismogramParameters:
    """Tests for setting parameters on several seismograms at once."""

    @staticmethod
    def _one_per_event(session: Session) -> list[AimbatSeismogram]:
        events = session.exec(select(AimbatEvent)).all()
        assert len(events) > 1
        return [events[0].seismograms[0], events[1].seismograms[0]]

    def test_sets_across_events(self, loaded_session: Session) -> None:
        """Seismograms of different events are updated in one call."""
        seismograms = self._one_per_event(loaded_session)

        set_seismogram_parameters(
            loaded_session,
            [s.id for s in seismograms],
            {SeismogramParameter.FLIP: True, SeismogramParameter.SELECT: False},
        )

        for seismogram in seismograms:
            assert seismogram.parameters.flip is True
            assert seismogram.parameters.select is False

    def test_invalid_value_changes_nothing(self, loaded_engine: Engine) -> None:
        """A value that fails validation leaves every seismogram as it was."""
        with Session(loaded_engine) as session:
            ids = [s.id for s in self._one_per_event(session)]
            with pytest.raises(ValidationError):
                set_seismogram_parameters(
                    session, ids, {SeismogramParameter.FLIP: "maybe"}
                )

        with Session(loaded_engine) as session:
            for seismogram_id in ids:
                seismogram = session.get(AimbatSeismogram, seismogram_id)
                assert seismogram is not None
                assert seismogram.parameters.flip is False

    def test_unknown_id_changes_nothing(self, loaded_engine: Engine) -> None:
        """An unknown ID is named in the error, and nothing is changed."""
        unknown = uuid.uuid4()
        with Session(loaded_engine) as session:
            known = self._one_per_event(session)[0].id
            with pytest.raises(NoResultFound, match=str(unknown)):
                set_seismogram_parameters(
                    session, [known, unknown], {SeismogramParameter.FLIP: True}
                )

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, known)
            assert seismogram is not None
            assert seismogram.parameters.flip is False


class TestSetSeismogramPicks:
    """Tests for setting each seismogram's refined pick to its own value."""

    def test_sets_each_pick(self, loaded_session: Session) -> None:
        """Every seismogram receives its own pick, across events."""
        events = loaded_session.exec(select(AimbatEvent)).all()
        seismograms = [events[0].seismograms[0], events[1].seismograms[0]]
        picks = {
            s.id: s.t0 + Timedelta(seconds=i + 1) for i, s in enumerate(seismograms)
        }

        set_seismogram_picks(loaded_session, picks)

        for seismogram in seismograms:
            assert seismogram.parameters.t1 == picks[seismogram.id]

    def test_unknown_id_changes_nothing(self, loaded_engine: Engine) -> None:
        """An unknown ID is named in the error, and nothing is changed."""
        unknown = uuid.uuid4()
        with Session(loaded_engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            known, before = seismogram.id, seismogram.parameters.t1
            with pytest.raises(NoResultFound, match=str(unknown)):
                set_seismogram_picks(
                    session,
                    {
                        known: seismogram.t0 + Timedelta(seconds=1),
                        unknown: seismogram.t0,
                    },
                )

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, known)
            assert seismogram is not None
            assert seismogram.parameters.t1 == before


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

    def test_reset_parameters_persists_across_sessions(
        self, loaded_engine: Engine
    ) -> None:
        """Verifies a reset survives the session it was made in being closed.

        Callers always call `reset_seismogram_parameters` inside a
        `with Session(engine) as session:` block and never commit
        themselves, so the write must be durable by the time that session
        closes — whether via this function's own commit or one it triggers
        indirectly (e.g. `clear_mccc_quality`). Guards against the reset
        being silently rolled back on session close.
        """
        with Session(loaded_engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            seismogram_id = seismogram.id
            set_seismogram_parameter(
                session, seismogram_id, SeismogramParameter.FLIP, True
            )
            reset_seismogram_parameters(session, seismogram_id)

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            defaults = AimbatSeismogramParametersBase()
            assert (
                getattr(seismogram.parameters, SeismogramParameter.FLIP)
                == defaults.flip
            )


class TestGetSelectedSeismograms:
    """Tests for retrieving selected seismograms."""

    def test_all_selected_by_default(self, loaded_session: Session) -> None:
        """Verifies that all seismograms in an event are selected by default.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None, "expected an event to be present in the database"
        selected = get_selected_seismograms(loaded_session, event_id=event.id)
        assert len(selected) > 0

    def test_after_deselecting_one(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that deselecting a seismogram removes it from the selected set.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram to deselect.
        """
        event = seismogram.event
        count_before = len(get_selected_seismograms(loaded_session, event_id=event.id))
        set_seismogram_parameter(
            loaded_session, seismogram.id, SeismogramParameter.SELECT, False
        )
        assert (
            len(get_selected_seismograms(loaded_session, event_id=event.id))
            == count_before - 1
        )

    def test_all_events(self, loaded_session: Session) -> None:
        """Verifies that get_selected_seismograms returns seismograms across all events.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None, "expected an event to be present in the database"
        selected_single = get_selected_seismograms(
            loaded_session, event_id=event.id, all_events=False
        )
        selected_all = get_selected_seismograms(loaded_session, all_events=True)
        assert len(selected_all) >= len(selected_single)


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

    def test_single_event_as_list(self, loaded_session: Session) -> None:
        """Verifies that a list of dicts of an event's parameters is returned.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        result = dump_seismogram_parameter_table(loaded_session, event_id=event.id)
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
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        fig, _ = plot_seismograms(plot_for=event, return_fig=True)
        assert isinstance(fig, Figure)

    def test_plot_event_marks_picks(self, loaded_session: Session) -> None:
        """Verifies that the event plot marks t0 and t1 at their times on each seismogram.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        picked = event.seismograms[0]
        picked.parameters.t1 = picked.t0 + Timedelta(seconds=2)
        loaded_session.add(picked)
        loaded_session.commit()

        _, ax = plot_seismograms(plot_for=event, return_fig=True)

        marks = {
            c.get_label(): c for c in ax.collections if isinstance(c, LineCollection)
        }
        t0_x = sorted(seg[0][0] for seg in marks["t0"].get_segments())
        assert t0_x == pytest.approx(
            sorted(mdates.date2num(s.t0) for s in event.seismograms)
        )
        t1_segments = marks["t1"].get_segments()
        assert len(t1_segments) == 1
        assert t1_segments[0][0][0] == pytest.approx(
            mdates.date2num(picked.parameters.t1)
        )

    def test_plot_station_marks_picks(
        self, loaded_session: Session, station: AimbatStation
    ) -> None:
        """Verifies that the station plot marks t1 at zero and t0 at its offset from t1.

        Args:
            loaded_session: The database session.
            station: An AimbatStation instance.
        """
        seismogram = station.seismograms[0]
        seismogram.parameters.t1 = seismogram.t0 + Timedelta(seconds=2)
        loaded_session.add(seismogram)
        loaded_session.commit()

        _, ax = plot_seismograms(plot_for=station, return_fig=True)

        marks = {
            c.get_label(): c for c in ax.collections if isinstance(c, LineCollection)
        }
        t1_x = [seg[0][0] for seg in marks["t1"].get_segments()]
        assert t1_x and all(x == 0.0 for x in t1_x)
        assert -2.0 in [seg[0][0] for seg in marks["t0"].get_segments()]

    def test_plot_station_returns_figure(
        self, loaded_session: Session, station: AimbatStation
    ) -> None:
        """Verifies that plot_seismograms for a station returns a matplotlib Figure.

        Args:
            loaded_session: The database session.
            station: An AimbatStation instance.
        """
        fig, _ = plot_seismograms(plot_for=station, return_fig=True)
        assert isinstance(fig, Figure)
