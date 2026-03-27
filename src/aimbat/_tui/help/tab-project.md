# Project tab

This is the starting point. The Project tab gives you an overview of
everything in the database: the seismic events and the recording stations.
**Most processing in AIMBAT is per-event** — you need to select an event
here before the Live data and Snapshots tabs show anything useful.

---

## What you see

### Event bar (top of screen)

The bar above the tabs always shows the currently selected event and its
ICCS status:

- **● ICCS ready** — the event's seismograms are loaded in memory and
  alignment can run. This is the normal working state.
- **○ no ICCS** — ICCS is built automatically in the background when you
  select an event. If this status persists, the ICCS instance could not be
  built — usually because a parameter combination is invalid or a waveform
  file is missing. Press `p` to check the event parameters; the most common
  cause is a time window longer than the available waveform data. Fix the
  problem and the status updates automatically.

### Events table (top)

Lists every seismic event in the project. Each row shows the event's
origin time, location, depth, and completion status. The highlighted row
drives the quality panel and note on the right.

Press `Enter` on an event row to open the action menu. The most important
action is **Select event** — this loads the event's seismograms into
memory and makes it the target for all processing commands (`a` Align,
`t` Tools, `p` Parameters, `n` New Snapshot).

### Stations table (bottom)

Lists every recording station. Highlighting a station row switches the
quality panel and note to show that station's data.

### Quality panel (right)

Shows a summary of ICCS and MCCC quality metrics for the highlighted event
or station. The panel updates as you move through the tables.

### Note (below quality panel)

A free-text Markdown note for the highlighted event or station. Switch to
**Edit** to type, then back to **View** to render the Markdown. Notes are
saved automatically whenever the editor loses focus — no explicit save
action is needed. Each event and station has its own note, which persists
in the database.

---

## Row actions — Events

| Action | Description |
|--------|-------------|
| Select event | Load this event for processing (populates Live data and Snapshots tabs) |
| Toggle completed | Mark or unmark the event as done |
| View seismograms | Switch to the Live data tab showing only this event's seismograms |
| Delete event | Remove the event and all its seismograms from the project |

## Row actions — Stations

| Action | Description |
|--------|-------------|
| View seismograms | Switch to the Live data tab filtered to this station |
| Delete station | Remove the station from the project |

---

## Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `g` / `G` | Jump to top / bottom |
| `Enter` | Open row action menu |
| `Tab` | Switch focus between Events and Stations tables |

---

## Global key bindings

These work from any tab:

| Key | Action |
|-----|--------|
| `e` | Open event switcher (quick select without leaving current tab) |
| `d` | Add data files to the project |
| `p` | Edit processing parameters for the selected event |
| `a` | Run alignment (ICCS or MCCC) |
| `t` | Open interactive tools (matplotlib picking, stack/matrix plots) |
| `n` | Create a new snapshot for the selected event |
| `r` | Refresh all panels |
| `c` | Toggle light/dark colour theme |
| `H` / `L` | Switch tabs (vim-style left/right) |
| `?` | Show this help |
| `q` | Quit |
