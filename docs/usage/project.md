# Project

## Creating a project

Before adding data, a project must be initialised. This creates the database
schema in a new SQLite file.

=== "CLI"

    ```bash
    aimbat project create
    ```

=== "Shell"

    ```bash
    project create
    ```

=== "TUI"

    Launch the TUI — if no project is found in the current directory, a prompt
    appears offering to create one or quit.

    ```bash
    aimbat tui
    ```

Re-running `project create` on an existing project is safe — it raises an error
rather than overwriting data.

## Upgrading a project

An existing project's database schema needs to be brought up to date after
upgrading AIMBAT to a version that changed it — including a project created
by a version of AIMBAT that predates schema versioning entirely.

=== "CLI"

    ```bash
    aimbat db upgrade
    ```

=== "Shell"

    ```bash
    db upgrade
    ```

This is safe to run at any time: it does nothing if the project is already up
to date, and otherwise brings it to the latest schema without touching
existing events, seismograms, parameters, or snapshots.

If a project's schema is out of date, every other `aimbat` command refuses to
run against it rather than risk operating on a schema it doesn't
recognise — the CLI/Shell report the error directly, and the TUI shows a
blocking dialog — pointing you at `aimbat db upgrade` instead.

To check a project's current schema version without upgrading it:

=== "CLI"

    ```bash
    aimbat db current
    ```

=== "Shell"

    ```bash
    db current
    ```

## Project location

By default, AIMBAT reads and writes a file called `aimbat.db` in the current
working directory. All interfaces respect the same configuration, so you only
need to set it once.

!!! warning "Keep the project on local storage"

    SQLite relies on POSIX file locking, which is not reliably supported over
    network filesystems (NFS, SMB, etc.). Placing the project database on a network
    share can lead to database corruption. Keep `aimbat.db` on a local disk.

### Using a different path

Set `AIMBAT_PROJECT` to any file path:

```bash
AIMBAT_PROJECT=/data/my-study/project.db aimbat tui
```

Or export it for the duration of a shell session:

```bash
export AIMBAT_PROJECT=/data/my-study/project.db
aimbat project create
aimbat data add *.sac
aimbat tui
```

### Using a .env file

Place a `.env` file in the directory where you run AIMBAT. Settings in `.env`
are loaded automatically and do not require exporting:

```bash title=".env"
AIMBAT_PROJECT=/data/my-study/project.db
```

This is the recommended approach for persistent, per-project configuration —
commit `.env` alongside your scripts so the path is always consistent.

### Using a full database URL

For advanced use (e.g. a non-default SQLite driver setup), set `AIMBAT_DB_URL`
to a full
[SQLAlchemy connection URL](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls).
When set, it takes precedence over `AIMBAT_PROJECT`:

```bash
AIMBAT_DB_URL=sqlite+pysqlite:////absolute/path/to/project.db aimbat tui
```

!!! warning "SQLite only"

    AIMBAT only supports `sqlite`-family URLs. Nothing stops `AIMBAT_DB_URL` from
    being set to a different backend (e.g. `postgresql://...`), but it will not work
    correctly: no non-SQLite driver is bundled, and even if one is installed
    separately, the triggers that keep quality metrics in sync with parameter
    changes are only ever created for SQLite. The database would come up without
    them, and quality data would silently go stale.

### Precedence

Configuration is resolved in this order (highest wins):

1. `AIMBAT_DB_URL` environment variable or `.env` entry
2. `AIMBAT_PROJECT` environment variable or `.env` entry
3. Built-in default: `aimbat.db` in the current directory

To inspect the settings currently in use:

```bash
aimbat utils settings            # human-readable table
aimbat utils settings --no-pretty  # KEY="value" format, ready to paste into .env or export
```
