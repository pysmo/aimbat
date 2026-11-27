# Components and phases

Each channel of a station is its own seismogram in AIMBAT. A three-component
recording therefore gives three seismograms per event, and rotated data give
one per rotated component (`BHT`, `BHQ`). A [phase](phases.md) is identified
by its name and its component, the last letter of the channel codes of its
seismograms. Picks of SKS on `BHQ` and on `BHT` seismograms belong to two
phases, `SKS (Q)` and `SKS (T)`, which are aligned and measured separately.
A seismogram whose channel code has no component letter belongs to a phase
without a component, shown by its name alone.

Nothing about the component is configured. A pick belongs to the phase of
its name on the component of its seismogram, and the phase is created when
the first such pick is promoted.

## Preparing the data

Waveforms are prepared before they are added: instrument response removed,
filtered, resampled, cut to a window, and rotated where a phase is measured
on a rotated component. pysmo provides the tools, among them
[`rotate_to_rt`][pysmo.tools.components.rotate_to_rt] and
[`rotate_to_lqt`][pysmo.tools.components.rotate_to_lqt]. AIMBAT reads the
prepared files and does not change them.

A prepared data set often carries every pick of a site on every channel, so
that P is picked on Z and T alike. Each component then gives a phase of its
own, and the phases that are not wanted are removed.

## Removing the phases of a component

`aimbat phase remove` with `--event all` removes the phase of a name and
component from every event that has it. `--dry-run` lists what would be
removed:

=== "CLI"

    ```bash
    aimbat phase remove --event all --phase P --component T --dry-run
    aimbat phase remove --event all --phase P --component T
    ```

=== "API"

    ```python
    from sqlmodel import Session, col, select
    from aimbat import actions
    from aimbat.db import engine
    from aimbat.models import AimbatPhase

    with Session(engine) as session:
        phase_ids = session.exec(
            select(AimbatPhase.id)
            .where(col(AimbatPhase.name) == "P")
            .where(col(AimbatPhase.component) == "T")
        ).all()
    actions.remove_phases(phase_ids)
    ```

The picks of a removed phase are dismissed, and the picks of the same name on
other components are kept. Dismissed picks are left out of promotion, so the
phase is not created again when the data are added again. `aimbat pick
restore` brings the picks back. See [Phases](phases.md) for what else
removal deletes.

## Selecting a phase by component

Commands that process a phase take `--component` beside `--phase`, and
`DEFAULT_COMPONENT` beside `DEFAULT_PHASE`. Either is enough when it selects
one phase of the event. See [Selecting a phase](event-selection.md#selecting-a-phase).

## Streams, sensors and sampling rates

A phase collects the seismograms of one component from every site, which can
include several streams of one site. `aimbat data check` reports them:

- **Several streams of one sensor** (one network, station and location code,
  such as `BHZ` and `LHZ`) block processing. The streams record one
  observation, which would count twice in the stack and in MCCC. Removing the
  picks of one stream with `aimbat pick remove --station STATION` fixes it.
  Deselecting the seismogram does not, as automatic selection can select it
  again.
- **Several sensors of one site** (two location codes) are a notice. Their
  seismograms are independent observations, close together.
- **Several sampling rates** in a phase are a notice when the stack holds
  frequencies above the Nyquist frequency of the coarsest seismograms: the
  bandpass filter is off, or reaches close to that Nyquist frequency.
  Seismograms are resampled to the finest sampling interval for the stack.
- **A bandpass at or above the Nyquist frequency** of a seismogram of the
  phase blocks processing, deselected seismograms included.

Larger preparation, such as choosing among streams or making their responses
agree, is done before the data are added.
