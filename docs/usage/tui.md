# Terminal User Interface (TUI)

The TUI is the primary interface for processing seismic events. It is designed
for keyboard-driven, mouse-free operation and provides a live view of the
project state.

## Launching

```bash
aimbat tui
```

## Layout

```
┌─ AIMBAT ────────────────────────────────── ...
│ ● 2000-01-01 12:00:00  |  45.1°, 120.4°  ... ← event bar
├───────────────────────────────────────────...
│  Seismograms │ Parameters │ Stations │ S  ... ← tabs
│ ┌─────────────────────────────────────── ...
│ │  ...                                   ...
│ └─────────────────────────────────────── ...
├───────────────────────────────────────────...
│ e Events  d Add Data  p Interactive Tools ... ← footer
└───────────────────────────────────────────...
```

### Event bar

The event bar shows the event currently selected for processing:

| Marker | Meaning |
|--------|---------|
| `●` | This event is also the [default event](index.md#default-event) |
| `▶` | This event is selected for TUI processing, but is not the default |

The right side of the bar shows the ICCS status (`● ICCS ready` / `○ no ICCS`)
and a `modified:` timestamp if the event parameters have been changed since the
project was created. The timestamp updates automatically when changes arrive
from an external source such as the CLI.

## Navigation

### Tabs

Switch between tabs with the mouse or with `H` / `L` (vim-style left/right).

### Tables

All tables support vim-style keyboard navigation:

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `g` | Jump to top |
| `G` | Jump to bottom |
| `Enter` | Open row action menu (or toggle/edit inline — see below) |

## Tabs

### Seismograms

Lists every seismogram in the current event. Pressing `Enter` on a row opens a
context menu with the following actions:

| Action | Description |
|--------|-------------|
| Toggle select | Include or exclude this seismogram from processing |
| Toggle flip | Flip the seismogram polarity |
| Reset parameters | Restore all per-seismogram parameters to their defaults |
| Delete seismogram | Remove the seismogram from the project |

### Parameters

Lists all processing parameters for the current event. Pressing `Enter` on a
parameter edits it:

- **Boolean** parameters toggle immediately.
- **Numeric / timedelta** parameters open an input dialog pre-filled with the
  current value. Press `Enter` to save or `Escape` to cancel.

Parameter changes are validated against the current ICCS instance before being
written to the database. Invalid values are rejected with an error notification.

### Stations

Lists all stations associated with the current event. Pressing `Enter` opens a
context menu with one action: **Delete station and all seismograms**.

### Snapshots

Lists all snapshots saved for the current event. Pressing `Enter` opens a
context menu:

| Action | Description |
|--------|-------------|
| Show details | Display all event parameters captured in this snapshot |
| Rollback to this snapshot | Restore event parameters to the snapshot state |
| Delete snapshot | Remove the snapshot |

Press `n` (only available on this tab) to create a new snapshot. An optional
comment can be entered before saving.

## Global actions

### Switch event — `e`

Opens the event switcher, which lists all events in the project. Each row shows:

- **Marker**: `★` = default + currently selected, `●` = default only, `▶` = currently selected only
- **✓**: event is marked as completed

Available actions inside the switcher:

| Key | Action |
|-----|--------|
| `Enter` | Select this event for TUI processing (does not change the default) |
| `d` | Select this event and set it as the [default event](index.md#default-event) |
| `c` | Toggle the completed flag |
| `Backspace` | Delete the event and all its data |
| `Escape` | Cancel |

The selected event is used for all processing operations until changed. If no
explicit selection has been made, the default event is used automatically.

### Interactive tools — `p`

Suspends the TUI and opens an interactive matplotlib window:

| Tool | Description |
|------|-------------|
| Phase arrival (t1) | Adjust the phase arrival for each seismogram |
| Time window | Set the pre- and post-pick time window |
| Min CC norm | Set the minimum cross-correlation normalisation threshold |

Two options can be toggled before launching:

- **Context** (`c`): show surrounding waveform context
- **All seismograms** (`a`): apply to all seismograms, not only selected ones

Close the matplotlib window to return to the TUI.

### Align — `a`

Runs a seismogram alignment algorithm in a background thread (the TUI remains
responsive). Choose between:

| Algorithm | Description |
|-----------|-------------|
| ICCS | Iterative Cross-Correlation and Stack |
| MCCC | Multi-Channel Cross-Correlation |

ICCS options (toggled before running):

- **Autoflip** (`f`): automatically flip seismograms with negative cross-correlation
- **Autoselect** (`s`): automatically deselect seismograms below the CC norm threshold

MCCC option:

- **All seismograms** (`a`): include deselected seismograms

### Other global keys

| Key | Action |
|-----|--------|
| `d` | Add data files to the project |
| `r` | Refresh all panels |
| `t` | Toggle light / dark theme |
| `q` | Quit |

## ICCS and external changes

The TUI maintains an in-memory ICCS instance for the current event. It is
created automatically on startup and recreated whenever the event or its
parameters change.

Every 5 seconds, the TUI polls the database for external changes. If the event
parameters or seismogram parameters have been modified from outside (e.g. via
the CLI), the ICCS instance is silently recreated and all panels refresh. This
means the TUI and CLI can be used side-by-side on the same project without
manual synchronisation.

If ICCS creation fails (for example because a parameter was set to an invalid
value via the CLI), the `○ no ICCS` status is shown and interactive tools and
alignment are disabled. Fixing the parameter externally will trigger an
automatic retry on the next poll cycle.
