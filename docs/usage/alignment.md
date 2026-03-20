# Aligning with ICCS

## The process

ICCS alignment is inherently exploratory. There is no fixed sequence of steps
that works for every dataset — it is a feedback loop between adjusting
parameters, running the algorithm, and examining the results. The goal is a
stack that is coherent across the array and CC norms that are high enough to
give MCCC a clean dataset to work with.

Parameters interact: a filter that sharpens the waveform may allow a narrower
time window, which in turn changes which seismograms align well. It is
generally best to change one thing at a time and observe the effect before
making further adjustments.

---

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

    Press `a` to open the alignment menu and choose **ICCS**. Before running,
    toggle **Autoflip** (`f`) and **Autoselect** (`s`) as needed.

=== "GUI"

    Use the **Run ICCS** button in the **Processing** tab. Autoflip and
    autoselect can be toggled before running.

After each run, inspect the stack and matrix image to assess alignment quality
before deciding what to change next.

---

## Parameters

All parameters are per-event and can be adjusted at any time. Changes take
effect on the next ICCS run.

### Time window

`window_pre` and `window_post` define how much of the seismogram — before and
after the pick — is used in the cross-correlation. Since the pick aims to sit
at the **onset** of the target phase (the first coherent ground motion), the
window effectively starts a little before the onset and extends through the
arrival. Keeping `window_pre` short and placing the onset near the beginning
of the window tends to work well, as it limits how much noise before the
arrival is included. The window should be narrow enough that it is dominated
by the target phase rather than noise or later arrivals.

A good starting point is a window that visually frames the onset in the stack
plot. Narrowing it once initial alignment is reasonable often improves
precision.

### Bandpass filter

`bandpass_apply`, `bandpass_fmin`, and `bandpass_fmax` control an optional
bandpass filter applied before cross-correlation. Filtering can dramatically
improve alignment on noisy data by suppressing frequencies where the signal
is weak, but the right frequency range depends on the event and the array.

Filtering is off by default. When enabled, the same filter is applied to
both the seismograms and the stack, so the cross-correlation is always
comparing like with like.

### The phase pick (t1)

`t1` is the per-seismogram pick that ICCS refines during each run — every
seismogram gets its own value, reflecting how much it needs to be shifted
relative to the stack. When adjusted interactively from the stack plot,
however, the same shift is applied to all seismograms simultaneously. This
makes interactive picking a coarse, global adjustment — useful for moving
the entire array onto the onset — while ICCS handles the fine, per-seismogram
refinement.

### Minimum CC norm

`min_ccnorm` is the threshold used by autoselect to deselect seismograms
automatically. It does not affect the cross-correlation itself — only which
seismograms are excluded from contributing to the stack in subsequent
iterations.

Setting this too high early on may exclude seismograms that would align well
once the stack improves. It is usually more effective to start with a
permissive threshold and tighten it as alignment converges.

---

## Interactive adjustment

In addition to setting parameters directly, three tools let you adjust values
by interacting with the plot — clicking or scrolling in a waveform display
rather than typing numbers.

=== "CLI"

    ```bash
    aimbat pick phase <ID>    # adjust t1 by clicking on the stack
    aimbat pick window <ID>   # set window_pre / window_post by clicking
    aimbat pick ccnorm <ID>   # set min_ccnorm by scrolling the matrix image
    ```

=== "Shell"

    ```bash
    pick phase    # adjust t1 by clicking on the stack
    pick window   # set window_pre / window_post by clicking
    pick ccnorm   # set min_ccnorm by scrolling the matrix image
    ```

Each command opens a matplotlib window. Click (or scroll, for ccnorm) to
set the value, then close the window to save it.

All three accept `--no-context` and `--all` (include deselected seismograms).

=== "TUI"

    Press `t` to open the **Tools** menu, then choose from:

    - **Phase arrival (t1)** — click in the stack to shift all picks globally
    - **Time window** — click to place the window boundaries
    - **Min CC norm** — scroll the matrix image to set the threshold

    Before launching, toggle **Context** (`c`) and **All seismograms** (`a`)
    as needed. The TUI suspends while the matplotlib window is open and
    resumes when you close it.

The pick and window tools open the **stack view**; the CC norm tool opens the
**matrix image**. The behaviour of each is described in [The ICCS
Stack](iccs-stack.md#use-in-interactive-adjustment).

---

## Running modes

### Basic

Running without autoflip or autoselect leaves all decisions about which
seismograms to include and whether to flip them up to the user. The stack and
matrix views show the full result, and you can manually toggle `select` and
`flip` on individual seismograms from the seismogram list.

### Autoflip

Depending on the focal mechanism and a station's azimuth and take-off angle,
some stations may record the target phase with opposite polarity to the rest
of the array. These seismograms contribute destructively to the stack,
degrading alignment for everything else. The `flip` flag multiplies a
seismogram's data by −1 before it enters the stack and cross-correlation,
correcting for this. With autoflip enabled, ICCS detects seismograms whose
maximum absolute cross-correlation with the stack is negative and
automatically toggles their `flip` parameter.

Autoflip can be run once early on to correct polarity issues, or left enabled
throughout. It is safe to run repeatedly.

### Autoselect

With autoselect enabled, seismograms whose CC norm falls below `min_ccnorm`
are automatically set to `select = False` and excluded from the stack in
subsequent iterations. Importantly, they are still cross-correlated against
the stack — so if parameters improve and they start to align better, they can
be re-selected automatically in a later run.

This means autoselect is not permanent. A seismogram deselected at an early
stage may recover as parameters improve — and narrowing the time window tends
to increase CC norms across the board, which can bring previously deselected
seismograms back above the threshold even without any change in alignment
quality. This is worth keeping in mind when interpreting CC norms after a
window adjustment.

---

## Convergence

Within a single run, ICCS iterates — rebuilding the stack and re-correlating
after each pass — until the stack stops changing meaningfully between iterations
or a maximum number of iterations is reached. Convergence is assessed by
comparing the current stack to the previous one: either by their correlation
coefficient, or by the normalised change in stack shape. This happens
automatically; there is no need to monitor it. Running ICCS again from
AIMBAT's interface always starts a fresh run from the current picks.

What matters is the convergence of the *overall process*: across multiple
runs with adjusted parameters, do the stack and CC norms keep improving, or
have they plateaued? When further adjustments produce no visible improvement
in the stack, alignment is as good as it is going to get with ICCS, and it is
time to move to MCCC.

---

## Knowing when to stop

There is no objective criterion for when ICCS alignment is "done". Practical
signals that the dataset is ready for MCCC:

- The stack is visually coherent — individual traces closely follow its shape
- CC norms are high across most of the array
- The time window highlights a clean, well-defined arrival
- Running ICCS again with or without autoflip/autoselect produces no
  meaningful change

It is worth taking a snapshot at this point before running MCCC.

---

## Tips

- **Change one parameter at a time.** It is easy to lose track of what caused
  an improvement or regression if multiple things change at once.
- **Take snapshots liberally.** They are lightweight and make it easy to
  backtrack to a promising state.
- **Don't over-optimise.** MCCC is more precise than ICCS and will further
  refine picks. The job of ICCS is to get the data to a state where MCCC can
  succeed — not to produce perfect picks itself.
- **Outlier seismograms.** If a seismogram consistently has a poor CC norm
  across many runs and parameter combinations, it may be worth deleting it
  from the project rather than letting it drag down the stack.
