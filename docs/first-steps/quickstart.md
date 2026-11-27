# Quickstart

A first session on the bundled sample dataset: set the project up from the
command line, then do the processing in the TUI. It assumes AIMBAT is
[installed](installation.md) and on `PATH`.

## Get the sample data

```bash
aimbat utils sampledata download
```

This downloads teleseismic recordings from several events into a `sample-data/`
directory. [Aimbat Defaults](../usage/defaults.md) covers how to change that
path.

## Create a project

```bash
aimbat project create
```

This creates `aimbat.db` in the current directory. All project state lives in
that one file. See [Project](../usage/project.md) for its location and how to
point AIMBAT at a different one.

## Add the data

Preview the import first with `--dry-run`, then run it for real:

```bash
aimbat data add --dry-run sample-data/*/*/*.BH?
aimbat data add sample-data/*/*/*.BH?
```

The shell expands the glob before AIMBAT runs. Each SAC file carries its
station, event, and initial picks in its header, each pick labelled with its
phase. Five events have `P`, and the deep event of 2014-11-01 in the Fiji
region also has `pP`. Four of them have `S`, and the event of 2014-08-24 in
Peru has `SKS`. The data are prepared as AIMBAT expects them: the horizontals
are rotated, to the transverse component (`BHT`) for the S events and to
`BHL`, `BHQ` and `BHT` for Peru, and every pick of a station is on every one
of its channels. `--dry-run` reports which stations, events, seismograms and
phases would be created without touching the database. Import also
deduplicates, so re-running the real command is safe. See
[Adding Data](../usage/data.md) for JSON sources, subset selection, and what
`--dry-run` catches.

## Choose the components

A phase is measured on one component, so the import creates a phase for each
component a pick is on: `P (Z)` and `P (T)`, `SKS (L)`, `SKS (Q)`, `SKS (T)`
and `SKS (Z)`. P and pP are measured on the vertical and S on the
transverse. SKS is kept on Q and on T, as two phases. The other phases are
removed from every event:

```bash
aimbat phase remove --event all --phase P --component T
aimbat phase remove --event all --phase pP --component T
aimbat phase remove --event all --phase S --component Z
aimbat phase remove --event all --phase SKS --component Z
aimbat phase remove --event all --phase SKS --component L
aimbat data check
```

`--dry-run` previews each removal. A removal deletes the phase with its
initial picks and snapshots, so it is best done before any processing.
`aimbat data check` then reports nothing that blocks processing, and lists the
Z and L seismograms of the Peru event, which no phase uses any more. See
[Components and Phases](../usage/components.md) for how phases follow the
components.

## Open the TUI

```bash
aimbat tui
```

The rest of the work happens here:

1. **Project tab** — select an event to work on. For an event with more than one
    phase, such as the 2014-11-01 event, a menu of its phases follows.
2. **Live data tab** — the seismogram table for that event. Adjust parameters,
    run ICCS, and inspect the alignment.
3. **Snapshots tab** — save the parameter state, and export results from a
    snapshot.

Press `?` at any point for the context-aware key bindings.

## Next

- [Using AIMBAT](../usage/index.md) — the three interfaces and when to use each
- [The ICCS Stack](../usage/iccs-stack.md) and
    [Aligning with ICCS](../usage/alignment.md) — the alignment loop in detail
- [MCCC Alignment](../usage/mccc.md) — the final pass for formal timing errors
- [Exporting Results](../usage/results.md) — the output format
