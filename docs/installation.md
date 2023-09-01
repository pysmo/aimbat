# Installation

AIMBAT is built on top of standard [Python](https://www.python.org) and uses some popular
third party modules (e.g. [NumPy][numpy], [SciPy][scipy]). In order
to benefit from modern Python features and up to date modules, AIMBAT is developed on the
latest stable Python versions. Automatic tests are done on version 3.10 and newer.

AIMBAT is available as a package from the
[Python Package Index](https://pypi.org/project/aimbat/). This means it can be easily
installed using the [`pip`](https://pip.pypa.io/en/stable/) module. However, as AIMBAT is
an application (rather than a library), we recommend installing it using
[`pipx`](https://pypa.github.io/pipx/) instead. Pipx installs a Python package into an
isolated environment, where other packages cannot interfere with it.

!!! warning
    Please consult the [pipx documentation](https://pypa.github.io/pipx/#install-pipx)
    before running the commands below! Installation and initial setup of pipx may vary
    depending on the operating system you are using.

<!-- termynal -->

```
# First we check the python version is at least 3.10
# (you may have to type python3 instead of python)
$ python --version
Python 3.11.2
# Next we install pipx with pip.
$ python -m pip install --user pipx
---> 100%
Successfully installed pipx-1.2.0
# Now we use pipx to install AIMBAT in an isolated environment.
$ pipx install aimbat
---> 100%
  installed package aimbat 2.0.0, installed using Python 3.11.2
  These apps are now globally available
    - aimbat
done! ✨ 🌟 ✨
# Let's verify AIMBAT is installed:
$ aimbat --version
aimbat, version 2.0.0
# hurray! 🥳
```
