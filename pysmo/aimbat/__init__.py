"""
AIMBAT
======

AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times)
is an open-source software package for efficiently measuring teleseismic 
body wave arrival times for large seismic arrays (Lou et al., 2012). It is 
based on a widely used method called MCCC (Multi-Channel Cross-Correlation) 
developed by VanDecar and Crosson (1990). The package is automated in the 
sense of initially aligning seismograms for MCCC which is achieved by an 
ICCS (Iterative Cross Correlation and Stack) algorithm. Meanwhile, a 
graphical user interface is built to perform seismogram quality control 
interactively. Therefore, user processing time is reduced while valuable 
input from a user\'s expertise is retained. As a byproduct, SAC (Goldstein 
et al., 2003) plotting and phase picking functionalities are replicated 
and enhanced.

"""
name = 'aimbat'
