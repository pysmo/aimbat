# Installing AIMBAT

!!! warning "Version 2 has not been released yet"

    The instructions below are written with the upcoming version 2 of AIMBAT in
    mind. It is not yet available on PyPI, so the only installation option is to use
    the development version from GitHub.

AIMBAT is available on [PyPI] and can be installed with any standard Python
package manager. A simple way to get started is to treat AIMBAT as a
command-line only application (i.e. _not_ as a library used in other code);
tools like [`uv`][uv] or [`pipx`][pipx] handle creating an isolated virtual
environment and making the `aimbat` command available in the shell
automatically.

The instructions below use `uv`[^1] as a convenient example, not because it is
the recommended way to install AIMBAT.

## Running without installation

`uv` can run AIMBAT directly without a permanent installation:

```bash
$ uvx aimbat --version
2.0.0
```

The first run downloads AIMBAT and its dependencies; subsequent runs use the
cache and start immediately.

## Running the development version

The same approach works directly against the GitHub repository, to try
unreleased features:

```bash
$ uvx git+https://github.com/pysmo/aimbat --version
2.1.0.dev0
```

To clear the cache afterwards:

```bash
uv clean
```

## Installing permanently

To make the `aimbat` command available in the shell permanently:

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

    If your shell cannot find the `aimbat` command, add `~/.local/bin` to your
    `PATH` by running `#!bash uv tool update-shell`.

Upgrade or uninstall with:

```bash
uv tool upgrade aimbat
uv tool uninstall aimbat
```

[^1]: `uv` can do more than just install command-line tools. See the
    [documentation][uv] for more information.

[pipx]: https://pipx.pypa.io
[pypi]: https://pypi.org/project/aimbat/
[uv]: https://docs.astral.sh/uv/
