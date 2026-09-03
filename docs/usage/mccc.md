# MCCC alignment

## When to run MCCC

ICCS produces relative arrival-time picks that are directly usable for many
purposes. MCCC is the usual next step because it adds a formal standard error to
each pick, from a pairwise least-squares inversion, making the output suitable
where timing uncertainties are required, such as tomographic inversion.

MCCC works best on already well-aligned data. It cannot recover poor alignment:
badly misaligned seismograms give weak pairwise correlations and a poorly
constrained inversion. Running ICCS first is standard, not by rule but because
ICCS has the tools MCCC lacks: interactive parameter adjustment, autoflip,
autoselect. Once those stop improving things, MCCC is ready.

Take a snapshot before running it.

## How MCCC differs from ICCS

ICCS aligns each seismogram against a running stack, a single reference built
from the array. MCCC instead computes cross-correlation delays between **all
pairs** of selected seismograms, then solves for the set of time shifts that best
satisfies every pairwise constraint at once, by weighted least squares with
Tikhonov regularisation.

Because every pair contributes a constraint, the solution is not anchored to any
one reference waveform. The picks are relative shifts that sum to zero across the
array: how far each seismogram moves relative to the group mean, not relative to
a stack.

The least-squares solution also yields a **standard error** for each delay, from
the covariance matrix. ICCS has no equivalent: its CC values indicate alignment
quality but carry no formal uncertainty. These standard errors are what make MCCC
picks suitable as direct input to further analysis.

MCCC is more rigorous but slower, roughly three to five times a comparable ICCS
run. It also has no interactive controls: no autoflip, no autoselect, no tuning
loop. It solves the problem it is given; shaping that problem (which seismograms,
what window, whether to filter) is done beforehand with ICCS.

!!! note "Reference"

    VanDecar, J. C., and R. S. Crosson. "Determination of Teleseismic Relative
    Phase Arrival Times Using Multi-Channel Cross-Correlation and Least Squares."
    *Bulletin of the Seismological Society of America*, vol. 80, no. 1, 1990,
    pp. 150–169.

## Running MCCC

=== "CLI"

    ```bash
    aimbat align mccc <ID>          # selected seismograms only
    aimbat align mccc <ID> --all    # include deselected seismograms
    ```

=== "Shell"

    ```bash
    align mccc
    align mccc --all
    ```

=== "TUI"

    Press `a` for the alignment menu and choose **MCCC**.

MCCC updates `t1` for all participating seismograms and writes the results to the
database immediately. Inspect the stack and matrix image afterwards to confirm
the picks improved.

## Parameters

### Minimum CC (`mccc_min_cc`)

Pairs whose cross-correlation coefficient falls below this threshold are excluded
from the inversion. Unlike ICCS's `min_cc`, which acts on whole seismograms, this
applies to **pairs**: a seismogram can still contribute through its good pairs
even if some pairings are weak.

Too low, and noisy pairs degrade the inversion. Too high, and too few constraints
remain for a stable solution. The ICCS correlation coefficients give a rough
sense of which seismograms correlate well.

### Damping (`mccc_damp`)

Tikhonov regularisation applied to the inversion. A little damping stabilises the
solution when the constraint matrix is poorly conditioned, for example when a
seismogram has few pairs above `mccc_min_cc` and its shift is weakly constrained.
Higher damping pulls all shifts towards zero (the group mean), a more
conservative solution.

Zero damping disables regularisation, fine on a large well-correlated dataset but
unstable on sparse or noisy ones.

## The `--all` flag

By default MCCC includes only `select = True` seismograms, the same subset that
formed the ICCS stack. `--all` includes the deselected ones: their picks are
updated too, but they may degrade the inversion if genuinely noisy or misaligned.
Use with caution. See
[`aimbat align mccc`][aimbat._cli.align.cli_mccc_run] for the full flag
reference.

## Exporting

After MCCC, take a snapshot and export the results from it. See
[Exporting Results](results.md).
