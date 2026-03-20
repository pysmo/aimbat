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

=== "GUI"

    The GUI creates a project automatically on startup if one does not already
    exist.

    ```bash
    aimbat-gui
    ```

Re-running `project create` on an existing project is safe — it raises an
error rather than overwriting data.

---

## Project location

By default, AIMBAT reads and writes a file called `aimbat.db` in the current
working directory. All four interfaces respect the same configuration, so you
only need to set it once.

!!! warning "Keep the project on local storage"
    SQLite relies on POSIX file locking, which is not reliably supported over
    network filesystems (NFS, SMB, etc.). Placing the project database on a
    network share can lead to database corruption. Keep `aimbat.db` on a local
    disk.

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

For advanced use (e.g. a remote or in-memory database), set `AIMBAT_DB_URL`
to a full [SQLAlchemy connection URL](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls).
When set, it takes precedence over `AIMBAT_PROJECT`:

```bash
AIMBAT_DB_URL=sqlite+pysqlite:////absolute/path/to/project.db aimbat tui
```

!!! note "In-memory databases"
    `AIMBAT_DB_URL=sqlite+pysqlite:///:memory:` creates a temporary in-memory
    database that is discarded when the process exits. This is used internally
    for testing.

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
