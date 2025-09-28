# Installing AIMBAT

AIMBAT is built on top of standard [Python](https://www.python.org) and uses
some popular third party modules (e.g. [NumPy][numpy], [SciPy][scipy]). In
order to benefit from modern Python features and up to date modules, AIMBAT is
developed on the latest stable Python versions. Automatic tests are done on
version 3.12 and newer.

AIMBAT is available as a package from the
[Python Package Index](https://pypi.org/project/aimbat/). This means it can be
installed using the [`pip`](https://pip.pypa.io/en/stable/) module. However, as
AIMBAT is a standalone application (rather than a library), we recommend
installing it using [`uv`](https://docs.astral.sh/uv/) instead. `uv` is a
single binary that doesn't require any dependencies to be installed, and it
allows to install and run AIMBAT in an isolated environment.

## Running AIMBAT without installing

Running applications with `uv` is very simple. It manages all dependencies and
even installs a compatible Python version if needed. A very convenient feature
of using `uv` is that it can run applications without installing them:

```bash
$ # First check that uv is available:
$ uv --version
uv 0.8.14
$ # Next run AIMBAT using uv tool:
$ uv tool run aimbat
⠦ Resolving dependencies...
...
Usage: aimbat COMMAND

AIMBAT command line interface entrypoint for all other commands.

This is the main command line interface for AIMBAT. It must be
executed with a command (as specified below) to actually do anything.
Help for individual commands is available by typing aimbat COMMAND
--help.

╭─ Commands ────────────────────────────────────────────────────────╮
│ data        Manage seismogram files in an AIMBAT project.         │
│ event       View and manage events in the AIMBAT project.         │
│ iccs        ICCS processing tools.                                │
│ project     Manage AIMBAT projects.                               │
│ seismogram  View and manage seismograms in the AIMBAT project.    │
│ settings    Print a table with default settings used in AIMBAT.   │
│ snapshot    View and manage snapshots.                            │
│ station     View and manage stations.                             │
│ utils       Utilities for AIMBAT.                                 │
│ --help -h   Display this message and exit.                        │
│ --version   Display application version.                          │
╰───────────────────────────────────────────────────────────────────╯
```

This will likely have taken a while, as `uv` has to download and install a lot
of dependencies. Subsequent runs will be much faster. `uv tool run` is such a
useful command that it has its own alias, `uvx`:

```bash
# 'uvx' is an alias for 'uv tool run':
$ uvx aimbat
Usage: aimbat COMMAND
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
Clearing cache at: /home/USER/.cache/uv
Removed 26702 files (2.1GiB)
```

## Installing AIMBAT locally

After successfully test driving AIMBAT you may want to actually install it.
This is very simple with `uv`:

```bash
# Again use uv tool, but this time with the 'install' command:
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

Upgrading or uninstalling AIMBAT is just as easy:

```bash
$ uv tool upgrade aimbat
Nothing to upgrade
$ uv tool uninstall aimbat
Uninstalled 1 executable: aimbat
```

## Demo

This demo shows what you can expect to see in your terminal when running
the commands above:

<div id="asciinema-installation-demo" style="z-index: 1; position: relative; "></div>

<script>
  window.onload = function(){
    const player = AsciinemaPlayer.create('../../images/asciinema/install-with-uv.cast', document.getElementById('asciinema-installation-demo'),
{poster: 'npt:0:18', idleTimeLimit: 2,   markers: [
    [3, 'Intro'],
    [5, 'Foo'],
    [9, 'Bar'],
  ] });

}
</script>

!!! tip

    These kinds of recordings work just like normal videos, but you can also
    select text and copy it to your clipboard!
