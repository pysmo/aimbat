# Snapshots

## What a snapshot captures

A snapshot freezes an event's processing state at a point in time:

- all event-level parameters: time window, bandpass filter, minimum CC
- per-seismogram `t1`, `select`, and `flip` for every seismogram in the event
- quality metrics available at the time: ICCS CC per seismogram (present once the
    event has been opened), and MCCC metrics plus the global RMSE (only if MCCC
    has run)
- whether it was created automatically (`aimbat data add`) or explicitly

Waveform data are not copied. A snapshot records a position in parameter space,
not the data. Restoring one reconstructs the exact ICCS state, because the CC and
context seismograms are fully determined by the raw data and the parameters.

Snapshots are per-event; each event keeps its own list. A seismogram added after
a snapshot has no entry in it, and is included in a rollback with its current
live parameters. The snapshot's event-level parameters still apply to it.

## When to take a snapshot

Before a change that might need undoing:

- after initial alignment looks good, before tightening parameters
- before an experimental configuration (a different window or filter)
- before running MCCC

`aimbat data add` snapshots each event that received new data, so a clean
post-import baseline already exists. See
[Adding Data](data.md#automatic-snapshots).

## Creating a snapshot

=== "CLI"

    ```bash
    aimbat snapshot create <ID>                        # no comment
    aimbat snapshot create <ID> "after bandpass 1–3Hz" # with comment
    ```

=== "Shell"

    ```bash
    snapshot create
    snapshot create "after bandpass 1–3Hz"
    ```

=== "TUI"

    Press `n`, optionally enter a comment, and confirm. The snapshot appears in
    the **Snapshots** tab.

The comment is optional but helps identify the snapshot later.

## Listing snapshots

=== "CLI"

    ```bash
    aimbat snapshot list <ID>  # one event
    aimbat snapshot list all   # every event
    ```

=== "Shell"

    ```bash
    snapshot list <ID>
    snapshot list all
    ```

=== "TUI"

    The **Snapshots** tab lists the selected event's snapshots. Select another
    event first to see its snapshots.

The table shows the ID, timestamp, comment, the automatic flag, and the
seismogram count.

## Inspecting a snapshot

=== "CLI"

    ```bash
    aimbat snapshot details <SNAPSHOT_ID>          # saved event parameters
    aimbat snapshot preview <SNAPSHOT_ID>          # stack plot
    aimbat snapshot preview --matrix <SNAPSHOT_ID> # matrix image
    ```

=== "Shell"

    ```bash
    snapshot details <SNAPSHOT_ID>
    snapshot preview <SNAPSHOT_ID>
    snapshot preview --matrix <SNAPSHOT_ID>
    ```

=== "TUI"

    Press `Enter` on a snapshot row for **Show details**, **Preview stack**, or
    **Preview matrix image**. The **context** (`c`) and **all seismograms** (`a`)
    toggles apply.

`details` shows the event-level parameters as they were when the snapshot was
taken. `preview` builds the stack from the snapshot's parameters without
modifying the database.

## Rolling back

Rolling back restores the snapshot's parameters as the current live values,
overwriting the event's current parameters. Any ICCS runs or parameter changes
made since are undone. The snapshot is not deleted and can be rolled back to
again.

=== "CLI"

    ```bash
    aimbat snapshot rollback <SNAPSHOT_ID>
    ```

=== "Shell"

    ```bash
    snapshot rollback <SNAPSHOT_ID>
    ```

=== "TUI"

    Press `Enter` on a snapshot row and choose **Rollback to this snapshot**. A
    confirmation dialog appears first.

If the snapshot holds MCCC quality data, the live quality metrics are restored
too. See
[`aimbat snapshot rollback`][aimbat._cli.snapshot.cli_snapshot_rollback] for the
rule used to pick which snapshot's quality data are restored.

## Deleting a snapshot

=== "CLI"

    ```bash
    aimbat snapshot delete <SNAPSHOT_ID>
    ```

=== "Shell"

    ```bash
    snapshot delete <SNAPSHOT_ID>
    ```

=== "TUI"

    Press `Enter` on a snapshot row and choose **Delete snapshot**.

Deletion is permanent.

## Notes

Each snapshot can carry a freeform Markdown note, for recording observations or
decisions at the time it was taken.

=== "CLI"

    ```bash
    aimbat snapshot note read <SNAPSHOT_ID>
    aimbat snapshot note edit <SNAPSHOT_ID>  # opens $EDITOR, saves on exit
    ```

=== "Shell"

    ```bash
    snapshot note read <SNAPSHOT_ID>
    snapshot note edit <SNAPSHOT_ID>
    ```

With no note yet, `read` prints `(no note)` and `edit` opens an empty buffer. The
note is saved when the editor closes without error.

## Exporting

Two exports, for different purposes:

- **`snapshot results`** — a curated per-station arrival-time document (frozen
    `t1`, ICCS CC, MCCC metrics if run). This is the format for downstream tools
    such as tomographic inversion. See [Exporting Results](results.md).
- **`snapshot dump`** — the raw snapshot tables as JSON, for archiving or
    scripting.

```bash
aimbat snapshot dump
```

The dump is a JSON object with five keys, cross-referenced by `snapshot_id`:

| Key | Contents | Always present |
| --- | --- | --- |
| `snapshots` | metadata (ID, time, comment, `automatic` flag, hash) | Yes |
| `event_parameters` | event parameter snapshots | Yes |
| `seismogram_parameters` | per-seismogram parameter snapshots | Yes |
| `event_quality` | event quality (MCCC RMSE) | Only if MCCC has run |
| `seismogram_quality` | per-seismogram quality (ICCS CC, MCCC metrics) | Only if quality metrics exist |

## Quality statistics

A summary of quality metrics across all of an event's snapshots, without opening
each one:

=== "CLI"

    ```bash
    aimbat snapshot quality list <ID>  # one event
    aimbat snapshot quality list all   # every event
    aimbat snapshot quality dump       # raw JSON
    ```

=== "Shell"

    ```bash
    snapshot quality list <ID>
    snapshot quality list all
    snapshot quality dump
    ```

The table shows per-snapshot aggregated ICCS CC and, where MCCC has run, its
metrics (mean, SEM) and the global RMSE, making it easy to compare quality across
snapshots.
