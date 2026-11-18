# Migrations

A project database outlives the version of AIMBAT that created it, so a change
to the schema has to bring existing projects along. The schema is managed with
[Alembic](https://alembic.sqlalchemy.org). The migration scripts are in
`src/aimbat/_migrations/versions/` and are included in the wheel.

!!! note "Before version 2"

    Until AIMBAT 2.0 is released, `versions/` holds a single baseline migration. A
    schema change regenerates the baseline instead of adding a migration, and a
    project created with an earlier development version is refused with a message to
    recreate it. The schema can therefore change freely until then.

## Two paths to the current schema

A database reaches the current schema in one of two ways:

- **New project.** [`create_project`][aimbat.core.create_project] creates every
    table from the models and stamps the database at the latest revision, in one
    transaction. No migration runs.
- **Existing project.** [`upgrade_project`][aimbat.core.upgrade_project]
    (`aimbat db upgrade`) runs the migrations that the database has not yet had.
    A copy of the database is saved beforehand as
    `<project>.pre-<revision>.bak`.

Both paths must produce the same schema.
`tests/integration/core/test_migrations.py` builds a database each way and
compares the resulting schemas.

## Schema checks

AIMBAT compares the revision of a project with the latest revision when it first
connects:

- The CLI and the TUI refuse to work on an out-of-date project. The message
    either suggests `aimbat db upgrade` or explains that the project has to be
    recreated.
- Code that uses [`aimbat.db.engine`][aimbat.db] directly receives a
    [`SchemaStaleWarning`][aimbat.core.SchemaStaleWarning] instead, which is
    also logged. With the setting `AIMBAT_STRICT_SCHEMA_CHECK=true` (see
    [Aimbat defaults](../usage/defaults.md)), the warning becomes an error.

## Writing a migration

After version 2, every change to the models requires a migration.
`make check-migrations` runs `alembic check` against a freshly upgraded database
and fails if the models and the migrations differ. `make check-wheel` confirms
that the built wheel contains the migration scripts.

Alembic generates a migration from the difference between the models and a
database at the latest revision:

```bash
uv run alembic revision --autogenerate -m "short description"
```

The command uses the project database that AIMBAT is configured to use (see
[`aimbat.db`][aimbat.db]), so `AIMBAT_PROJECT` (see
[Aimbat defaults](../usage/defaults.md)) has to point to an up-to-date project.
The generated script is a starting point and needs review:

- **A renamed column is detected as a dropped and an added column.** The pair of
    `drop_column` and `add_column` calls has to be replaced by
    `alter_column(table, "old_name", new_column_name="new_name")`, which keeps
    the data. A column of a parameter or quality table usually also exists on
    the matching snapshot table (see
    [Database models](database-models.md#base-live-and-snapshot-classes)).
    Autogenerate does not relate the two, so both need the same correction.
- **SQLite recreates a table to alter it.** Migrations are generated in
    Alembic's batch mode, which copies the table, drops the original and renames
    the copy. With foreign keys enforced, dropping a table deletes the rows of
    every table that references it with `ON DELETE CASCADE`.
    `_migrations/env.py` therefore disables foreign key enforcement for the
    duration of a migration and enables it again afterwards.
- **Data may need converting.** Autogenerate only changes the structure. A
    migration that changes the meaning or unit of a column has to convert the
    existing values itself.

A migration is tested by upgrading a database created at the previous revision.
`TestUpgradeAcrossRevisions` in `test_migrations.py` shows the pattern.
