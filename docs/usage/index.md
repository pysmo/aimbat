# Using AIMBAT

AIMBAT provides three interfaces — the command line, an interactive shell, and a
terminal UI — that read from and write to the same project database. There is no
synchronisation step; every interface reflects the current state of the project.

## Choosing an event to work on

A project can contain multiple events, but processing operates on one at a time.
Before running ICCS, MCCC, or taking a snapshot, select the event to work on.
That selection determines the **[live data](iccs-stack.md#live-data)** — the
seismogram picks and parameters that every interface reads from and writes to.

See [Selecting an Event](event-selection.md) for how to choose one in each
interface.

## Saving progress

Parameter changes (picks, filter settings, select/flip flags, ...) are applied
to the live data immediately, in every interface. There is no separate save step
and no undo. See [Snapshots](snapshots.md) to capture a point-in-time copy for
later rollback.

## Interfaces

### Command Line Interface (CLI)

```bash
aimbat <command> [options]
```

Best for bulk data ingestion and scripting — chaining commands in shell scripts,
as opposed to the Python API. Each operation is a single command that runs,
prints its result, and exits.

Run `aimbat --help` to list the top-level subcommands. Commands are grouped
(`data`, `event`, `align`, ...), and `--help` works at every level, so
`aimbat data --help` lists that group's subcommands and `aimbat data add --help`
shows the options for one specific command. Every command exits non-zero on
error:

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

### Interactive Shell

```bash
aimbat shell
```

Best for interactive command-line work: tab completion speeds up writing
commands, and keeping the session open avoids the per-command startup cost, so
commands run faster than through the CLI. It wraps the same commands, without
the leading `aimbat`, and adds command history and an event context that removes
the need to repeat `--event`. Tab completion doubles as command discovery —
press Tab at any point to see the available subcommands or flags — and `--help`
still works on any command:

```
aimbat> event switch 6a4a
aimbat [6a4a]> align iccs
```

After each command the shell reports whether the ICCS instance for the current
event is still valid, and rejects a parameter change that would invalidate it
before it is written to the database. Exit with `exit`, `quit`, `q`, or
**Ctrl+D**.

### Terminal UI (TUI)

```bash
aimbat tui
```

Where most processing work happens, once data have been added — typically via
the CLI or shell. A full-screen, keyboard-driven interface covering the core
iterative workflow: adjusting parameters, running ICCS, inspecting alignment,
managing snapshots. Three tabs cover the whole project:

- **Project** — events and stations; select the event to work on here.
- **Live data** — the seismogram table for the selected event.
- **Snapshots** — saved parameter snapshots for the selected event.

Each table row has its own actions, shown as footer shortcuts when the row has
focus, or via `Enter`. Press `?` for the full, context-aware list of key
bindings.

## Shared concepts

All interfaces read and write the same `aimbat.db` — see [Project](project.md)
for its location and how to override it. Changes made in one interface are
visible in the others immediately; the TUI polls for external changes every five
seconds. Logging is controlled by `AIMBAT_LOG_LEVEL` / `AIMBAT_LOGFILE`, or
`--debug` for a single invocation — see [Aimbat Defaults](defaults.md).

Every parameter change is validated before it is accepted; a change that would
produce an invalid configuration — for example, a time window extending beyond a
seismogram's data — is rejected, and the live data are left unchanged.

!!! warning "Unexpected warnings"

    If a warning appears before any parameter changes have been made, something is
    likely wrong with the data themselves (e.g. a seismogram with incomplete data).
