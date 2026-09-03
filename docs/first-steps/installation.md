# Installing AIMBAT

!!! warning "Version 2 has not been released yet"

    This page is written for the upcoming version 2. It is not on PyPI yet, so
    `uvx aimbat` and `uv tool install aimbat` currently fetch only a placeholder
    release.

    Until version 2 is released, run or install it from GitHub:

    ```bash
    # run without installing
    uvx git+https://github.com/pysmo/aimbat

    # or install permanently
    uv tool install git+https://github.com/pysmo/aimbat
    ```

AIMBAT runs in the terminal and is published on [PyPI][pypi]. A tool like
[`uv`][uv] or [`pipx`][pipx] is the easiest way to install it: it creates an
isolated virtual environment and puts the `aimbat` command on `PATH`. The
examples below use `uv`[^1].

!!! note "Coming from version 1"

    Version 1 was distributed and imported as `pysmo.aimbat`. Version 2 is a
    separate, top-level package: install `aimbat`, import `aimbat`.

## Running without installation

`uv` can run AIMBAT directly, without a permanent installation:

```bash
$ uvx aimbat --version
2.0.0
```

The first run downloads AIMBAT and its dependencies. Later runs use the cache and
start immediately.

## Running the development version

The same command works against the GitHub repository, to try the latest
development version:

```bash
$ uvx git+https://github.com/pysmo/aimbat --version
2.1.0.dev0
```

Clear the download cache afterwards with:

```bash
uv cache clean
```

## Installing permanently

To keep the `aimbat` command available in the shell:

```bash
$ uv tool install aimbat
Installed 1 executable: aimbat
```

```bash
$ aimbat
Usage: aimbat COMMAND
...
```

!!! tip "`aimbat` command not found"

    If the shell cannot find the `aimbat` command, add `~/.local/bin` to `PATH`
    by running `#!bash uv tool update-shell`.

Upgrade or uninstall with:

```bash
uv tool upgrade aimbat
uv tool uninstall aimbat
```

## Using AIMBAT as a library

To call the [Python API](../usage/api.md) from other code, add AIMBAT as a
project dependency rather than installing the command:

```bash
uv add aimbat
```

```python
import aimbat
```

pysmo's [installation guide][pysmo-install] covers the project setup this assumes
(`uv init`, `uv run`, optional direnv); the same steps apply here.

[^1]: `uv` can do more than install command-line tools. See the
    [documentation][uv] for more information.

[pipx]: https://pipx.pypa.io
[pypi]: https://pypi.org/project/aimbat/
[pysmo-install]: https://docs.pysmo.org/first-steps/installation/#a-project-recommended
[uv]: https://docs.astral.sh/uv/
