# Quality Assessment

## Overview

AIMBAT provides a suite of statistical metrics to help you assess the reliability
of your arrival-time picks. Metrics come from two sources:

- **ICCS CC** — computed whenever an ICCS instance is created (i.e. on any
  operation that touches the active event). No explicit run step is needed.
- **MCCC metrics** — computed only when you explicitly run the MCCC pass.

Both types are captured in snapshots and displayed in the Event and Station views.

---

## ICCS Cross-Correlation (Live)

For every seismogram, AIMBAT records the **Pearson cross-correlation coefficient**
between that seismogram and the current ICCS stack as `iccs_cc`.

- **When it is computed**: automatically whenever AIMBAT loads or processes an
  event — for example when running ICCS, displaying waveforms, or adjusting the
  minimum CC threshold. You do not need to run any explicit step.
- **What it tells you**: How closely the waveform matches the array stack under
  the current window and filter settings. It is the basis for the
  `--autoselect` threshold.
- **Interpretation**: Values closer to 1.0 indicate high similarity to the stack.
  Values near 0 or negative suggest misalignment, poor SNR, or a polarity flip.

Because ICCS CC is computed automatically, it is available for every event that
has been opened in the current session — including events that are not currently
active.

---

## MCCC Metrics

When you run MCCC, the following statistics are calculated for every participating
seismogram:

### CC Mean (Waveform Similarity)

The **CC Mean** is the arithmetic mean of all pairwise cross-correlation
coefficients involving a specific seismogram.

- **What it tells you**: How similar a station's waveform is to the rest of the
  array. It serves as a proxy for the Signal-to-Noise Ratio (SNR).
- **Interpretation**: Values closer to 1.0 indicate very high similarity. Low
  values (e.g., < 0.6) often suggest noisy sites or instrument issues.

### CC Std (Waveform Consistency)

The **CC Std** is the standard deviation of those same correlation coefficients.

- **What it tells you**: Whether the station's waveform matches the *entire*
  array consistently, or only a subset of it.
- **Interpretation**: A high CC Std indicates that the waveform shape is evolving
  as it passes through the array, likely due to significant site effects or
  complex geology (structural boundaries).

### Timing Error (Precision)

The **Timing Error** is the formal standard error of the arrival-time estimate,
derived from the covariance matrix of the least-squares inversion.

- **What it tells you**: How "stable" the station's timing is relative to the
  network geometry and the quality of the correlations.
- **Interpretation**: This is your primary metric for QC. High error values
  suggest inconsistent relative delays, often caused by cycle skipping or
  severe noise.

### Global RMSE (Network Fit)

The **RMSE** (Root-Mean-Square Error) is a single value for the entire event.

- **What it tells you**: The overall "tightness" of the mathematical fit for the
  entire array.
- **Interpretation**: A high global RMSE suggests the array may be too large or
  sparse to be treated as a single coherent arrival (e.g., the wavefront is
  distorted by a major tectonic boundary).

---

## Quality Control Quick-Reference

Use the combination of **ICCS CC**, **CC Mean**, and **Timing Error** to triage
your data:

| ICCS CC | CC Mean | Timing Error | Interpretation | Recommended Action |
| :--- | :--- | :--- | :--- | :--- |
| **High** | **High** | **Low** | Robust pick. | Keep. |
| **High** | **High** | **High** | Likely **Cycle Skip**. | Manually re-pick or discard. |
| **High** | **Low** | **Low** | Noisy site, but stable timing. | Keep with caution. |
| **Low** | — | — | Poor waveform similarity. | Review window/filter or discard. |
| — | **Low** | **High** | Poor data quality. | Discard seismogram. |

---

## Aggregated Statistics

In the Event and Station views, AIMBAT provides aggregated statistics across
the seismograms included in the most recent MCCC run. The label shows
**"Averages across N seismograms"** where N is the count of seismograms that
have quality records in the active snapshot.

These aggregates include the **SEM** (Standard Error of the Mean), which
quantifies the uncertainty of the average itself.

---

## Scope of Quality Data

### ICCS CC

ICCS CC is updated automatically each time AIMBAT processes an event, so it is
available for all seismograms in any snapshot created after the event was first
opened. It does not require an explicit MCCC run.

### Rollback

When you roll back to a snapshot, AIMBAT restores the live quality metrics from
the most recent snapshot whose parameter hash matches the restored state and
that has MCCC quality data. This means your quality view reflects the metrics
that were valid for those parameters, without having to re-run MCCC.

If no snapshot with a matching hash contains MCCC data (e.g. you rolled back to
a state that pre-dates any MCCC run), the live MCCC metrics are left unchanged.

### MCCC Metrics

MCCC can be run in two mutually exclusive modes, controlled by the `--all` flag:

- **Selected only** (default, `--all` omitted): quality metrics are computed and
  stored only for seismograms whose `select` flag is `True`.
- **All seismograms** (`--all`): quality metrics are computed and stored for
  every seismogram, regardless of selection state.

The mode used is determined from the snapshot data itself: if any seismogram that
was deselected at snapshot time has MCCC quality records, the run is treated as
"all seismograms". In particular:

- A **deselected seismogram** will show MCCC quality data only if it has a record
  in the most recent MCCC snapshot — meaning MCCC was run with `--all` at that
  time. If the most recent run used selected-only mode, its MCCC quality view
  will be empty, even if an older snapshot contains data for it.
- Running MCCC twice with the same parameters but different `--all` values
  produces two snapshots; AIMBAT always reports from the most recent one.
