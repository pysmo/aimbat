# Core concepts

## The problem

Teleseismic travel time tomography requires accurate phase arrival picks across
large seismic arrays. Picking each trace individually does not scale — and
doing so in isolation discards the most useful information available: the
coherence of the wavefield across the array.

AIMBAT works at the array level. Filter settings, time windows, and data
quality decisions apply to the whole dataset, and picks are refined across all
traces simultaneously using cross-correlation.

## Workflow

Processing follows a standard pattern:

1. **Initial picks** — broad time windows are placed around approximate phase
   arrivals, typically from a reference model.
2. **ICCS** — the Iterative Cross-Correlation and Stack algorithm refines picks
   and windows across all seismograms simultaneously. Parameters controlling
   the algorithm are adjusted between iterations until the results are
   satisfactory.
3. **Quality control** — seismograms can be selected or deselected manually, or
   automatically by ICCS based on cross-correlation quality.
4. **MCCC** — Multi-Channel Cross-Correlation produces the final relative
   arrival time measurements from the refined picks.

## Snapshots

Because tuning parameters is an inherently iterative process, AIMBAT supports
snapshots — named saves of the current parameter state. Rolling back to a
snapshot restores parameters exactly, without removing other snapshots. This
makes it safe to explore parameter space without losing previous results.
