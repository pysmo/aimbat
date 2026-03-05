# Workflow and Strategy

The best results with AIMBAT are obtained if you understand the unique,
non-linear workflow that it prescribes. Unlike more traditional top-down
processing, AIMBAT is more of an iterative process whereby parameters are
constantly adjusted to gradually determine the optimal settings. The exact
strategy for a particular event may differ, but there are some general
guidelines below that we recommend following.

## Without AIMBAT

Multi-Channel Cross-Correlation[^1] (MCCC) relies on
narrow time windows, focused on the initial arrival of the targeted
phase in order to yield high quality results. Manually picking the phase
arrival on each seismogram individually is a very time consuming task, which is
highlighted by the stacked cards in the flowchart below:

[^1]:
  VanDecar, J. C., and R. S. Crosson. “Determination of Teleseismic
  Relative Phase Arrival Times Using Multi-Channel Cross-Correlation and
  Least Squares.” Bulletin of the Seismological Society of America,
  vol. 80, no. 1, Feb. 1990, pp. 150–69,
  <https://doi.org/10.1785/BSSA0800010150>.

```mermaid
flowchart TD
  A@{ shape: circle, label: "Start"} --> B>Import seismograms];
  B --> C[Select suitable filter parameters]
  C --> D[Choose high quality seismograms to use for MCCC]
  D --> E@{ shape: processes, label: "Individually pick phase arrival for seismograms 1...N"}
  E --> F[Choose time window for MCCC]
  F --> G>Run MCCC to align seismograms]
```

## With AIMBAT

AIMBAT[^2] stacks all input seismograms (aligned on the picked
phase arrival) and operates on that stack instead of individual seismograms.
This allows picking the phase arrival once for all seismograms simultaneously,
and then improving it iteratively before running MCCC. Note that both the ICCS
algorithm, as well as adjusting AIMBAT parameters are iterative processes.

[^2]:
  Lou, X., et al. “AIMBAT: A Python/Matplotlib Tool for Measuring
  Teleseismic Arrival Times.” Seismological Research Letters, vol. 84,
  no. 1, Jan. 2013, pp. 85–93, <https://doi.org/10.1785/0220120033>.

``` mermaid
flowchart TD
  A@{ shape: circle, label: "Start"}
  A --> B>Import seismograms containing initial picks t0];
  B --> F
  E[Adjust AIMBAT parameters];
  E --> F>Run ICCS with initial/updated parameters]
  F --> G[Inspect results of alignment];
  G --> H{"Continue
          with
          MCCC?"}
  H ---->|Yes| M>"Run MCCC for final alignment"];
  H -->|No| E;
```

## Strategy

AIMBAT does not prescribe a single strategy for picking/updating processing
parameters. That said, some general principles to follow are:

1. Only change one parameter at a time, and then run ICCS to see the effect
   of that change on the alignment
2. Snapshots are immediate and use no storage, so create them often (and don't
   skip adding a comment that describes the snapshot).
3. Don't get too distracted by individual seismograms that are not well aligned
   or seem of poor quality. Trust the algorithm to deal with those.

### ICCS running modes

Points 1 and 2 above are pretty self-explanatory, but point 3 deserves a bit
more explanation. The ICCS algorithm has two flags that can be set before each
run:
  
- **Autoflip**: If set to `True`, the algorithm will toggle the ``flip``
  parameter for seismograms that are negatively correlated with the stack (i.e.
  the maximum absolute correlation coefficient is negative).
- **Autoselect**: If set to `True`, the algorithm will automatically set the
  `select` parameter for seismograms that are poorly correlated with the stack
  to `False`, but it will also toggle previously deselected seismograms back
  to `True` if they become well correlated with the stack.

The `flip` parameter determines whether a seismogram is flipped in polarity as
the data are prepared for the stack and following cross-correlation. The
`select` parameter determines whether a seismogram is included in the stack;
however, *all* seismograms are cross-correlated with that stack regardless of
their `select` status. This means that all seismograms, even with
`select=False`, can self-recover if they fit the stack better after changing
parameters.

!!! Tip
    If seismograms are so bad that they wander off into the distance (i.e the
    difference between initial pick and revised pick after running ICCS is
    very large), consider deleting them completely from the AIMBAT project.
    This will prevent these rogue seismograms from influencing the valid
    ranges for updating time windows and picks.
