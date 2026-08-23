<h1 align="center">AIMBAT</h1>

<p align="center">
<em>Automated and Interactive Measurement of Body wave Arrival Times</em>
</p>

<div align="center">
<a href="https://github.com/pysmo/aimbat/actions/workflows/run-tests.yml" target="_blank">
<img src="https://github.com/pysmo/aimbat/actions/workflows/run-tests.yml/badge.svg" alt="Test Status">
</img></a>
<a href="https://github.com/pysmo/aimbat/actions/workflows/build.yml" target="_bank">
<img src= "https://github.com/pysmo/aimbat/actions/workflows/build.yml/badge.svg" alt="Build Status">
</img></a>
<a href="https://aimbat.readthedocs.io/en/latest/?badge=latest" target="_blank">
<img src="https://readthedocs.org/projects/aimbat/badge/?version=latest" alt="Documentation Status">
</img></a>
<a href="https://codecov.io/gh/pysmo/aimbat" target="_blank">
<img src="https://codecov.io/gh/pysmo/aimbat/branch/master/graph/badge.svg?token=ZsHTBN4rxF" alt="codecov">
</img></a>
<a href="https://pypi.org/project/aimbat/" target="_blank">
<img src="https://img.shields.io/pypi/v/aimbat" alt="PyPI">
</img></a></div>

<p align="center">
<em>Documentation:</em> <a href="https://aimbat.pysmo.org" target="_blank">https://aimbat.pysmo.org</a>
</p>
<p align="center">
<em>Source Code:</em> <a href="https://github.com/pysmo/aimbat" target="_blank">https://github.com/pysmo/aimbat</a>
</p>

AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times) is an
open-source tool for measuring teleseismic body wave arrival times. Seismograms
are automatically aligned using the ICCS [Iterative Cross-Correlation and Stack][^1]
algorithm; picks are then reviewed and refined interactively before a final
MCCC (Multi-Channel Cross-Correlation) [^2] pass computes the definitive
arrival times.

## Version 2

AIMBAT v2 is a complete rewrite, sharing no code with v1. Changes for users
include:

- **Flexible workflow.** Snapshots record the processing state at any point,
  so earlier states can be restored and parameter sets compared without
  losing prior work. ICCS and MCCC can be run in any order and repeated as
  needed; results can be exported from any snapshot, not only after a final
  MCCC pass.
- **Multi-event projects.** A single project database holds any number of
  seismic events. Waveform files can be stored anywhere on disk; no fixed
  directory layout is required.
- **Structured output.** Each snapshot can be exported as a JSON document
  containing per-station arrival times, ICCS correlation coefficients, and,
  if MCCC has been run, formal timing standard errors. This format supports
  uses beyond tomographic inversion, such as station quality assessment or
  analysis of delay patterns as a function of back-azimuth.
- **Multiple interfaces.** AIMBAT is available as a CLI, an interactive
  shell, a terminal UI, and a Python library. All functionality is
  accessible through the Python API.


## Authors' Contacts

- Xiaoting Lou — xlou at u.northwestern.edu
- Suzan van der Lee — suzan at northwestern.edu
- Simon Lloyd — simon at pysmo.org

[^1]: Xiaoting Lou, Suzan van der Lee, and Simon Lloyd, “AIMBAT: A Python/Matplotlib
  Tool for Measuring Teleseismic Arrival Times.” Seismological Research Letters,
  vol. 84, no. 1, Jan. 2013, pp. 85–93, <https://doi.org/10.1785/0220120033>.

[^2]: VanDecar, J. C., and R. S. Crosson. “Determination of Teleseismic
  Relative Phase Arrival Times Using Multi-Channel Cross-Correlation and
  Least Squares.” Bulletin of the Seismological Society of America,
  vol. 80, no. 1, Feb. 1990, pp. 150–69,
  <https://doi.org/10.1785/BSSA0800010150>.
