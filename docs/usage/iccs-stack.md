# The ICCS Stack

## Live data

The TUI's **Live data** tab shows the seismogram table for the currently
selected event. The name reflects the data's nature: it is always derived
directly from the in-memory ICCS instance and therefore always reflects the
current working state of the project.

Concretely, this means:

- **CC values** shown in the table come from `ICCS.ccs` — a cached property
  that cross-correlates each seismogram against the current stack on first
  access and clears automatically whenever parameters change. You do not need
  to run `align iccs` to see CC values; they exist as soon as seismograms are
  loaded.
- **Picks** (`t1`), **select** and **flip** flags all reflect the values
  stored in the database and loaded into the ICCS instance. Any change made
  from the CLI, shell, or TUI row-action menu is reflected immediately, without
  restarting any interface.

This is deliberately different from **Snapshots**, which capture a frozen copy
of all parameters at a point in time. Live data is the working set you are
actively adjusting; snapshots are the checkpoints you save along the way.

The TUI polls the database every five seconds to detect changes made externally
(e.g. from the CLI or shell) and silently rebuilds the ICCS instance if
necessary, keeping the Live data tab in sync.

---

## How the stack is assembled

At the start of each ICCS run, each seismogram is windowed around the current
phase pick (`t1`, or `t0` if `t1` has not yet been set) and tapered at both
ends to suppress edge effects. These windowed, tapered copies — the **CC
seismograms** — are summed to form the initial **stack**. Only seismograms
with `select = True` contribute to the stack; deselected seismograms are
excluded.

Each seismogram is then cross-correlated with this stack to determine the time
shift that aligns it most closely. The picks (`t1`) are updated with these
refined shifts and the stack is rebuilt from the newly aligned seismograms.
This process repeats iteratively — each new stack is better aligned than the
last — until the picks converge. The CC value produced at each iteration
quantifies how closely each seismogram matches the current stack.

Because every seismogram is correlated against the stack rather than against
every other seismogram, ICCS is substantially faster than MCCC — and it is
designed to be run first, to prepare well-aligned data for a final MCCC pass.

---

## Two seismogram types

Every ICCS instance maintains two representations of each seismogram, both
derived from the original data but never modifying it:

**CC seismograms** — the windowed, tapered copies used in the actual
cross-correlation. The window is defined by `window_pre` and `window_post`
relative to the pick. A cosine taper (width controlled by `ramp_width`) is
applied just outside the window to bring the signal smoothly to zero. This is
what the algorithm operates on, and what is shown when `context` is off.

**Context seismograms** — a broader view around the same pick, extended by
`context_width` on each side, without any tapering. These exist purely for
display and interactive picking: seeing the waveform beyond the taper edges
makes it much easier to judge where the window boundaries should be placed.
This is the default view.

The time window region is highlighted in the plots so the boundary between
the two representations is always visible.

---

## Viewing the stack

The **stack view** overlays all individual seismograms as thin lines on top of
the bold stack waveform. Lines are coloured by their CC on a light-blue-to-pink scale using a
power-law normalisation (γ = 2), which compresses the low end and spreads
out the high end. Differences among well-aligned seismograms are therefore
more visually distinct than differences among poorly-matching ones, making
it easy to identify which traces are contributing most to the stack.

=== "CLI"

    ```bash
    aimbat plot stack                  # context mode (default)
    aimbat plot stack --no-context     # CC seismograms only
    aimbat plot stack --all            # include deselected seismograms
    ```

=== "Shell"

    ```bash
    plot stack
    plot stack --no-context
    plot stack --all
    ```

=== "TUI"

    Press `t` to open the Tools menu and choose **Plot stack**. Before
    launching, the options **context** and **all seismograms** can be toggled
    in the menu.

=== "GUI"

    The stack is shown in the **Processing** tab. Use the **Context / CC**
    toggle to switch between the two seismogram types.

---

## Viewing the matrix image

The **matrix image** plots each seismogram as a horizontal row in a 2-D
colour image, with time on the x-axis and one row per seismogram. Rows are
sorted by CC, so the best-aligned seismograms appear at the top and the
worst at the bottom. This layout makes it easy to spot systematic misalignment
or outlier traces that stand out from the rest of the array.

The same time window highlight and `context` / `--no-context` toggle apply as
in the stack view.

=== "CLI"

    ```bash
    aimbat plot matrix
    aimbat plot matrix --no-context
    aimbat plot matrix --all
    ```

=== "Shell"

    ```bash
    plot matrix
    plot matrix --no-context
    plot matrix --all
    ```

=== "TUI"

    Press `t` and choose **Plot matrix image**.

=== "GUI"

    Switch to the **Image** tab within the Processing panel.

---

## Choosing a view

The two views complement each other:

- **Stack view** is best for assessing overall alignment and picking a new
  phase arrival — the waveform shape of the stack and its coherence with
  individual traces is immediately apparent.
- **Matrix image** is better for spotting patterns: a cluster of rows at the
  bottom with poor CCs, a seismogram whose polarity is inverted (shows as
  an opposite-coloured band), or a group of traces that are consistently
  shifted in one direction.

Using both views together, especially after adjusting parameters, gives the
most complete picture of alignment quality.

---

## Use in interactive adjustment

These two views are not just for passive inspection — they are the same plots
used when interactively adjusting the phase pick, time window, and minimum CC
norm threshold. Which view is presented depends on the tool and can usually
be chosen before launching it.

During interactive adjustment of the minimum CC, the matrix image gains
an additional behaviour: scrolling the mouse wheel removes rows from the top,
progressively revealing where the well-aligned seismograms end and the poor
ones begin. The point where the remaining rows stop looking coherent is a
natural place to set the threshold.

---

## The `--all` flag

By default, only seismograms with `select = True` appear in the plots.
Passing `--all` (or toggling **all seismograms** in the TUI/GUI) also shows
deselected seismograms. This is useful for checking whether deselected traces
could recover if parameters are adjusted — recall that deselected seismograms
are still cross-correlated against the stack and can be re-selected
automatically by autoselect in a subsequent ICCS run.
