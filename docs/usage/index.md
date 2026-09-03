# Using AIMBAT

AIMBAT has three interfaces: the command line, an interactive shell, and a
terminal UI. All three read and write the same project database, so a change
made in one is immediately visible to the others. There is no synchronisation
step.

## The three interfaces

### Command line

```bash
aimbat <command> [options]
```

Best for bulk data ingestion and scripting. Each operation is a single command
that runs, prints its result, and exits non-zero on error. Commands are grouped
(`data`, `event`, `align`, ...), and `--help` works at every level.

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

### Interactive shell

```bash
aimbat shell
```

Best for interactive command-line work. It wraps the same commands without the
leading `aimbat`, and keeps an event context so `--event` need not be repeated.
Keeping the session open avoids the per-command startup cost, and tab completion
doubles as command discovery.

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

## Choosing an event

A project can hold many events, but processing acts on one at a time. Select it
before running ICCS, MCCC, or taking a snapshot. The CLI and shell track this
selection separately from the TUI. See [Selecting an Event](event-selection.md).

## Live data and saving

The picks and parameters for the selected event are the **live data**: the
working set every interface reads and writes. Changes are written to the
database immediately. There is no save step and no undo. See
[Snapshots](snapshots.md) to capture a state to roll back to, and
[The ICCS Stack](iccs-stack.md#live-data) for what the live data includes.

## What every interface enforces

- **Validation.** A parameter change that would produce an invalid
    configuration, such as a time window extending past a seismogram's data, is
    rejected, and the live data are left unchanged.
- **Schema currency.** A project whose schema predates the installed AIMBAT
    version is refused until it is upgraded. See [Project](project.md).
- **External changes.** The TUI polls the database every five seconds and picks
    up changes made from the CLI or shell.

Logging is controlled by `AIMBAT_LOG_LEVEL` and `AIMBAT_LOGFILE`, or `--debug`
for one invocation. See [Aimbat Defaults](defaults.md).

!!! warning "Unexpected warnings"

    A warning before any parameter has been changed usually means something is
    wrong with the data themselves, for example a seismogram with incomplete
    data.
