# Quality metric validity

A quality metric in AIMBAT belongs to the parameters it was computed from, not
to the ICCS or MCCC run that computed it. A run only determines the value for
the parameters current at that time. The value is stored together with a
fingerprint of those parameters, and is reported only while the fingerprint
matches the current parameters.

Changing a parameter therefore clears no stored values. A value that no longer
matches is reported as absent, whether in a table, an export, a plot or a
snapshot. Setting the parameter back to its earlier value, before the metric has
been recomputed, makes the stored value valid again without a new run.

The metrics themselves are described in
[Quality assessment](../usage/quality.md).

## Digests and fingerprints

The `iccs_cc` of a seismogram depends on the parameters that shape the ICCS
stack. These are parameters of the event, of every selected seismogram, and of
the seismogram itself. The MCCC results depend on the event parameters that
shape the stack or the inversion, and on the parameters of each seismogram that
took part in the run.

Which parameter is an input to which result is declared once, on each parameter
field, with `ParameterSpec` in `aimbat.models._parameters`. The digests are
computed from these declarations, so a new parameter needs no other change to be
tracked.

A digest is a SHA-256 hash of parameter values as the database stores them. Five
digests are computed per event:

| Digest        | Covers                                                                                           | Used for                                                                                             |
| :------------ | :----------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------- |
| Stack         | Event parameters that are inputs to the stack, and the stack inputs of each selected seismogram. | Seismogram CC digest                                                                                 |
| Seismogram CC | The stack digest, and the stack inputs of one seismogram.                                        | `iccs_fingerprint`                                                                                   |
| MCCC          | Event parameters that are inputs to MCCC, and the MCCC inputs of each seismogram in the run.     | `mccc_fingerprint`, and `mccc_hash` of a snapshot                                                    |
| Instance      | Every seismogram CC digest of the event.                                                         | Staleness of a cached ICCS instance, which is rebuilt once it differs, and `iccs_hash` of a snapshot |
| Tracked       | Every parameter of the event and its seismograms that is not bookkeeping.                        | Detection by the TUI of any parameter change, which causes a repaint without a rebuild               |

A fingerprint is the digest that was current when a value was computed, stored
together with the value. Checking a value compares its fingerprint with the
digest computed from the current parameters:

- Building an ICCS instance, or running ICCS, writes each seismogram's `iccs_cc`
    together with its seismogram CC digest (`iccs_fingerprint`).
- Running MCCC writes the results together with their MCCC digest
    (`mccc_fingerprint`) and the IDs of the seismograms that took part
    (`mccc_members`). Membership is recorded because MCCC can include deselected
    seismograms, so `select` does not indicate which seismograms took part.
- Code that reads quality values builds one [`Validity`][aimbat.core.Validity]
    per command. It computes the current digests of every event involved in one
    pass and compares them with the stored fingerprints.

The digests and their encoding are defined in `aimbat.core._validity`.

## What a change leaves out of date

| Change                                                            | `iccs_cc` out of date for    | MCCC results out of date |
| :---------------------------------------------------------------- | :--------------------------- | :----------------------- |
| Event parameter that shapes the stack                             | All seismograms in the event | Yes                      |
| Event parameter of the MCCC inversion only                        | None                         | Yes                      |
| Event parameter that is an input to neither                       | None                         | No                       |
| Seismogram parameter that shapes the stack, seismogram selected   | All seismograms in the event | If it was in the run     |
| Seismogram parameter that shapes the stack, seismogram deselected | This seismogram only         | If it was in the run     |
| Selection of a seismogram (either direction)                      | All seismograms in the event | No                       |
| Seismogram deleted                                                | All, if it was selected      | If it was in the run     |
| Selected seismogram added                                         | All seismograms in the event | No                       |

`tests/integration/core/test_validity_rules.py` holds these rules as tables and
checks them for every parameter.

## Restoring from snapshots

Because a metric belongs to its parameters, a value frozen in a snapshot applies
again whenever the parameters match those of the snapshot. A snapshot freezes
only values that are valid when it is taken.

A snapshot records two stored digests of the same kind as fingerprints.
`mccc_hash` holds the MCCC digest of the run it froze, as `mccc_fingerprint`
does for live values. `iccs_hash` holds a single instance digest for the whole
event, whereas live `iccs_cc` values carry one fingerprint per seismogram. A
change that affects one seismogram only therefore leaves the live values of the
others valid, but prevents the `iccs_cc` values of a snapshot from being
restored.

After a parameter change, or a rollback to a snapshot, out-of-date values are
restored from the most recent snapshot whose digests match the current
parameters. Valid values are kept, except that a rollback restores from the
snapshot it rolls back to whenever that snapshot matches. `iccs_cc` and the MCCC
results are matched independently.
