# Workflow

``` mermaid
---
title: AIMBAT Workflow
---
flowchart TD
  A[Start] --> B>Read seismogram files into AIMBAT];
  B --> C>Check data];
  C --> D{"Any
          errors?"};
  D --->|No| G>Filter seismograms];
  D -->|Yes| F[Fix files];
  F --> B;
  G --> H>"ICCS with initital pick and default time window"];
  H --> I["Inspect initial results"];

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
