# Finalising with MCCC

## When to run MCCC

MCCC works best on data that is already reasonably well aligned — coherent
stack, high CC norms across most of the array, a clean and stable time window.
It cannot recover poor alignment; if the seismograms are badly misaligned,
many pairwise correlations will be weak and the inversion will be poorly
constrained.

Running ICCS first is therefore the usual approach, not because of a strict
rule, but because ICCS gives you tools that MCCC does not: interactive
parameter adjustment, autoflip to correct polarity, and autoselect to remove
seismograms that consistently fail to align. Once the dataset is in a state
where those tools are no longer improving things, MCCC is the natural next
step — and because it produces formal standard errors for each delay estimate,
its output is directly usable in further analyses such as tomographic
inversion.

Take a snapshot before running MCCC.

---

## How MCCC differs from ICCS

ICCS aligns each seismogram against a running stack: a reference constructed
from the combined array. MCCC takes a different approach — it computes
cross-correlation delays between **all pairs** of selected seismograms
simultaneously, then finds the set of time shifts that best satisfies all of
those pairwise constraints at once, using a weighted least-squares inversion
with Tikhonov regularisation.

Because every seismogram pair contributes a constraint, the solution is not
anchored to any single reference waveform. The resulting picks are relative
shifts that sum to zero across the array — they express how much each
seismogram needs to move relative to the group mean, not relative to a stack.

Because the solution comes from a least-squares inversion, MCCC also produces
a **standard error** for each delay estimate, derived from the covariance
matrix of the solution. ICCS provides no equivalent — its CC norms indicate
alignment quality but carry no formal uncertainty. The standard errors are what
make MCCC picks suitable as direct input to further analyses.

This makes MCCC more rigorous but also slower — roughly three to five times
slower than a comparable ICCS run. More importantly, MCCC offers no equivalent
of ICCS's interactive controls: there is no autoflip, no autoselect, no
parameter tuning loop. It solves the problem it is given; shaping that problem
— deciding which seismograms to include, what window to use, whether to apply
a filter — is done beforehand with ICCS.

!!! note "Reference"
    VanDecar, J. C., and R. S. Crosson. "Determination of Teleseismic Relative
    Phase Arrival Times Using Multi-Channel Cross-Correlation and Least Squares."
    *Bulletin of the Seismological Society of America*, vol. 80, no. 1, 1990,
    pp. 150–169.

---

## Running MCCC

=== "CLI / Shell"

    ```bash
    aimbat align mccc          # selected seismograms only
    aimbat align mccc --all    # include deselected seismograms
    ```

=== "TUI"

    Press `a` to open the alignment menu and choose **MCCC**.

=== "GUI"

    Use the **Run MCCC** button in the **Processing** tab.

MCCC updates `t1` for all participating seismograms and writes the results back
to the database immediately. Inspect the stack and matrix image afterwards to
confirm the picks improved.

---

## Parameters

### Minimum CC norm (`mccc_min_ccnorm`)

Pairs of seismograms whose cross-correlation coefficient falls below this
threshold are excluded from the inversion. Unlike ICCS's `min_ccnorm`, which
operates on whole seismograms, this threshold applies to **pairs**: a
seismogram can still contribute to the solution through its good pairs even if
some of its pairings are weak.

Setting this too low allows noisy pairs to degrade the inversion; setting it
too high may leave too few constraints for a stable solution. The ICCS CC
norms give a rough sense of which seismograms are likely to correlate well with
each other.

### Damping (`mccc_damp`)

Tikhonov regularisation applied to the inversion. A small amount of damping
stabilises the solution when the constraint matrix is poorly conditioned —
for example, when a seismogram has few pairs above `mccc_min_ccnorm` and its
time shift is therefore weakly constrained. Higher damping pulls all shifts
closer to zero (the group mean), producing a more conservative solution.

Setting damping to zero disables regularisation entirely, which is fine when
the dataset is large and well-correlated but can produce unstable results on
sparse or noisy datasets.

---

## The `--all` flag

By default, MCCC only includes seismograms with `select = True` — the same
subset that contributed to the ICCS stack. Passing `--all` includes deselected
seismograms in the inversion. Their picks are still updated, but they may
degrade the inversion if they are genuinely noisy or misaligned. Use with
caution.
