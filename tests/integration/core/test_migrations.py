"""Integration tests for Alembic-backed schema migrations.

Uses real file-based databases rather than `:memory:`, since Alembic's
`env.py` opens its own connection.
"""

import re
import shutil
from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, text

import aimbat._migrations
from aimbat.core import (
    create_project,
    get_current_revision,
    get_head_revision,
    upgrade_project,
)
from aimbat.core._migrations import SchemaMismatchError
from aimbat.core._project import _NULL_ICCS_FOR_EVENT, _NULL_ICCS_IF_SELECTED
from aimbat.models._parameters import (
    EVENT_PARAMETER_SPECS,
    SEISMOGRAM_PARAMETER_SPECS,
    ParameterSpec,
    Reach,
)


def _triggers(engine: Engine) -> dict[str, str]:
    """Maps trigger name to its normalised (whitespace-collapsed) SQL body.

    Comparing bodies, not just names, matters: `create_project()` and the
    baseline migration each hand-maintain a copy of the same trigger SQL
    (triggers are invisible to Alembic autogenerate, so there's no way to
    keep them in sync automatically) - a same-named trigger whose logic
    silently drifted between the two would still compare equal under a
    names-only check. Whitespace is collapsed because the two copies are
    nested at different indentation levels in `_project.py` vs. the
    migration file, which would otherwise make identical SQL compare
    unequal as raw text.
    """
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'")
        ).all()
    return {name: " ".join(sql.split()) for name, sql in rows}


def _when_columns(trigger_sql: str) -> set[str]:
    """Extract the set of `NEW.<column>` names referenced in a trigger's `WHEN` clause.

    Assumes the `CREATE TRIGGER ... WHEN (...) BEGIN ... END` shape used
    throughout `core/_project.py`'s quality-invalidation triggers.
    """
    when_clause = trigger_sql.split("WHEN", 1)[1].split("BEGIN", 1)[0]
    return set(re.findall(r'NEW\."?([A-Za-z_][A-Za-z0-9_]*)"?', when_clause))


def _tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def _columns(engine: Engine, table: str) -> dict[str, tuple[str, bool]]:
    """Maps column name to (rendered type, nullable) for `table`."""
    return {
        col["name"]: (str(col["type"]), col["nullable"])
        for col in inspect(engine).get_columns(table)
    }


def _foreign_keys(engine: Engine, table: str) -> set[tuple[str, ...]]:
    return {
        (fk["referred_table"], *fk["constrained_columns"])
        for fk in inspect(engine).get_foreign_keys(table)
    }


def _unique_constraints(engine: Engine, table: str) -> set[tuple[str, ...]]:
    """Set of sorted column-name tuples, one per unique constraint on `table`.

    Compared by columns, not name: AIMBAT's unique constraints (e.g.
    `AimbatEvent.time`, `AimbatSnapshot.time`) are unnamed - SQLAlchemy/SQLite
    auto-name them, so comparing names would compare an implementation
    detail neither creation path actually controls.
    """
    return {
        tuple(sorted(name for name in uc["column_names"] if name is not None))
        for uc in inspect(engine).get_unique_constraints(table)
    }


def _check_constraints(engine: Engine, table: str) -> set[tuple[str | None, str]]:
    """Set of (name, normalised SQL text), one per check constraint on `table`.

    Unlike unique constraints, AIMBAT's check constraints are explicitly
    named (e.g. `aimbat_note_exactly_one_parent`) - the name is part of the
    constraint's actual intent here, not an auto-generated implementation
    detail, so it's included in the comparison.
    """
    return {
        (cc["name"], " ".join(cc["sqltext"].split()))
        for cc in inspect(engine).get_check_constraints(table)
    }


def _indexes(engine: Engine, table: str) -> set[tuple[tuple[str, ...], bool]]:
    """Set of (sorted column names, unique flag), one per explicit index on `table`."""
    return {
        (
            tuple(sorted(name for name in idx["column_names"] if name is not None)),
            idx["unique"],
        )
        for idx in inspect(engine).get_indexes(table)
    }


class TestCreateAllVsMigrateParity:
    """`create_project()` (`create_all`) and `upgrade_project()` (Alembic)
    must produce structurally identical schemas, since both are used to
    reach the same "current schema" state via different code paths (§5 of
    the Alembic plan).
    """

    @pytest.fixture
    def create_all_engine(self, tmp_path: Path) -> Generator[Engine]:
        engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'create_all.db'}")
        create_project(engine)
        yield engine
        engine.dispose()

    @pytest.fixture
    def migrated_engine(self, tmp_path: Path) -> Generator[Engine]:
        engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'migrated.db'}")
        upgrade_project(engine)
        yield engine
        engine.dispose()

    def test_same_tables(
        self, create_all_engine: Engine, migrated_engine: Engine
    ) -> None:
        assert _tables(create_all_engine) == _tables(migrated_engine)

    def test_same_columns_per_table(
        self, create_all_engine: Engine, migrated_engine: Engine
    ) -> None:
        for table in _tables(create_all_engine):
            assert _columns(create_all_engine, table) == _columns(
                migrated_engine, table
            ), f"column mismatch in {table!r}"

    def test_same_foreign_keys_per_table(
        self, create_all_engine: Engine, migrated_engine: Engine
    ) -> None:
        for table in _tables(create_all_engine):
            assert _foreign_keys(create_all_engine, table) == _foreign_keys(
                migrated_engine, table
            ), f"foreign key mismatch in {table!r}"

    def test_same_unique_constraints_per_table(
        self, create_all_engine: Engine, migrated_engine: Engine
    ) -> None:
        """E.g. `AimbatEvent.time`/`AimbatSnapshot.time` being UNIQUE."""
        for table in _tables(create_all_engine):
            assert _unique_constraints(create_all_engine, table) == _unique_constraints(
                migrated_engine, table
            ), f"unique constraint mismatch in {table!r}"

    def test_same_check_constraints_per_table(
        self, create_all_engine: Engine, migrated_engine: Engine
    ) -> None:
        """E.g. `aimbat_note_exactly_one_parent` on `AimbatNote`."""
        for table in _tables(create_all_engine):
            assert _check_constraints(create_all_engine, table) == _check_constraints(
                migrated_engine, table
            ), f"check constraint mismatch in {table!r}"

    def test_same_indexes_per_table(
        self, create_all_engine: Engine, migrated_engine: Engine
    ) -> None:
        for table in _tables(create_all_engine):
            assert _indexes(create_all_engine, table) == _indexes(
                migrated_engine, table
            ), f"index mismatch in {table!r}"

    def test_same_triggers(
        self, create_all_engine: Engine, migrated_engine: Engine
    ) -> None:
        """Structural (names) and behavioural (bodies) parity - see `_triggers`."""
        assert _triggers(create_all_engine) == _triggers(migrated_engine)


def test_triggers_helper_detects_body_drift(tmp_path: Path) -> None:
    """Guards `_triggers` itself: a same-named trigger with a different body
    must compare unequal, proving `test_same_triggers` would actually catch
    a trigger's logic silently drifting between `create_project()` and the
    migration - not just a trigger being entirely missing or extra.
    """
    engine_a = create_engine(f"sqlite+pysqlite:///{tmp_path / 'a.db'}")
    engine_b = create_engine(f"sqlite+pysqlite:///{tmp_path / 'b.db'}")
    for engine in (engine_a, engine_b):
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE t (x INTEGER)"))

    with engine_a.begin() as connection:
        connection.execute(
            text("CREATE TRIGGER trig AFTER INSERT ON t BEGIN SELECT 1; END")
        )
    with engine_b.begin() as connection:
        connection.execute(
            text("CREATE TRIGGER trig AFTER INSERT ON t BEGIN SELECT 2; END")
        )

    assert set(_triggers(engine_a)) == set(_triggers(engine_b))  # same names
    assert _triggers(engine_a) != _triggers(engine_b)  # different bodies

    engine_a.dispose()
    engine_b.dispose()


class TestTriggerWhenClausesFollowTheParameterSpecs:
    """The trigger `WHEN` column lists are hand-written SQL in
    `core/_project.py`. Each must list exactly the parameters whose specs (see
    `models/_parameters.py`) say the trigger's effect applies, so a parameter
    that is added or reclassified without editing the triggers fails here.
    """

    @pytest.fixture
    def triggers(self, tmp_path: Path) -> Generator[dict[str, str]]:
        engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'triggers.db'}")
        create_project(engine)
        yield _triggers(engine)
        engine.dispose()

    @pytest.mark.parametrize(
        ("trigger", "expected"),
        [
            pytest.param(
                "event_modified_on_params_update",
                lambda spec: not spec.bookkeeping,
                id="1-last-modified",
            ),
            pytest.param(
                "event_stack_modified_on_params_update",
                lambda spec: spec.stack is Reach.EVENT,
                id="1b-stack-modified",
            ),
            pytest.param(
                "null_all_quality_on_window_bandpass_change",
                lambda spec: spec.stack is Reach.EVENT,
                id="3-null-all-quality",
            ),
            pytest.param(
                "null_mccc_quality_on_mccc_params_change",
                lambda spec: spec.mccc is Reach.EVENT and spec.stack is Reach.NONE,
                id="4-null-mccc-quality",
            ),
        ],
    )
    def test_event_parameter_trigger(
        self,
        triggers: dict[str, str],
        trigger: str,
        expected: Callable[[ParameterSpec], bool],
    ) -> None:
        assert _when_columns(triggers[trigger]) == {
            name for name, spec in EVENT_PARAMETER_SPECS.items() if expected(spec)
        }

    @pytest.mark.parametrize(
        "trigger",
        [
            pytest.param("event_modified_on_seis_params_update", id="2-last-modified"),
            pytest.param(
                "event_stack_modified_on_seis_params_update", id="2b-stack-modified"
            ),
        ],
    )
    def test_seismogram_parameter_trigger(
        self, triggers: dict[str, str], trigger: str
    ) -> None:
        """Every seismogram parameter reaches the stack, at least conditionally."""
        assert all(
            spec.stack is not Reach.NONE for spec in SEISMOGRAM_PARAMETER_SPECS.values()
        )
        assert _when_columns(triggers[trigger]) == set(SEISMOGRAM_PARAMETER_SPECS)

    @pytest.mark.parametrize("name", SEISMOGRAM_PARAMETER_SPECS)
    def test_seismogram_quality_trigger(
        self, triggers: dict[str, str], name: str
    ) -> None:
        """Triggers 5a/5b/5c: one per seismogram parameter. A conditional
        parameter nulls `iccs_cc` for the event only if the seismogram is
        selected; the others always do.
        """
        trigger = triggers[f"null_quality_on_seis_{name}_change"]
        null_iccs = {
            Reach.CONDITIONAL: _NULL_ICCS_IF_SELECTED,
            Reach.EVENT: _NULL_ICCS_FOR_EVENT,
        }[SEISMOGRAM_PARAMETER_SPECS[name].stack]

        assert _when_columns(trigger) == {name}
        assert " ".join(null_iccs.split()) in trigger


def test_constraint_helpers_detect_drift(tmp_path: Path) -> None:
    """Guards `_unique_constraints`/`_check_constraints`/`_indexes`
    themselves: each must report a difference when one database has a
    constraint/index the other doesn't, proving the corresponding parity
    test would actually catch that kind of drift - e.g. a future migration
    silently dropping `AimbatEvent`'s unique `time` constraint or
    `aimbat_note_exactly_one_parent`, which the schema comparisons this
    module used before (tables/columns/foreign keys/triggers only) would
    have missed entirely.
    """
    engine_with = create_engine(f"sqlite+pysqlite:///{tmp_path / 'with.db'}")
    engine_without = create_engine(f"sqlite+pysqlite:///{tmp_path / 'without.db'}")

    with engine_with.begin() as connection:
        connection.execute(
            text("CREATE TABLE t (x INTEGER, y INTEGER, UNIQUE (x), CHECK (y > 0))")
        )
        connection.execute(text("CREATE INDEX ix_t_y ON t (y)"))
    with engine_without.begin() as connection:
        connection.execute(text("CREATE TABLE t (x INTEGER, y INTEGER)"))

    assert _unique_constraints(engine_with, "t") != _unique_constraints(
        engine_without, "t"
    )
    assert _check_constraints(engine_with, "t") != _check_constraints(
        engine_without, "t"
    )
    assert _indexes(engine_with, "t") != _indexes(engine_without, "t")

    engine_with.dispose()
    engine_without.dispose()


class TestUpgradeProject:
    """`upgrade_project()` against AIMBAT's own migration chain."""

    def test_stamps_new_project_immediately(self, engine_from_file: Engine) -> None:
        """`create_project()` should stamp at head, not leave it un-versioned."""
        assert get_current_revision(engine_from_file) is None
        create_project(engine_from_file)
        assert get_current_revision(engine_from_file) is not None

    def test_upgrade_on_already_stamped_project_is_a_no_op(
        self, engine_from_file: Engine
    ) -> None:
        create_project(engine_from_file)
        revision_before = get_current_revision(engine_from_file)

        upgrade_project(engine_from_file)

        assert get_current_revision(engine_from_file) == revision_before

    def test_upgrade_rejects_unstamped_database_with_current_schema(
        self, engine_from_file: Engine
    ) -> None:
        """A database with no version history is refused even when its
        schema is the current one.
        """
        create_project(engine_from_file)
        with engine_from_file.begin() as connection:
            connection.exec_driver_sql("DROP TABLE alembic_version")

        with pytest.raises(SchemaMismatchError, match="predates the current"):
            upgrade_project(engine_from_file)

    def test_upgrade_backs_up_database_file_first(
        self, engine_from_file: Engine, db_path: Path
    ) -> None:
        """A file-backed database should be copied aside before `command.upgrade`
        runs, labelled with the revision it was backed up from.
        """
        create_project(engine_from_file)
        revision = get_current_revision(engine_from_file)

        upgrade_project(engine_from_file)

        backup_path = db_path.with_name(f"{db_path.name}.pre-{revision}.bak")
        assert backup_path.exists()
        assert backup_path.stat().st_size > 0

    def test_upgrade_never_overwrites_an_existing_backup(
        self, engine_from_file: Engine, db_path: Path
    ) -> None:
        """Retrying an upgrade must not clobber the backup from the first attempt.

        The revision alone doesn't identify a backup, so a second upgrade from
        the same revision has to land on a different name - otherwise the one
        intact copy is destroyed by the retry it exists to protect.
        """
        create_project(engine_from_file)
        revision = get_current_revision(engine_from_file)
        first = db_path.with_name(f"{db_path.name}.pre-{revision}.bak")

        upgrade_project(engine_from_file)
        assert first.exists()
        original_bytes = first.read_bytes()

        upgrade_project(engine_from_file)

        second = db_path.with_name(f"{db_path.name}.pre-{revision}.1.bak")
        assert second.exists()
        assert first.read_bytes() == original_bytes

    def test_upgrade_backup_is_self_contained_in_wal_mode(
        self, engine_from_file: Engine, db_path: Path
    ) -> None:
        """The backup file must stand on its own.

        In WAL mode the newest pages live in the `-wal` sidecar, so copying
        the database file alone captures a database missing its most recent
        writes - the schema the migration is about to change, among them.
        Checkpointing first folds them back in, which also makes the `-wal`
        copy unnecessary and the `-shm` copy (rebuildable shared memory)
        pointless.
        """
        with engine_from_file.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL")
        create_project(engine_from_file)
        revision = get_current_revision(engine_from_file)

        upgrade_project(engine_from_file)

        backup_path = db_path.with_name(f"{db_path.name}.pre-{revision}.bak")
        assert backup_path.exists()
        assert not backup_path.with_name(backup_path.name + "-wal").exists()
        assert not backup_path.with_name(backup_path.name + "-shm").exists()

        restored = create_engine(rf"sqlite+pysqlite:///{backup_path}")
        try:
            with restored.begin() as connection:
                table_names = inspect(connection).get_table_names()
        finally:
            restored.dispose()
        assert "aimbatevent" in table_names

    def test_upgrade_skips_backup_for_in_memory_database(self, engine: Engine) -> None:
        """An in-memory database has no file to back up and must not error."""
        upgrade_project(engine)  # already created + stamped by the `engine` fixture

    def test_downgrade_from_head_to_base_drops_all_tables(
        self, engine_from_file: Engine
    ) -> None:
        """Every migration's `downgrade()` should unwind cleanly, not just
        `upgrade()` step forward.
        """
        from alembic import command

        from aimbat.core._migrations import _alembic_config

        create_project(engine_from_file)
        config = _alembic_config(engine_from_file)

        command.downgrade(config, "base")

        with engine_from_file.begin() as connection:
            table_names = inspect(connection).get_table_names()
        assert not any(name.startswith("aimbat") for name in table_names)

    def test_upgrade_rejects_unstamped_database_with_unknown_schema(
        self, engine_from_file: Engine
    ) -> None:
        """A database with some schema but no version history must be
        rejected rather than silently stamped.
        """
        with engine_from_file.begin() as connection:
            connection.execute(text("CREATE TABLE aimbatevent (id TEXT)"))

        assert get_current_revision(engine_from_file) is None
        with pytest.raises(SchemaMismatchError):
            upgrade_project(engine_from_file)

    def test_upgrade_rejects_stamped_database_with_unrecognised_revision(
        self, engine_from_file: Engine
    ) -> None:
        """A database stamped at a revision this installation's migration
        scripts don't recognise (from before the current project format, a
        newer AIMBAT release, or a corrupted `alembic_version` value) must be
        rejected with a friendly error, not `command.upgrade()`'s raw "Can't
        locate revision" exception.
        """
        create_project(engine_from_file)
        with engine_from_file.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = 'not_a_real_revision'")
            )

        with pytest.raises(SchemaMismatchError, match="doesn't recognise"):
            upgrade_project(engine_from_file)


_FIRST_REVISION = """
revision = "aaa000000001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "t",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("x", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("t")
"""

_SECOND_REVISION = """
revision = "bbb000000002"
down_revision = "aaa000000001"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("t", sa.Column("y", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("t", "y")
"""


@pytest.fixture
def two_revision_migrations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None]:
    """Points `core._migrations` at a disposable, hand-written two-revision
    migration chain (unrelated to AIMBAT's real models), so an upgrade from
    an older revision can be tested while AIMBAT itself has only a baseline.
    """
    from aimbat.core import _migrations

    migrations_dir = tmp_path / "test_migrations"
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(parents=True)
    shutil.copy(
        Path(aimbat._migrations.__file__).parent / "env.py", migrations_dir / "env.py"
    )
    (versions_dir / "aaa000000001_first.py").write_text(_FIRST_REVISION)
    (versions_dir / "bbb000000002_second.py").write_text(_SECOND_REVISION)

    monkeypatch.setattr(_migrations, "_migrations_dir", lambda: migrations_dir)
    yield


class TestUpgradeAcrossRevisions:
    """`upgrade_project` on a database stamped at an older revision."""

    @pytest.fixture
    def old_engine(
        self, tmp_path: Path, two_revision_migrations: None
    ) -> Generator[Engine]:
        from alembic import command

        from aimbat.core._migrations import _alembic_config

        engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'old.db'}")
        command.upgrade(_alembic_config(engine), "aaa000000001")
        yield engine
        engine.dispose()

    def test_runs_the_pending_migrations(self, old_engine: Engine) -> None:
        assert get_current_revision(old_engine) == "aaa000000001"

        upgrade_project(old_engine)

        assert get_current_revision(old_engine) == get_head_revision() == "bbb000000002"
        columns = {col["name"] for col in inspect(old_engine).get_columns("t")}
        assert columns == {"id", "x", "y"}

    def test_backup_is_labelled_with_the_old_revision(
        self, old_engine: Engine, tmp_path: Path
    ) -> None:
        upgrade_project(old_engine)

        assert (tmp_path / "old.db.pre-aaa000000001.bak").exists()

    def test_staleness_warning_suggests_upgrade(self, old_engine: Engine) -> None:
        from aimbat.core import _migrations

        warning = _migrations._build_staleness_warning(get_current_revision(old_engine))

        assert warning is not None
        assert warning.upgradeable
        assert "run `aimbat db upgrade`" in str(warning)


class TestBuildStalenessWarning:
    """`_build_staleness_warning` for databases that cannot be upgraded.

    The upgradeable case is in `TestUpgradeAcrossRevisions`.
    """

    def test_up_to_date_gives_no_warning(self) -> None:
        from aimbat.core import _migrations

        assert _migrations._build_staleness_warning(get_head_revision()) is None

    def test_unrecognised_revision_does_not_suggest_upgrade(self) -> None:
        from aimbat.core import _migrations

        warning = _migrations._build_staleness_warning("not_a_real_revision")

        assert warning is not None
        assert not warning.upgradeable
        assert "doesn't recognise" in str(warning)
        assert "aimbat project create" in str(warning)
        assert "run `aimbat db upgrade`" not in str(warning)

    def test_no_version_history_does_not_suggest_upgrade(self) -> None:
        from aimbat.core import _migrations

        warning = _migrations._build_staleness_warning(None)

        assert warning is not None
        assert not warning.upgradeable
        assert "predates the current AIMBAT project format" in str(warning)
        assert "run `aimbat db upgrade`" not in str(warning)
