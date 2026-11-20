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
    default_phase_parameters,
    delete_seismogram,
    dump_seismogram_parameter_table,
    dump_seismogram_table,
    get_seismogram_parameters,
    get_selected_rows,
    reset_seismogram_parameters,
    set_refined_picks,
    set_seismogram_parameter,
    set_seismogram_parameters,
)
from aimbat.models import (
    AimbatEvent,
    AimbatPhase,
    AimbatPick,
    AimbatSeismogram,
    AimbatSeismogramParameters,
    AimbatStation,
    PickOrigin,
)
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
        create_iccs_instance(loaded_session, event.phases[0].id)  # writes live iccs_cc

        seismograms = list(event.seismograms)  # preload the collection
        assert len(seismograms) > 1
        victim_id, survivor_id = seismograms[0].id, seismograms[1].phase_rows[0].id
        assert seismograms[0].phase_rows[0].quality is not None

        delete_seismogram(loaded_session, victim_id)

        assert loaded_session.get(AimbatSeismogram, victim_id) is None
        assert not Validity.read(loaded_session, event_id=event.id).iccs_cc(survivor_id)


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
        original = getattr(seismogram.phase_rows[0], SeismogramParameter.SELECT)
        set_seismogram_parameter(
            loaded_session,
            seismogram.phase_rows[0].phase_id,
            seismogram.id,
            SeismogramParameter.SELECT,
            not original,
        )
        assert (
            getattr(seismogram.phase_rows[0], SeismogramParameter.SELECT)
            is not original
        )

    def test_set_timestamp_parameter(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that a Timestamp parameter is persisted correctly.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram instance.
        """
        t1 = seismogram.phase_rows[0].initial_pick
        set_seismogram_parameter(
            loaded_session,
            seismogram.phase_rows[0].phase_id,
            seismogram.id,
            SeismogramParameter.REFINED_PICK,
            t1,
        )
        assert getattr(seismogram.phase_rows[0], SeismogramParameter.REFINED_PICK) == t1

    def test_set_by_id_not_found(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that NoResultFound is raised for an unknown seismogram ID.

        Args:
            loaded_session: The database session.
            seismogram: Any seismogram, for its phase.
        """
        with pytest.raises(NoResultFound):
            set_seismogram_parameter(
                loaded_session,
                seismogram.phase_rows[0].phase_id,
                uuid.uuid4(),
                SeismogramParameter.FLIP,
                True,
            )

    def test_seismogram_of_another_phase(self, loaded_session: Session) -> None:
        """A seismogram without a row in the phase is not changed."""
        events = loaded_session.exec(select(AimbatEvent)).all()
        other = events[1].seismograms[0]
        with pytest.raises(NoResultFound, match=str(other.id)):
            set_seismogram_parameter(
                loaded_session,
                events[0].phases[0].id,
                other.id,
                SeismogramParameter.FLIP,
                True,
            )
        assert other.phase_rows[0].flip is False

    @pytest.mark.parametrize("commit", [False, True])
    def test_change_is_kept_only_if_the_caller_commits(
        self, loaded_engine: Engine, commit: bool
    ) -> None:
        """`set_seismogram_parameter` leaves committing to the caller."""
        with Session(loaded_engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            seismogram_id = seismogram.id
            phase_id = seismogram.phase_rows[0].phase_id
            original = getattr(seismogram.phase_rows[0], SeismogramParameter.SELECT)
            set_seismogram_parameter(
                session,
                phase_id,
                seismogram_id,
                SeismogramParameter.SELECT,
                not original,
            )
            if commit:
                session.commit()

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            expected = (not original) if commit else original
            assert (
                getattr(seismogram.phase_rows[0], SeismogramParameter.SELECT)
                is expected
            )


class TestSetSeismogramParameters:
    """Tests for setting parameters on several seismograms at once."""

    @staticmethod
    def _two_of_one_phase(session: Session) -> list[AimbatSeismogram]:
        event = session.exec(select(AimbatEvent)).first()
        assert event is not None
        return list(event.seismograms[:2])

    def test_sets_several(self, loaded_session: Session) -> None:
        """Several seismograms of a phase are updated in one call."""
        seismograms = self._two_of_one_phase(loaded_session)

        set_seismogram_parameters(
            loaded_session,
            seismograms[0].phase_rows[0].phase_id,
            [s.id for s in seismograms],
            {SeismogramParameter.FLIP: True, SeismogramParameter.SELECT: False},
        )

        for seismogram in seismograms:
            assert seismogram.phase_rows[0].flip is True
            assert seismogram.phase_rows[0].select is False

    def test_invalid_value_changes_nothing(self, loaded_engine: Engine) -> None:
        """A value that fails validation leaves every seismogram as it was."""
        with Session(loaded_engine) as session:
            seismograms = self._two_of_one_phase(session)
            phase_id = seismograms[0].phase_rows[0].phase_id
            ids = [s.id for s in seismograms]
            with pytest.raises(ValidationError):
                set_seismogram_parameters(
                    session, phase_id, ids, {SeismogramParameter.FLIP: "maybe"}
                )

        with Session(loaded_engine) as session:
            for seismogram_id in ids:
                seismogram = session.get(AimbatSeismogram, seismogram_id)
                assert seismogram is not None
                assert seismogram.phase_rows[0].flip is False

    def test_unknown_id_changes_nothing(self, loaded_engine: Engine) -> None:
        """An unknown ID is named in the error, and nothing is changed."""
        unknown = uuid.uuid4()
        with Session(loaded_engine) as session:
            seismogram = self._two_of_one_phase(session)[0]
            known, phase_id = seismogram.id, seismogram.phase_rows[0].phase_id
            with pytest.raises(NoResultFound, match=str(unknown)):
                set_seismogram_parameters(
                    session,
                    phase_id,
                    [known, unknown],
                    {SeismogramParameter.FLIP: True},
                )

        with Session(loaded_engine) as session:
            assert session.get_one(AimbatSeismogram, known).phase_rows[0].flip is False


class TestSetRefinedPicks:
    """Tests for setting each seismogram's refined pick to its own value."""

    def test_sets_each_pick(self, loaded_session: Session) -> None:
        """Every seismogram receives its own pick."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        seismograms = list(event.seismograms[:2])
        picks = {
            s.id: s.phase_rows[0].initial_pick + Timedelta(seconds=i + 1)
            for i, s in enumerate(seismograms)
        }

        set_refined_picks(loaded_session, event.phases[0].id, picks)

        for seismogram in seismograms:
            assert seismogram.phase_rows[0].refined_pick == picks[seismogram.id]

    def test_unknown_id_changes_nothing(self, loaded_engine: Engine) -> None:
        """An unknown ID is named in the error, and nothing is changed."""
        unknown = uuid.uuid4()
        with Session(loaded_engine) as session:
            seismogram = session.exec(select(AimbatSeismogram)).first()
            assert seismogram is not None
            known, before = seismogram.id, seismogram.phase_rows[0].refined_pick
            with pytest.raises(NoResultFound, match=str(unknown)):
                set_refined_picks(
                    session,
                    seismogram.phase_rows[0].phase_id,
                    {
                        known: seismogram.phase_rows[0].initial_pick
                        + Timedelta(seconds=1),
                        unknown: seismogram.phase_rows[0].initial_pick,
                    },
                )

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, known)
            assert seismogram is not None
            assert seismogram.phase_rows[0].refined_pick == before


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
            loaded_session,
            seismogram.phase_rows[0].phase_id,
            seismogram.id,
            SeismogramParameter.FLIP,
            True,
        )
        set_seismogram_parameter(
            loaded_session,
            seismogram.phase_rows[0].phase_id,
            seismogram.id,
            SeismogramParameter.SELECT,
            False,
        )
        set_seismogram_parameter(
            loaded_session,
            seismogram.phase_rows[0].phase_id,
            seismogram.id,
            SeismogramParameter.REFINED_PICK,
            seismogram.phase_rows[0].initial_pick,
        )
        reset_seismogram_parameters(
            loaded_session, seismogram.phase_rows[0].phase_id, seismogram.id
        )
        defaults = AimbatSeismogramParametersBase()
        for field_name in AimbatSeismogramParametersBase.model_fields:
            assert getattr(seismogram.phase_rows[0], field_name) == getattr(
                defaults, field_name
            )

    def test_reset_parameters_by_id_not_found(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that resetting a non-existent seismogram ID raises NoResultFound.

        Args:
            loaded_session: The database session.
            seismogram: Any seismogram, for its phase.
        """
        with pytest.raises(NoResultFound):
            reset_seismogram_parameters(
                loaded_session, seismogram.phase_rows[0].phase_id, uuid.uuid4()
            )

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
            phase_id = seismogram.phase_rows[0].phase_id
            set_seismogram_parameter(
                session, phase_id, seismogram_id, SeismogramParameter.FLIP, True
            )
            reset_seismogram_parameters(session, phase_id, seismogram_id)

        with Session(loaded_engine) as session:
            seismogram = session.get(AimbatSeismogram, seismogram_id)
            assert seismogram is not None
            defaults = AimbatSeismogramParametersBase()
            assert (
                getattr(seismogram.phase_rows[0], SeismogramParameter.FLIP)
                == defaults.flip
            )


class TestGetSelectedRows:
    """Tests for retrieving the selected seismograms of a phase."""

    def test_all_selected_by_default(self, loaded_session: Session) -> None:
        """Verifies that all seismograms of a phase are selected by default.

        Args:
            loaded_session: The database session.
        """
        phase = loaded_session.exec(select(AimbatPhase)).first()
        assert phase is not None, "expected a phase to be present in the database"
        selected = get_selected_rows(loaded_session, phase.id)
        assert len(selected) == len(phase.seismogram_parameters) > 0
        assert all(row.phase_id == phase.id for row in selected)

    def test_after_deselecting_one(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        """Verifies that deselecting a seismogram removes it from the selected set.

        Args:
            loaded_session: The database session.
            seismogram: An AimbatSeismogram to deselect.
        """
        phase_id = seismogram.phase_rows[0].phase_id
        count_before = len(get_selected_rows(loaded_session, phase_id))
        set_seismogram_parameter(
            loaded_session,
            phase_id,
            seismogram.id,
            SeismogramParameter.SELECT,
            False,
        )
        selected = get_selected_rows(loaded_session, phase_id)
        assert len(selected) == count_before - 1
        assert seismogram.id not in {row.seismogram_id for row in selected}


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

    def test_phase_name_dumps_only_its_seismograms(
        self, loaded_session: Session
    ) -> None:
        """Seismograms of the event that are not in the phase are left out."""
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        (p_phase,) = event.phases
        p_member = p_phase.seismogram_parameters[0]
        pkp = AimbatPhase(name="PKP", parameters=default_phase_parameters("PKP"))
        event.phases.append(pkp)
        pick = AimbatPick(
            time=p_member.pick.time,
            phase_name="PKP",
            origin=PickOrigin.MANUAL,
            seismogram_id=p_member.seismogram_id,
        )
        loaded_session.add(
            AimbatSeismogramParameters(
                seismogram_id=p_member.seismogram_id, phase=pkp, pick=pick
            )
        )
        loaded_session.flush()

        def ids(phase_name: str, event_id: uuid.UUID | None) -> set[str]:
            rows = dump_seismogram_table(
                loaded_session,
                from_read_model=True,
                event_id=event_id,
                phase_name=phase_name,
            )
            return {str(row["id"]) for row in rows}

        assert ids("PKP", event.id) == {str(p_member.seismogram_id)}
        assert ids("P", event.id) == {str(s.id) for s in event.seismograms}
        assert ids("PKP", None) == {str(p_member.seismogram_id)}


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

    def test_rows_carry_their_phase_name(self, loaded_session: Session) -> None:
        """Verifies that each row names its phase, and that the name filters rows."""
        result = dump_seismogram_parameter_table(loaded_session, by_alias=True)
        assert {row["phaseName"] for row in result} == {"P"}
        assert dump_seismogram_parameter_table(loaded_session, phase_name="S") == []


class TestGetSeismogramParameters:
    """Tests for `get_seismogram_parameters`."""

    def test_row_of_the_phase(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        row = seismogram.phase_rows[0]
        assert (
            get_seismogram_parameters(loaded_session, row.phase_id, seismogram.id)
            is row
        )

    def test_not_in_phase(
        self, loaded_session: Session, seismogram: AimbatSeismogram
    ) -> None:
        with pytest.raises(NoResultFound, match="is not in phase"):
            get_seismogram_parameters(loaded_session, uuid.uuid4(), seismogram.id)


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

    def test_plot_phase_plots_its_rows(self, loaded_session: Session) -> None:
        """Verifies that plotting a phase draws one trace per seismogram of the phase."""
        phase = loaded_session.exec(select(AimbatPhase)).first()
        assert phase is not None
        _, ax = plot_seismograms(plot_for=phase, return_fig=True)
        assert len(ax.lines) == len(phase.seismogram_parameters)

    def test_plot_event_marks_picks(self, loaded_session: Session) -> None:
        """Verifies that the event plot marks both picks at their times on each seismogram.

        Args:
            loaded_session: The database session.
        """
        event = loaded_session.exec(select(AimbatEvent)).first()
        assert event is not None
        picked = event.seismograms[0]
        picked.phase_rows[0].refined_pick = picked.phase_rows[
            0
        ].initial_pick + Timedelta(seconds=2)
        loaded_session.add(picked)
        loaded_session.commit()

        _, ax = plot_seismograms(plot_for=event, return_fig=True)

        marks = {
            c.get_label(): c for c in ax.collections if isinstance(c, LineCollection)
        }
        t0_x = sorted(seg[0][0] for seg in marks["initial pick"].get_segments())
        assert t0_x == pytest.approx(
            sorted(
                mdates.date2num(s.phase_rows[0].initial_pick) for s in event.seismograms
            )
        )
        t1_segments = marks["refined pick"].get_segments()
        assert len(t1_segments) == 1
        assert t1_segments[0][0][0] == pytest.approx(
            mdates.date2num(picked.phase_rows[0].refined_pick)
        )

    def test_plot_station_marks_picks(
        self, loaded_session: Session, station: AimbatStation
    ) -> None:
        """Verifies that the station plot marks the refined pick at zero and the initial pick at its offset.

        Args:
            loaded_session: The database session.
            station: An AimbatStation instance.
        """
        seismogram = station.seismograms[0]
        seismogram.phase_rows[0].refined_pick = seismogram.phase_rows[
            0
        ].initial_pick + Timedelta(seconds=2)
        loaded_session.add(seismogram)
        loaded_session.commit()

        _, ax = plot_seismograms(plot_for=station, return_fig=True)

        marks = {
            c.get_label(): c for c in ax.collections if isinstance(c, LineCollection)
        }
        t1_x = [seg[0][0] for seg in marks["refined pick"].get_segments()]
        assert t1_x and all(x == 0.0 for x in t1_x)
        assert -2.0 in [seg[0][0] for seg in marks["initial pick"].get_segments()]

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
