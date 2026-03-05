# Using AIMBAT

## Interfaces

Once [installed](../first-steps/installation.md), AIMBAT can be used in several
ways, each of which has unique strengths depending on the task at hand:

- **[Command line](cli.md)**: Ideal for administrative tasks like
  adding data to a project, and exploring the data after they are added.
- **[Interactive Shell](shell.md)**: Similar to the CLI but with the added benefit of extra
  context and command history. Unlike the CLI, it is not possible to set
  parameters to nonsensical values.
- **[Terminal UI](tui.md)**: This is where processing typically happens.
  The TUI is designed for efficient, mouse-free, and keyboard-driven navigation
  for users familiar with the workflow.
- **[Graphical UI](gui.md)**: Mouse driven interface for users who prefer a
  more visual approach. The GUI is ideal for newer users who need more guidance
  and visual cues to navigate the workflow.
- **[Python API](api.md)**: The preferred way for scripting and automated
processing by writing custom Python scripts.

Complete walkthroughs for each of these options are presented in the following sections.

## Default event

AIMBAT projects often contain many seismic events. To streamline work, you
can designate a **default event** to serve as a persistent context.

The default event is a convenience fallback for the [CLI](cli.md). Commands
automatically target this event unless you explicitly provide an ID. This
reduces the need to repeatedly copy and paste IDs when focusing on one event.

### Flexible Processing

A default event is **not required** for processing tasks. AIMBAT allows
flexibility across all interfaces:

- **Interactive Tools**: The [Terminal UI](tui.md), [Graphical UI](gui.md),
  and [Shell](shell.md) can navigate and process any event in the project,
  regardless of the default setting.
- **Command Line**: You can override the default for any command using the
  global `--event` flag.

Setting a default event is simply a way to reduce repetition. Change it at
any time using:

```bash
aimbat event default <EVENT_ID>
```
