# Exporting results

## Overview

Any snapshot exports as a structured JSON document with `aimbat snapshot
results`. It carries what is needed to identify the snapshot and its event, the
per-station picks, ICCS correlation coefficients, and, if MCCC has run, formal
timing standard errors.

MCCC is not required. ICCS picks alone suffice for many workflows. The format is
the same either way; MCCC fields are `null` in a snapshot that predates any MCCC
run.

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

    Press `Enter` on a snapshot row in the **Snapshots** tab and choose **Save
    results to JSON**. A file-picker dialog opens. The suggested filename is
    `results_<short_id>.json`.

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import dump_snapshot_results

    with Session(engine) as session:
        results = dump_snapshot_results(session, snapshot_id)
    ```

    `results` is the same dict the CLI serialises to JSON. Pass
    `by_alias=True` for the camelCase field names `--alias` produces.

The CLI and shell commands accept `--alias` to use camelCase field names (e.g.
`snapshotId`, `eventTime`, `mcccRmse`).

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
  "event_depth": 35000.0,
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

Event-level information appears once in the envelope, rather than being repeated
on every seismogram row.

| Field              | Type           | Always present | Description                                      |
| ------------------ | -------------- | :------------: | ------------------------------------------------ |
| `snapshot_id`      | UUID string    |      Yes       | Snapshot this export came from                   |
| `snapshot_time`    | ISO 8601       |      Yes       | When the snapshot was taken                      |
| `snapshot_comment` | string \| null |      Yes       | Optional label from snapshot creation            |
| `event_id`         | UUID string    |      Yes       | Event this snapshot belongs to                   |
| `event_time`       | ISO 8601       |      Yes       | Seismic event origin time                        |
| `event_latitude`   | float          |      Yes       | Event latitude (degrees)                         |
| `event_longitude`  | float          |      Yes       | Event longitude (degrees)                        |
| `event_depth`      | float \| null  |      Yes       | Event depth in metres, null if not recorded      |
| `mccc_rmse`        | float \| null  |      Yes       | Global MCCC RMSE (seconds), null if MCCC not run |
| `seismograms`      | array          |      Yes       | Per-seismogram entries (see below)               |

### Per-seismogram fields

| Field           | Type          | Always present | Description                                      |
| --------------- | ------------- | :------------: | ------------------------------------------------ |
| `seismogram_id` | UUID string   |      Yes       | Seismogram record identifier                     |
| `name`          | string        |      Yes       | Station name in `NETWORK.NAME` format            |
| `channel`       | string        |      Yes       | Channel code (e.g. `BHZ`)                        |
| `select`        | bool          |      Yes       | Selection state at snapshot time                 |
| `flip`          | bool          |      Yes       | Whether polarity was flipped at snapshot time    |
| `t1`            | ISO 8601      |      Yes       | Frozen absolute arrival-time pick                |
| `iccs_cc`       | float \| null |      Yes       | Correlation coefficient with ICCS stack          |
| `mccc_cc_mean`  | float \| null |      Yes       | Mean pairwise MCCC correlation coefficient       |
| `mccc_cc_std`   | float \| null |      Yes       | Std of pairwise MCCC correlation coefficients    |
| `mccc_error`    | float \| null |      Yes       | Formal timing standard error from MCCC (seconds) |

`iccs_cc` is `null` for snapshots taken before the event was first opened in
AIMBAT. All MCCC fields are `null` for snapshots taken before MCCC was run.

See [Working with exported results](recipes.md#working-with-exported-results)
for `jq` and Python examples of filtering and reading this output.

## ICCS vs MCCC picks

An ICCS-only snapshot has `t1` values from the iterative stack alignment. A
post-MCCC snapshot has `t1` from the least-squares pairwise solution instead:
slightly different in value, plus formal standard errors in `mccc_error`.

The MCCC `t1` values are preferable where formal uncertainties matter; an
ICCS-only snapshot is enough where only relative picks are needed.

See [Aligning with ICCS](alignment.md) and [MCCC Alignment](mccc.md) for what
each algorithm produces and when to use it.
