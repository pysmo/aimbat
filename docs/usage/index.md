# Using AIMBAT

AIMBAT provides four interfaces that all read from and write to the **same
project database**. You can switch between them at any point — run alignment
from the CLI, inspect the result in the TUI, tweak a parameter in the shell,
then take a snapshot from the GUI. There is no synchronisation step; every
interface always reflects the current state of the project.

---

## Interfaces

### Command Line Interface (CLI)

```bash
aimbat <command> [options]
```

The CLI is the most direct interface. Every operation is a single command that
runs, prints its result, and exits. It is the natural choice for scripting,
batch jobs, and any task where you already know what you want to do.

Every command accepts `--help` for a full option listing. Most processing
commands require an event to operate on. Pass the event ID as a positional
argument:

```bash
aimbat align iccs 6a4a
```

You can also use the named form (`--event` or `--event-id`) if you prefer:

```bash
aimbat align iccs --event 6a4a
```

Alternatively, set the `DEFAULT_EVENT_ID` environment variable to avoid
repeating the ID every time:

```bash
export DEFAULT_EVENT_ID=6a4a
aimbat align iccs
```

IDs can be supplied as the full UUID or any unique prefix.

All commands exit with a non-zero status on error, making them safe to chain
in shell scripts:

```bash
aimbat project create
aimbat data add *.sac   # automatically snapshots each newly imported event
export DEFAULT_EVENT_ID=$(aimbat event dump | jq -r '.[0].id')
aimbat align iccs --autoflip --autoselect
aimbat snapshot create "post-ICCS"
aimbat snapshot results <SNAPSHOT_ID> --output results.json  # export ICCS picks
# or continue to MCCC for formal timing uncertainties:
aimbat align mccc
aimbat snapshot create "post-MCCC"
aimbat snapshot results <SNAPSHOT_ID> --output results.json
```

---

### Interactive Shell

```bash
aimbat shell
aimbat shell --event <ID>    # start in the context of a specific event
```

The shell is a persistent session that wraps all CLI commands with tab
completion, command history (saved to `~/.aimbat_history`), and live ICCS
feedback. Commands are identical to the CLI but without the leading `aimbat`:

```
aimbat> event list
aimbat> align iccs
```

The shell maintains a local **event context** that can be pre-selected on
launch or switched at any time. When an event is selected, the shell
automatically injects it into all relevant commands:

```
aimbat [6a4a]> event switch <ID>
```

After every command the shell prints whether the ICCS instance for the current
event is still valid, so you always know whether alignment is ready to run.

Parameter validation in the shell is stricter than the CLI: setting a parameter
that would produce an invalid ICCS configuration is rejected before anything is
written to the database, and the error message explains exactly why.

Exit with `exit`, `quit`, `q`, or **Ctrl+D**.

---

### Terminal UI (TUI)

```bash
aimbat tui           # via main CLI
aimbat-tui           # standalone entry point (same app)
aimbat tui --debug   # enable verbose logging
```

The TUI is a full-screen, keyboard-driven interface built for efficient
processing. It is best suited to the core iterative workflow — adjusting
parameters, running ICCS, inspecting alignment, managing snapshots — all
without leaving the terminal.

#### Layout

```
┌─ AIMBAT ────────────────────────────────────────────────────────┐
│ ▶ 2000-01-01 12:00:00  |  45.100°, 120.400°  ● ICCS ready        │  ← event bar
├─────────────────────────────────────────────────────────────────┤
│  Project │ Live data │ Snapshots                                 │  ← tabs
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │  ...                                                         │ │
│ └──────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ i Add Data  p Parameters  t Tools  a Align  n New Snapshot  q Quit│ ← footer
└─────────────────────────────────────────────────────────────────┘
```

The **event bar** shows the event currently selected for processing and the
ICCS status (`● ICCS ready` / `○ no ICCS`).

The **footer** is both project-state- and table-aware. Actions that require an
event to be selected (Align, Tools, Parameters, New Snapshot) only appear once
one is chosen, and several only appear on the tab (or table) they apply to —
see [Global key bindings](#global-key-bindings) below. When a table row has
keyboard focus, that row's own actions (normally reached via `Enter`) also
appear directly in the footer as one-key shortcuts — see
[Row actions](#row-actions).

#### Tabs

The TUI has three tabs:

- **Project** — two tables side by side: the events in the project and the stations. Focus the events table and press its hotkey, or press `Enter` to open the row's action menu, to select it, mark it completed, view its seismograms, or delete it.
- **Live data** — the seismogram table for the currently selected event. "Live" means the table always reflects the current in-memory ICCS state: picks, CC norms, and select/flip flags update immediately as you run alignment or change parameters, without any manual refresh. See [The ICCS Stack](iccs-stack.md) for a detailed explanation.
- **Snapshots** — a list of saved parameter snapshots for the selected event with a quality summary panel.

#### Navigation

Switch tabs with `H` / `L` (vim-style) or with the mouse. All tables support:

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `l` | Scroll left / right (wide tables) |
| `g` / `G` | Jump to top / bottom |
| `Enter` | Open row action menu |

#### Row actions

Every row action is reachable two ways: press its key directly once the row's
table has keyboard focus (it appears in the footer for as long as that table
is focused), or press `Enter` on the row to open the same actions as a
context menu — useful for mouse users, or when the key isn't top of mind.
Available actions depend on the tab:

**Project — Events table:**

| Key | Action | Description |
|-----|--------|-------------|
| `s` | Select event | Make this the active event for processing |
| `m` | Toggle completed | Mark or unmark the event as completed |
| `v` | View seismograms | Switch to the Live data tab filtered to this event |
| `d` | Delete event | Remove the event and its seismograms from the project |

**Project — Stations table:**

| Key | Action | Description |
|-----|--------|-------------|
| `v` | View seismograms | Switch to the Live data tab filtered to this station |
| `d` | Delete station | Remove the station from the project |

**Live data — Seismograms table:**

| Key | Action | Description |
|-----|--------|-------------|
| `s` | Toggle select | Include or exclude this seismogram from the ICCS stack |
| `f` | Toggle flip | Multiply the seismogram's data by −1 to correct polarity |
| `u` | Reset seismogram | Restore all per-seismogram parameters to their defaults |
| `d` | Delete seismogram | Remove the seismogram from the project |

**Snapshots — Snapshots table:**

| Key | Action | Description |
|-----|--------|-------------|
| `v` | Show details | Display the event-level parameters saved in the snapshot |
| `s` | Preview stack | Open the ICCS stack plot built from the snapshot's parameters |
| `x` | Preview matrix image | Open the matrix image built from the snapshot's parameters |
| `w` | Save results to JSON | Export per-seismogram picks and MCCC metrics to a JSON file |
| `b` | Rollback to this snapshot | Restore the snapshot's parameters as the current live values |
| `d` | Delete snapshot | Permanently remove the snapshot |

The same key means the same thing on every table it appears on (`d` always
deletes, `v` always means "look at this in more detail", `s` is the tab's
main/default action), so once you've learned one table's hotkeys the others
are largely familiar. The direct hotkey for **Preview stack**/**Preview
matrix image** uses the action menu's default toggle values (context
waveforms on, all seismograms off); to use non-default values, open the
action menu with `Enter` and toggle `c`/`a` there before selecting the action.
See [Snapshots](snapshots.md) for a description of each action and the format
of the exported results file.

#### Global key bindings

| Key | Action | Scope |
|-----|--------|-------|
| `i` | Add data files to the project | Project tab |
| `p` | Edit processing parameters | Live data tab, or Project tab with the Events table focused |
| `t` | Open interactive parameter tools (phase pick, time window, min CC, bandpass filter) | Live data tab |
| `a` | Run alignment (ICCS or MCCC) | Live data tab |
| `n` | Create a new snapshot | Live data tab |
| `r` | Refresh all panels | Global |
| `c` | Toggle colour theme | Global |
| `q` | Quit | Global |

The interactive tools modal (`t`) additionally supports `c` (toggle context
waveforms) and `a` (include all seismograms) for every tool, and `z`
(zero-phase instead of causal filtering) for the three tools that support it
(phase pick, time window, min CC). The alignment modal (`a`) supports `f`
(autoflip) and `s` (autoselect) for ICCS, and `a` (include all seismograms)
for MCCC. All are toggled inside their respective modal before running the
tool.

#### ICCS lifecycle in the TUI

The TUI keeps an in-memory ICCS instance for the selected event. It is
built automatically on startup and rebuilt whenever the event or its parameters
change — including changes made externally by the CLI or shell. Every five
seconds the TUI polls the database for such changes and silently updates.

If ICCS cannot be built (for example because a parameter was set to an invalid
value from outside the TUI), the event bar shows `○ no ICCS` and alignment and
interactive tools are disabled. Fixing the parameter from any interface
triggers an automatic retry on the next poll cycle.

---

### Graphical UI (GUI)

```bash
aimbat-gui
```

!!! note "Separate dependency group"
    The GUI requires additional packages not installed by default. Install them
    with:
    ```bash
    uv sync --group gui
    # or: pip install "aimbat[gui]"
    ```

The GUI opens a browser window (default: `http://localhost:8612`) and provides
a mouse-driven interface built with [NiceGUI](https://nicegui.io) and
[Plotly](https://plotly.com/python/). It is suited to users who prefer visual
interaction and to reviewing results — hovering over plots, clicking to set
picks, and comparing snapshots side-by-side.

The four tabs — **Project**, **Event**, **Snapshots**, and **Processing** —
follow the left-to-right workflow. The Processing tab provides an interactive
ICCS stack and matrix image; clicking on the plot sets picks and thresholds
directly.

---

## Shared concepts

### Project location

All interfaces look for `aimbat.db` in the current directory. Override this
with an environment variable:

```bash
export AIMBAT_PROJECT=/path/to/my/project.db
```

### Event selection

Projects can contain multiple seismic events. Most commands operate on a single
event at a time. Pass the event ID as a positional argument:

```bash
aimbat align iccs 6a4a
```

The named forms `--event` and `--event-id` are also accepted and behave
identically. IDs can be the full UUID or any unique prefix.

For convenience, set the `DEFAULT_EVENT_ID` environment variable to avoid
repeating the ID:

```bash
export DEFAULT_EVENT_ID=6a4a
```

When this variable is set, the CLI and shell use it as the default target
whenever an explicit ID is omitted. The shell prompt also reflects this ID.
The TUI and GUI maintain their own event selection independently and never
change it.

Note that `DEFAULT_EVENT_ID` is a plain shell environment variable consumed
directly by the CLI argument parser — it has no `AIMBAT_` prefix, cannot be
set in `.env`, and does not appear in `aimbat settings list`. See
[Selecting an Event](event-selection.md) for details.

### The ICCS instance

When you work on an event, AIMBAT builds an **ICCS instance** — an in-memory
container that holds all the seismograms for that event, their current picks
and parameters, and the data structures the alignment algorithm needs. Think
of it as the working set for a processing session: everything required to run
ICCS or MCCC, inspect the stack, or adjust picks is loaded into this container
and kept consistent with the database.

The instance is built automatically when an event is selected. **ICCS ready**
means the container has been successfully built and reflects the current state
of the project. **No ICCS** means it could not be built — usually because a
parameter combination is invalid or a waveform file is inaccessible — and
alignment and interactive tools are unavailable until the problem is resolved.

### Logging and debugging

AIMBAT writes a log to `aimbat.log` in the current directory. By default only
`INFO`-level messages and above are recorded. To get more detail, pass
`--debug` to any CLI command or TUI entry point:

```bash
aimbat align iccs --debug   # any CLI command
aimbat tui --debug           # TUI via main CLI
aimbat-tui --debug           # TUI standalone entry point
```

This sets the log level to `DEBUG` for that invocation and writes verbose
output — SQL queries, parameter validation steps, ICCS iteration details — to
the log file. The log is the first place to look when something behaves
unexpectedly.

The log file path and level can also be set permanently via environment
variable or `.env`:

```bash title=".env"
AIMBAT_LOG_LEVEL=DEBUG
AIMBAT_LOGFILE=/path/to/aimbat.log
```

Log files are rotated automatically at 100 MB.

### Live consistency

Because all interfaces share the same database file, changes from one are
immediately visible in another. The TUI polls for external changes every five
seconds. The shell reports ICCS status after every command. There is no need
to restart any interface to pick up changes made elsewhere.
