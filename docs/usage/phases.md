# Phases

A phase is one seismic phase of an event, such as P or PKP, and the unit of
processing in AIMBAT. An event recorded with picks for P and PKP has two
phases, and each is aligned, checked and snapshotted on its own.

## What belongs to a phase

Each phase holds its own processing state:

- the phase parameters (time window, bandpass filter, minimum CC), described in
  [Parameters](parameters.md);
- a row for each seismogram in the phase, with its initial pick, refined pick
  and the flags set during quality control;
- the ICCS and MCCC quality values;
- its [snapshots](snapshots.md);
- a completed flag.

A seismogram can belong to several phases of its event. Its rows in those
phases are independent, so deselecting a seismogram in PKP leaves it selected
in P. The waveform data are shared, since they belong to the seismogram.

## How phases are created

Phases are not created directly. An event gains a phase when a pick is promoted
to an initial pick in a phase of that name, which happens during an import (see
[Initial picks](data.md#initial-picks)) or later with `aimbat pick name` and
`aimbat pick promote` (see [Picks and Readiness](picks.md)). A phase name
identifies the same seismic phase in every event, so `P` names the P phase of
each event that has one.

A new phase takes its parameters from the current AIMBAT settings, the same for
every phase name. A setting changed in the configuration therefore applies to
phases created afterwards, not to existing ones. The settings and their defaults
are listed in [Aimbat Defaults](defaults.md).

## Listing phases

=== "CLI"

    ```bash
    aimbat phase list all
    aimbat phase list <EVENT_ID>
    ```

=== "Shell"

    ```bash
    phase list all
    ```

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.core import get_phases
    from aimbat.db import engine

    with Session(engine) as session:
        phases = get_phases(session, event_id)
    ```

The table shows the seismogram counts of each phase and its processing state.
How commands select one phase is described in
[Selecting an Event](event-selection.md#selecting-a-phase).

## Managing phases

| Command | Effect |
|---|---|
| `aimbat phase rename` | Renames a phase, together with the picks of the event named for it. |
| `aimbat phase remove` | Deletes a phase with its rows, parameters, quality and snapshots. The picks named for it are dismissed. |
| `aimbat phase completed` | Marks a phase as completed, or clears the mark. |

Removing a phase does not delete any picks. `aimbat pick restore` brings the
dismissed picks back and promotes them again, which creates the phase anew with
parameters from the current settings. The parameters, quality and snapshots of
the removed phase are lost.

The completed flag is bookkeeping only and does not affect processing. An event
counts as completed when all of its phases are.

The matching functions in [`aimbat.actions`][aimbat.actions] are
[`rename_phase`][aimbat.actions.rename_phase],
[`remove_phase`][aimbat.actions.remove_phase] and
[`toggle_phase_completed`][aimbat.actions.toggle_phase_completed].
