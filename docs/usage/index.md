# Using AIMBAT

AIMBAT has four interfaces: the command line, an interactive shell, a terminal
UI, and a Python API. All four read and write the same project database, so a
change made in one is immediately visible to the others. There is no
synchronisation step.

## The four interfaces

### Command line

```bash
aimbat <command> [options]
```

One operation per invocation: it runs, prints its result, and exits non-zero on
error. Commands are grouped (`data`, `event`, `align`, ...), and `--help` works
at every level.

A full CLI session:

```bash
aimbat project create
aimbat data add *.sac
aimbat event list                # note the event ID
export DEFAULT_EVENT_ID=6a4a
aimbat align iccs --autoflip --autoselect
aimbat snapshot create "post-ICCS"
aimbat align mccc
aimbat snapshot create "post-MCCC"
```

Chaining calls like this in a shell script works for a simple, fixed sequence.
For anything with branching, loops, or error handling, use the
[Python API](#python-api) instead.

### Interactive shell

```bash
aimbat shell
```

Wraps the same commands without the leading `aimbat`, and keeps an event context
so `--event` need not be repeated. Keeping the session open avoids the
per-command startup cost, and tab completion doubles as command discovery.

```
aimbat> event switch 6a4a
aimbat [6a4a]> align iccs
```

After each command the shell reports whether the current event's ICCS instance
is still valid, and rejects a parameter change that would invalidate it before
it reaches the database. Exit with `exit`, `quit`, `q`, or **Ctrl+D**.

### Terminal UI

```bash
aimbat tui
```

Where most processing happens once data have been added. A full-screen,
keyboard-driven interface over three tabs:

- **Project.** Events and stations; select the event to work on here.
- **Live data.** The seismogram table for the selected event.
- **Snapshots.** Saved parameter snapshots for the selected event.

Each row has its own actions, shown as footer shortcuts when the row has focus,
or via `Enter`. Press `?` for the full, context-aware key bindings.

### Python API

For anything beyond a short, fixed sequence of commands, this is more robust
than scripting the CLI: real control flow and error handling, instead of gluing
shell commands together. Paired with a modern IDE, it provides a pleasant
development experience (e.g. auto-completion). Mixing it with the CLI, shell, or
TUI on the same project is fine; all four read and write the same database.

A full API session, mirroring the CLI one above:

```python
from pathlib import Path

from sqlmodel import Session, select
from aimbat.core import (
    add_data_to_project,
    create_iccs_instance,
    create_project,
    create_snapshot,
    run_iccs,
    run_mccc,
)
from aimbat.db import engine
from aimbat.io import DataType
from aimbat.models import AimbatEvent

create_project(engine)

with Session(engine) as session:
    add_data_to_project(session, sorted(Path().glob("*.sac")), DataType.SAC)
    event = session.exec(select(AimbatEvent)).first()
    create_snapshot(session, event, comment="import")  # add_data_to_project doesn't auto-snapshot like data add

    bound = create_iccs_instance(session, event)  # an ICCS instance bound to this event
    run_iccs(session, event, bound.iccs, autoflip=True, autoselect=True)
    create_snapshot(session, event, comment="post-ICCS")

    run_mccc(session, event, bound.iccs, all_seismograms=False)
    create_snapshot(session, event, comment="post-MCCC")
```

!!! tip "Working with a session"

    Every database operation needs a `Session`: a SQLAlchemy object that tracks
    changes against the project database until they're committed, opened as a
    context manager so it always closes cleanly. Core functions like the ones above
    commit internally; querying and mutating models directly needs an explicit
    `commit()` too.

See each chapter's API tab or "Python API" section for the calls behind that
chapter's workflow, and [Recipes](recipes.md) for API fundamentals and
cross-cutting scripts.

## Choosing an event

A project can hold many events, but processing acts on one at a time, so it
needs to be selected before running ICCS, MCCC, or taking a snapshot. The CLI
and shell track this selection separately from the TUI; the Python API has no
such state; every call takes the event explicitly. See
[Selecting an Event](event-selection.md).

## Live data and saving

The picks and parameters for the selected event are the **live data**: the
working set every interface reads and writes. Changes are written to the
database immediately. There is no save step and no undo. See
[Snapshots](snapshots.md) to capture a state to roll back to, and
[The ICCS Stack](iccs-stack.md#live-data) for what the live data includes.

## Notes

Every event, station, seismogram, and snapshot can carry a freeform Markdown
note, for recording observations or decisions.

=== "CLI"

    ```bash
    aimbat event note read <ID>
    aimbat event note edit <ID>  # opens $EDITOR, saves on exit
    ```

    Same pattern for `station`, `seismogram`, and `snapshot`. With no note yet,
    `read` prints `(no note)` and `edit` opens an empty buffer; the note saves when
    the editor closes without error.

=== "Shell"

    ```bash
    event note read <ID>
    event note edit <ID>
    ```

    Same "no note yet" behaviour as the CLI.

=== "TUI"

    The **Note** panel next to a table shows the highlighted row's note, with
    **View** and **Edit** tabs (moving the cursor to a row is enough; `Enter` opens
    the row's action menu instead). An edit saves automatically when the Edit tab
    loses focus or the View tab is selected. With no note yet, the View tab shows a
    placeholder instead.

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import get_note_content, save_note

    with Session(engine) as session:
        content = get_note_content(session, "event", event_id)
        save_note(session, "event", event_id, "some note text")
    ```

    `target` is one of `event`, `station`, `seismogram`, `snapshot`. With no note
    yet, `get_note_content` returns an empty string.

## What every interface enforces

- **Validation.** A parameter change that would produce an invalid
    configuration, such as a time window extending past a seismogram's data, is
    rejected, and the live data are left unchanged.
- **Schema currency.** A project whose schema predates the installed AIMBAT
    version is refused until it is upgraded, for the CLI, shell, and TUI. Code
    that imports `aimbat.db.engine` directly gets a warning instead of a hard
    failure, unless `AIMBAT_STRICT_SCHEMA_CHECK=true`. See
    [Project](project.md).
- **External changes.** The TUI polls the database every five seconds and picks
    up changes made from the CLI or shell.

Logging is controlled by `AIMBAT_LOG_LEVEL` and `AIMBAT_LOGFILE`, or `--debug`
for one invocation. See [Aimbat Defaults](defaults.md).

!!! warning "Unexpected warnings"

    A warning before any parameter has been changed usually means something is wrong
    with the data themselves, for example a seismogram with incomplete data.
