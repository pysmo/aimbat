# Workflow

``` mermaid
graph TD
  A[Start] --> B>Check seismogram files];
  B --> C{"Any
          Errors?"};
  C -->|Yes| D[Fix Files];
  D --> B;
  C --->|No| E>Read files into AIMBAT];
  E --> G[Filter seismograms];
  G --> H>"ICCS with initital
          pick and time window"];
  H --> I["Pick new phase arrival
          Adjust window width
          Select/deselect seismograms
          Adjust filter parameters"];
  I --> K>"ICCS with refined
          pick and time window"];
  K --> J["Inspect results"]
  J --> L{"Continue
           with MCCC?"};
  L -->|No| I;
  L -->|Yes| M;
  L -.->|Restart| G;
  M>"MCCC with final
pick and time window"] --> N[End];
```
