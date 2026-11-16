# Quality metric validity

AIMBAT stores quality metrics in the database so they can be displayed without
re-running ICCS or MCCC. A stored metric depends on the parameters it was
computed from, so it is only shown while those parameters are unchanged.

Nothing is cleared when a parameter changes. Each stored value carries a
fingerprint of its inputs, and whatever reads it compares that fingerprint with
the current parameters. A value whose fingerprint no longer matches is reported
as absent, in tables, exports, plots and snapshots alike.

## Quality fields at a glance

| Field | Scope | Source |
| :--- | :--- | :--- |
| `iccs_cc` | per seismogram | ICCS — correlation against the current stack |
| `mccc_cc_mean` | per seismogram | MCCC — mean pairwise CC involving this seismogram |
| `mccc_cc_std` | per seismogram | MCCC — std of those pairwise CCs |
| `mccc_error` | per seismogram | MCCC — formal timing error from the inversion |
| `mccc_rmse` | per event | MCCC — global root-mean-square residual for the array |

## Fingerprints

A fingerprint is a SHA-256 digest of the parameter values as the database
stores them. The digests and their encoding are defined in
`aimbat.core._validity`.

- Building an ICCS instance, or running ICCS, writes each seismogram's
  `iccs_cc` together with its digest (`iccs_fingerprint`).
- Running MCCC writes the results together with their digest
  (`mccc_fingerprint`) and the IDs of the seismograms that took part
  (`mccc_members`). Membership is recorded because MCCC run with `--all`
  includes deselected seismograms, so `select` does not say who took part.
- A reader builds one `Validity` per command. It computes the current digests
  of every event involved in one pass and compares them with the stored
  fingerprints.

## What each result depends on

| Result | Inputs |
| :--- | :--- |
| `iccs_cc` of a seismogram | `window_pre`, `window_post`, `ramp_width`, `bandpass_apply`, `bandpass_fmin`, `bandpass_fmax`, `corners`; which seismograms are selected, and their `t1` and `flip`; the seismogram's own `t1` and `flip` |
| MCCC results | the same event parameters, plus `mccc_damp` and `mccc_min_cc`; `t1` and `flip` of each seismogram in the run |

`min_cc` and `completed` are inputs to neither. `select` is not an input to
MCCC. Which parameter is an input to which result is declared once, on each
parameter field, with `ParameterSpec` in `aimbat.models._parameters`.

## What a change leaves out of date

| Change | `iccs_cc` out of date for… | MCCC results out of date |
| :--- | :--- | :--- |
| Window / bandpass / ramp / corners | All seismograms in the event | Yes |
| `mccc_damp` / `mccc_min_cc` | — | Yes |
| `min_cc` / `completed` | — | — |
| `flip` or `t1`, seismogram selected | All seismograms in the event | If it was in the run |
| `flip` or `t1`, seismogram deselected | This seismogram only | If it was in the run |
| `select` (either direction) | All seismograms in the event | — |
| Seismogram deleted | All, if it was selected | If it was in the run |
| Selected seismogram added | All seismograms in the event | — |

`tests/integration/core/test_validity_rules.py` holds these rules as tables and
checks them for every parameter.

## Restoring from snapshots

A snapshot freezes only values that are valid when it is taken. It records two
digests: `iccs_hash`, the event's instance digest (every seismogram's `iccs_cc`
digest), and `mccc_hash`, the MCCC digest of the run it froze.

After a parameter change through the `set_*` functions, or a rollback,
`resync_quality` restores out-of-date values from the most recent snapshot
whose digests match the current parameters. Valid values are kept, except
that a rollback restores from the snapshot it rolls back to whenever that
snapshot matches. `iccs_cc` and the MCCC results are matched independently.

## Staleness of an ICCS instance

A built ICCS instance records the instance digest of the parameters it was
built from, and is stale once that differs from the stored parameters. The TUI
recomputes two digests on each poll: a changed instance digest rebuilds the
ICCS instance, and a change in the tracked digest (every parameter that is not
bookkeeping) only repaints the panels.
