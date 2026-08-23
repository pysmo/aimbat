# Core concepts

## The problem

Teleseismic travel time tomography requires accurate phase arrival picks across
large seismic arrays. Picking each trace individually is slow and error-prone at
scale, and treating each trace in isolation ignores the coherence of the
wavefield across the array.

AIMBAT works at the array level: picks are refined and quality decisions — such
as whether to include a trace or flip its polarity — are made across all traces
simultaneously using cross-correlation.

## Workflow

Processing follows a standard pattern:

1. **Initial picks** — broad time windows are placed around approximate phase
    arrivals, typically from a reference model.
2. **ICCS** — the Iterative Cross-Correlation and Stack algorithm refines picks
    and windows across all seismograms simultaneously. Parameters controlling
    the algorithm are adjusted between iterations until the results are
    satisfactory.
3. **MCCC** — Multi-Channel Cross-Correlation produces the final relative
    arrival time measurements from the refined picks.

## Snapshots

Snapshots are named saves of the current parameter state. This is possible
because the parameters, together with the raw seismograms on disk (which are
never modified), always produce the same working seismograms — the prepared
seismograms used for ICCS and MCCC. A snapshot can be restored exactly, without
discarding other snapshots, so ICCS and MCCC can be re-run with different
parameters or in a different order, and results compared across snapshots. Steps
in the workflow above are often revisited rather than run once in sequence.

Results are always exported from a specific snapshot, not from "the data" as a
whole — there is no single canonical result for an event, since the exported
picks depend on whichever parameters produced that snapshot. This matters most
when parameters are set programmatically rather than adjusted by hand: the same
raw seismograms can yield different results depending on the parameter choices
captured in each snapshot.

## Beyond phase picking

The CLI, interactive shell, and TUI cover the workflow above — importing data,
running ICCS and MCCC, exporting results. All three are wrappers around the same
Python API ([`aimbat.core`][], [`aimbat.models`][]), so
anything they do can also be scripted directly.

AIMBAT as an application is built around that one workflow, but the API itself
is not — it can be used for purposes beyond it. See the
[Python API](../usage/api.md) guide for details.
