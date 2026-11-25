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
aimbat data add --dry-run sample-data/*/*/*.BHZ
aimbat data add sample-data/*/*/*.BHZ
```

The shell expands the glob before AIMBAT runs. Each SAC file carries its
station, event, and initial picks in its header, each pick labelled with its
phase. The glob selects the vertical channels. Five events have a `P` pick on
them. The deep event of 2014-11-01 in the Fiji region also has a `pP` pick, so
it has two phases. The event of 2014-08-24 in Peru has only an `SKS` pick on
the horizontal channels, so its vertical seismograms have no pick and the
event gets no phase to process. `--dry-run` reports which stations, events,
seismograms and phases would be created without touching the database.
Import also deduplicates, so re-running the real command is safe. See
[Adding Data](../usage/data.md) for JSON sources, subset selection, and what
`--dry-run` catches.

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
