from aimbat.app import app
from aimbat.aimbat_types import SeismogramParameter
from aimbat.models import AimbatSeismogram
from sqlmodel import Session, select
from sqlalchemy import Engine
from typing import Any
from matplotlib.figure import Figure
from collections.abc import Generator
import aimbat.core._seismogram as seismogram
import pytest
import random
import json


class TestSeismogramBase:
    @pytest.fixture(autouse=True)
    def session(
        self, fixture_engine_session_with_active_event: tuple[Engine, Session]
    ) -> Generator[Session, Any, Any]:
        session = fixture_engine_session_with_active_event[1]
        yield session


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
        aimbat_seismogram = random.choice(list(session.exec(select(AimbatSeismogram))))
        id = aimbat_seismogram.id

        with pytest.raises(SystemExit) as excinfo:
            app(["seismogram", "delete", str(id)])

        assert excinfo.value.code == 0

        session.flush()
        assert (
            session.exec(
                select(AimbatSeismogram).where(AimbatSeismogram.id == id)
            ).one_or_none()
            is None
        )

    def test_cli_delete_seismogram_by_id_with_wrong_id(self) -> None:
        import uuid

        from aimbat import settings

        settings.log_level = "INFO"

        id = uuid.uuid4()

        with pytest.raises(SystemExit) as excinfo:
            app(["seismogram", "delete", str(id)])

        assert excinfo.value.code == 1

    def test_cli_delete_seismogram_by_string(self, session: Session) -> None:
        aimbat_seismogram = random.choice(list(session.exec(select(AimbatSeismogram))))
        id = aimbat_seismogram.id

        with pytest.raises(SystemExit) as excinfo:
            app(["seismogram", "delete", str(id)[:5]])

        assert excinfo.value.code == 0

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
        from aimbat.utils import get_active_event

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
        self, random_seismogram: AimbatSeismogram, capsys: pytest.CaptureFixture
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(
                [
                    "seismogram",
                    "get",
                    str(random_seismogram.id),
                    SeismogramParameter.SELECT,
                ]
            )

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "True" in captured.out

    def test_cli_get_seismogram_parameter_with_string(
        self, random_seismogram: AimbatSeismogram, capsys: pytest.CaptureFixture
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(
                [
                    "seismogram",
                    "get",
                    str(random_seismogram.id)[:6],
                    SeismogramParameter.SELECT,
                ]
            )

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "True" in captured.out


class TestSetSeismogramParameter(TestSeismogramBase):
    @pytest.fixture
    def random_seismogram(
        self, session: Session
    ) -> Generator[AimbatSeismogram, Any, Any]:
        from aimbat.utils import get_active_event

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
        with pytest.raises(SystemExit) as excinfo:
            app(
                [
                    "seismogram",
                    "set",
                    str(random_seismogram.id),
                    SeismogramParameter.SELECT,
                    "False",
                ]
            )

        assert excinfo.value.code == 0

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
        with pytest.raises(SystemExit) as excinfo:
            app(
                [
                    "seismogram",
                    "set",
                    str(random_seismogram.id)[:6],
                    SeismogramParameter.SELECT,
                    "False",
                ]
            )

        assert excinfo.value.code == 0

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
    def test_lib_print_seismogram_table_no_short(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        seismogram.print_seismogram_table(session, short=False, all_events=False)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "ID (shortened)" not in captured.out

    def test_lib_print_seismogram_table_short(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        seismogram.print_seismogram_table(session, short=True, all_events=False)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "ID (shortened)" in captured.out

    def test_lib_print_seismogram_table_no_short_all_events(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        seismogram.print_seismogram_table(session, short=False, all_events=True)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for all events" in captured.out
        assert "ID (shortened)" not in captured.out

    def test_lib_print_seismogram_table_short_all_events(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        seismogram.print_seismogram_table(session, short=True, all_events=True)
        captured = capsys.readouterr()
        assert "AIMBAT seismograms for all events" in captured.out
        assert "ID (shortened)" in captured.out

    def test_cli_print_seismogram_table(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["seismogram", "list"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        assert "AIMBAT seismograms for event" in captured.out
        assert "ID (shortened)" in captured.out


class TestDumpSeismogram(TestSeismogramBase):
    def test_lib_dump_data(
        self, session: Session, capsys: pytest.CaptureFixture
    ) -> None:
        seismogram.dump_seismogram_table(session)
        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatSeismogram(**i)

    def test_cli_dump_data(self, capsys: pytest.CaptureFixture) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["seismogram", "dump"])

        assert excinfo.value.code == 0

        captured = capsys.readouterr()
        loaded_json = json.loads(captured.out)
        assert isinstance(loaded_json, list)
        assert len(loaded_json) > 0
        for i in loaded_json:
            _ = AimbatSeismogram(**i)


class TestSeismogramPlot(TestSeismogramBase):
    @pytest.mark.mpl_image_compare
    def test_lib_plotseis_mpl(self, session: Session) -> Figure:
        return seismogram.plot_all_seismograms(session)

    @pytest.mark.skip(reason="I con't know how to test QT yet.")
    def test_lib_plotseis_qt(
        self,
        session: Session,
    ) -> None:
        _ = seismogram.plot_all_seismograms(session, use_qt=True)

    def test_cli_plotseis_mpl(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            app(["seismogram", "plot"])

        assert excinfo.value.code == 0
