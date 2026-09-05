# Aligning with ICCS

## The loop

ICCS alignment is exploratory. There is no fixed sequence that works for every
dataset. It is a feedback loop: adjust a parameter, run ICCS, examine the result,
adjust again. The goal is a stack that is coherent across the array, with high
correlation coefficients on most traces. See
[Workflow and strategy](../first-steps/workflow.md#with-aimbat) for where this
loop fits in the wider pipeline.

Parameters interact. A filter that sharpens the waveform may allow a narrower
window, which changes which traces align well.

## What one run does

Each iteration within a run cross-correlates every seismogram against the current
stack, shifts its pick (`t1`) by the lag that best aligns it, and rebuilds the
stack from the newly aligned traces. This repeats, each stack better aligned than
the last, until the stack stops changing (see [Convergence](#convergence)) or an
iteration limit is reached. See pysmo's
[execution flow](https://docs.pysmo.org/api/pysmo/tools/iccs/#pysmo.tools.iccs--execution-flow)
for the exact steps.

Because every seismogram is compared with the stack rather than with every other
seismogram, ICCS is fast. It is meant to run first, preparing well-aligned data
for a final [MCCC](mccc.md) pass.

## Running ICCS

=== "CLI"

    ```bash
    aimbat align iccs <ID>                          # basic run
    aimbat align iccs <ID> --autoflip               # also correct inverted polarity
    aimbat align iccs <ID> --autoselect             # also deselect poor traces
    aimbat align iccs <ID> --autoflip --autoselect  # both
    ```

=== "Shell"

    ```bash
    align iccs
    align iccs --autoflip
    align iccs --autoselect
    align iccs --autoflip --autoselect
    ```

=== "TUI"

    Press `a` for the alignment menu and choose **ICCS**. Toggle **Autoflip**
    (`f`) and **Autoselect** (`s`) before running.

=== "API"

    ```python
    from sqlmodel import Session, select
    from aimbat.db import engine
    from aimbat.core import create_iccs_instance, run_iccs
    from aimbat.models import AimbatEvent

    with Session(engine) as session:
        event = session.exec(select(AimbatEvent)).first()
        bound = create_iccs_instance(session, event)
        run_iccs(session, event, bound.iccs, autoflip=True, autoselect=True)
    ```

The stack and matrix image after each run show what to change next. See
[Parameters](parameters.md) for what each one controls, and
[`aimbat align iccs`][aimbat._cli.align.cli_iccs_run] for the flags.

## Running modes

### Basic

Without autoflip or autoselect, every decision about inclusion and polarity is
manual. Toggle `select` and `flip` on individual seismograms from the seismogram
list; the stack and matrix views show the full result.

### Autoflip

Depending on the focal mechanism and a station's azimuth and take-off angle, some
stations record the target phase with opposite polarity to the rest of the array.
These traces contribute destructively to the stack. The `flip` flag multiplies a
seismogram by −1 before it enters the stack and cross-correlation. With autoflip,
ICCS detects traces whose maximum absolute correlation with the stack is negative
and sets their `flip`.

Autoflip is safe to run repeatedly, whether run once early or left on
throughout.

### Autoselect

With autoselect, a seismogram whose CC falls below `min_cc` is set to
`select = False` and excluded from the stack in later iterations. It is still
cross-correlated against the stack, so it can be re-selected automatically in a
later run if parameters improve and it aligns better.

Autoselect is therefore not permanent. Narrowing the time window also raises CC
values across the board, which can bring deselected traces back above the
threshold without any change in alignment quality. This is worth remembering
when reading CC values after a window change.

## Convergence

Within a run, ICCS iterates until the stack stops changing meaningfully between
passes (compared by correlation coefficient or by normalised change in shape) or
an iteration limit is reached. This is automatic and needs no monitoring. Running
ICCS again always starts a fresh run from the current picks.

What matters is the convergence of the *overall process*: across successive runs
with adjusted parameters, do the stack and CC values keep improving, or have they
plateaued? When further adjustment produces no visible improvement, the data are
ready.

## Knowing when to stop

There is no objective criterion. Practical signals that the dataset is ready:

- the stack is visually coherent, and individual traces closely follow its shape
- CC values are high across most of the array
- the time window frames a clean, well-defined arrival
- another ICCS run, with or without autoflip and autoselect, changes nothing

At this point the ICCS picks can be exported directly from a snapshot (see
[Exporting Results](results.md)). For formal per-station timing errors, for
example as input to tomographic inversion, continue to [MCCC](mccc.md) first.
Either way, a snapshot taken before any further change preserves this result.

## Tips

- **Change one parameter at a time.** Tracking what caused an improvement or a
    regression is hard when several things move at once.
- **Snapshot before each experiment.** A different window or filter is easy to
    back out of with a snapshot in place.
- **Delete persistent outliers.** A seismogram with a poor CC across many runs
    and parameter combinations is dragging the stack down and rarely improves
    with further adjustment.
