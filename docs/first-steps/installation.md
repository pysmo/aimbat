# Installing AIMBAT

AIMBAT is built on top of standard [Python](https://www.python.org), combined
with a number of popular third party modules such as [NumPy][numpy] and
[SciPy][scipy]. It is available as a package from the
[Python Package Index][pypi], and can therefore be
installed using Python's standard package manager,
[`pip`](https://pip.pypa.io/en/stable/).

However, as AIMBAT is a standalone application, we recommend installing it
using tools like [`uv`][uv] or [`pipx`][pipx] instead[^1]. Here we show how to
install and run AIMBAT using `uv`.

[^1]: If you want to get really fancy you can also use tools like
    [MISE-EN-PLACE](https://mise.jdx.dev), which use `uv` or `pipx` under the
    hood.

## Running AIMBAT without installing

Running applications with `uv` is very simple. It manages all dependencies and
even installs a compatible Python version if needed. A very convenient feature
of using `uv` is that it can run applications without installing them:

```bash
$ # First check that uv is available:
$ uv self version
uv 0.10.6
$ # Next run AIMBAT using uv tool:
$ uv tool run aimbat --version
⠴ Resolving dependencies...
2.0.0
```

The initial run may take a while to download AIMBAT and its dependencies, but
once that is done subsequent runs will be much faster. `uv tool run` is such a
useful command that it has its own alias, `uvx`:

```bash
$ uvx aimbat --version
2.0.0
...
```

## Running the development version

Running AIMBAT without installing it is particularly useful for trying out the
latest development version:

```
$ uvx git+https://github.com/pysmo/aimbat --version
Updating https://github.com/pysmo/aimbat (HEAD)
⠇ Resolving dependencies...
⠦ Preparing packages... (66/69)
---> 100%
---> 100%
2.1.0.dev0
```

To clean up after yourself, you can remove the `uv` cache:

```bash
$ uv clean
Clearing cache at: /home/bob/.cache/uv
Cleaning [==================> ] 91%
Removed 26702 files (2.1GiB)
```

## Installing locally

Permanent installation is just as easy. Just run `uv tool install`:

```bash
$ uv tool install aimbat
⠦ Resolving dependencies...
⠇ Preparing packages... (66/69)
+ aimbat==2.0.0
...
Installed 1 executable: aimbat
```

You can now run AIMBAT using the `aimbat` command directly:

```bash
$ aimbat
Usage: aimbat COMMAND
...
```

!!! tip
    If the above command fails (because your shell can't find the `aimbat`
    command), you may need to add `~/.local/bin` to your `PATH`. This can be
    done automatically by running `#!bash uv tool update-shell`.

Upgrading or uninstalling is just as easy with `uv tool upgrade` and `uv tool
uninstall`:

```bash
$ uv tool upgrade aimbat
Nothing to upgrade
$ uv tool uninstall aimbat
Uninstalled 1 executable: aimbat
```

[numpy]: https://numpy.org
[scipy]: https://scipy.org
[pypi]: https://pypi.org/project/aimbat/
[uv]: https://docs.astral.sh/uv/
[pipx]: https://pipx.pypa.io
