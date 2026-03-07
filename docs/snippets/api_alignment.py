from sqlmodel import Session, select
from aimbat.db import engine
from aimbat.core import (
    create_iccs_instance,
    create_snapshot,
    run_iccs,
    run_mccc,
)
from aimbat.models import AimbatEvent

with Session(engine) as session:
    event = session.exec(select(AimbatEvent)).first()
    assert event is not None

    bound = create_iccs_instance(session, event)

    run_iccs(session, bound.iccs, autoflip=True, autoselect=True)
    create_snapshot(session, event, comment="after ICCS")

    run_mccc(session, event, bound.iccs, all_seismograms=False)
    create_snapshot(session, event, comment="after MCCC")
