# Quality assessment

AIMBAT records statistical metrics for judging how reliable the arrival-time
picks are, from two sources:

- **ICCS CC.** Recorded whenever an ICCS instance is created, which happens on
    any operation that touches an event. No explicit step.
- **MCCC metrics.** Recorded only when MCCC is run.

Both are captured in snapshots and shown in the event and station views.

## ICCS cross-correlation

For every seismogram, AIMBAT records the Pearson cross-correlation coefficient
between it and the current ICCS stack as `iccs_cc`.

- **What it shows.** How closely the waveform matches the array stack under the
    current window and filter. This is the value the autoselect threshold
    (`min_cc`) is compared against.
- **How to read it.** Near 1.0 means high similarity to the stack. Near zero or
    negative suggests misalignment, poor signal-to-noise, or an unflipped
    polarity.

Because it is computed automatically, `iccs_cc` is available for every event
opened in the session and for any snapshot taken after the event was first
opened. It does not need an MCCC run.

## MCCC metrics

Computed for every participating seismogram when MCCC runs.

### CC mean

The mean of all pairwise cross-correlation coefficients involving a seismogram.

- **What it shows.** How similar a station's waveform is to the rest of the
    array; a proxy for signal-to-noise.
- **How to read it.** Near 1.0 is high similarity. Below about 0.6 often points
    to a noisy site or an instrument problem.

### CC standard deviation

The standard deviation of those same pairwise coefficients.

- **What it shows.** Whether the waveform matches the whole array consistently,
    or only part of it.
- **How to read it.** A high value means the shape changes as it crosses the
    array, often from strong site effects or complex structure.

### Timing error

The formal standard error of the arrival-time estimate, from the covariance
matrix of the least-squares inversion.

- **What it shows.** How stable the station's timing is, given the array geometry
    and the correlation quality.
- **How to read it.** The main quality-control metric. High values suggest
    inconsistent relative delays, often from cycle skipping or severe noise.

### Global RMSE

A single root-mean-square residual for the whole event.

- **What it shows.** How tightly the inversion fits the array as a whole.
- **How to read it.** A high value suggests the array is too large or too sparse
    to be one coherent arrival, for example when the wavefront is distorted by a
    major tectonic boundary.

## Quick reference

Use `iccs_cc`, CC mean, and timing error together to triage:

| ICCS CC | CC mean | Timing error | Reading | Action |
| :--- | :--- | :--- | :--- | :--- |
| High | High | Low | Reliable pick | Keep |
| High | High | High | Likely cycle skip | Re-pick by hand or discard |
| High | Low | Low | Noisy site, stable timing | Keep with caution |
| Low | — | — | Poor waveform similarity | Review window or filter, or discard |
| — | Low | High | Poor data quality | Discard the seismogram |

## Aggregated statistics

The event and station views also show aggregates across the seismograms in the
most recent MCCC run, labelled "Averages across N seismograms" where N is the
number with quality records in the active snapshot. The aggregates include the
standard error of the mean.

## Which metrics a snapshot shows

- Rolling back to a snapshot restores its quality metrics along with its
    parameters, so the quality view matches that parameter state with no MCCC
    re-run. See [Rolling back](snapshots.md#rolling-back).
- An MCCC run in the default mode stores metrics for `select = True` seismograms
    only; `--all` stores them for every seismogram. The mode is inferred from the
    snapshot, and the view always reports the most recent MCCC run, so a
    deselected seismogram shows MCCC data only if the last run used `--all`.
