# Project tab

The Project tab lists everything in the database: seismic events and
recording stations. **Most processing in AIMBAT is per-event** — select an
event here before the Live data and Snapshots tabs show anything.

**Changes are written to the database immediately** — there is no save step
and no undo. On the Live data tab, press `n` to create a snapshot of the
current parameter state to roll back to later. Data imported via the CLI
(`aimbat data add`) already takes an automatic snapshot of each newly
imported event, so a manual snapshot right after import is not necessary.

---

## Row action hotkeys vs. the Enter menu

Every row action below is reachable two ways:

- **Hotkey** — focus the table (`Tab` switches focus between Events and
  Stations) and press the action's key. The key is shown in the footer
  while that table has focus.
- **Menu** — press `Enter` on a row to open the same actions as a list.

The hotkey path is faster. The menu path can expose options a single
keypress cannot: on the Snapshots tab, the hotkeys for **Preview stack**
and **Preview matrix image** always use the menu's default toggle values
(context waveforms on, all seismograms off). Previewing with different
toggle values requires the `Enter` menu, since those toggles only exist
there.

---

## What you see

### Event bar (top of screen)

The bar above the tabs shows the currently selected event and its ICCS
status:

- **● ICCS ready** — the event's seismograms are loaded in memory and
  alignment can run.
- **○ no ICCS** — ICCS is built automatically in the background when you
  select an event. If this status persists, the ICCS instance could not be
  built — usually because a parameter combination is invalid or a waveform
  file is missing. Press `p` to check the event parameters; the most common
  cause is a time window longer than the available waveform data. The
  status updates automatically once the problem is fixed.

### Events table (top)

Lists every seismic event in the project. Each row shows the event's
origin time, location, depth, and completion status. The highlighted row
drives the quality panel and note on the right.

With the events table focused, press `s` (or `Enter` → **Select event**) to
select a row. This loads the event's seismograms into memory and makes it
the target for processing: `p` Parameters is available here; `a` Align,
`t` Tools, and `n` New Snapshot become available on the Live data tab.

### Stations table (bottom)

Lists every recording station. Highlighting a station row switches the
quality panel and note to show that station's data. Once an event is
selected, stations that did not record it are dimmed; the dimming updates
when the selected event changes.

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

| Key | Action | Description |
|-----|--------|-------------|
| `s` | Select event | Load this event for processing (populates Live data and Snapshots tabs) |
| `m` | Toggle completed | Mark or unmark the event as done |
| `v` | View seismograms | Switch to the Live data tab showing only this event's seismograms |
| `d` | Delete event | Remove the event and all its seismograms from the project |

## Row actions — Stations

| Key | Action | Description |
|-----|--------|-------------|
| `v` | View seismograms | Switch to the Live data tab filtered to this station |
| `d` | Delete station | Remove the station from the project |

---

## Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `l` | Scroll left / right (wide tables) |
| `g` / `G` | Jump to top / bottom |
| `Enter` | Open row action menu |
| `Tab` | Switch focus between Events and Stations tables |

---

## Global key bindings

These work from this tab. `p` additionally requires the Events table
(not Stations) to be focused:

| Key | Action |
|-----|--------|
| `i` | Add data files to the project |
| `p` | Edit processing parameters for the selected event (Events table must be focused) |
| `r` | Refresh all panels |
| `c` | Toggle light/dark colour theme |
| `H` / `L` | Switch tabs (vim-style left/right) |
| `?` | Show this help |
| `q` | Quit |
