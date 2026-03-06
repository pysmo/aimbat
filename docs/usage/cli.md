# Command Line Interface (CLI)

The CLI is the primary tool for project administration, data import, and batch
processing. Every command has a `--help` flag that prints its full option list.

!!! note "Parameter validation"
    Event parameters (e.g. time window, bandpass settings) are validated against
    the seismogram data before being written to the database — invalid values are
    rejected with an error message. Other fields (e.g. raw seismogram or station
    attributes) are written directly without data-aware checks.

## Project location

By default, AIMBAT looks for a project file called `aimbat.db` in the current
directory. All commands must be run from the same directory, or the project path
must be set explicitly:

```bash
export AIMBAT_PROJECT=/path/to/my/project.db
```

## Getting started

```bash
aimbat project create          # create a new project in the current directory
aimbat data add *.sac          # import SAC files
aimbat event list              # list events and find the ID to work with
aimbat event default <ID>      # set the default event
```

Re-adding a file that is already in the project is safe — existing records are
reused rather than duplicated.

## Targeting a specific event

Most processing commands operate on the [default event](index.md#default-event)
unless overridden with `--event`:

```bash
aimbat align iccs --event 6a4a
aimbat event parameter set window_pre --event 6a4a 10.0
```

IDs can be supplied as the full UUID or any unique prefix — as short as the
display in `aimbat event list` shows.

## Alignment

```bash
aimbat align iccs                          # iterative cross-correlation and stack
aimbat align iccs --autoflip --autoselect  # with automatic QC
aimbat align mccc                          # final relative arrival times
aimbat align mccc --all                    # include deselected seismograms
```

ICCS updates picks in `t1`, using `t0` as the starting point if `t1` is not yet
set. MCCC reads the ICCS-refined `t1` picks.

## Parameters

```bash
aimbat event parameter list                # show all parameters for default event
aimbat event parameter get window_pre      # get a single parameter
aimbat event parameter set window_pre 10.0 # set a single parameter

aimbat seismogram parameter list           # seismogram-level parameters
```

## Snapshots

```bash
aimbat snapshot create --comment "before filter change"
aimbat snapshot list
aimbat snapshot rollback <ID>
aimbat snapshot details <ID>
```

## Interactive picking

These commands open a matplotlib window. Click to set the value, then close the
window to save it.

```bash
aimbat pick phase    # adjust phase arrival (t1) per seismogram
aimbat pick window   # set the cross-correlation time window
aimbat pick ccnorm   # set the minimum CC norm threshold
```

## Inspection and plotting

```bash
aimbat event list
aimbat seismogram list
aimbat station list

aimbat plot data     # raw seismograms sorted by epicentral distance
aimbat plot stack    # ICCS cross-correlation stack
aimbat plot image    # 2-D wiggle plot
```

Most plot commands accept `--context` / `--no-context` and `--all` (include
deselected seismograms).

## Scripting

All commands exit with a non-zero status on error, making them safe to use in
shell scripts:

```bash
aimbat project create
aimbat data add *.sac
aimbat event default $(aimbat event dump | jq -r '.[0].id')
aimbat snapshot create --comment "initial import"
aimbat align iccs --autoflip --autoselect
aimbat align mccc
```
