from __future__ import annotations
from aimbat.lib.typing import SeismogramParameter
from aimbat.lib.models import AimbatSeismogram
from typing import TYPE_CHECKING
from pathlib import Path
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session, select
from importlib import reload
import aimbat.lib.seismogram as seismogram
import pytest
import random


if TYPE_CHECKING:
    from aimbat.lib.models import AimbatSeismogram
    from collections.abc import Generator
    from typing import Any
    from pytest import CaptureFixture
    from matplotlib.figure import Figure


class TestSeismogramBase:
    @pytest.fixture(autouse=True)
    def reload_modules(self, test_db_with_active_event: tuple[Path, Session]) -> None:
        reload(seismogram)

    @pytest.fixture
    def session(
        self, test_db_with_active_event: tuple[Path, Session]
    ) -> Generator[Session, Any, Any]:
        yield test_db_with_active_event[1]


class TestLibSeismogram(TestSeismogramBase):
    def test_lib_seismogram_uuid_dict_reversed(self, session: Session) -> None:
        import uuid

        for k, v in seismogram.seismogram_uuid_dict_reversed(session).items():
            assert isinstance(k, uuid.UUID)
            assert isinstance(v, str)


class TestDeleteSeismogram(TestSeismogramBase):
    def test_lib_delete_seismogram_by_id(self, session: Session) -> None:
        aimbat_seismogram = random.choice(list(session.exec(select(AimbatSeismogram))))
        id = aimbat_seismogram.id
        seismogram.delete_seismogram_by_id(session, id)
        assert (
            session.exec(
                select(AimbatSeismogram).where(AimbatSeismogram.id == id)
            ).one_or_none()
            is None
        )

    def test_cli_delete_seismogram_by_id(self, session: Session) -> None:
        from aimbat.app import app

        aimbat_seismogram = random.choice(list(session.exec(select(AimbatSeismogram))))
        id = aimbat_seismogram.id

        app(["seismogram", "delete", str(id)])
        session.flush()
        assert (
            session.exec(
                select(AimbatSeismogram).where(AimbatSeismogram.id == id)
            ).one_or_none()
            is None
        )

    def test_cli_delete_seismogram_by_id_with_wrong_id(self) -> None:
        from aimbat.app import app
        from uuid import uuid4

        id = uuid4()

        with pytest.raises(NoResultFound):
            app(["seismogram", "delete", str(id)])

    def test_cli_delete_seismogram_by_string(self, session: Session) -> None:
        from aimbat.app import app

        aimbat_seismogram = random.choice(list(session.exec(select(AimbatSeismogram))))
        id = aimbat_seismogram.id

        app(["seismogram", "delete", str(id)[:5]])
        session.flush()
        assert (
            session.exec(
                select(AimbatSeismogram).where(AimbatSeismogram.id == id)
            ).one_or_none()
            is None
        )


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
        assert (
            seismogram.get_seismogram_parameter(random_seismogram, parameter)
            == expected
        )
        assert getattr(random_seismogram.parameters, parameter) == expected

    def test_lib_get_seismogram_parameter_by_id(
        self, session: Session, random_seismogram: AimbatSeismogram
    ) -> None:
        import uuid

        assert (
            seismogram.get_seismogram_parameter_by_id(
                session, random_seismogram.id, SeismogramParameter.SELECT
            )
            is True
        )

        with pytest.raises(ValueError):
            seismogram.get_seismogram_parameter_by_id(
                session, uuid.uuid4(), SeismogramParameter.SELECT
            )

    def test_cli_get_seismogram_parameter_with_uuid(
        self, random_seismogram: AimbatSeismogram, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app

        app(
            ["seismogram", "get", str(random_seismogram.id), SeismogramParameter.SELECT]
        )
        captured = capsys.readouterr()
        assert "True" in captured.out

    def test_cli_get_seismogram_parameter_with_string(
        self, random_seismogram: AimbatSeismogram, capsys: CaptureFixture
    ) -> None:
        from aimbat.app import app

        app(
            [
                "seismogram",
                "get",
                str(random_seismogram.id)[:6],
                SeismogramParameter.SELECT,
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
        seismogram.set_seismogram_parameter(
            session, random_seismogram, SeismogramParameter.SELECT, False
        )

        assert (
            seismogram.get_seismogram_parameter(
                random_seismogram, SeismogramParameter.SELECT
            )
            is False
        )

    def test_lib_set_seismogram_parameter_by_id(
        self, session: Session, random_seismogram: AimbatSeismogram
    ) -> None:
        import uuid

        seismogram.set_seismogram_parameter_by_id(
            session, random_seismogram.id, SeismogramParameter.SELECT, False
        )

        assert (
            seismogram.get_seismogram_parameter(
                random_seismogram, SeismogramParameter.SELECT
            )
            is False
        )

        with pytest.raises(ValueError):
            seismogram.set_seismogram_parameter_by_id(
                session, uuid.uuid4(), SeismogramParameter.SELECT, False
            )

    def test_cli_set_seismogram_parameter_with_uuid(
        self, random_seismogram: AimbatSeismogram, session: Session
    ) -> None:
        from aimbat.app import app

        app(
            [
                "seismogram",
                "set",
                str(random_seismogram.id),
                SeismogramParameter.SELECT,
                "False",
            ]
        )
        session.refresh(random_seismogram)
        assert (
            seismogram.get_seismogram_parameter(
                random_seismogram, SeismogramParameter.SELECT
            )
            is False
        )

    def test_cli_set_seismogram_parameter_with_string(
        self, random_seismogram: AimbatSeismogram, session: Session
    ) -> None:
        from aimbat.app import app

        app(
            [
                "seismogram",
                "set",
                str(random_seismogram.id)[:6],
                SeismogramParameter.SELECT,
                "False",
            ]
        )
        session.refresh(random_seismogram)
        assert (
            seismogram.get_seismogram_parameter(
                random_seismogram, SeismogramParameter.SELECT
            )
            is False
        )


class TestGetAllSelectedSeismograms(TestSeismogramBase):
    def test_lib_get_selected_seismograms_for_active_event(
        self, session: Session
    ) -> None:
        assert len(seismogram.get_selected_seismograms(session)) == 13

    def test_lib_get_selected_seismograms_for_all_events(
        self, session: Session
    ) -> None:
        assert len(seismogram.get_selected_seismograms(session, all_events=True)) == 20


class TestPrintSeismogramTable(TestSeismogramBase):
    def test_lib_print_seismogram_table_no_format(self, capsys: CaptureFixture) -> None:
        seismogram.print_seismogram_table(format=False, all_events=False)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "id (shortened)" not in captured.out

    def test_lib_print_seismogram_table_format(self, capsys: CaptureFixture) -> None:
        seismogram.print_seismogram_table(format=True, all_events=False)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "id (shortened)" in captured.out

    def test_lib_print_seismogram_table_no_format_all_events(
        self, capsys: CaptureFixture
    ) -> None:
        seismogram.print_seismogram_table(format=False, all_events=True)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for all events" in captured.out
        assert "id (shortened)" not in captured.out

    def test_lib_print_seismogram_table_format_all_events(
        self, capsys: CaptureFixture
    ) -> None:
        seismogram.print_seismogram_table(format=True, all_events=True)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for all events" in captured.out
        assert "id (shortened)" in captured.out

    def test_cli_print_seismogram_table(self, capsys: CaptureFixture) -> None:
        from aimbat.app import app

        app(["seismogram", "list"])

        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "id (shortened)" in captured.out


class TestSeismogramPlot(TestSeismogramBase):
    @pytest.mark.mpl_image_compare
    def test_lib_plotseis_mpl(self) -> Figure:
        return seismogram.plot_seismograms()

    @pytest.mark.skip(reason="I con't know how to test QT yet.")
    def test_lib_plotseis_qt(
        self,
    ) -> None:
        _ = seismogram.plot_seismograms(use_qt=True)

    def test_cli_plotseis_mpl(self) -> None:
        from aimbat.app import app

        app(["seismogram", "plot"])
