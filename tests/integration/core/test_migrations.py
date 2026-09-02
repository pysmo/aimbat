"""Integration tests for Alembic-backed schema migrations.

Uses real file-based databases rather than `:memory:`, since Alembic's
`env.py` opens its own connection.
"""

import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlmodel import Session, select

import aimbat._migrations
from aimbat.core import (
    create_project,
    get_current_revision,
    get_head_revision,
    upgrade_project,
)
from aimbat.core._migrations import SchemaMismatchError
from aimbat.models import AimbatEvent, AimbatSeismogram, AimbatSnapshot


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
    def create_all_engine(self, tmp_path: Path) -> Generator[Engine, None, None]:
        engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'create_all.db'}")
        create_project(engine)
        yield engine
        engine.dispose()

    @pytest.fixture
    def migrated_engine(self, tmp_path: Path) -> Generator[Engine, None, None]:
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
    """Tests for the auto-verify-and-stamp behaviour of `upgrade_project()`."""

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

    def test_upgrade_stamps_legacy_database_matching_baseline(
        self, engine_from_file: Engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pre-Alembic database (schema created but never stamped) should
        be recognised and stamped automatically, not rejected.
        """
        from aimbat.core import _migrations

        # Simulate a database created before `create_project()` stamped at
        # head, by preventing the stamp step it would normally perform.
        monkeypatch.setattr(_migrations, "stamp_head", lambda engine: None)
        create_project(engine_from_file)
        assert get_current_revision(engine_from_file) is None

        monkeypatch.undo()
        upgrade_project(engine_from_file)

        assert get_current_revision(engine_from_file) is not None

    def test_upgrade_rejects_unstamped_database_with_unknown_schema(
        self, engine_from_file: Engine
    ) -> None:
        """A database with *some* schema that doesn't match any known
        revision must be rejected rather than silently stamped.
        """
        with engine_from_file.begin() as connection:
            connection.execute(text("CREATE TABLE aimbatevent (id TEXT)"))

        assert get_current_revision(engine_from_file) is None
        with pytest.raises(SchemaMismatchError):
            upgrade_project(engine_from_file)

    def test_upgrade_fails_clearly_on_pre_existing_duplicate_notes(
        self, engine_from_file: Engine
    ) -> None:
        """The per-parent-unique-index migration must name the offending
        parent rather than raising a bare "UNIQUE constraint failed" when the
        project already has two notes for the same event.
        """
        from alembic import command

        from aimbat.core._migrations import _alembic_config

        config = _alembic_config(engine_from_file)
        command.upgrade(config, "ca35a8b78a91")  # one revision before the index

        with engine_from_file.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO aimbatevent (id, time, latitude, longitude) "
                    "VALUES ('ev1', '2020-01-01 00:00:00', 0.0, 0.0)"
                )
            )
            for note_id in ("n1", "n2"):
                connection.execute(
                    text(
                        "INSERT INTO aimbatnote (id, content, event_id) "
                        f"VALUES ('{note_id}', 'dupe', 'ev1')"
                    )
                )

        with pytest.raises(
            RuntimeError, match="more than one row for the same event_id"
        ):
            command.upgrade(config, "c7ba9d07fa0a")

    def test_hash_split_renames_parameters_hash_and_adds_iccs_hash(
        self, engine_from_file: Engine
    ) -> None:
        """The column rename preserves the stored value; `iccs_hash` starts NULL."""
        from alembic import command

        from aimbat.core._migrations import _alembic_config

        config = _alembic_config(engine_from_file)
        command.upgrade(config, "c7ba9d07fa0a")  # one revision before the split

        with engine_from_file.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO aimbatevent (id, time, latitude, longitude) "
                    "VALUES ('ev1', '2020-01-01 00:00:00', 0.0, 0.0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatsnapshot (id, time, event_id, parameters_hash) "
                    "VALUES ('sn1', '2020-01-01 00:00:00', 'ev1', 'frozen-digest')"
                )
            )

        command.upgrade(config, "490f0a998ee3")

        with engine_from_file.begin() as connection:
            row = connection.execute(
                text("SELECT mccc_hash, iccs_hash FROM aimbatsnapshot WHERE id = 'sn1'")
            ).one()
        assert row.mccc_hash == "frozen-digest"
        assert row.iccs_hash is None

    def test_snapshot_durability_backfills_seismogram_id(
        self, engine_from_file: Engine
    ) -> None:
        """The new `seismogram_id` column is filled from the live parameter /
        quality row each snapshot record points at."""
        from alembic import command

        from aimbat.core._migrations import _alembic_config

        config = _alembic_config(engine_from_file)
        command.upgrade(config, "490f0a998ee3")  # one revision before durability

        with engine_from_file.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO aimbatevent (id, time, latitude, longitude) "
                    "VALUES ('ev1', '2020-01-01 00:00:00', 0.0, 0.0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatstation "
                    "(id, name, network, location, channel, latitude, longitude) "
                    "VALUES ('st1', 'AAK', 'II', '00', 'BHZ', 0.0, 0.0)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatseismogram "
                    "(id, begin_time, delta, t0, event_id, station_id) "
                    "VALUES ('se1', '2020-01-01 00:00:00', 20000000, "
                    "'2020-01-01 00:00:10', 'ev1', 'st1')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatseismogramparameters "
                    '(id, "select", flip, seismogram_id) '
                    "VALUES ('sp1', 1, 0, 'se1')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatseismogramquality (id, iccs_cc, seismogram_id) "
                    "VALUES ('sq1', 0.5, 'se1')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatsnapshot (id, time, event_id) "
                    "VALUES ('sn1', '2020-01-01 00:00:00', 'ev1')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatseismogramparameterssnapshot "
                    '(id, "select", flip, seismogram_parameters_id, snapshot_id) '
                    "VALUES ('pps1', 1, 0, 'sp1', 'sn1')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO aimbatseismogramqualitysnapshot "
                    "(id, iccs_cc, seismogram_quality_id, snapshot_id) "
                    "VALUES ('qqs1', 0.5, 'sq1', 'sn1')"
                )
            )

        command.upgrade(config, "d08f5f734f78")

        with engine_from_file.begin() as connection:
            pps = connection.execute(
                text(
                    "SELECT seismogram_id FROM aimbatseismogramparameterssnapshot "
                    "WHERE id = 'pps1'"
                )
            ).one()
            qqs = connection.execute(
                text(
                    "SELECT seismogram_id FROM aimbatseismogramqualitysnapshot "
                    "WHERE id = 'qqs1'"
                )
            ).one()
        assert pps.seismogram_id == "se1"
        assert qqs.seismogram_id == "se1"

    def test_upgrade_rejects_stamped_database_with_unrecognised_revision(
        self, engine_from_file: Engine
    ) -> None:
        """A database stamped at a revision this installation's migration
        scripts don't recognise at all (e.g. a different/newer AIMBAT
        release, or a corrupted `alembic_version` value) must be rejected
        with a friendly error, not `command.upgrade()`'s raw "Can't locate
        revision" exception.
        """
        create_project(engine_from_file)
        with engine_from_file.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = 'not_a_real_revision'")
            )

        with pytest.raises(SchemaMismatchError, match="doesn't recognise"):
            upgrade_project(engine_from_file)


class TestOldDatabaseRegressionFixture:
    """Regression test against a real pre-Alembic database, not a freshly
    generated one.

    `tests/assets/pre_alembic_project.db` was built by running
    `create_project()`/`add_data_to_project()`/`create_snapshot()` from the
    last commit before Alembic was introduced (`7c1acd0`), against a small
    ICCS dataset - one event, three seismograms, one snapshot. Every other
    test in this module builds its database fresh at the current schema;
    this is the one that represents what `aimbat db upgrade` actually has to
    handle for an existing test user's project, and would have caught a
    regression that a synthetic empty database wouldn't.
    """

    @pytest.fixture
    def old_project_engine(self, tmp_path: Path) -> Generator[Engine, None, None]:
        db_path = tmp_path / "pre_alembic_project.db"
        shutil.copy(
            Path(__file__).parents[2] / "assets" / "pre_alembic_project.db",
            db_path,
        )
        engine = create_engine(f"sqlite+pysqlite:///{db_path}")
        yield engine
        engine.dispose()

    def test_upgrade_brings_legacy_database_to_head(
        self, old_project_engine: Engine
    ) -> None:
        assert get_current_revision(old_project_engine) is None

        upgrade_project(old_project_engine)

        assert get_current_revision(old_project_engine) == get_head_revision()

    def test_upgrade_preserves_existing_rows(self, old_project_engine: Engine) -> None:
        upgrade_project(old_project_engine)

        with Session(old_project_engine) as session:
            events = session.exec(select(AimbatEvent)).all()
            seismograms = session.exec(select(AimbatSeismogram)).all()
            snapshots = session.exec(select(AimbatSnapshot)).all()

        assert len(events) == 1
        assert len(seismograms) == 3
        assert len(snapshots) == 1


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
) -> Generator[None, None, None]:
    """Points `core._migrations` at a disposable, hand-written two-revision
    migration chain (unrelated to AIMBAT's real models), so multi-revision
    matching can be tested against a genuine "older, non-head revision"
    without needing a second real AIMBAT migration to exist yet.
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


def _build_database_matching_first_revision_only(db_path: Path) -> Engine:
    """Builds a database matching `aaa000000001` exactly, then un-stamps it -
    simulating a legacy database that predates the second revision, created
    before Alembic tracked it (rather than one that was actually migrated
    and then had its `alembic_version` row deleted).

    Built by running the *real* first migration rather than hand-written raw
    SQL: a raw `CREATE TABLE t (id INTEGER PRIMARY KEY, ...)` reflects with
    `nullable=True` on the primary key column (a SQLite reflection quirk),
    while `op.create_table(..., sa.Column("id", ..., primary_key=True))`
    renders it explicitly `NOT NULL` - a spurious mismatch that has nothing
    to do with the logic under test. Going through the real migration avoids
    it, and is more representative of how a real legacy database would have
    been built in the first place.
    """
    from alembic import command

    from aimbat.core._migrations import _alembic_config

    engine = create_engine(f"sqlite+pysqlite:///{db_path}")
    command.upgrade(_alembic_config(engine), "aaa000000001")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE alembic_version")
    return engine


class TestFindMatchingRevisionAcrossMultipleRevisions:
    """`_find_matching_revision`/`upgrade_project` must correctly stamp a
    database at an *older* known revision, not just head or nothing - the
    scenario a names-only/head-only check gets wrong: a database that
    skipped an intermediate AIMBAT release, matching an older revision
    exactly. Only one real AIMBAT migration exists today, so this uses a
    disposable synthetic two-revision chain (`two_revision_migrations`) to
    actually exercise the multi-revision path.
    """

    def test_matches_older_revision_not_just_head(
        self, tmp_path: Path, two_revision_migrations: None
    ) -> None:
        from aimbat.core._migrations import _find_matching_revision

        engine = _build_database_matching_first_revision_only(tmp_path / "old.db")

        assert _find_matching_revision(engine) == "aaa000000001"
        engine.dispose()

    def test_upgrade_project_stamps_at_matched_older_revision_then_completes(
        self, tmp_path: Path, two_revision_migrations: None
    ) -> None:
        """The full `upgrade_project()` path: stamp at the matched older
        revision, then apply the remaining migrations on top - not reject
        outright just because the live schema doesn't match head.
        """
        engine = _build_database_matching_first_revision_only(tmp_path / "old.db")

        assert get_current_revision(engine) is None
        upgrade_project(engine)

        assert get_current_revision(engine) == "bbb000000002"
        columns = {col["name"] for col in inspect(engine).get_columns("t")}
        assert columns == {"id", "x", "y"}  # the second migration's column applied
        engine.dispose()


class TestBuildStalenessWarning:
    """Tests for `_build_staleness_warning`'s three-way classification:
    up to date, genuinely behind a *known* revision, or stamped at a
    revision this installation doesn't recognise at all. The last case
    can't be constructed with real data while only one migration exists
    (any non-head, non-`None` value is definitionally unrecognised today),
    so the "genuinely behind" case is simulated by monkeypatching the set
    of known ancestors.
    """

    def test_unrecognised_revision_does_not_suggest_upgrade(self) -> None:
        """The message must not tell the user to run `aimbat db upgrade`
        for a revision that command can't actually resolve.
        """
        from aimbat.core import _migrations

        warning = _migrations._build_staleness_warning("not_a_real_revision")

        assert warning is not None
        assert "doesn't recognise" in str(warning)
        assert "run `aimbat db upgrade`" not in str(warning)

    def test_known_ancestor_suggests_upgrade(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A revision that genuinely is a known ancestor of head must still
        get the normal "run `aimbat db upgrade`" advice.
        """
        from aimbat.core import _migrations

        monkeypatch.setattr(
            _migrations,
            "_known_ancestors_of_head",
            lambda: {"some_old_revision", _migrations.get_head_revision()},
        )

        warning = _migrations._build_staleness_warning("some_old_revision")

        assert warning is not None
        assert "out of date" in str(warning)
        assert "run `aimbat db upgrade`" in str(warning)

    def test_none_still_means_legacy_predates_versioning(self) -> None:
        """`None` (never stamped at all) keeps its own distinct message,
        unaffected by the unrecognised-revision check.
        """
        from aimbat.core import _migrations

        warning = _migrations._build_staleness_warning(None)

        assert warning is not None
        assert "predates AIMBAT's schema versioning" in str(warning)
