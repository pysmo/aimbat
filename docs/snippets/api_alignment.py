from sqlmodel import Session
from aimbat.db import engine
from aimbat.core import (
    create_iccs_instance,
    create_snapshot,
    get_default_event,
    run_iccs,
    run_mccc,
)

with Session(engine) as session:
    event = get_default_event(session)
    assert event is not None

    bound = create_iccs_instance(session, event)

    run_iccs(session, bound.iccs, autoflip=True, autoselect=True)
    create_snapshot(session, event, comment="after ICCS")

    run_mccc(session, event, bound.iccs, all_seismograms=False)
    create_snapshot(session, event, comment="after MCCC")
