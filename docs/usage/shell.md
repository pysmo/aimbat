# Interactive Shell

The AIMBAT shell is a persistent, interactive session that wraps all CLI commands
with tab-completion, command history, and live ICCS feedback. It is the recommended
interface when working interactively from the terminal.

## Starting the shell

```bash
aimbat shell                    # start in the context of the default event
aimbat shell --event <ID>       # start in the context of a specific event
```

The `--event` flag accepts a full UUID or any unique prefix. It sets the shell's
initial event context without changing the database default event.

## Event context

The shell maintains a local **event context** — the event that all commands
operate on. This is independent of the database default event and is never
written to the database.

The prompt reflects the current context:

```
aimbat>                         # using the database default event
aimbat [6a4a1b2c]>              # using a specific event (first 8 chars of ID)
```

### Switching events

```
event switch <ID>               # switch to a specific event
event switch                    # reset to the database default event
```

`event switch` accepts a full UUID or any unique prefix. Switching immediately
reports the ICCS status for the new event.

## Commands

All CLI commands are available in the shell, without the leading `aimbat`. For
example, `aimbat event list` becomes simply `event list`.

## Tab completion and history

Press **Tab** at any point to complete commands, subcommands, and flags.
Command history is saved to `~/.aimbat_history` and persists across sessions.
Use the up/down arrow keys to navigate it.

## ICCS status

After every command, the shell checks whether the ICCS instance for the current
event is still valid and prints a status line when something changes:

```
ICCS ready (event 6a4a1b2c)
ICCS not ready — <reason>
```

The status is also printed on startup. A warm ICCS cache is reused across
commands in the same session, so repeated operations on the same event avoid
redundant data loading.

## Parameter validation

Setting a parameter that would produce an invalid ICCS configuration is
rejected before anything is written to the database:

```
aimbat> event parameter set window_pre 999
ValueError: ICCS rejected window_pre=999: <reason>
```

The database is left unchanged on rejection.

## Exiting

Type `exit`, `quit`, or `q`, or press **Ctrl+D**.
