<h1 style="text-align: center;">AIMBAT</h1>

<p align="center">
<em>Automated and Interactive Measurement of Body wave Arrival Times</em>
</p>

<div align="center">
<a href="https://github.com/pysmo/pysmo/actions/workflows/run-tests.yml" target="_blank">
<img src="https://github.com/pysmo/aimbat/actions/workflows/run-tests.yml/badge.svg" alt="Test Status">
</img></a>
<a href="https://github.com/pysmo/pysmo/actions/workflows/build.yml" target="_bank">
<img src= "https://github.com/pysmo/aimbat/actions/workflows/build.yml/badge.svg" alt="Build Status">
</img></a>
<a href="https://aimbat.readthedocs.io/en/latest/?badge=latest" target="_blank">
<img src="https://readthedocs.org/projects/aimbat/badge/?version=latest" alt="Documentation Status">
</img></a>
<h href="https://codecov.io/gh/pysmo/aimbat" target="_blank">
<img src="https://codecov.io/gh/pysmo/aimbat/branch/master/graph/badge.svg?token=ZsHTBN4rxF" alt="codecov">
</img></a>
<h href="https://pypi.org/project/aimbat/" target="_blank">
<img src="https://img.shields.io/pypi/v/aimbat" alt="PyPI">
</img></a></div>

<p style="text-align: center;">
<em>Documentation:</em> <a href="https://aimbat.readthedocs.io" target="_blank">https://aimbat.readthedocs.io</a>
</p>
<p style="text-align: center;">
<em>Source Code:</em> <a href="https://github.com/pysmo/aimbat" target="_blank">https://github.com/pysmo/aimbat</a>
</p>


---

AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times) is an
open-source software package for efficiently measuring teleseismic body wave arrival
times for large seismic arrays [[1]](#1). It is based on a widely used method called
MCCC (Multi-Channel Cross-Correlation) [[2]](#2). The package is automated in the sense
of initially aligning seismograms for MCCC, which is achieved by an ICCS (Iterative Cross
Correlation and Stack) algorithm. Meanwhile, a GUI (graphical user interface) is built to
perform seismogram quality control interactively. Therefore, user processing time is
reduced while valuable input from a user's expertise is retained. As a byproduct, SAC
[[3]](#3) plotting and phase picking functionalities are replicated and enhanced.

Modules and scripts included in the AIMBAT package were developed using
[Python](http://www.python.org/) and its open-source modules on the Mac OS X platform
since 2009. The original MCCC [[2]](#2) code was transcribed into Python.
The GUI of AIMBAT was inspired and initiated at the
[2009 EarthScope USArray Data Processing and Analysis Short Course](https://www.iris.edu/hq/es_course/content/2009.html).
AIMBAT runs on Mac OS X, Linux/Unix and Windows thanks to the platform-independent
feature of Python.

For more information visit the
[project website](http://www.earth.northwestern.edu/~xlou/aimbat.html) or the
[pysmo repositories](https://github.com/pysmo).


## Authors' Contacts

* [Xiaoting Lou](http://geophysics.earth.northwestern.edu/people/xlou/aimbat.html) Email: xlou at u.northwestern.edu

* [Suzan van der Lee](http://geophysics.earth.northwestern.edu/seismology/suzan/) Email: suzan at northwestern.edu

* [Simon Lloyd](https://www.slloyd.net/) Email: simon at pysmo.org

## Contributors

* Lay Kuan Loh

## References

<a id="1">[1]</a>
Xiaoting Lou, Suzan van der Lee, and Simon Lloyd (2013),
AIMBAT: A Python/Matplotlib Tool for Measuring Teleseismic Arrival Times.
*Seismol. Res. Lett.*, 84(1), 85-93, doi:10.1785/0220120033.

<a id="2">[2]</a>
VanDecar, J. C., and R. S. Crosson (1990),
Determination of teleseismic relative phase arrival times using multi-channel
cross-correlation and
least squares.
*Bulletin of the Seismological Society of America*, 80(1), 150–169.

<a id="3">[3]</a>
Goldstein, P., D. Dodge, M. Firpo, and L. Minner (2003),
SAC2000: Signal processing and analysis tools for seismologists and engineers,
*International Geophysics*, 81, 1613–1614.
