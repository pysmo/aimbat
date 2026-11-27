# Picks and readiness

A phase can be processed once no blocking readiness item applies to it, which
requires at least one initial pick in the phase. Seismograms without an initial
pick for the phase are left out of its processing. This page describes how the picks read from the data sources become
initial picks, how the data are checked for readiness, and how gaps are fixed.

## From picks to initial picks

AIMBAT stores every pick as it was read from a data source, with its time and
its label. Before a pick can serve as an initial pick, it needs two things:

- **A phase name.** The label of the pick gives its phase name, or
  `--unlabelled-as` gives one during the import (see
  [Initial picks](data.md#initial-picks)). A pick without either is
  *unnamed*.
- **A seismogram.** A pick is matched to the seismogram it was read with. A pick
  that matches no seismogram of its event is *unmatched*.

A pick that is named and matched is *promoted*: it becomes the initial pick of
its seismogram in the phase of that name, and the event gains the
[phase](phases.md) if it does not have it yet. The phase is the one of that
name on the [component](components.md) of the seismogram. Picks that cannot be promoted stay stored, so nothing read
from a data source is lost, and they can be completed later.

`aimbat pick list` shows the stored picks of an event with their state.
`--unnamed`, `--unmatched` and `--phase` narrow the listing.

## Checking readiness

`aimbat data check` lists what stands between the data and processing. Each item
names the picks, seismograms or phase it concerns and the command that fixes it.
Items are of two kinds:

- **Blocking items** prevent processing of the phases they cover. Unnamed picks
  and a phase without any initial pick are examples.
- **Notices** may need attention but do not prevent processing, for example a
  seismogram without any pick.

=== "CLI"

    ```bash
    aimbat data check                 # every event
    aimbat data check 6a4a --phase P  # one phase of one event
    ```

=== "Shell"

    ```bash
    data check
    ```

=== "API"

    ```python
    from aimbat.actions import check_data

    report = check_data()
    for item in report.blocking:
        print(item.message, item.fixes)
    ```

The exit status is 2 while a blocking item remains, so a script can stop before
alignment, and 1 when the check itself fails. `--strict` treats notices as
blocking items, and `--json` prints the
items in a form other programs can read. `aimbat data check --help` describes
every option.

Readiness is worked out from the project each time it is checked and is never
stored. A fix therefore takes effect at once, with nothing to refresh.

### Refused processing

ICCS and MCCC refuse a phase while a blocking item applies to it. The CLI and
shell print the items with their fixes, and the TUI shows them in a warning.
From the API, [`prepare_iccs`][aimbat.actions.prepare_iccs],
[`run_iccs`][aimbat.actions.run_iccs] and [`run_mccc`][aimbat.actions.run_mccc]
raise a [`NotReadyError`][aimbat.core.NotReadyError] that carries the items.

!!! note "The TUI does not fix picks"

    Gaps in the picks are fixed once, after the import, with the CLI or the
    shell. The TUI names the commands that fix them.

## Fixing gaps

A gap can be fixed at its origin, in the data sources, or inside the project.
Both routes give the same result, and they can be combined.

### In the data sources

When the data sources themselves are wrong, for example a missing or misspelt
label in a SAC header, the sources are corrected with an external tool and read
again. `aimbat data add` does not read a source that is already in the project,
so `aimbat pick add` reads the picks of such sources:

```bash
aimbat pick add --dry-run *.sac   # report what changed
aimbat pick add --update *.sac    # apply changed times and labels
```

New picks are stored and promoted as during the import. A pick whose time or
label changed is reported, and updated only with `--update`. An initial pick
then follows its pick, and a pick whose new label names another phase moves to
that phase. `pick add` snapshots each phase that gained initial picks, unless
`--no-snapshot` is given.

This route keeps the data sources and the project in agreement, which suits
sources that are shared or used by other programs.

### Inside the project

The `aimbat pick` commands complete the stored picks without touching the data
sources:

| Command        | Purpose                                                            |
| -------------- | ------------------------------------------------------------------ |
| `pick name`    | Give selected picks a phase name.                                  |
| `pick match`   | Match an unmatched pick to a seismogram, or retry matching.        |
| `pick promote` | Promote named, matched picks that were left out.                   |
| `pick set`     | Set an initial pick by hand, from a time.                          |
| `pick remove`  | Dismiss picks that should play no part.                            |
| `pick restore` | Undo a dismissal.                                                  |

`pick name` and `pick remove` select picks by ID or by criteria such as their
label, and `pick name --dry-run` shows the effect of a naming before it is made.
Each command's `--help` lists its arguments and options. Like an import,
`pick name`, `pick match`, `pick promote` and `pick restore` snapshot each phase
that gains initial picks, unless `--no-snapshot` is given. A phase completed
inside the project therefore also starts with a baseline to roll back to.

A typical case is a set of files whose picks carry no label:

```bash
aimbat data check                          # lists the unnamed picks
aimbat pick list 6a4a --unnamed            # inspects them
aimbat pick name P --event 6a4a --unnamed  # names them, and promotes them
aimbat data check                          # confirms nothing blocks
```

The same fixes are available from the API through
[`aimbat.actions`][aimbat.actions], with
[`PickSelection`][aimbat.core.PickSelection] describing which picks a call
acts on:

```python
from aimbat.actions import name_picks
from aimbat.core import PickSelection

name_picks(PickSelection(event_id=event.id, unnamed=True), "P")
```

!!! tip "Refined picks"

    These commands set initial picks, which are a first guess for alignment.
    The refined pick of a seismogram is set by ICCS, MCCC or `aimbat tool pick`
    (see [Parameters](parameters.md#the-refined-pick)).

## Dismissing and deleting picks

`aimbat pick remove` dismisses picks by default. A dismissed pick stays stored
and is left out of promotion and of `data check`. Because it stays stored, a later
`pick add` does not bring it back, and `pick restore` undoes the dismissal.

`--purge` deletes the picks instead. A deleted pick of a data source is stored
again the next time the source is read, which suits a pick whose source has
since been corrected.

Removing a pick that is an initial pick also removes that seismogram from the
phase.
