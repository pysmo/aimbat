# Snapshots

## What a snapshot captures

A snapshot saves the current processing parameters and quality metrics for an
event at a point in time. Specifically, it stores:

- All event-level parameters: the time window, bandpass filter settings, and
  Min CC (`min_cc`) — see [Aligning with ICCS](alignment.md) for what each
  controls
- Per-seismogram parameters for every seismogram in the event: the current `t1`
  pick, `select` flag, and `flip` flag
- Quality metrics, if available at snapshot time:
  - ICCS CC per seismogram (always present once the event has been opened)
  - MCCC metrics per seismogram and the global RMSE (present only if MCCC has
      been run)

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
parameters (window, filter, Min CC) still apply to them.

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

=== "CLI"

    ```bash
    aimbat snapshot create <ID>                        # no comment
    aimbat snapshot create <ID> "after bandpass 1–3Hz" # with comment
    ```

=== "Shell"

    ```bash
    snapshot create                        # no comment
    snapshot create "after bandpass 1–3Hz" # with comment
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

=== "CLI"

    ```bash
    aimbat snapshot list <ID>  # for a specific event
    aimbat snapshot list all   # across all events
    ```

=== "Shell"

    ```bash
    snapshot list <ID>  # uses the current event context
    snapshot list all   # across all events
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

=== "CLI"

    ```bash
    aimbat snapshot details <SNAPSHOT_ID>          # view saved event parameters
    aimbat snapshot preview <SNAPSHOT_ID>          # view stack plot
    aimbat snapshot preview --matrix <SNAPSHOT_ID> # view matrix image
    ```

=== "Shell"

    ```bash
    snapshot details <SNAPSHOT_ID>
    snapshot preview <SNAPSHOT_ID>
    snapshot preview --matrix <SNAPSHOT_ID>
    ```

`details` shows the event-level parameters (window, filter, min_cc) as
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

=== "CLI"

    ```bash
    aimbat snapshot rollback <SNAPSHOT_ID>
    ```

=== "Shell"

    ```bash
    snapshot rollback <SNAPSHOT_ID>
    ```

=== "TUI"

    Press `Enter` on a snapshot row and choose **Rollback to this snapshot**.
    A confirmation dialog appears before any changes are made.

=== "GUI"

    Select a snapshot and click **Rollback to this**.

After rolling back, the event's parameters are exactly as they were when the
snapshot was taken. Any ICCS runs or parameter changes made after that snapshot
are undone. The snapshot itself is not deleted — you can roll back to it again.

If the snapshot contains MCCC quality data, the live quality metrics are
restored from the best matching snapshot: the one whose parameter hash matches
the restored state and that has the most recent MCCC data. In practice this is
the snapshot you rolled back to, but if that snapshot predates any MCCC run,
the most recent snapshot with the same parameters and MCCC data is used instead.

---

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

    Press `Enter` on a snapshot row and choose **Delete snapshot**. A
    confirmation dialog appears.

=== "GUI"

    Select a snapshot and click **Delete**.

Deletion is permanent. The snapshot cannot be recovered after deletion.

---

## Exporting snapshot data

For archiving or scripting purposes, snapshot data can be exported to JSON:

=== "CLI"

    ```bash
    aimbat snapshot dump
    ```

=== "Shell"

    ```bash
    snapshot dump
    ```

The output is a JSON object with five keys, all cross-referenced by
`snapshot_id`:

| Key | Contents | Always present? |
|-----|----------|----------------|
| `snapshots` | Snapshot metadata (ID, time, comment, hash) | Yes |
| `event_parameters` | Event parameter snapshots | Yes |
| `seismogram_parameters` | Per-seismogram parameter snapshots | Yes |
| `event_quality` | Event quality snapshots (MCCC RMSE) | Only if MCCC has been run |
| `seismogram_quality` | Per-seismogram quality snapshots (ICCS CC, MCCC metrics) | Only if quality metrics exist |

---

## Saving results

Any snapshot can be exported as a structured JSON document containing the
frozen `t1` picks, ICCS correlation coefficients, and — if MCCC was run before
the snapshot — per-seismogram MCCC quality metrics and the event-level RMSE.
MCCC does not need to have been run; the export is useful at any stage of
processing.

This is the primary format for passing AIMBAT picks into downstream tools such
as tomographic inversion codes. See [Exporting Results](results.md) for full
details on the output format and how to work with it.

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
    filename is `results_<short_id>.json`. Confirm to write the file.

Pass `--alias` to use camelCase field names in the output.

---

## Snapshot notes

Each snapshot can carry a freeform Markdown note — useful for recording
observations, decisions, or links to external references at the time the
snapshot was taken.

=== "CLI"

    ```bash
    aimbat snapshot note read <SNAPSHOT_ID>  # display the note
    aimbat snapshot note edit <SNAPSHOT_ID>  # open in $EDITOR and save on exit
    ```

=== "Shell"

    ```bash
    snapshot note read <SNAPSHOT_ID>
    snapshot note edit <SNAPSHOT_ID>
    ```

If no note exists yet, `read` prints `(no note)` and `edit` opens an empty
buffer. The note is saved when you close the editor without error.

---

## Snapshot quality statistics

A summary of quality metrics across all snapshots for an event can be viewed
without opening individual snapshot records:

=== "CLI"

    ```bash
    aimbat snapshot quality list <ID>  # for a specific event
    aimbat snapshot quality list all   # across all events
    aimbat snapshot quality dump       # raw JSON export
    ```

=== "Shell"

    ```bash
    snapshot quality list <ID>  # for a specific event
    snapshot quality list all   # across all events
    snapshot quality dump       # raw JSON export
    ```

The table shows per-snapshot aggregated ICCS correlation coefficients and, where
MCCC has been run, MCCC metrics (mean, SEM) and the global RMSE. This makes it
easy to compare the quality evolution across snapshots without having to export
each one individually.
