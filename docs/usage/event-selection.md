# Selecting an event

Processing commands act on one event at a time. After import, the next step is
knowing which one to select before inspecting or aligning.

## Listing events

=== "CLI"

    ```bash
    aimbat event list
    ```

=== "Shell"

    ```bash
    event list
    ```

=== "TUI"

    The **Project** tab, under **Events**.

=== "API"

    ```python
    from sqlmodel import Session, select
    from aimbat.db import engine
    from aimbat.models import AimbatEvent

    with Session(engine) as session:
        events = session.exec(select(AimbatEvent)).all()
    ```

The CLI and TUI tables show each event's ID, origin time, and location, with
IDs truncated to the shortest prefix that other commands still accept
unambiguously. The API returns full model objects with untruncated IDs.

## CLI and shell

The event is a positional argument, either a full UUID or any unique prefix:

```bash
aimbat align iccs 6a4a
```

`--event` and `--event-id` are accepted equivalents.

For a run of commands on the same event, setting `DEFAULT_EVENT_ID` avoids
repeating it. AIMBAT uses it whenever no ID is given:

```bash
export DEFAULT_EVENT_ID=6a4a
aimbat align iccs
aimbat snapshot create "post-ICCS"
```

`unset DEFAULT_EVENT_ID` clears it. In the shell, `event switch <ID>` does the
same for the session and shows the ID in the prompt.

!!! note "Not an AIMBAT setting"

    `DEFAULT_EVENT_ID` is a plain shell environment variable read by the CLI
    argument parser. It has no `AIMBAT_` prefix, cannot be set in `.env`, and
    does not appear in `aimbat utils settings`.

## TUI

The TUI keeps its own event selection, independent of the CLI and shell.

Pressing `s` on a row in the **Project** tab's **Events** table (or `Enter`,
then **Select event**) selects that event. It then shows in the bar at the top
of the screen, is marked `▶` in the table, and populates the **Live data** and
**Snapshots** tabs.

## Python API

Core functions take an `event_id` directly, so there is no `DEFAULT_EVENT_ID`
equivalent to set. The event is queried and its `id` passed to whichever
function needs it:

```python
from sqlmodel import Session, select
from aimbat.db import engine
from aimbat.models import AimbatEvent

with Session(engine) as session:
    event = session.exec(select(AimbatEvent)).first()
    event_id = event.id
```
