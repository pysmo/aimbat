# Snapshots

## What a snapshot captures

A snapshot saves the current processing parameters for an event at a point in
time. Specifically, it stores:

- All event-level parameters: the time window, bandpass filter settings, and
  minimum CC norm threshold
- Per-seismogram parameters for every seismogram in the event: the current `t1`
  pick, `select` flag, and `flip` flag

The seismogram waveform data itself is not copied — snapshots are lightweight.
They capture where you are in the parameter space, not the data.

This works because the CC seismograms and context seismograms that ICCS
operates on are entirely deterministic: given the original waveform data and a
set of parameters, they are always reconstructed identically. Restoring a
snapshot therefore restores the exact state of the ICCS instance — there is
nothing lost by not saving the derived arrays.

If seismograms are added to the project after a snapshot was taken, they have
no entry in that snapshot. When previewing or rolling back, those seismograms
are included using their current live parameters — the snapshot's event-level
parameters (window, filter, min CC norm) still apply to them.

Snapshots are per-event. Each event maintains its own list.

---

## When to take a snapshot

Take a snapshot before making changes you might want to undo:

- After importing data, before any processing — a clean baseline to return to
- After initial alignment looks good, before tightening parameters further
- Before trying an experimental configuration (different window, filter, etc.)
- Before running MCCC

Snapshots are cheap. Taking one costs almost nothing, and having a rollback
point available is worth it.

---

## Creating a snapshot

=== "CLI / Shell"

    ```bash
    aimbat snapshot create                        # no comment
    aimbat snapshot create "after bandpass 1–3Hz" # with comment
    ```

    The comment is optional but useful for identifying the snapshot later.

=== "TUI"

    Press `n` to open the snapshot comment dialog, optionally enter a comment,
    and confirm. The new snapshot appears immediately in the **Snapshots** tab.

=== "GUI"

    Click **New Snapshot** in the **Processing** tab. A dialog lets you enter
    an optional comment.

---

## Listing snapshots

=== "CLI / Shell"

    ```bash
    aimbat snapshot list               # for the default event
    aimbat snapshot list --all-events  # across all events
    ```

    The table shows the snapshot ID, date and time, comment, and number of
    seismograms captured.

=== "TUI"

    Snapshots for the current event are listed in the **Snapshots** tab.
    Switch events using the event switcher (`e`) to see another event's
    snapshots.

=== "GUI"

    The **Snapshots** tab lists all snapshots for the selected event.

---

## Inspecting a snapshot

Before rolling back, it can be useful to see what a snapshot contains.

=== "CLI / Shell"

    ```bash
    aimbat snapshot details <SNAPSHOT_ID>  # view saved event parameters
    aimbat snapshot preview <SNAPSHOT_ID>  # view stack plot
    aimbat snapshot preview --matrix <SNAPSHOT_ID>  # view matrix image
    ```

    `details` shows the event-level parameters (window, filter, min_ccnorm) as
    they were when the snapshot was taken. `preview` builds the ICCS stack from
    the snapshot's parameters and displays it — without modifying anything in
    the database.

=== "TUI"

    Press `Enter` on a snapshot row in the **Snapshots** tab to open the action
    menu. Options include:

    - **Show details** — displays the saved event parameters
    - **Preview stack** — opens the stack plot built from the snapshot
    - **Preview matrix image** — opens the matrix image

    Both preview options support the **context** (`c`) and **all seismograms**
    (`a`) toggles in the action menu before launching.

=== "GUI"

    Select a snapshot in the **Snapshots** tab — its stack and matrix image
    are shown in the right panel in read-only mode.

---

## Rolling back

Rolling back restores the snapshot's parameters as the current live values.
This overwrites the current event and seismogram parameters for this event.

=== "CLI / Shell"

    ```bash
    aimbat snapshot rollback <SNAPSHOT_ID>
    ```

=== "TUI"

    Press `Enter` on a snapshot row and choose **Rollback to this snapshot**.
    A confirmation dialog appears before any changes are made.

=== "GUI"

    Select a snapshot and click **Rollback to this**.

After rolling back, the event's parameters are exactly as they were when
the snapshot was taken. Any ICCS runs or parameter changes made after that
snapshot are undone. The snapshot itself is not deleted — you can roll
back to it again.

---

## Deleting a snapshot

=== "CLI / Shell"

    ```bash
    aimbat snapshot delete <SNAPSHOT_ID>
    ```

=== "TUI"

    Press `Enter` on a snapshot row and choose **Delete snapshot**. A
    confirmation dialog appears.

=== "GUI"

    Select a snapshot and click **Delete**.

Deletion is permanent. The snapshot cannot be recovered after deletion.

---

## Exporting snapshot data

For archiving or scripting purposes, snapshot data can be exported to JSON:

=== "CLI / Shell"

    ```bash
    aimbat snapshot dump                  # default event
    aimbat snapshot dump --all-events     # all events
    ```

    The output contains three sections: snapshot metadata, event parameter
    snapshots, and seismogram parameter snapshots, cross-referenced by
    snapshot ID.
