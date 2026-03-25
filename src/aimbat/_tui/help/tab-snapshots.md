# Snapshots tab

A snapshot is a saved checkpoint of the current processing state — the
time window, bandpass filter, picks, and per-seismogram flags. Snapshots
let you experiment freely: take one before making changes, and roll back
if things go wrong.

If the list is empty, go to the **Project** tab and select an event first,
then press `n` to create a snapshot.

---

## What you see

### Snapshot list (left)

Each row is one snapshot for the selected event, showing when it was taken
and an optional comment you can add at creation time. The most recent
snapshot is at the bottom.

### Quality panel (right)

Shows ICCS CC and MCCC quality metrics as they were at snapshot time. This
lets you compare quality across snapshots — for example to see whether a
parameter change improved alignment — without loading each one.

### Note (below quality panel)

A free-text Markdown note for the highlighted snapshot. Switch to **Edit**
to type, then back to **View** to render the Markdown. Notes are saved
automatically whenever the editor loses focus — no explicit save action is
needed. Each snapshot has its own note, which persists in the database.

---

## What a snapshot captures

- **Event parameters** — time window (`t0`/`t1` window bounds), bandpass
  filter settings, and Min CC threshold
- **Per-seismogram parameters** — the `t1` pick, `select` flag, and `flip`
  flag for every seismogram
- **Quality metrics** — ICCS correlation coefficients per seismogram (always captured);
  MCCC metrics (only if MCCC has been run with the current parameters)

Waveform data is not copied — snapshots are lightweight records of where
you are in the parameter space.

---

## Row actions

| Action | Description |
|--------|-------------|
| Show details | View the event parameters (window, filter, min CC) as saved |
| Preview stack | Open the ICCS stack plot built from this snapshot's parameters, without changing anything in the database |
| Preview matrix image | Open the cross-correlation matrix image from this snapshot |
| Save results to JSON | Export the snapshot's quality metrics and picks to a JSON file via a file-save dialogue |
| Rollback to this snapshot | Restore these parameters as the current live values — overwrites the current parameters for this event |
| Delete snapshot | Permanently remove the snapshot (the live parameters are not affected) |

### About rollback

Rolling back restores the snapshot's parameters to the live state. Any
ICCS runs or parameter changes made after that snapshot are undone. The
snapshot itself is not deleted — you can roll back to it again or compare
it against other snapshots.

If the snapshot contains MCCC quality data, the live quality metrics are
also restored from the best matching snapshot.

---

## Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `g` / `G` | Jump to top / bottom |
| `Enter` | Open row action menu |

When previewing a stack or matrix image, two extra toggles appear:
- `c` — include context seismograms (wider view around the pick window)
- `a` — include all seismograms, even those with `Select = ✗`

---

## Global key bindings

| Key | Action |
|-----|--------|
| `e` | Open event switcher |
| `n` | Create a new snapshot for the current event |
| `r` | Refresh all panels |
| `?` | Show this help |
| `q` | Quit |
