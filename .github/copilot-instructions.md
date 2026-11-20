# GitHub Copilot Instructions for AIMBAT

## Build, Test, and Lint

Dependencies are managed with **uv**. All commands assume the virtualenv is
active or are prefixed with `uv run`.

```bash
# Install all dependencies
make sync                          # uv sync --locked --all-extras

# Format and lint
make format                        # ruff check --fix + ruff format
make lint                          # ruff check + ruff format --check
uv run ruff check --fix .          # auto-fix ruff issues
uv run ruff format .               # format code (replaces black)

# Type checking
make mypy                          # uv run pytest --mypy -m mypy src tests

# Run the tests in parallel (includes mypy + matplotlib comparison)
make tests                         # skips tests marked slow
make tests-full                    # all tests, including slow functional ones

# Run a single test file or test
uv run pytest tests/unit/test_foo.py
uv run pytest tests/unit/test_foo.py::test_specific_function

# Regenerate matplotlib baseline images (then manually move to test directories)
make test-figs
```

Configuration: `pyproject.toml` (pytest, mypy, ruff, coverage). Tests run
against Python 3.13–3.15 in CI via tox.

## Design goals

AIMBAT is not just a tool for producing delay times for tomographic inversions.
The quality metrics it accumulates during alignment — ICCS cross-correlation
coefficients, MCCC timing errors, CC means and standard deviations, and global
RMSE — are scientifically interesting in their own right. Analysis of these
metrics after alignment is a primary use case and should be treated as a
first-class output, not an afterthought. The Python API is the primary interface
for this kind of post-processing analysis; the CLI and TUI are workflow tools
for interactive alignment, not the end of the pipeline.

## Architecture

AIMBAT is a seismological tool for automated and interactive measurement of
body-wave arrival times. It processes SAC-format seismograms and stores state in
a SQLite database.

### Module Layout

```
src/aimbat/
├── app.py           # Cyclopts CLI root, registers all subcommands
├── _cli/            # CLI commands (thin layer, writes go through actions/)
├── _tui/            # Textual TUI application
├── actions/         # One function per user action: own session, one commit
├── core/            # Building blocks: flush only, the caller commits
│   ├── _data.py          # Data ingestion entry point
│   ├── _iccs.py          # ICCS/MCCC alignment (wraps pysmo.tools.iccs), BoundICCS cache
│   ├── _snapshot.py      # Parameter and quality capture for rollback/comparison
│   └── _validity.py      # Parameter digests that decide whether quality values are valid
├── models/          # SQLModel ORM definitions (events, seismograms, stations, etc.)
│   ├── _models.py        # All table models
│   ├── _parameters.py    # Parameter bases and ParameterSpec (what each parameter affects)
│   ├── _quality.py       # AimbatPhaseQualityBase, AimbatSeismogramQualityBase
│   └── _readers.py       # Read models for display and export
├── plot/            # Matplotlib plots and interactive tools
├── types/           # Custom Pydantic and SQLAlchemy types
├── io/              # Data source I/O: _base.py defines the interface; sac.py, mseed.py implement it
├── utils/           # Shared helpers (JSON→table, UUID truncation, styling, sample data)
├── _migrations/     # Alembic migrations (a single baseline before v2)
├── _config.py       # Global Settings (pydantic-settings, env prefix AIMBAT_)
├── db.py            # SQLite engine singleton (foreign keys enforced via PRAGMA)
└── logger.py        # Loguru-based logging
```

### Data Flow

1. Data are ingested via `aimbat data add` → `actions` → `core/_data.py` → `io/`
    → stored in SQLite
2. Commands that act on an event take `--event-id`, defaulting to the
    `DEFAULT_EVENT_ID` environment variable; nothing about the selection is
    stored in the project. The CLI resolves the event's phase
    (`resolve_phase_option`) and passes its ID on: `core` and `actions`
    functions that process data take the phase ID
3. ICCS (Iterative Cross-Correlation and Stack) aligns the seismograms of a
    phase: `core/_iccs.py` wraps `pysmo.tools.iccs` and caches one `BoundICCS`
    per phase; ICCS CC values are written to `AimbatSeismogramQuality` whenever
    an instance is built
4. MCCC (Multi-Channel Cross-Correlation) refines arrival time picks; results
    are written to `AimbatPhaseQuality` and `AimbatSeismogramQuality`
5. Snapshots (`core/_snapshot.py`) capture a point-in-time copy of a phase's
    parameters **and** quality metrics

### Transactions

- `core` functions flush but never commit. A caller can combine several of them
    in one transaction and commit once.
- `aimbat.actions` is the write path for the CLI, shell, TUI and plot tools.
    Each action opens a session, validates its input, commits once and evicts
    the caches its commit made stale. List-taking actions are all or nothing.
- Reads may call `core` directly. A read that builds an ICCS instance writes CC
    values, so it goes through `actions.prepare_iccs`.

### Key Models

Parameters and quality follow the same three-layer pattern:

| Layer                                                     | Parameters                                                             | Quality                                                          |
| --------------------------------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Base (fields only)                                        | `AimbatPhaseParametersBase` / `AimbatSeismogramParametersBase`         | `AimbatPhaseQualityBase` / `AimbatSeismogramQualityBase`         |
| Live table (one row per phase / per seismogram and phase) | `AimbatPhaseParameters` / `AimbatSeismogramParameters`                 | `AimbatPhaseQuality` / `AimbatSeismogramQuality`                 |
| Snapshot table (point-in-time copy)                       | `AimbatPhaseParametersSnapshot` / `AimbatSeismogramParametersSnapshot` | `AimbatPhaseQualitySnapshot` / `AimbatSeismogramQualitySnapshot` |

- **AimbatEvent**: seismic event; its phases hang off it
- **AimbatPhase**: the unit of processing, one per seismic phase of an event;
    its parameters, quality and snapshots hang off it. Core and action functions
    that process data take a phase ID; `resolve_phase` finds the phase of an
    event
- **AimbatSeismogram**: links to AimbatEvent + AimbatStation; delegates `data`
    to the data source
- **AimbatSeismogramParameters**: the row of a seismogram in a phase:
    `refined_pick`, `flip`, `select`, and its initial pick through `AimbatPick`
- **AimbatSeismogramQuality**: live quality of a row: `iccs_cc` (written
    whenever an ICCS instance is built), `mccc_error`, `mccc_cc_mean`,
    `mccc_cc_std` (written after MCCC runs)
- **AimbatPhaseQuality**: live quality: `mccc_rmse` (written after MCCC runs)
- **AimbatSnapshot**: point-in-time container for one phase; holds parameter
    snapshots for its rows and, when available, quality snapshots
- **SAPandasTimestamp / SAPandasTimedelta** in `types/_sqlalchemy.py`: custom
    SQLAlchemy type decorators storing pandas timestamps as UTC datetimes and
    timedeltas as nanosecond integers

### Quality validity

- Each parameter declares what it affects through a `ParameterSpec` in
    `models/_parameters.py` (stack, MCCC, or bookkeeping).
- Quality values are stored with a fingerprint of the parameters they were
    computed from: `AimbatSeismogramQuality.iccs_fingerprint` and
    `AimbatPhaseQuality.mccc_fingerprint`.
- `core/_validity.py` computes the current digests. A stored value counts only
    while its fingerprint matches; a `Validity` object, built once per command,
    is passed to every reader of quality values.
- Nothing nulls stale values. There are no database triggers; a parameter change
    simply makes the old fingerprint stop matching.
- Snapshots store quality values without fingerprints. A rollback restores
    parameters first, then restores quality values from a snapshot whose digests
    match (`resync_quality`) and stamps them with the current digests.
- MCCC membership is stored explicitly (`AimbatPhaseQuality.mccc_members`), not
    inferred from `select`, since MCCC can be run with `--all`.

### Configuration

Settings live in `_config.py` as a `pydantic-settings` class. All settings can
be overridden via environment variables prefixed with `AIMBAT_` (e.g.
`AIMBAT_LOG_LEVEL=DEBUG`) or a `.env` file. The default project file is
`aimbat.db` in the current directory.

## Key Conventions

### Testing

- **Each test gets a fresh in-memory SQLite database** via the `engine` fixture
    in `tests/conftest.py`; never share state between tests
- **UUID generation is seeded** (`random.Random(42)`) in tests via `mock_uuid4`
    autouse fixture — do not rely on random UUIDs in assertions
- Override a setting with
    `monkeypatch.setattr(aimbat.settings, "<name>", value)`
- `loaded_engine` / `loaded_session` give a project with the multi-event test
    data already ingested (built once per worker and copied)
- `multi_phase_engine` / `multi_phase_engine_from_file` give a project with one
    event and two phases, P and pP, from labelled picks; one station has no pP
    pick
- Test assets (SAC files) live in `tests/assets/`; use `tmp_path_factory` copies
    to avoid mutating them
- Mirror `src/aimbat/` directory structure under `tests/` (e.g.
    `tests/unit/core/`, `tests/unit/models/`)
- Matplotlib comparison tests use `--mpl` flag; baseline images live in
    `baseline/`
- Tests run in parallel with pytest-xdist; subprocess-based functional tests are
    marked `slow`
- Behaviour is tested against `aimbat.actions` (`tests/integration/actions/`);
    CLI tests cover argument parsing and wiring

### CLI Pattern

Each CLI module in `_cli/` creates a Cyclopts `App` instance and registers it
with the root app in `app.py`. Commands that write call one `aimbat.actions`
function. Commands that only read may open a `Session` from `aimbat.db.engine`
and call `core/` directly. Interfaces never commit.

### Migrations

`_migrations/` holds a single Alembic baseline, regenerated rather than migrated
until v2. `tests/integration/core/test_migrations.py` compares tables, columns,
foreign keys, unique and check constraints, and indexes between
`create_project()` and the migration chain. Autogenerate sees a column rename as
a drop and an add; replace it with `op.alter_column`, and check for the same
column on the matching `*Snapshot` table.

### Custom Types

- Use `PydanticTimestamp` / `PydanticTimedelta` (from `aimbat.types`) for
    pandas-compatible time fields in models
- Use `PydanticNegativeTimedelta` / `PydanticPositiveTimedelta` for constrained
    sign validation
- Use `SAPandasTimestamp` / `SAPandasTimedelta` as the `sa_type` in SQLModel
    fields

## Code Style and Standards

### General Principles

- Write clean, readable, and maintainable code
- Write self-documenting code with clear variable and function names
- Suggest improvements to code style, efficiency, and readability in pull
    request reviews

### PEP 8 Compliance

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide for all Python
    code
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 88 characters
- Use blank lines to separate functions and classes
- Imports should be grouped: standard library, third-party, local

### Code Formatting

- All code must pass **Ruff** formatting and linting
  - Target Python versions: 3.13, 3.14, 3.15
  - Line length: 88 characters
  - Run `ruff format .` before committing (replaces black)
  - Run `ruff check --fix .` to auto-fix linting issues

### Language

- Use **British English** spelling in all:
  - Comments
  - Docstrings
  - Variable names
  - Documentation
  - Error messages
- Examples:
  - `colour` not `color`
  - `normalise` not `normalize`
  - `initialise` not `initialize`
  - `behaviour` not `behavior`
  - `centre` not `center`

### Documentation Style

#### Docstrings

- Use **Google Style** docstrings for all public functions, classes, and methods

- Don't add the args and return types in the docstring if they are already
    specified in the type hints.

- Format:

    ```python
    def function_name(param1: type1, param2: type2) -> return_type:
        """Brief one-line description.

        Longer description if needed, explaining the purpose and behaviour
        of the function in more detail.

        Args:
            param1: Description of param1.
            param2: Description of param2.
                Multi-line descriptions should be indented.

        Returns:
            Description of the return value.

        Raises:
            ErrorType: Description of when this error is raised.

        Examples:
            >>> function_name(value1, value2)
            expected_output
        """
    ```

#### Type Hints

- Use type hints for all function parameters and return values
- Use modern Python type syntax (Python 3.13+):
  - `list[str]` not `List[str]`
  - `dict[str, int]` not `Dict[str, int]`
  - `type1 | type2` not `Union[type1, type2]`
  - `type | None` not `Optional[type]`

### Testing

- Write tests for all new functionality
- Use pytest framework
- Tests should be in the `tests/` directory
- Use descriptive test names: `test_function_does_expected_behaviour`
- Try to mirror the directory structure of `src/aimbat/` in `tests/`

### Commit Messages

- Use clear, descriptive commit messages
- Follow conventional commits format
- Use British English spelling

## Review Priorities

- Take the above Code Style and Standards into account when reviewing pull
    requests
- Suggest improvements to code style, efficiency, documentation, and testing
- Suggest improvements to variable names, function names, and overall code
    readability
- Suggest newer syntax features where appropriate
- Check spelling
- Check if docstrings in existing code follow Google style and suggest
    improvements if needed

## Project-Specific Guidelines

### Seismology Domain

- Follow seismological conventions for variable names
- Use proper units and document them
- Maintain scientific accuracy in all calculations

### Dependencies

- Minimum Python version: 3.13, maximum 3.15
- Core dependencies: pysmo, sqlmodel, numpy, scipy, matplotlib
- Keep dependencies up to date

### File Organisation

- Source code in `src/aimbat/`
- Tests in `tests/`
- Documentation in `docs/`
- Use appropriate module structure

## Before Committing

1. Run `ruff format .` to format code
2. Run `ruff check --fix .` to check and fix linting issues
3. Run tests with `make tests` (includes mypy + pytest)
4. Check British English spelling
5. Ensure docstrings follow Google style
