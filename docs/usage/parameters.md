# Parameters

ICCS parameters belong to a phase of an event (the time window, bandpass filter,
and minimum CC) or to a seismogram in a phase (the refined pick,
`refined_pick`). All can be changed at any time. They are part of the
[live data](iccs-stack.md#live-data) and are captured by
[snapshots](snapshots.md). Phase parameters are read and set with
`aimbat phase parameter`, and seismogram parameters with
`aimbat seismogram parameter`. Both select the phase as described in
[Selecting an Event](event-selection.md#selecting-a-phase).

Any parameter can be set directly through CLI arguments, the shell, the TUI, or
the Python API. In practice the interactive tools below are the usual way, since
they show the effect on the stack or matrix image as a value is chosen.

Changing the time window, bandpass filter, or refined pick takes effect
immediately: they change the CC seismograms directly, so the stack and CC values
reflect the new value the next time they are accessed. No ICCS run is needed.

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

A window that frames the onset in the stack plot is a reasonable starting
point. Narrowing it once alignment is reasonable often improves precision.

## Bandpass filter

`bandpass_apply`, `bandpass_fmin`, and `bandpass_fmax` control an optional
bandpass filter applied before cross-correlation. On noisy data it can improve
alignment substantially by suppressing frequencies where the signal is weak; the
right band depends on the event, the phase and the array.

Filtering is off by default. When on, the same filter is applied to the
seismograms and the stack, so the cross-correlation always compares like with
like.

!!! tip "Widen the band before narrowing it"

    `bandpass_fmax` must stay above `bandpass_fmin`, and the CLI and TUI set
    one bound at a time. Moving a 0.5-1 Hz band up to 1.5-2 Hz is therefore
    rejected if `bandpass_fmin` goes first. Raise `bandpass_fmax` first and it
    works; moving the band down, lower `bandpass_fmin` first.

## The refined pick

`refined_pick` is the per-seismogram pick ICCS refines each run: one value per seismogram,
reflecting how far it needs to shift relative to the stack. Adjusted
interactively from the stack plot, though, the same shift applies to every
seismogram at once. Interactive picking is therefore a coarse global adjustment,
moving the whole array onto the onset; ICCS does the fine per-seismogram work.

## Minimum CC

`min_cc` is the threshold autoselect uses to deselect seismograms. It does not
affect the cross-correlation itself, only which seismograms contribute to the
stack in later iterations.

Set too high early on, it excludes seismograms that would align well once the
stack improves. A permissive starting value, tightened as alignment converges,
works better. `aimbat tool cc` adjusts it interactively.

!!! tip "Window changes shift what min_cc excludes"

    Narrowing the time window typically raises CC values across the array. A
    seismogram that autoselect had deselected can cross back above `min_cc`
    without any real improvement in alignment. Running ICCS with autoselect
    after narrowing the window may call for raising `min_cc`, to deselect it
    again or keep it deselected; see [Autoselect](alignment.md#autoselect).

## Python API

```python
from pandas import Timedelta
from sqlmodel import Session, select
from aimbat.db import engine
from aimbat.core import resolve_phase, set_phase_parameter, set_seismogram_parameter
from aimbat.types import PhaseParameter, SeismogramParameter
from aimbat.models import AimbatEvent

with Session(engine) as session:
    event = session.exec(select(AimbatEvent)).first()
    phase = resolve_phase(session, event.id)
    set_phase_parameter(session, phase.id, PhaseParameter.WINDOW_PRE, Timedelta(seconds=-10))

    seismogram = event.seismograms[0]
    set_seismogram_parameter(
        session, phase.id, seismogram.id, SeismogramParameter.SELECT, False
    )

    session.commit()
```

`set_phase_parameter` validates the new value on its own. With
`validate_iccs=True`, it also checks that the value does not break ICCS
construction, as the CLI does. A value ICCS rejects raises
`IccsValidationError` and leaves the parameter unchanged.
[`set_phase_parameters`][aimbat.core.set_phase_parameters] sets several
parameters as one validated batch, for values only valid together (e.g. a new
`bandpass_fmin` above the old `bandpass_fmax`).

## Resetting a seismogram

A seismogram's per-seismogram parameters (`refined_pick`, `select`, `flip`) can
be reset to their defaults, discarding any pick, deselection, or flip. Useful
when one seismogram has drifted too far from the array to be worth correcting by
hand. Resetting clears the refined pick, so the initial pick takes its place on
the next stack rebuild.

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

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import reset_seismogram_parameters

    with Session(engine) as session:
        reset_seismogram_parameters(session, phase_id, seismogram_id)
        session.commit()
    ```

## Interactive adjustment

Four tools set a value by interaction with a waveform plot rather than a typed
number. Each wraps a `pysmo.tools.iccs` function where the exact interaction is
documented: [`update_pick`][pysmo.tools.iccs.update_pick] (`refined_pick`),
[`update_timewindow`][pysmo.tools.iccs.update_timewindow] (`window_pre` /
`window_post`), [`update_min_cc`][pysmo.tools.iccs.update_min_cc] (`min_cc`), and
[`update_bandpass`][pysmo.tools.iccs.update_bandpass] (the filter).

=== "CLI"

    ```bash
    aimbat tool pick <ID>     # adjust the refined picks by clicking on the stack
    aimbat tool window <ID>   # set window_pre / window_post by clicking
    aimbat tool cc <ID>       # set min_cc by scrolling the matrix image
    aimbat tool bandpass <ID> # adjust the bandpass filter interactively
    ```

    All four accept `--phase`, `--no-context` and `--all`. `pick`, `window`,
    and `cc` also accept `--causal`, and `bandpass` does not take it.
    Defaults: causal for `pick`, zero-phase for `window` and `cc`. See
    [The ICCS stack](iccs-stack.md) for why the defaults differ.

=== "Shell"

    ```bash
    tool pick
    tool window
    tool cc
    tool bandpass
    ```

    All four accept `--phase`, `--no-context` and `--all`. `pick`, `window`,
    and `cc` also accept `--causal`, and `bandpass` does not take it.
    Defaults: causal for `pick`, zero-phase for `window` and `cc`. See
    [The ICCS stack](iccs-stack.md) for why the defaults differ.

=== "TUI"

    Press `t` for the **Tools** menu:

    - **Refined pick.** Click in the stack to shift all picks.
    - **Time window.** Click to place the boundaries.
    - **Min CC.** Scroll the matrix image to set the threshold.
    - **Bandpass filter.** Toggle the filter and adjust the bounds.

    Toggle **Context** (`c`) and **All seismograms** (`a`) before launching.
    **Refined pick**, **Time window**, and **Min CC** also show a **zero-phase**
    toggle (`z`); **Bandpass filter** doesn't. The TUI suspends while the
    matplotlib window is open.
