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

---

AIMBAT (Automated and Interactive Measurement of Body wave Arrival Times) is an
open-source tool for measuring teleseismic body wave arrival times. Seismograms
are automatically aligned using the ICCS [Iterative Cross-Correlation and Stack][^1]
algorithm; picks are then reviewed and refined interactively before a final
MCCC (Multi-Channel Cross-Correlation) [^2] pass computes the definitive
arrival times.

## Version 2

AIMBAT v2 is a complete rewrite. It shares the same goal as v1 but none of the
code.

- **Complete rewrite.** The algorithms are optimised and projects are stored in
  a SQLite database (via [SQLModel](https://sqlmodel.tiangolo.com)), making them
  persistent, portable, and inspectable.
- **Focused scope.** Much of the underlying code has moved into the
  [pysmo](https://github.com/pysmo/pysmo) library, leaving AIMBAT to focus on
  the user-facing ICCS → quality-control → MCCC workflow rather than
  reimplementing general seismogram utilities.
- **Flexible data storage.** A single project can hold any number of seismic
  events. Files from different events can live anywhere on disk — no need to
  keep them in separate directories or follow a particular layout.
- **Maintainable.** v2 is built on modern, typed Python with a comprehensive
  test suite and strict dependency management, so it keeps working as the
  ecosystem evolves.
- **Multiple interfaces.** AIMBAT can be used via a CLI, an interactive shell,
  a terminal UI, or directly as a Python library.

## Quick Start

```bash
pip install aimbat

# Create a project in the current directory
aimbat project create

# Import SAC files — events and stations are detected automatically
aimbat data add *.sac

# List events to find their IDs, then set one as the default
aimbat event list
aimbat event default <ID>

# Open the terminal UI to run ICCS, review picks, and run MCCC
aimbat tui

# Or work interactively from the shell (tab-completion, command history)
aimbat shell
```

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
