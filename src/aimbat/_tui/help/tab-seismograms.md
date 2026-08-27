# Live data tab

This tab shows the seismograms for the currently selected event. If the
table is empty, go to the **Project** tab and select an event first
(`s`, or `Enter` → **Select event**, on any event row).

**Everything here is synced directly to the database.** Row actions (toggle
select, toggle flip, reset, delete) take effect immediately — there is no
separate save step. The table reflects the current state at all times.

---

## What you see

Each row is one seismogram (one station recording of one event). The columns are:

| Column | Description |
|--------|-------------|
| Name | Recording station name (network.station) |
| Channel | Station channel code |
| Select | `✓` if this seismogram is included in the ICCS stack, `✗` if excluded |
| Flip | `✓` if the waveform's polarity has been inverted (multiplied by −1) |
| Δt (s) | Arrival time residual (t1 − t0) in seconds. Empty until a phase-arrival pick has been set. |
| MCCC err Δt (s) | Per-seismogram timing uncertainty from the last MCCC run. Only shown after MCCC has been run. |
| Stack CC | Correlation coefficient against the current ICCS stack. Higher is better. Seismograms below `min_cc` are excluded automatically if autoselect is on. |
| MCCC CC | Mean cross-correlation coefficient from the MCCC cluster. Only shown after MCCC has been run. |
| MCCC CC std | Standard deviation of cross-correlation coefficients in the MCCC cluster. Only shown after MCCC has been run. |

### The ICCS stack

ICCS (Iterative Cross-Correlation and Stack) is the core alignment
algorithm. It cross-correlates each selected seismogram against the current
stack waveform, adjusts the picks, rebuilds the stack, and repeats until
convergence. Only seismograms with `Select = ✓` contribute to the stack.

The Stack CC column is recalculated each time the event is loaded or after
any parameter change — it shows how well each seismogram matches the current
stack, even before you run alignment. After running ICCS (`a`), the picks
(Δt) and Stack CC values are updated and written to the database immediately.

### Seismogram plot (right panel)

When a row is highlighted the right panel shows the processed waveform for
that seismogram in two tabs:

- **CC** — the cross-correlation seismogram: tapered and normalised to the
  window used for alignment. This is exactly what ICCS correlates against
  the stack.
- **Context** — the same trace with extra padding beyond the time window,
  normalised within the window. Use this to check whether the window
  boundaries fit the surrounding signal.

The x-axis shows time in seconds relative to the phase-arrival pick (t1), or
relative to t0 if t1 has not yet been set. The y-axis shows normalised
amplitude — tick labels are hidden since the absolute scale is arbitrary.

### Note (right panel)

A free-text Markdown note for the highlighted seismogram. Switch to **Edit**
to type, then back to **View** to render the Markdown. Notes are saved
automatically whenever the editor loses focus. Each seismogram has its own
note, which persists in the database.

### Typical workflow

1. Select an event in the Project tab.
2. Check the seismograms here — look for outliers (very low Stack CC) or
   wrongly-polarised traces (flip flag).
3. Run ICCS (`a`) to align all selected seismograms.
4. Use the interactive tools (`t`) to manually adjust picks or the time
   window if needed.
5. Exclude obvious outliers with **Toggle select** (press `s` on the row,
   or `Enter` for the menu).
6. Take a snapshot (`n`) to save a checkpoint.
7. Run MCCC (`a` → MCCC) for the final high-precision picks.

---

## Row actions

Each action's key works directly once this table has focus, or via `Enter`
for the equivalent menu.

| Key | Action | Description |
|-----|--------|-------------|
| `s` | Toggle select | Include or exclude this seismogram from the ICCS stack |
| `f` | Toggle flip | Invert polarity — use this if a seismogram is clearly upside down |
| `u` | Reset seismogram | Restore all per-seismogram parameters (t1, select, flip) to their defaults |
| `d` | Delete seismogram | Remove this seismogram from the project permanently |

---

## Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `h` / `l` | Scroll left / right (wide tables) |
| `g` / `G` | Jump to top / bottom |
| `Enter` | Open row action menu |

---

## Global key bindings

| Key | Action |
|-----|--------|
| `a` | Run alignment (opens ICCS / MCCC menu) |
| `t` | Open interactive tools |
| `p` | Edit processing parameters |
| `n` | Create a new snapshot |
| `r` | Refresh all panels |
| `c` | Toggle light/dark colour theme |
| `H` / `L` | Switch tabs (vim-style left/right) |
| `?` | Show this help |
| `q` | Quit |

The tools modal (`t`) additionally supports `c` (toggle context waveforms)
and `a` (include all seismograms) for every tool, and `z` (zero-phase
instead of causal filtering) for phase pick, time window, and min CC. The
alignment modal (`a`) supports `f` (autoflip) and `s` (autoselect) for ICCS,
and `a` (include all seismograms) for MCCC.
