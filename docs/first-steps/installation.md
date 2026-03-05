# Installing AIMBAT

AIMBAT is available on [PyPI][pypi] and can be installed with any standard
Python package manager. We recommend [`uv`][uv] or [`pipx`][pipx], which
isolate the installation from the rest of your Python environment.

## Running without installing

`uv` can run AIMBAT directly without a permanent installation:

```bash
$ uvx aimbat --version
2.0.0
```

The first run downloads AIMBAT and its dependencies; subsequent runs use the
cache and start immediately.

## Running the development version

```bash
$ uvx git+https://github.com/pysmo/aimbat --version
2.1.0.dev0
```

To clear the cache afterwards:

```bash
$ uv clean
```

## Installing permanently

```bash
$ uv tool install aimbat
Installed 1 executable: aimbat
```

```bash
$ aimbat
Usage: aimbat COMMAND
...
```

!!! tip
    If your shell cannot find the `aimbat` command, add `~/.local/bin` to your
    `PATH` by running `#!bash uv tool update-shell`.

Upgrade or uninstall with:

```bash
$ uv tool upgrade aimbat
$ uv tool uninstall aimbat
```

[pypi]: https://pypi.org/project/aimbat/
[uv]: https://docs.astral.sh/uv/
[pipx]: https://pipx.pypa.io
