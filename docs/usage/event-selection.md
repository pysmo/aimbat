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
the `phase` commands) also select a phase of the event, by name and
component:

```bash
aimbat align iccs 6a4a --phase PKP
aimbat align iccs 6a4a --phase SKS --component Q
```

A phase is identified by its name and component (see
[Components and Phases](components.md)). Either is enough when it selects one
phase of the event, and neither is needed when the event has only one phase.
A command whose selection matches several phases fails and lists them, for
example `SKS (Q), SKS (T)`. A phase without a component is selected with
`--component ''` when its name also has phases on components. The
`seismogram parameter` commands take the component from the seismogram, so
they select by name only.

`DEFAULT_PHASE` and `DEFAULT_COMPONENT` serve the phase as `DEFAULT_EVENT_ID`
serves the event, and count as given when set, an empty `DEFAULT_COMPONENT`
included. `DEFAULT_COMPONENT` applies without `--phase`, or with the name in
`DEFAULT_PHASE`, so another name given with `--phase` does not take its
component. Phase names and components are the same
across events, so one value of each covers a whole project:

```bash
export DEFAULT_PHASE=SKS
export DEFAULT_COMPONENT=Q
```

Like `DEFAULT_EVENT_ID`, they are plain environment variables and not AIMBAT
settings. In the shell, `phase switch <NAME> [<COMPONENT>]` does the same for
the session, and the prompt then shows the phase after the event ID:

```
aimbat [6a4a]> phase switch SKS Q
aimbat [6a4a/SKS (Q)]> align iccs
```

The phase must belong to the event of the shell. `phase switch` without a name
clears the phase, so the event's only phase is used again. `event switch` keeps
the phase, or the previous event's only phase, when the new event has a phase
of that name and component. Otherwise it keeps the phase of that name when the
new event has it on one component only, and clears the phase when it does not.

Listings that can cover several phases, such as `phase list` and
`snapshot list`, read `--phase` as a filter by name. They do not read
`DEFAULT_PHASE`, so they list every phase unless `--phase` is given.

## TUI

The TUI keeps its own event and phase selection, independent of the CLI and
shell.

Pressing `s` on a row in the **Project** tab's **Events** table (or `Enter`,
then **Select event**) selects that event. It then shows in the bar at the top
of the screen, is marked `▶` in the table, and populates the **Live data** and
**Snapshots** tabs.

An event with only one phase needs no further selection. Selecting an event
with several phases opens a list of its phases, such as `SKS (Q)` and
`SKS (T)`, and `p` switches phase. The bar shows the current phase. The
**Live data** and **Snapshots** tabs show that phase only, and stay empty
until a phase is chosen. Selecting another event keeps the current phase,
chosen or the previous event's only phase, when the event has a phase of that
name and component. Otherwise it keeps the phase of that name when the event
has it on one component only, and opens the list of phases when the event has
several.

## Python API

Processing functions in `aimbat.core` and `aimbat.actions` take the ID of a
phase, so there is no `DEFAULT_EVENT_ID` or `DEFAULT_PHASE` equivalent to set.
[`resolve_phase`][aimbat.core.resolve_phase] returns the phase of an event by
name and component, by either when it selects one phase, or the only phase of
the event when neither is given:

```python
from sqlmodel import Session, select
from aimbat.core import resolve_phase
from aimbat.db import engine
from aimbat.models import AimbatEvent

with Session(engine) as session:
    event = session.exec(select(AimbatEvent)).first()
    phase_id = resolve_phase(session, event.id).id
```
