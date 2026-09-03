# Project

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

Re-running `project create` on an existing project raises an error rather than
overwriting anything.

## Project location

By default, AIMBAT reads and writes `aimbat.db` in the current working
directory. All interfaces use the same configuration, so the location only needs
to be set once.

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
    correctly even with a driver installed: the triggers that keep quality
    metrics in sync with parameter changes are only ever created for SQLite, so
    the database would come up without them and quality data would silently go
    stale.

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
older version, including one predating schema versioning, must be brought up to
date:

=== "CLI"

    ```bash
    aimbat db upgrade
    ```

=== "Shell"

    ```bash
    db upgrade
    ```

This is safe to run at any time. It does nothing if the project is already
current, and otherwise upgrades the schema without touching events, seismograms,
parameters, or snapshots.

Until a project is upgraded, every other `aimbat` command refuses to run against
it: the CLI and shell report the error, and the TUI shows a blocking dialog.
Check the current schema version without upgrading:

=== "CLI"

    ```bash
    aimbat db current
    ```

=== "Shell"

    ```bash
    db current
    ```
