# Initial data inspection

Before aligning anything, a visual check of the imported seismograms catches
obvious problems: garbled waveforms, excessive noise, flat traces, data gaps.
Catching these early avoids tuning parameters around unusable data.

This pass is for the obvious cases only. Autoselect handles borderline traces
algorithmically, across the whole array, not one trace at a time.

Two views help.

## By event

A record section: every seismogram for one event, sorted by epicentral distance,
with absolute time on the x-axis. Coherent arrivals show as a roughly linear
moveout across the traces.

=== "CLI"

    ```bash
    aimbat plot seismograms <ID>
    ```

=== "Shell"

    ```bash
    plot seismograms <ID>
    ```

=== "TUI"

    In the **Project** tab, press `Enter` on an event row and choose **View
    seismograms**.

=== "API"

    ```python
    from sqlmodel import Session
    from aimbat.db import engine
    from aimbat.models import AimbatEvent
    from aimbat.plot import plot_seismograms

    with Session(engine) as session:
        event = session.get(AimbatEvent, event_id)
        plot_seismograms(session, event, return_fig=False)
    ```

With many traces, only a subset shows at first. Scrolling pans through the
rest; scrolling with **Shift** held pans the time axis.

Look for:

- traces that are flat, clipped, or incoherent with the array
- stations with excessive noise relative to signal
- arrivals much earlier or later than moveout predicts
- unusually large or small amplitudes after normalisation, often a gain problem
    in the original file

## By station

Every seismogram recorded at one station across all events in the project,
aligned on the initial pick (`t0`) and stacked vertically in time order. Useful
for telling whether a station is consistently problematic or the issue is
isolated to one event.

=== "CLI"

    ```bash
    aimbat station plotseis <STATION_ID>
    ```

=== "Shell"

    ```bash
    station plotseis <STATION_ID>
    ```

=== "TUI"

    In the **Project** tab, press `Enter` on a station row and choose **View
    seismograms**.

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

Same scroll behaviour: scrolling pans traces, shift+scroll pans time.

## How the data are prepared

Both plots apply the same in-memory preprocessing before display. The files are
never modified.

1. **Detrend.** Remove the mean and linear trend.
2. **Bandpass filter** *(optional)*. Applied only if `bandpass_apply` is enabled
    in the event parameters, using that event's `bandpass_fmin` /
    `bandpass_fmax`. Off by default, so inspection shows the waveforms as
    imported. Data pre-filtered before import can be inspected with it left off.
3. **Resample.** To a common 10 Hz for consistent display.
4. **Normalise.** Each trace to unit amplitude, so shapes are comparable
    regardless of gain.

Because the filter follows the current event parameters, the plots change with
it. Inspecting both filtered and unfiltered helps separate noise from signal.

## Excluding bad data

Excluding a seismogram from processing means deleting it: see
[Removing data](data.md#removing-data). The file on disk is unaffected.

Deletion is for the obvious cases above; autoselect handles the rest via
`min_cc`.
