from sqlmodel import Session, select
from datetime import timedelta
from random import randrange
from aimbat.lib.models import AimbatEvent


class TestLibEvent:
    def test_get_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, event

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            assert event.event_get_parameter(
                session=session, event_id=1, parameter_name="window_pre"
            ) == timedelta(seconds=-7.5)
            assert event.event_get_parameter(
                session=session, event_id=1, parameter_name="window_post"
            ) == timedelta(seconds=7.5)

            select_aimbat_event = select(AimbatEvent).where(AimbatEvent.id == 1)
            assert event.event_get_selected_event(session) is None
            aimbat_event = session.exec(select_aimbat_event).one()
            assert aimbat_event.selected is False
            event.event_set_selected_event(session, aimbat_event)
            assert aimbat_event.selected is True
            assert event.event_get_selected_event(session) is aimbat_event
            event.event_set_selected_event(session, aimbat_event)

    def test_set_parameter(self, sac_file_good) -> None:  # type: ignore
        from aimbat.lib import db, project, data, event

        project.project_new()

        data.data_add_files([sac_file_good], filetype="sac")

        with Session(db.engine) as session:
            window_post_new = timedelta(seconds=randrange(10))
            event.event_set_parameter(
                session=session,
                event_id=1,
                parameter_name="window_post",
                parameter_value=window_post_new,
            )
            assert (
                event.event_get_parameter(
                    session=session, event_id=1, parameter_name="window_post"
                )
                == window_post_new
            )
