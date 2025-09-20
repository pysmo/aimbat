from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path
from sqlmodel import Session
from aimbat.lib.seismogram import SeismogramParameter
import pytest
import random


if TYPE_CHECKING:
    from aimbat.lib.models import AimbatSeismogram
    from collections.abc import Generator
    from typing import Any
    from sqlalchemy.engine import Engine
    from pytest import CaptureFixture
    from matplotlib.figure import Figure


class TestSeismogramBase:
    @pytest.fixture
    def session(
        self, test_db_with_active_event: tuple[Path, str, Engine, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_active_event[3]

    @pytest.fixture
    def db_url(
        self, test_db_with_active_event: tuple[Path, str, Engine, Session]
    ) -> Generator[str, Any, Any]:
        yield test_db_with_active_event[1]


class TestLibSeismogram(TestSeismogramBase):
    def test_lib_seismogram_uuid_dict_reversed(self, session: Session) -> None:
        from aimbat.lib.seismogram import seismogram_uuid_dict_reversed
        import uuid

        for k, v in seismogram_uuid_dict_reversed(session).items():
            assert isinstance(k, uuid.UUID)
            assert isinstance(v, str)


class TestGetSeismogramParameter(TestSeismogramBase):
    @pytest.fixture
    def random_seismogram(
        self, session: Session
    ) -> Generator[AimbatSeismogram, Any, Any]:
        from aimbat.lib.event import get_active_event

        yield random.choice(list(get_active_event(session).seismograms))

    @pytest.mark.parametrize(
        "parameter, expected",
        [
            (SeismogramParameter.SELECT, True),
            (SeismogramParameter.FLIP, False),
            (SeismogramParameter.T1, None),
        ],
    )
    def test_lib_get_seismogram_parameter(
        self,
        random_seismogram: AimbatSeismogram,
        parameter: SeismogramParameter,
        expected: Any,
    ) -> None:
        from aimbat.lib.seismogram import get_seismogram_parameter

        assert get_seismogram_parameter(random_seismogram, parameter) == expected
        assert getattr(random_seismogram.parameters, parameter) == expected

    def test_lib_get_seismogram_parameter_by_id(
        self, session: Session, random_seismogram: AimbatSeismogram
    ) -> None:
        from aimbat.lib.seismogram import (
            get_seismogram_parameter_by_id,
            SeismogramParameter,
        )
        import uuid

        assert (
            get_seismogram_parameter_by_id(
                session, random_seismogram.id, SeismogramParameter.SELECT
            )
            is True
        )

        with pytest.raises(ValueError):
            get_seismogram_parameter_by_id(
                session, uuid.uuid4(), SeismogramParameter.SELECT
            )

    def test_cli_get_seismogram_parameter_with_uuid(
        self, db_url: str, random_seismogram: AimbatSeismogram, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.seismogram import SeismogramParameter

        app(
            [
                "seismogram",
                "get",
                str(random_seismogram.id),
                SeismogramParameter.SELECT,
                "--db-url",
                db_url,
            ]
        )
        captured = capsys.readouterr()
        assert "True" in captured.out

    def test_cli_get_seismogram_parameter_with_string(
        self, db_url: str, random_seismogram: AimbatSeismogram, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.seismogram import SeismogramParameter

        app(
            [
                "seismogram",
                "get",
                str(random_seismogram.id)[:6],
                SeismogramParameter.SELECT,
                "--db-url",
                db_url,
            ]
        )
        captured = capsys.readouterr()
        assert "True" in captured.out


class TestSetSeismogramParameter(TestSeismogramBase):
    @pytest.fixture
    def random_seismogram(
        self, session: Session
    ) -> Generator[AimbatSeismogram, Any, Any]:
        from aimbat.lib.event import get_active_event

        seismogram = random.choice(list(get_active_event(session).seismograms))
        assert seismogram.parameters.select is True
        yield seismogram

    def test_lib_set_seismogram_parameter(
        self, session: Session, random_seismogram: AimbatSeismogram
    ) -> None:
        from aimbat.lib.seismogram import (
            set_seismogram_parameter,
            get_seismogram_parameter,
            SeismogramParameter,
        )

        set_seismogram_parameter(
            session, random_seismogram, SeismogramParameter.SELECT, False
        )

        assert (
            get_seismogram_parameter(random_seismogram, SeismogramParameter.SELECT)
            is False
        )

    def test_lib_set_seismogram_parameter_by_id(
        self, session: Session, random_seismogram: AimbatSeismogram
    ) -> None:
        from aimbat.lib.seismogram import (
            set_seismogram_parameter_by_id,
            get_seismogram_parameter,
            SeismogramParameter,
        )
        import uuid

        set_seismogram_parameter_by_id(
            session, random_seismogram.id, SeismogramParameter.SELECT, False
        )

        assert (
            get_seismogram_parameter(random_seismogram, SeismogramParameter.SELECT)
            is False
        )

        with pytest.raises(ValueError):
            set_seismogram_parameter_by_id(
                session, uuid.uuid4(), SeismogramParameter.SELECT, False
            )

    def test_cli_set_seismogram_parameter_with_uuid(
        self, db_url: str, random_seismogram: AimbatSeismogram, session: Session
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.seismogram import SeismogramParameter, get_seismogram_parameter

        app(
            [
                "seismogram",
                "set",
                str(random_seismogram.id),
                SeismogramParameter.SELECT,
                "False",
                "--db-url",
                db_url,
            ]
        )
        session.refresh(random_seismogram)
        assert (
            get_seismogram_parameter(random_seismogram, SeismogramParameter.SELECT)
            is False
        )

    def test_cli_set_seismogram_parameter_with_string(
        self, db_url: str, random_seismogram: AimbatSeismogram, session: Session
    ) -> None:
        from aimbat.app import app
        from aimbat.lib.seismogram import SeismogramParameter, get_seismogram_parameter

        app(
            [
                "seismogram",
                "set",
                str(random_seismogram.id)[:6],
                SeismogramParameter.SELECT,
                "False",
                "--db-url",
                db_url,
            ]
        )
        session.refresh(random_seismogram)
        assert (
            get_seismogram_parameter(random_seismogram, SeismogramParameter.SELECT)
            is False
        )


class TestGetAllSelectedSeismograms(TestSeismogramBase):
    def test_lib_get_selected_seismograms_for_active_event(
        self, session: Session
    ) -> None:
        from aimbat.lib.seismogram import get_selected_seismograms

        assert len(get_selected_seismograms(session)) == 13

    def test_lib_get_selected_seismograms_for_all_events(
        self, session: Session
    ) -> None:
        from aimbat.lib.seismogram import get_selected_seismograms

        assert len(get_selected_seismograms(session, all_events=True)) == 20


class TestPrintSeismogramTable(TestSeismogramBase):
    def test_lib_print_seismogram_table_no_format(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.seismogram import print_seismogram_table

        print_seismogram_table(session, format=False, all_events=False)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "id (shortened)" not in captured.out

    def test_lib_print_seismogram_table_format(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.seismogram import print_seismogram_table

        print_seismogram_table(session, format=True, all_events=False)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "id (shortened)" in captured.out

    def test_lib_print_seismogram_table_no_format_all_events(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.seismogram import print_seismogram_table

        print_seismogram_table(session, format=False, all_events=True)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for all events" in captured.out
        assert "id (shortened)" not in captured.out

    def test_lib_print_seismogram_table_format_all_events(
        self, session: Session, capsys: CaptureFixture
    ) -> None:
        from aimbat.lib.seismogram import print_seismogram_table

        print_seismogram_table(session, format=True, all_events=True)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for all events" in captured.out
        assert "id (shortened)" in captured.out

    def test_cli_print_seismogram_table(
        self, db_url: str, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app

        app(["seismogram", "list", "--db-url", db_url])

        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "id (shortened)" in captured.out


class TestSeismogramPlot(TestSeismogramBase):
    @pytest.mark.mpl_image_compare
    def test_lib_plotseis_mpl(self, session: Session) -> Figure:
        from aimbat.lib.seismogram import plot_seismograms

        return plot_seismograms(session)

    @pytest.mark.skip(reason="I con't know how to test QT yet.")
    def test_lib_plotseis_qt(self, session: Session) -> None:
        from aimbat.lib.seismogram import plot_seismograms

        _ = plot_seismograms(session, use_qt=True)

    def test_cli_plotseis_mpl(self, db_url: str) -> None:
        from aimbat.app import app

        app(["seismogram", "plot", "--db-url", db_url])
