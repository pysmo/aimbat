# Initial Data Inspection

Before running any alignment, it is worth visually inspecting the imported
seismograms to catch obvious problems: garbled waveforms, stations with
excessive noise, flat traces, or data gaps. Catching these early avoids
wasting time tuning parameters around fundamentally unusable data.

AIMBAT provides two complementary views for this purpose.

---

## By event — record section

Plots all seismograms for an event as a record section: waveforms sorted by
epicentral distance, with absolute time on the x-axis. This gives an immediate
overview of the array — coherent arrivals should appear as a roughly linear
moveout across the traces.

=== "CLI / Shell"

    ```bash
    aimbat plot seismograms
    aimbat plot seismograms --event <ID>   # specific event
    ```

=== "TUI"

    In the **Project** tab, navigate to the **Events** table, press `Enter`
    on a row, and choose **View seismograms**.

=== "GUI"

    Select an event in the **Project** tab and click **View seismograms**.

**What to look for:**

- Traces that are flat, clipped, or visually incoherent with the rest of the array
- Stations with excessive noise relative to the signal
- Traces where the arrival appears to arrive much earlier or later than expected from moveout
- Unusually large or small amplitudes after normalisation (can indicate a gain issue in the original file)

---

## By station — across events

Plots all seismograms recorded at a single station across every event in the
project, aligned on the initial pick (`t0`). The x-axis shows time relative
to the pick; traces are stacked vertically in chronological order. This view
is useful for checking whether a station is consistently problematic across
multiple events, or whether an issue is isolated to one.

=== "CLI / Shell"

    ```bash
    aimbat station plotseis <STATION_ID>
    ```

=== "TUI"

    In the **Project** tab, navigate to the **Stations** table, press `Enter`
    on a row, and choose **View seismograms**.

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.models import AimbatStation
    from aimbat.plot import plot_seismograms

    with Session(engine) as session:
        station = session.get(AimbatStation, station_id)
        plot_seismograms(session, station, return_fig=False)
    ```

---

## How the data is prepared

Both plots apply the same preprocessing before displaying:

1. **Detrend** — removes the mean and linear trend
2. **Bandpass filter** *(optional)* — applied if `bandpass_apply` is enabled in
   the event parameters; uses the `bandpass_fmin` / `bandpass_fmax` values set
   for that event. Filtering is **off by default**, so the initial inspection
   shows the raw waveforms as imported. Users who pre-filter their data before
   import can leave it disabled and work directly with the filtered waveforms
   they already have
3. **Resample** — resampled to a common 10 Hz sample rate for consistent display
4. **Normalise** — each trace is normalised to unit amplitude so waveforms are
   visually comparable regardless of original gain

The original files are never modified. These steps are applied in memory for
display only.

Because the bandpass filter uses the current event parameters, the inspection
plots will look different depending on whether a filter is applied. It can be
useful to inspect both with and without filtering to distinguish noise from
signal.

---

## What to do with bad data

If you identify a seismogram that should not be included in processing, see
[Removing data](data.md#removing-data). Deleting a seismogram from the project
does not affect the underlying file.

For borderline cases — noisy but potentially usable traces — it is better to
leave them in and rely on ICCS autoselect to exclude them based on
cross-correlation quality rather than deleting them outright.

---

!!! tip "Before moving on"
    Once you are happy with the imported data, take a snapshot. This gives you
    a clean baseline to return to if processing goes in an unexpected direction.
    See [Snapshots](snapshots.md) for how to create one.
