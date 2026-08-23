# Aligning with ICCS

## The process

ICCS alignment is inherently exploratory. There is no fixed sequence of steps
that works for every dataset — it is a feedback loop between adjusting
parameters, running the algorithm, and examining the results. The goal is a
stack that is coherent across the array and correlation coefficients that are
high across most of the array.

Parameters interact: a filter that sharpens the waveform may allow a narrower
time window, which in turn changes which seismograms align well. It is generally
best to change one thing at a time and observe the effect before making further
adjustments.

## Running ICCS

=== "CLI"

    ```bash
    aimbat align iccs <ID>                          # basic run
    aimbat align iccs <ID> --autoflip               # flip inverted polarity automatically
    aimbat align iccs <ID> --autoselect             # deselect poor-quality seismograms automatically
    aimbat align iccs <ID> --autoflip --autoselect  # both
    ```

=== "Shell"

    ```bash
    align iccs                          # basic run
    align iccs --autoflip               # flip inverted polarity automatically
    align iccs --autoselect             # deselect poor-quality seismograms automatically
    align iccs --autoflip --autoselect  # both
    ```

=== "TUI"

    Press `a` to open the alignment menu and choose **ICCS**. Before running, toggle
    **Autoflip** (`f`) and **Autoselect** (`s`) as needed.

After each run, inspect the stack and matrix image to assess alignment quality
before deciding what to change next.

See [Parameters](parameters.md) for what each ICCS parameter controls and how
to set it, including the interactive tools. See
[`aimbat align iccs`][aimbat._cli.align.cli_iccs_run] for the exact flags.

## Running modes

### Basic

Running without autoflip or autoselect leaves all decisions about which
seismograms to include and whether to flip them up to the user. The stack and
matrix views show the full result, and you can manually toggle `select` and
`flip` on individual seismograms from the seismogram list.

### Autoflip

Depending on the focal mechanism and a station's azimuth and take-off angle,
some stations may record the target phase with opposite polarity to the rest of
the array. These seismograms contribute destructively to the stack, degrading
alignment for everything else. The `flip` flag multiplies a seismogram's data by
−1 before it enters the stack and cross-correlation, correcting for this. With
autoflip enabled, ICCS detects seismograms whose maximum absolute
cross-correlation with the stack is negative and automatically toggles their
`flip` parameter.

Autoflip can be run once early on to correct polarity issues, or left enabled
throughout. It is safe to run repeatedly.

### Autoselect

With autoselect enabled, seismograms whose CC falls below `min_cc` are
automatically set to `select = False` and excluded from the stack in subsequent
iterations. They are still cross-correlated against the stack, however — so if
parameters improve and they start to align better, they can be re-selected
automatically in a later run.

This means autoselect is not permanent. A seismogram deselected at an early
stage may recover as parameters improve — and narrowing the time window tends to
increase CC values across the board, which can bring previously deselected
seismograms back above the threshold even without any change in alignment
quality. This is worth keeping in mind when interpreting CC values after a
window adjustment.

## Convergence

Within a single run, ICCS iterates — rebuilding the stack and re-correlating
after each pass — until the stack stops changing meaningfully between iterations
or a maximum number of iterations is reached. Convergence is assessed by
comparing the current stack to the previous one: either by their correlation
coefficient, or by the normalised change in stack shape. This happens
automatically; there is no need to monitor it. Running ICCS again from AIMBAT's
interface always starts a fresh run from the current picks.

What matters is the convergence of the *overall process*: across multiple runs
with adjusted parameters, do the stack and correlation coefficients keep
improving, or have they plateaued? When further adjustments produce no visible
improvement in the stack, the data are ready — either for direct export, or as
input to MCCC for formal timing uncertainties.

## Knowing when to stop

There is no objective criterion for when ICCS alignment is "done". Practical
signals that the dataset is ready:

- The stack is visually coherent — individual traces closely follow its shape
- Correlation coefficients are high across most of the array
- The time window highlights a clean, well-defined arrival
- Running ICCS again with or without autoflip/autoselect produces no meaningful
    change

At this point the ICCS picks can be exported directly from a snapshot — see
[Exporting Results](results.md). If formal per-station timing standard errors
are needed (for example, as input to tomographic inversion), continue to
[MCCC alignment](mccc.md) before taking the final snapshot. Either way, it is
worth taking a snapshot now before making any further changes.

## Tips

- **Change one parameter at a time.** It is easy to lose track of what caused an
    improvement or regression if multiple things change at once.
- **Take snapshots liberally.** They are lightweight and make it easy to
    backtrack to a promising state.
- **ICCS picks are directly usable.** For workflows that do not require formal
    timing uncertainties, ICCS picks exported from a snapshot are suitable for
    further analysis as-is. MCCC adds formal standard errors and a more rigorous
    pairwise solution — run it when those are needed, but there is no obligation
    to do so.
- **Outlier seismograms.** If a seismogram consistently has a poor CC across
    many runs and parameter combinations, it may be worth deleting it from the
    project rather than letting it drag down the stack.
