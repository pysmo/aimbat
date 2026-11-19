# Selecting an event

Processing commands act on one phase of one event at a time. An event has a
[phase](phases.md) for each seismic phase picked in its data, for example P
alone, or P and PKP. After import, the next step is knowing which event and
phase to select before inspecting or aligning.

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

The CLI and TUI tables show each event's ID, origin time, location and phases,
with IDs truncated to the shortest prefix that other commands still accept
unambiguously. The API returns full model objects with untruncated IDs.
`aimbat phase list` shows the phases of an event, or of every event, with their
seismogram counts and processing state.

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

### Selecting a phase

Commands that process data (`align`, `tool`, `plot`, `snapshot create`, and
the `phase parameter` and `seismogram parameter` commands) also select a phase
of the event, by name:

```bash
aimbat align iccs 6a4a --phase PKP
```

The name is not needed when the event has only one phase, which is then used.
For an event with several phases, a command without a name fails and lists the
phases of the event.

`DEFAULT_PHASE` serves the phase as `DEFAULT_EVENT_ID` serves the event. Phase
names are the same across events, so one value covers a whole project:

```bash
export DEFAULT_PHASE=P
```

Like `DEFAULT_EVENT_ID`, it is a plain environment variable and not an AIMBAT
setting. In the shell, `phase switch <NAME>` does the same for the session,
and the prompt then shows the phase after the event ID:

```
aimbat [6a4a]> phase switch PKP
aimbat [6a4a/PKP]> align iccs
```

The phase must belong to the event of the shell. `phase switch` without a name
clears the phase, so the event's only phase is used again. `event switch` to an
event without the phase also clears it.

Listings that can cover several phases, such as `phase list` and
`snapshot list`, read `--phase` as a filter by name. They do not read
`DEFAULT_PHASE`, so they list every phase unless `--phase` is given.

## TUI

The TUI keeps its own event selection, independent of the CLI and shell.

Pressing `s` on a row in the **Project** tab's **Events** table (or `Enter`,
then **Select event**) selects that event. It then shows in the bar at the top
of the screen, is marked `▶` in the table, and populates the **Live data** and
**Snapshots** tabs.

The TUI processes the only phase of the selected event. For an event with
several phases it shows a notice, and processing is done with the CLI until the
TUI can select a phase.

## Python API

Processing functions in `aimbat.core` and `aimbat.actions` take the ID of a
phase, so there is no `DEFAULT_EVENT_ID` or `DEFAULT_PHASE` equivalent to set.
[`resolve_phase`][aimbat.core.resolve_phase] returns the phase of an event by
name, or the only phase of the event when no name is given:

```python
from sqlmodel import Session, select
from aimbat.core import resolve_phase
from aimbat.db import engine
from aimbat.models import AimbatEvent

with Session(engine) as session:
    event = session.exec(select(AimbatEvent)).first()
    phase_id = resolve_phase(session, event.id).id
```
