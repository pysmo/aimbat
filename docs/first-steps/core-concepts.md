# Core concepts

## Motivation

Precise phase arrival picks are the foundation of travel time tomography —
the accuracy of the resulting images of Earth's interior depends directly on
the quality of these measurements. Obtaining them requires picking the phase
arrival and assessing data quality for every seismogram, across every event
in the dataset. With modern seismic arrays recording each earthquake on
increasingly large numbers of seismometers, doing this seismogram by seismogram
quickly becomes impractical.

AIMBAT addresses this by shifting the focus from individual seismograms to the
dataset as a whole. Rather than assessing and processing each trace in
isolation, the focus is at the array level — where data quality and phase
arrivals can be judged in the context of all seismograms at once. Decisions
about filter settings, time windows, and which seismograms to include apply to
the entire dataset, and picks are refined across all traces simultaneously.
Everything is processed in bulk.

## Semi-automatic

This bulk processing happens in a semi-automatic way, whereby initial picks
surrounded by large time windows are iteratively refined into accurate phase
arrival picks with narrow time windows. Selecting high quality seismograms and
updating picks (for all stations simultaneously) are either performed manually,
or automatically by the ICCS algorithm. The automatically refined picks depend
on user-adjustable parameters, which are typically tuned between iterations to
achieve the best results. Once satisfied with the picks and parameter settings,
MCCC is run to produce the final relative arrival time measurements.

## Snapshots and rollback

The iterative nature of the workflow means exploring different parameter
combinations is central to the process. This is safe to do because the
seismogram data themselves are never modified — AIMBAT only stores and updates
processing parameters separately from the data.

To support this further, snapshots of the current parameter state can be saved
at any point during processing — including before any changes are made.
Rolling back to a snapshot restores the parameters exactly as they were, but
does not delete any other snapshots, so it is possible to switch freely between
saved states.
