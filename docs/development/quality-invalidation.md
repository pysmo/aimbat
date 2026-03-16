# Quality Metric Invalidation

AIMBAT stores quality metrics in the database so they can be displayed without
re-running expensive computations. Because those metrics depend on the current
parameter set and seismogram selection, they must be cleared whenever a change
makes them stale. This is handled automatically by SQLite triggers at commit
time — you never need to clear them manually.

This page documents every case that triggers invalidation and explains the
reasoning behind it.

---

## Quality fields at a glance

| Field | Scope | Source |
| :--- | :--- | :--- |
| `iccs_cc` | per seismogram | ICCS — correlation against the current stack |
| `mccc_cc_mean` | per seismogram | MCCC — mean pairwise CC involving this seismogram |
| `mccc_cc_std` | per seismogram | MCCC — std of those pairwise CCs |
| `mccc_error` | per seismogram | MCCC — formal timing error from the inversion |
| `mccc_rmse` | per event | MCCC — global root-mean-square residual for the array |

When a field is *invalidated* its database column is set to `NULL`. It will be
recomputed the next time ICCS or MCCC is run.

---

## Inferring MCCC participation

A seismogram is included in a MCCC run either because it was selected (default
mode) or because MCCC was run with `--all` (all seismograms). The `select` flag
alone is therefore not a reliable indicator of whether a seismogram contributed
to the current MCCC results.

The correct signal is the presence of **live MCCC stats**: if `mccc_cc_mean IS
NOT NULL` for a seismogram, it was included in the last MCCC run. The triggers
use this as the criterion for deciding whether an MCCC invalidation is necessary.

---

## Event-level parameter changes

### Window, bandpass, and ramp parameters

**Trigger**: `null_all_quality_on_window_bandpass_change`

**Fields nulled**: all seismogram-level fields + `mccc_rmse`

| Changed parameter | Why all quality is invalidated |
| :--- | :--- |
| `window_pre` / `window_post` | The analysis window defines which part of the waveform is used. Every correlation and inversion result changes when the window shifts. |
| `ramp_width` | The cosine taper at the window edges is part of the signal preprocessing, so even small ramp changes alter the effective waveform. |
| `bandpass_apply` | Toggling the filter on/off produces a different signal for both ICCS and MCCC. |
| `bandpass_fmin` / `bandpass_fmax` | Changing the passband changes the signal used to compute all correlations. |

### MCCC-specific parameters

**Trigger**: `null_mccc_quality_on_mccc_params_change`

**Fields nulled**: `mccc_cc_mean`, `mccc_cc_std`, `mccc_error`, `mccc_rmse`
(`iccs_cc` is **not** nulled — the ICCS stack is unaffected)

| Changed parameter | Why MCCC quality is invalidated |
| :--- | :--- |
| `mccc_damp` | Tikhonov regularisation strength changes the inversion solution and therefore all MCCC output statistics. |
| `mccc_min_cc` | The minimum CC threshold controls which seismogram pairs enter the inversion, directly changing `mccc_error`, `mccc_cc_mean`, and `mccc_rmse`. |

---

## Per-seismogram parameter changes

### `flip` changes

**Trigger**: `null_quality_on_seis_flip_change`

**ICCS** — if selected, the stack changes so `iccs_cc` is nulled for all
seismograms in the event. If deselected, the stack is unchanged but the
flipped seismogram's own `iccs_cc` is stale (its polarity relative to the
stack has reversed), so only that seismogram's `iccs_cc` is nulled.

**MCCC** — nulled for all seismograms in the event **if the seismogram has live
MCCC stats** (`mccc_cc_mean IS NOT NULL`). This covers both the default
(selected-only) and `--all` MCCC modes:

| Scenario | MCCC nulled? | Reason |
| :--- | :--- | :--- |
| Selected, has live MCCC stats | Yes | Was in MCCC run; flipping changes the correlation pattern. |
| Selected, no live MCCC stats | No | MCCC has not been run; nothing to null. |
| Deselected, has live MCCC stats | Yes | Was included via `--all`; flip invalidates those results. |
| Deselected, no live MCCC stats | No | Was not in MCCC run; nothing to null. |

### `select` changes

**Trigger**: `null_quality_on_seis_select_change`

**ICCS** — always nulled for all seismograms in the event. The stack
composition changes in both directions (selecting or deselecting), making every
stored `iccs_cc` stale.

**MCCC** — nulled for all seismograms in the event **if the seismogram has live
MCCC stats**:

| Scenario | MCCC nulled? | Reason |
| :--- | :--- | :--- |
| Has live MCCC stats (selected-only run) | Yes | Changing selection alters the MCCC set for the next run. |
| Has live MCCC stats (`--all` run) | Yes | Conservative: the seismogram was in the previous run; the next run may differ. |
| No live MCCC stats | No | MCCC has not been run; nothing to null. |

### `t1` changes

**Trigger**: `null_quality_on_seis_t1_change`

`t1` is the current arrival-time pick. ICCS invalidation depends on whether the
seismogram is in the stack (`select`); MCCC invalidation depends on whether the
seismogram was in the MCCC run (live stats).

**ICCS:**

| `select` | `iccs_cc` nulled for… |
| :--- | :--- |
| `TRUE` | All seismograms in the event — the stack changed. |
| `FALSE` | This seismogram only — it is not in the stack, but its own correlation with the current stack is stale. |

**MCCC:**

| Scenario | MCCC nulled? | Reason |
| :--- | :--- | :--- |
| Has live MCCC stats (any `select`) | Yes | Whether it was selected or included via `--all`, the stored arrival time has changed and MCCC results are stale. |
| No live MCCC stats | No | Seismogram was not in the MCCC run; nothing to null. |

---

## Summary table

| Change | `iccs_cc` nulled for… | MCCC metrics nulled for… | `mccc_rmse` nulled |
| :--- | :--- | :--- | :--- |
| Window / bandpass / ramp | All seismograms in event | All seismograms in event | Yes |
| MCCC parameters (`damp`, `min_cc`) | — | All seismograms in event | Yes |
| `flip` (if selected) | All seismograms in event | All, if live MCCC stats | If live MCCC stats |
| `flip` (if deselected) | This seismogram only | All, if live MCCC stats | If live MCCC stats |
| `select` (either direction) | All seismograms in event | All, if live MCCC stats | If live MCCC stats |
| `t1` (if selected) | All seismograms in event | All, if live MCCC stats | If live MCCC stats |
| `t1` (if deselected) | This seismogram only | All, if live MCCC stats | If live MCCC stats |
