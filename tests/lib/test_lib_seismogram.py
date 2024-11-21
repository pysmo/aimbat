from importlib import reload
from sqlmodel import Session


class TestLibSeismogram:
    def test_get_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, seismogram

        reload(project)

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            assert (
                seismogram.seismogram_get_parameter(
                    session=session, seismogram_id=1, parameter_name="select"
                )
                is True
            )
            assert (
                seismogram.seismogram_get_parameter(
                    session=session, seismogram_id=1, parameter_name="t1"
                )
                is None
            )
            assert (
                seismogram.seismogram_get_parameter(
                    session=session, seismogram_id=1, parameter_name="t2"
                )
                is None
            )

    def test_set_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, seismogram

        reload(project)

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            seismogram.seismogram_set_parameter(
                session=session,
                seismogram_id=1,
                parameter_name="select",
                parameter_value=False,
            )
            assert (
                seismogram.seismogram_get_parameter(
                    session=session, seismogram_id=1, parameter_name="select"
                )
                is False
            )
