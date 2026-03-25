# Exporting Results

## Overview

Any snapshot can be exported as a structured JSON document using
`aimbat snapshot results`. The output contains everything needed to identify
the snapshot, the source event, and the per-station arrival-time picks —
including quality metrics from ICCS and, if MCCC has been run, formal timing
standard errors.

Exporting does not require MCCC to have been run. ICCS picks alone are
sufficient for many workflows. MCCC adds formal per-station timing uncertainties
and is worth running when those are required, but the output format is the
same either way — MCCC fields are simply `null` in snapshots that pre-date any
MCCC run.

---

## Running the export

=== "CLI"

    ```bash
    aimbat snapshot results <SNAPSHOT_ID>                    # print to stdout
    aimbat snapshot results <SNAPSHOT_ID> --output out.json  # save to file
    ```

=== "Shell"

    ```bash
    snapshot results <SNAPSHOT_ID>
    snapshot results <SNAPSHOT_ID> --output out.json
    ```

=== "TUI"

    Press `Enter` on a snapshot row in the **Snapshots** tab and choose
    **Save results to JSON**. A file-picker dialog opens; the suggested
    filename is `results_<short_id>.json`.

Pass `--alias` to use camelCase field names (e.g. `snapshotId`, `eventTime`,
`mcccRmse`).

---

## Output format

The output is a JSON object with two parts: an envelope containing event-level
information, and a `seismograms` list with one entry per station.

```json
{
  "snapshot_id": "3f1a2b4c-...",
  "snapshot_time": "2025-03-01T14:22:00Z",
  "snapshot_comment": "post-MCCC final",
  "event_id": "6a4a...",
  "event_time": "2024-11-15T08:43:12Z",
  "event_latitude": 37.2,
  "event_longitude": 141.8,
  "event_depth_km": 35.0,
  "mccc_rmse": 0.021,
  "seismograms": [
    {
      "seismogram_id": "...",
      "name": "II.MAJO",
      "channel": "BHZ",
      "select": true,
      "flip": false,
      "t1": "2024-11-15T08:43:47.312Z",
      "iccs_cc": 0.94,
      "mccc_cc_mean": 0.91,
      "mccc_cc_std": 0.03,
      "mccc_error": 0.018
    }
  ]
}
```

### Envelope fields

Event-level information appears once in the envelope, rather than being
repeated on every seismogram row.

| Field | Type | Always present | Description |
|-------|------|:---:|-------------|
| `snapshot_id` | UUID string | Yes | Snapshot this export came from |
| `snapshot_time` | ISO 8601 | Yes | When the snapshot was taken |
| `snapshot_comment` | string \| null | Yes | Optional label from snapshot creation |
| `event_id` | UUID string | Yes | Event this snapshot belongs to |
| `event_time` | ISO 8601 | Yes | Seismic event origin time |
| `event_latitude` | float | Yes | Event latitude (degrees) |
| `event_longitude` | float | Yes | Event longitude (degrees) |
| `event_depth_km` | float \| null | Yes | Event depth in km; null if not recorded |
| `mccc_rmse` | float \| null | Yes | Global MCCC RMSE (seconds); null if MCCC not run |
| `seismograms` | array | Yes | Per-seismogram entries (see below) |

### Per-seismogram fields

| Field | Type | Always present | Description |
|-------|------|:---:|-------------|
| `seismogram_id` | UUID string | Yes | Seismogram record identifier |
| `name` | string | Yes | Station name in `NETWORK.NAME` format |
| `channel` | string | Yes | Channel code (e.g. `BHZ`) |
| `select` | bool | Yes | Selection state at snapshot time |
| `flip` | bool | Yes | Whether polarity was flipped at snapshot time |
| `t1` | ISO 8601 | Yes | Frozen absolute arrival-time pick |
| `iccs_cc` | float \| null | Yes | Correlation coefficient with ICCS stack |
| `mccc_cc_mean` | float \| null | Yes | Mean pairwise MCCC correlation coefficient |
| `mccc_cc_std` | float \| null | Yes | Std of pairwise MCCC correlation coefficients |
| `mccc_error` | float \| null | Yes | Formal timing standard error from MCCC (seconds) |

`iccs_cc` is `null` for snapshots taken before the event was first opened in
AIMBAT. All MCCC fields are `null` for snapshots taken before MCCC was run.

---

## Working with the output

### Filtering with `jq`

Extract only selected seismograms:

```bash
aimbat snapshot results <SNAPSHOT_ID> | \
  jq '[.seismograms[] | select(.select == true)]'
```

Extract stations where MCCC timing error is below 0.05 s:

```bash
aimbat snapshot results <SNAPSHOT_ID> | \
  jq '[.seismograms[] | select(.mccc_error != null and .mccc_error < 0.05)]'
```

Export station names and pick times as CSV:

```bash
aimbat snapshot results <SNAPSHOT_ID> | \
  jq -r '.seismograms[] | [.name, .t1] | @csv'
```

### Python

```python
import json

with open("results.json") as f:
    data = json.load(f)

print(f"Event: {data['event_time']}  ({data['event_latitude']}, {data['event_longitude']})")
print(f"MCCC RMSE: {data['mccc_rmse']} s")

for seis in data["seismograms"]:
    if seis["select"]:
        print(f"  {seis['name']:12s}  t1={seis['t1']}  err={seis['mccc_error']}")
```

---

## ICCS vs MCCC picks

Picks exported from an ICCS-only snapshot have `t1` values refined by the
iterative stack alignment. Picks from a post-MCCC snapshot have `t1` values
replaced by the least-squares pairwise solution — slightly different in value,
with the addition of formal standard errors in `mccc_error`.

The MCCC-derived `t1` values are generally preferred for applications that
require formal uncertainties. For applications where only relative picks are
needed and uncertainties are not, an ICCS-only snapshot is sufficient.

See [Aligning with ICCS](alignment.md) and [MCCC Alignment](mccc.md) for a
full description of what each algorithm produces and when to use each one.
