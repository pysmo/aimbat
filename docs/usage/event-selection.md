# Selecting an event

Processing commands act on one event at a time. After import, identify which one
before inspecting or aligning.

## Listing events

=== "CLI"

    ```bash
    aimbat event list
    ```

=== "Shell"

    ```bash
    event list
    ```

=== "TUI"

    The **Project** tab, under **Events**.

The table shows each event's ID, origin time, and location. IDs appear in their
shortest unambiguous form; pass any unique prefix to other commands.

## CLI and shell

Give the event as a positional argument, a full UUID or any unique prefix:

```bash
aimbat align iccs 6a4a
```

`--event` and `--event-id` are accepted equivalents.

For a run of commands on the same event, set `DEFAULT_EVENT_ID`. AIMBAT uses it
whenever no ID is given:

```bash
export DEFAULT_EVENT_ID=6a4a
aimbat align iccs
aimbat snapshot create "post-ICCS"
```

Clear it with `unset DEFAULT_EVENT_ID`. In the shell, `event switch <ID>` does
the same for the session and shows the ID in the prompt.

!!! note "Not an AIMBAT setting"

    `DEFAULT_EVENT_ID` is a plain shell environment variable read by the CLI
    argument parser. It has no `AIMBAT_` prefix, cannot be set in `.env`, and
    does not appear in `aimbat utils settings`.

## TUI

The TUI keeps its own event selection, independent of the CLI and shell.

In the **Project** tab, go to the **Events** table and press `s` (or `Enter` on a
row, then **Select event**). The selected event shows in the bar at the top of
the screen, is marked `▶` in the table, and populates the **Live data** and
**Snapshots** tabs.
