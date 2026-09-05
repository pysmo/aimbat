# Core concepts

## Motivation

Teleseismic travel time tomography requires accurate phase arrival picks across
large seismic arrays. Picking each trace individually is slow and error-prone at
scale. It also ignores the coherence of the teleseismic wavefield. Within the
phase window, traces across the array are similar, differing mainly by a
relative time shift.

AIMBAT exploits that coherence. Traces are aligned on a rough initial pick and
stacked into a reference waveform. The stack has a higher signal-to-noise ratio
than any individual trace. Cross-correlating each trace against the stack yields
its relative arrival time. The same comparison drives quality decisions such as
whether to include a trace or flip its polarity.

## The processing pipeline

The measurement runs as a three-stage pipeline:

1. **Initial picks.** Broad time windows are placed around approximate phase
    arrivals, typically from a reference model.
2. **ICCS.** The Iterative Cross-Correlation and Stack algorithm repeats the
    stack-and-cross-correlate step. Each pass re-stacks the newly aligned traces
    and re-picks against the updated stack, until the stack stabilises. Window
    and filter parameters are adjusted between runs.
3. **MCCC.** Multi-Channel Cross-Correlation produces the final relative
    arrival time measurements from the refined picks.

These stages are not run once in sequence. ICCS is repeated as parameters
change. MCCC can be run at any point, not only at the end.

## Snapshots

Because the pipeline is revisited rather than run straight through, AIMBAT
records state in snapshots. A snapshot is a named save of the current parameter
state.

Snapshots work because the inputs are fixed. The raw seismograms on disk are
never modified, so a given set of parameters always produces the same working
seismograms. These are the prepared seismograms used for ICCS and MCCC.

A snapshot can be restored exactly, without discarding other snapshots. ICCS and
MCCC can then be re-run with different parameters, or in a different order, and
the results compared.

Results are always exported from a specific snapshot, not from "the data" as a
whole. There is no single canonical result for an event: the exported picks
depend on whichever parameters produced that snapshot. This matters most when
parameters are set programmatically rather than adjusted by hand. The same raw
seismograms can then yield different results, depending on the parameter choices
captured in each snapshot.

## Beyond phase picking

Setting parameters programmatically is possible because the interfaces are thin.
The CLI, interactive shell, and TUI all cover the workflow above: importing
data, running ICCS and MCCC, and exporting results. All three are wrappers
around the same Python API ([`aimbat.core`][], [`aimbat.models`][]). Anything
they do can also be scripted directly.

AIMBAT as an application is built around that one workflow, but the API itself is
not limited to it. Each usage chapter shows the API calls for that step; see
[Recipes](../usage/recipes.md) for API fundamentals and cross-cutting scripts.
