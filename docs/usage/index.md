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

AIMBAT projects may contain multiple seismic events. To reduce repetition when
using the [CLI](cli.md), you can designate a **default event**: commands
automatically target it unless you explicitly pass an `--event` flag.

The default event is primarily a CLI convenience. The [Terminal UI](tui.md)
and [Graphical UI](gui.md) maintain their own event selection independently.
The [Shell](shell.md) also tracks its own event context, but will fall back to
the default event at startup if one is set and no `--event` flag is provided.

Set or change the default at any time using:

```bash
aimbat event default <EVENT_ID>
```
