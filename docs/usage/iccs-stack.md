# The ICCS stack

AIMBAT's ICCS instance for an event is a [`pysmo.tools.iccs.ICCS`][] object. It
holds the current state of every seismogram in the event (picks, select and flip
flags) together with the stack and the views derived from them. This page covers
that state and those views. The algorithm that updates them is in
[Aligning with ICCS](alignment.md).

## Live data

The live data are the state of the event currently being worked on: picks, the
select and flip flags, and the values derived from them, as held by the
in-memory ICCS instance. The CLI, shell, and TUI all read and write this same
state, so it always reflects the most recent change, whichever interface made
it. The TUI shows it as a table in its **Live data** tab.

- **CC values** come from `ICCS.ccs`, a cached property that cross-correlates
    each seismogram against the current stack on first access and clears when
    parameters change. You do not need to run `align iccs` to see them; they
    exist as soon as the seismograms are loaded.
- **Picks (`t1`), select, and flip** reflect the database values loaded into the
    instance. A change from any interface takes effect immediately, with no
    restart.

Live data are the working set under active adjustment. **Snapshots** are the
frozen checkpoints saved along the way. The TUI polls the database every five
seconds and rebuilds the ICCS instance if an external change (from the CLI or
shell) is detected.

## How the stack is assembled

Each seismogram is windowed around its current pick (`t1`, or `t0` if `t1` is not
yet set) and tapered at both ends to suppress edge effects. These windowed,
tapered copies, the **CC seismograms**, are averaged into the **stack**, using
only seismograms with `select = True`.

This does not require running ICCS. The stack, and each seismogram's correlation
with it, are built lazily and cached as soon as the instance exists, from
whatever picks are currently set. Running ICCS then iterates on it: see
[Aligning with ICCS](alignment.md).

## Seismogram representations

Every ICCS instance keeps four representations of each seismogram, all derived
from the original data and never modifying it: **CC** and **context**
seismograms, each with a zero-phase (default) and a causally filtered variant.

- **CC seismograms** are the windowed, tapered copies used in the
    cross-correlation. The window is `window_pre` to `window_post` relative to
    the pick; a cosine taper (width `ramp_width`) just outside the window brings
    the signal smoothly to zero. This is what the algorithm operates on, and
    what is shown with `--no-context`.
- **Context seismograms** are a broader view around the same pick, extended by
    `context_width` on each side, untapered. They exist only for display and
    interactive picking: seeing the waveform beyond the taper edges makes it
    easier to place the window boundaries. This is the default view.
- **Causal variants** exist when a bandpass filter is applied, viewed with
    `--causal`. They are for picking-oriented display only. The algorithm always
    uses the zero-phase CC seismograms.

The time window is highlighted in the plots, so the boundary between the two
representations is always visible.

## Viewing the stack

The stack view overlays all individual seismograms as thin lines over the bold
stack waveform. Lines are coloured by CC on a light-blue-to-pink scale with a
power-law normalisation (γ = 2), which spreads out the high end so that
differences among well-aligned traces are more visible than differences among
poor ones.

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

    Press `t` for the Tools menu and choose **Plot stack**. Toggle **context**
    and **all seismograms** in the menu before launching.

## Viewing the matrix image

The matrix image plots each seismogram as one horizontal row in a 2-D colour
image, time on the x-axis, rows sorted by CC (best-aligned at the top). This
makes systematic misalignment and outlier traces easy to spot.

The same time-window highlight and `context` / `--no-context` toggle apply.

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

## Choosing a view

The two views complement each other:

- **Stack view** is best for assessing overall alignment and picking a new
    arrival: the stack's shape and its coherence with individual traces are
    immediately apparent.
- **Matrix image** is best for spotting patterns: a cluster of poor CCs at the
    bottom, an inverted-polarity trace (an opposite-coloured band), or a group
    of traces shifted consistently in one direction.

Using both after a parameter change gives the most complete picture.

## Interactive adjustment

These two plots are also the surface for interactively adjusting the pick, time
window, and minimum CC. During min-CC adjustment the matrix image gains an extra
behaviour: scrolling removes rows from the top, revealing where the well-aligned
seismograms end. See [Parameters](parameters.md) for the tools.

## The `--all` flag

By default the plots show only `select = True` seismograms. `--all` (or the TUI
toggle) adds the deselected ones, useful for checking whether they would recover
under different parameters. Deselected seismograms are still cross-correlated
against the stack and can be re-selected by autoselect; see
[Aligning with ICCS](alignment.md).
