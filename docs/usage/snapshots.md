# Snapshots

## When to take a snapshot

Before a change that might need undoing:

- after initial alignment looks good, before tightening parameters
- before an experimental configuration (a different window or filter)
- before running MCCC

`aimbat data add` snapshots each event that received new data, so a clean
post-import baseline already exists. See
[Adding Data](data.md#automatic-snapshots).

!!! tip "Snapshot good parameter combinations — final results are exported from snapshots"

    A promising combination is only exportable once it has been snapshotted,
    so snapshotting one as soon as it looks good works better than waiting
    until the end. It also leaves multiple parameter sets to compare, and a
    choice of which results to keep. See [Exporting Results](results.md).

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

=== "API"

    ```python
    from sqlmodel import Session, select
    from aimbat.db import engine
    from aimbat.core import create_snapshot
    from aimbat.models import AimbatEvent

    with Session(engine) as session:
        event = session.exec(select(AimbatEvent)).first()
        create_snapshot(session, event, comment="after bandpass 1–3Hz")
    ```

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

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import get_snapshots

    with Session(engine) as session:
        snapshots = get_snapshots(session, event_id)  # one event
        all_snapshots = get_snapshots(session)         # every event
    ```

The CLI, shell, and TUI table shows the ID, timestamp, comment, the automatic
flag, and the seismogram count. The API returns `AimbatSnapshot` objects with
the same information as attributes.

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

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import build_iccs_from_snapshot
    from aimbat.plot import plot_stack

    with Session(engine) as session:
        bound = build_iccs_from_snapshot(session, snapshot_id)
        plot_stack(bound.iccs, context=True, all_seismograms=False, return_fig=False)
    ```

    [`build_iccs_from_snapshot`][aimbat.core.build_iccs_from_snapshot] reads
    waveform data live but uses the snapshot's parameters; it never writes to
    the database.

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

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import rollback_to_snapshot

    with Session(engine) as session:
        rollback_to_snapshot(session, snapshot_id)
    ```

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

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import delete_snapshot

    with Session(engine) as session:
        delete_snapshot(session, snapshot_id)
    ```

Deletion is permanent.

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

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.core import dump_snapshot_quality_table

    with Session(engine) as session:
        stats = dump_snapshot_quality_table(session, event_id=event_id)  # one event
        all_stats = dump_snapshot_quality_table(session)                 # every event
    ```

All three surface per-snapshot aggregated ICCS CC and, where MCCC has run, its
metrics (mean, SEM) and the global RMSE, making it easy to compare quality
across snapshots. The CLI and shell render a table; the API returns the same
fields as a list of dicts.
