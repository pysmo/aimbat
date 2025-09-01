# Workflow and Strategy

## Without AIMBAT

Multi-Channel Cross-Correlation[@vandecar_determination_1990] (MCCC) relies on
narrow time windows, focused on the initial arrival arrival of the targeted
phase in order to yield high quality results. Manually picking the phase
arrival on each seismogram individually is a very time consuming task, which we
highlight with stacked cards in the below flowchart:

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

AIMBAT[@lou_aimbat_2013] stacks all input seismograms (aligned on the picked
phase arrival) and operates on that stack instead of individual seismograms.
This allows picking the phase arrival once for all seismograms simultaneously,
and then improving it iteratively before running MCCC. Note that both the ICCS
algorithm, as well as adjusting AIMBAT parameters are iterative processes.

``` mermaid
flowchart TD
  A@{ shape: circle, label: "Start"} --> B>Import seismograms containing initial picks t0];
  B --> C>"Run ICCS with intitial picks and default values for AIMBAT parameters (window width, filter parameters, etc)."];
  C --> D[Inspect results of course alignment];
  D --> E[Adjust AIMBAT parameters];
  E --> F>Run ICCS with updated parameters]
  F --> G[Inspect results of refined alignment];
  G --> H{"Continue
          with
          MCCC?"}
  H -->|Yes| M>"Run MCCC for final alignment"];
  H -->|No| E;
```

## Strategy

AIMBAT does not prescribe a single strategy for picking processing parameters.
Generally speaking, we recommend adjusting only one parameter at a time between
ICCS runs, and prioritising them as follows:

1. Filter parameters.
2. Selection of high quality seismograms.
3. Time window boundaries
4. Manually picking phase arrival.

!!! tip

    Remember that you can create snapshots of the current AIMBAT parameters at
    any time, and then rollback to that state if you notice you went into the
    wrong direction. We therefore encourage experimenting a bit with the
    strategy, as different events may require doing things slightly
    differently.

``` mermaid
---
title: AIMBAT Workflow
---
flowchart TD
  A[Start] --> B>Check data];
  B --> C{"Any
          errors?"};
  C --->|No| G>Import files to AIMBAT and
              run ICCS with initial picks
              and default parameters];
  C -->|Yes| F[Fix files];
  F --> B;
  G --> I["Inspect initial results"];

  I --> Iq2{"Adjust
                   filtering?"};
  Iq2 -->|No| Iq3{"Any bad
                   traces?"};
  Iq3 -->|No| Iq4{"Adjust time
                   window?"};
  Iq4 -->|No| Iq5{"Has the phase
                   arrival emerged
                   in stack?"};
  Iq5 -->|No| Irerun;

  Iq2 -->|Yes| Iq2y["Set new filter parameters."];
  Iq2y --> Iq2yq{"Re-run
                  ICCS
                  now?"};
  Iq2yq -->|No|Iq3;
  Iq2yq -->|Yes|Irerun;

  Iq3 -->|Yes| Iq3y["Select/deselect seismograms."];
  Iq3y --> Iq3yq{"Re-run
                  ICCS
                  now?"};
  Iq3yq -->|No|Iq4;
  Iq3yq -->|Yes|Irerun;

  Iq4 -->|Yes| Iq4y["Pick new time window"];
  Iq4y --> Iq4yq{"Re-run
                  ICCS
                  now?"};
  Iq4yq -->|No|Iq5;
  Iq4yq -->|Yes|Irerun;

  Iq5 -->|Yes| Iq5q{"Is the pick
                     on the visible
                     arrival?"};
  Iq5q -->|No| Iq5qy["Pick new Time"]  --> Irerun;
  Iq5q -->|Yes| Irerun;

  Irerun>"Run ICCS with
          updated settings"] --> I2;

  I2["Inspect updated results"];

  I2 --> qM{"Continue
             with
             MCCC?"}
  qM -->|Yes| M>"MCCC with final pick
                  and time window"] --> Z[END];
  qM -->|No| Iq2;

```
