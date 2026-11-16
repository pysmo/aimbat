# Project

A project is a single SQLite database file (`aimbat.db` by default) holding
everything AIMBAT knows about a dataset: events, stations, seismograms, their
processing parameters, and snapshots. All four interfaces read and write the
same project file.

## Creating a project

A project must be initialised before data can be added. This creates the
database schema in a new SQLite file.

=== "CLI"

    ```bash
    aimbat project create
    ```

=== "Shell"

    ```bash
    project create
    ```

=== "TUI"

    Launch the TUI. If no project exists in the current directory, a prompt
    offers to create one or quit.

    ```bash
    aimbat tui
    ```

=== "API"

    ```python
    from aimbat.db import engine
    from aimbat.core import create_project

    create_project(engine)
    ```

Re-running `project create` on an existing project raises an error rather than
overwriting anything. [`create_project`][aimbat.core.create_project] raises
`RuntimeError` for the same case.

## Project location

By default, AIMBAT reads and writes `aimbat.db` in the current working
directory. The location only needs to be set once.

!!! warning "Keep the project on local storage"

    SQLite relies on POSIX file locking, which is not reliable over network
    filesystems (NFS, SMB, and similar). A project database on a network share
    can be corrupted. Keep `aimbat.db` on a local disk.

### A different path

Set `AIMBAT_PROJECT` to any file path, for one command or a whole session:

```bash
AIMBAT_PROJECT=/data/my-study/project.db aimbat tui
```

```bash
export AIMBAT_PROJECT=/data/my-study/project.db
aimbat project create
aimbat data add *.sac
```

### A .env file

A `.env` file in the working directory is loaded automatically, with no
exporting:

```bash title=".env"
AIMBAT_PROJECT=/data/my-study/project.db
```

This is the best option for persistent per-project configuration. Commit `.env`
alongside the project scripts so the path stays consistent.

### A full database URL

For advanced setups, such as a non-default SQLite driver, set `AIMBAT_DB_URL` to
a full
[SQLAlchemy URL](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls).
It takes precedence over `AIMBAT_PROJECT`:

```bash
AIMBAT_DB_URL=sqlite+pysqlite:////absolute/path/to/project.db aimbat tui
```

!!! warning "SQLite only"

    AIMBAT supports only `sqlite`-family URLs. A non-SQLite backend will not work
    correctly even with a driver installed: AIMBAT tells whether stored quality
    metrics are still up to date by comparing parameter values in the form
    SQLite stores them.

### Precedence

Highest wins:

1. `AIMBAT_DB_URL`
2. `AIMBAT_PROJECT`
3. `aimbat.db` in the current directory

Check what is in effect with `aimbat utils settings`, or
`aimbat utils settings --no-pretty` for `KEY="value"` output ready to paste into
`.env`.

## Upgrading a project

AIMBAT changes the database schema between some releases. A project created by an
older version must be brought up to date:

=== "CLI"

    ```bash
    aimbat db upgrade
    ```

=== "Shell"

    ```bash
    db upgrade
    ```

=== "TUI"

    Launch the TUI. A stale schema is caught on startup, before any panel that
    might query a column the live schema doesn't have: a modal offers to
    upgrade now (`u` or **Enter**) or quit.

    ```bash
    aimbat tui
    ```

=== "API"

    ```python
    from aimbat.db import engine
    from aimbat.core import upgrade_project

    upgrade_project(engine)
    ```

This is safe to run at any time. It does nothing if the project is already
current, and otherwise upgrades the schema without touching events, seismograms,
parameters, or snapshots.

!!! warning "Projects from development versions"

    A project made with an earlier development version of AIMBAT cannot be
    upgraded, and AIMBAT will not open it. Your seismogram files are not
    affected. Rename or move the project file (or point `AIMBAT_PROJECT` at a
    new one), run `aimbat project create`, and add the same files again with
    `aimbat data add`. Picks and parameters from the old project are not
    carried over.

Until a project is upgraded, every other `aimbat` command refuses to run against
it: the CLI and shell report the error, and the TUI shows a blocking dialog.
The Python API differs: see
[What every interface enforces](index.md#what-every-interface-enforces).

Check the current schema version without upgrading:

=== "CLI"

    ```bash
    aimbat db current
    ```

=== "Shell"

    ```bash
    db current
    ```

=== "API"

    ```python
    from aimbat.db import engine
    from aimbat.core import get_current_revision

    revision = get_current_revision(engine)  # None if never stamped
    ```

The TUI has no equivalent command; it runs this same check automatically on
startup and only surfaces it as the upgrade modal above.
