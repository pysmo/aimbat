# Parameters

ICCS parameters are either per-event — the time window, bandpass filter, and
minimum CC — or per-seismogram — the phase pick (`t1`). All of them can be
adjusted at any time, and they are part of the
[live data](iccs-stack.md#live-data) and captured by [snapshots](snapshots.md).

Every parameter can be set directly — via CLI arguments, in the shell, in the
TUI, or through the Python API. In practice, the interactive tools described
below are the typical way to set them, since they let you see the effect on
the stack or matrix image while choosing a value.

Changing the time window, bandpass filter, or `t1` takes effect immediately:
these directly change the CC seismograms, so the stack and CC values reflect
the new value as soon as they are next accessed — no ICCS run is needed.

!!! note "Autoflip and autoselect only act during an ICCS run"
    Minimum CC (`min_cc`) does not change the data or the current selection by
    itself — it only takes effect through autoselect, and autoselect (like
    autoflip) only runs as part of `align iccs`. Setting a lower `min_cc`
    between runs does not retroactively re-select anything.

## Time window

`window_pre` and `window_post` define how much of the seismogram — before and
after the pick — is used in the cross-correlation. Since the pick aims to sit at
the **onset** of the target phase (the first coherent ground motion), the window
effectively starts a little before the onset and extends through the arrival.
Keeping `window_pre` short and placing the onset near the beginning of the
window tends to work well, as it limits how much noise before the arrival is
included. The window should be narrow enough that it is dominated by the target
phase rather than noise or later arrivals.

A good starting point is a window that visually frames the onset in the stack
plot. Narrowing it once initial alignment is reasonable often improves
precision.

## Bandpass filter

`bandpass_apply`, `bandpass_fmin`, and `bandpass_fmax` control an optional
bandpass filter applied before cross-correlation. Filtering can dramatically
improve alignment on noisy data by suppressing frequencies where the signal is
weak, but the right frequency range depends on the event and the array.

Filtering is off by default. When enabled, the same filter is applied to both
the seismograms and the stack, so the cross-correlation is always comparing like
with like.

## The phase pick (t1)

`t1` is the per-seismogram pick that ICCS refines during each run — every
seismogram gets its own value, reflecting how much it needs to be shifted
relative to the stack. When adjusted interactively from the stack plot, however,
the same shift is applied to all seismograms simultaneously. This makes
interactive picking a coarse, global adjustment — useful for moving the entire
array onto the onset — while ICCS handles the fine, per-seismogram refinement.

## Minimum CC

`min_cc` is the threshold used by autoselect to deselect seismograms
automatically. It does not affect the cross-correlation itself — only which
seismograms are excluded from contributing to the stack in subsequent
iterations.

Setting this too high early on may exclude seismograms that would align well
once the stack improves. It is usually more effective to start with a permissive
threshold and tighten it as alignment converges. The threshold can be adjusted
interactively with `aimbat tool cc`.

## Resetting a seismogram

A single seismogram's per-seismogram parameters (`t1`, `select`, `flip`) can be
reset to their defaults, discarding any pick, deselection, or flip applied to
it. This is useful when one seismogram has drifted too far from the rest of
the array — for example after repeated ICCS runs pull its pick somewhere
unhelpful — and it is easier to start it over than to correct it by hand.
Resetting clears `t1`, so the seismogram falls back to its initial pick (`t0`)
on the next stack rebuild.

=== "CLI"

    ```bash
    aimbat seismogram parameter reset <SEISMOGRAM_ID>
    ```

=== "Shell"

    ```bash
    seismogram parameter reset <SEISMOGRAM_ID>
    ```

=== "TUI"

    Press `Enter` on a row in the **Live data** tab and choose **Reset
    seismogram** (`u`).

## Interactive adjustment

Four interactive tools let you set parameter values by interacting with the
plot — clicking or scrolling in a waveform display rather than typing numbers.
Each wraps a `pysmo.tools.iccs` function, where the exact interaction is
documented: [`update_pick`][pysmo.tools.iccs.update_pick] (`t1`),
[`update_timewindow`][pysmo.tools.iccs.update_timewindow] (`window_pre` /
`window_post`), [`update_min_cc`][pysmo.tools.iccs.update_min_cc] (`min_cc`),
and [`update_bandpass`][pysmo.tools.iccs.update_bandpass] (the bandpass
filter).

=== "CLI"

    ```bash
    aimbat tool phase <ID>    # adjust t1 by clicking on the stack
    aimbat tool window <ID>   # set window_pre / window_post by clicking
    aimbat tool cc <ID>       # set min_cc by scrolling the matrix image
    aimbat tool bandpass <ID> # adjust bandpass filter settings interactively
    ```

    All four accept `--no-context` and `--all` (include deselected
    seismograms).

=== "Shell"

    ```bash
    tool phase    # adjust t1 by clicking on the stack
    tool window   # set window_pre / window_post by clicking
    tool cc       # set min_cc by scrolling the matrix image
    tool bandpass # adjust bandpass filter settings interactively
    ```

    All four accept `--no-context` and `--all` (include deselected
    seismograms).

=== "TUI"

    Press `t` to open the **Tools** menu, then choose from:

    - **Phase arrival (t1)** — click in the stack to shift all picks globally
    - **Time window** — click to place the window boundaries
    - **Min CC** — scroll the matrix image to set the threshold
    - **Bandpass filter** — toggle the filter and adjust frequency bounds

    Before launching, toggle **Context** (`c`) and **All seismograms** (`a`) as
    needed. The TUI suspends while the matplotlib window is open and resumes when
    you close it.
