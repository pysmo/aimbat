# Parameters

ICCS parameters are per-event (the time window, bandpass filter, and minimum CC)
or per-seismogram (the phase pick, `t1`). All can be changed at any time. They
are part of the [live data](iccs-stack.md#live-data) and are captured by
[snapshots](snapshots.md).

Any parameter can be set directly through CLI arguments, the shell, the TUI, or
the Python API. In practice the interactive tools below are the usual way, since
they show the effect on the stack or matrix image as a value is chosen.

Changing the time window, bandpass filter, or `t1` takes effect immediately: they
change the CC seismograms directly, so the stack and CC values reflect the new
value the next time they are accessed. No ICCS run is needed.

!!! note "Autoflip and autoselect only act during an ICCS run"

    Minimum CC (`min_cc`) changes nothing by itself. It takes effect only through
    autoselect, which, like autoflip, runs only as part of `align iccs`. Lowering
    `min_cc` between runs does not retroactively re-select anything.

## Time window

`window_pre` and `window_post` set how much of the seismogram before and after
the pick enters the cross-correlation. The pick sits at the phase onset, so the
window starts a little before the onset and extends through the arrival. A short
`window_pre` limits how much pre-arrival noise is included. The window should be
narrow enough to be dominated by the target phase rather than noise or later
arrivals.

Start with a window that frames the onset in the stack plot. Narrowing it once
alignment is reasonable often improves precision.

## Bandpass filter

`bandpass_apply`, `bandpass_fmin`, and `bandpass_fmax` control an optional
bandpass filter applied before cross-correlation. On noisy data it can improve
alignment substantially by suppressing frequencies where the signal is weak; the
right band depends on the event and the array.

Filtering is off by default. When on, the same filter is applied to the
seismograms and the stack, so the cross-correlation always compares like with
like.

## The phase pick (t1)

`t1` is the per-seismogram pick ICCS refines each run: one value per seismogram,
reflecting how far it needs to shift relative to the stack. Adjusted
interactively from the stack plot, though, the same shift applies to every
seismogram at once. Interactive picking is therefore a coarse global adjustment,
moving the whole array onto the onset; ICCS does the fine per-seismogram work.

## Minimum CC

`min_cc` is the threshold autoselect uses to deselect seismograms. It does not
affect the cross-correlation itself, only which seismograms contribute to the
stack in later iterations.

Set too high early on, it excludes seismograms that would align well once the
stack improves. Start permissive and tighten as alignment converges. Adjust it
interactively with `aimbat tool cc`.

## Resetting a seismogram

A seismogram's per-seismogram parameters (`t1`, `select`, `flip`) can be reset to
their defaults, discarding any pick, deselection, or flip. Useful when one
seismogram has drifted too far from the array to be worth correcting by hand.
Resetting clears `t1`, so it falls back to `t0` on the next stack rebuild.

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

Four tools set a value by interaction with a waveform plot rather than a typed
number. Each wraps a `pysmo.tools.iccs` function where the exact interaction is
documented: [`update_pick`][pysmo.tools.iccs.update_pick] (`t1`),
[`update_timewindow`][pysmo.tools.iccs.update_timewindow] (`window_pre` /
`window_post`), [`update_min_cc`][pysmo.tools.iccs.update_min_cc] (`min_cc`), and
[`update_bandpass`][pysmo.tools.iccs.update_bandpass] (the filter).

=== "CLI"

    ```bash
    aimbat tool phase <ID>    # adjust t1 by clicking on the stack
    aimbat tool window <ID>   # set window_pre / window_post by clicking
    aimbat tool cc <ID>       # set min_cc by scrolling the matrix image
    aimbat tool bandpass <ID> # adjust the bandpass filter interactively
    ```

    All four accept `--no-context` and `--all`.

=== "Shell"

    ```bash
    tool phase
    tool window
    tool cc
    tool bandpass
    ```

    All four accept `--no-context` and `--all`.

=== "TUI"

    Press `t` for the **Tools** menu:

    - **Phase arrival (t1).** Click in the stack to shift all picks.
    - **Time window.** Click to place the boundaries.
    - **Min CC.** Scroll the matrix image to set the threshold.
    - **Bandpass filter.** Toggle the filter and adjust the bounds.

    Toggle **Context** (`c`) and **All seismograms** (`a`) before launching. The
    TUI suspends while the matplotlib window is open.
