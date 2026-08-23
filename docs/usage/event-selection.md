# Selecting an Event

After importing data, the first step before inspecting or processing is to
identify which event you want to work with. All processing commands operate on
one event at a time.

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

    Events are listed in the **Project** tab under **Events**.

The table shows each event's ID, time, and location. IDs are displayed in their
shortest unambiguous form — use any unique prefix when passing an ID to other
commands.

## Selecting an Event for the CLI and Shell

Most processing commands (like `aimbat align iccs` or `aimbat snapshot create`)
operate on a single event. You can specify the target event in two ways:

### 1. Positional argument

Pass the ID directly as the first argument. You can use the full UUID or any
unique prefix:

```bash
aimbat align iccs 6a4a
```

The named forms `--event` and `--event-id` are also accepted and behave
identically:

```bash
aimbat align iccs --event 6a4a
```

### 2. The `DEFAULT_EVENT_ID` environment variable

If you are working on the same event for multiple commands, set the
`DEFAULT_EVENT_ID` environment variable in your shell. AIMBAT uses it whenever
no explicit ID is provided:

```bash
export DEFAULT_EVENT_ID=6a4a
aimbat align iccs
aimbat snapshot create "post-ICCS"
```

The shell prompt also reflects this ID when set. To clear it, unset the
variable: `unset DEFAULT_EVENT_ID`.

!!! note

    `DEFAULT_EVENT_ID` is a plain shell environment variable consumed directly by
    the CLI argument parser. It is **not** an AIMBAT setting: it has no `AIMBAT_`
    prefix, cannot be set in `.env`, and does not appear in `aimbat settings list`.

## Selecting an event for processing (TUI)

The TUI maintains its own event selection independently of the CLI / shell
context — changing it here does not affect what the CLI uses, and vice versa.

=== "TUI"

    In the **Project** tab, navigate to the **Events** table and press `s` (or press
    `Enter` on a row and choose **Select event**).

    The selected event is shown in the event bar at the top of the screen and marked
    with `▶` in the events table. Selecting an event populates the **Live data** and
    **Snapshots** tabs with that event's data.
