# Selecting an Event

After importing data, the first step before inspecting or processing is to
identify which event you want to work with. All processing commands operate on
one event at a time.

## Listing events

=== "CLI / Shell"

    ```bash
    aimbat event list
    ```

    The table shows each event's ID, time, location, and whether it is
    currently the default. IDs are displayed in their shortest unambiguous
    form — use any unique prefix when passing an ID to other commands.

=== "TUI"

    Events are listed in the **Project** tab under **Events**.

=== "GUI"

    Events are listed in the **Project** tab.

---

## Setting the default event (CLI / Shell)

The CLI and shell operate on a **default event** — a single event stored in
the database that all commands target unless overridden with `--event`. Set it
after import:

```bash
aimbat event default <EVENT_ID>
```

From that point on, commands like `aimbat plot seismograms` or
`aimbat align iccs` automatically target this event without needing an
explicit ID.

To target a different event for a single command without changing the default:

```bash
aimbat align iccs --event <EVENT_ID>
```

The default event is marked in `aimbat event list` and is also shown in the
shell prompt.

---

## Selecting an event for processing (TUI / GUI)

The TUI and GUI maintain their own event selection independently of the
database default — changing it here does not affect what the CLI uses, and
vice versa.

=== "TUI"

    Two ways to select an event:

    - Press `e` to open the event switcher, navigate with `j` / `k`, and
      press `Enter` to select.
    - In the **Project** tab, navigate to the **Events** table, press `Enter`
      on a row, and choose **Select event**.

    The selected event is shown in the event bar at the top of the screen
    and marked with `▶` in both the switcher and the events table.

=== "GUI"

    Select an event in the **Project** tab. The selection is reflected across
    the **Event**, **Snapshots**, and **Processing** tabs.

