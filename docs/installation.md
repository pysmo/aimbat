# Installing AIMBAT

## Prerequisites

AIMBAT is built on top of standard [Python](https://www.python.org) and uses some popular
third party modules (e.g. [NumPy](inv:numpy#index), [SciPy](inv:scipy#index)). In order
to benefit from modern Python features and up to date modules, AIMBAT is developed on the
latest stable Python versions. Automatic tests are done on version 3.10 and newer.

AIMBAT is available as a package from the
[Python Package Index](https://pypi.org/project/aimbat/). This means it can be easily
installed using the [`pip`](inv:pip#index) module:

<!-- termynal -->

```
$ python3 -m pip install aimbat
---> 100%
Done!

```


Pre-release versions of aimbat can be installed with the `--pre` flag:

<!-- termynal -->

```
$ python3 -m pip install aimbat  --pre
---> 100%
Done!
```

Finally, the latest development version of aimbat can be installed directly from
[GitHub](https://github.com/pysmo/aimbat) by running:


<!-- termynal -->

```
$ python3 -m pip install git+https://github.com/pysmo/aimbat
---> 100%
Done!

```

```{note}
It is possible to install the stable release alongside the development
version. Please read the aimbat
[development documentation](<project:developing.md#development-environment>) for
instructions.
```

## Upgrading

Upgrades to pysmo are also performed with the ``pip`` command:

```bash
$ python3 -m pip install -U aimbat
```

## Uninstalling

To remove AIMBAT from the system run:

```bash
$ python3 -m pip uninstall aimbat
```

!!! note

    Unfortunately `pip` currently does not remove dependencies that were automatically
    installed. We suggest running `pip list` to see the installed packages, which can
    then also be removed using `pip uninstall`.