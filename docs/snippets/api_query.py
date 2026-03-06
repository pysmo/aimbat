from sqlmodel import Session, select
from aimbat.db import engine
from aimbat.models import AimbatEvent, AimbatSeismogram

with Session(engine) as session:
    events = session.exec(select(AimbatEvent)).all()
    for event in events:
        print(f"{event.time}  {len(event.seismograms)} seismograms")

    # Filter — seismograms marked as selected
    selected = session.exec(
        select(AimbatSeismogram).where(
            AimbatSeismogram.parameters.has(select=True)  # type: ignore[attr-defined]
        )
    ).all()
