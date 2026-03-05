# Command Line Interface (CLI)

The AIMBAT CLI is the primary tool for administrative tasks like creating projects,
importing data, and managing snapshots. It is also suitable for batch
processing and scripting.

!!! Warning "Parameter Validation"
    The CLI performs basic validation of processing parameters (e.g., ensuring
    values are provided in the correct format), but it does *not* perform the
    same data-aware validation as the other interfaces. For example, the TUI
    will prevent you from setting a time window that extends beyond the
    available data for an event.
