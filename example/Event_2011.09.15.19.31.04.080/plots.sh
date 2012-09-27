#!/bin/sh

# one seimogram:
egsac.py

# Read 22 seismograms with sampling interval: 0.025000s
egplot.py TA.[1-K]*Z  -f1

# Read 87 seismograms with sampling interval: 0.025000s
egalign1.py CI*Z TA*Z -f1

# Read 163 seismograms with sampling interval: 0.025000s
egalign2.py *Z


