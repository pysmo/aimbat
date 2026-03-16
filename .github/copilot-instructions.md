# GitHub Copilot Instructions for AIMBAT

## Build, Test, and Lint

Dependencies are managed with **uv**. All commands assume the virtualenv is active or are prefixed with `uv run`.

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

# Run all tests (includes mypy + matplotlib comparison)
make tests                         # pytest --cov --mpl + mypy

# Run a single test file or test
uv run pytest tests/unit/test_foo.py
uv run pytest tests/unit/test_foo.py::test_specific_function

# Regenerate matplotlib baseline images (then manually move to test directories)
make test-figs
```

Configuration: `pyproject.toml` (pytest, mypy, ruff, coverage). Tests run against Python 3.12–3.14 in CI via tox.

## Design goals

AIMBAT is not just a tool for producing delay times for tomographic inversions. The quality metrics it accumulates during alignment — ICCS cross-correlation coefficients, MCCC timing errors, CC means and standard deviations, and global RMSE — are scientifically interesting in their own right. Analysis of these metrics after alignment is a primary use case and should be treated as a first-class output, not an afterthought. The Python API is the primary interface for this kind of post-processing analysis; the CLI and TUI are workflow tools for interactive alignment, not the end of the pipeline.

## Architecture

AIMBAT is a seismological tool for automated and interactive measurement of body-wave arrival times. It processes SAC-format seismograms and stores state in a SQLite database.

### Module Layout

```
src/aimbat/
├── app.py           # Cyclopts CLI root — registers all subcommands
├── _cli/             # CLI command definitions (thin layer, delegates to core/)
├── core/            # Business logic: ICCS/MCCC algorithms, event/seismogram ops
│   ├── _data.py          # SAC ingestion entry point
│   ├── _iccs.py          # ICCS/MCCC alignment (wraps pysmo.tools.iccs)
│   ├── _snapshot.py      # Parameter and quality state capture for rollback/comparison
│   └── _views.py         # Quality retrieval and aggregated display data
├── models/          # SQLModel ORM definitions (Events, Seismograms, Stations, etc.)
│   ├── _models.py        # All table models
│   ├── _parameters.py    # AimbatEventParametersBase, AimbatSeismogramParametersBase
│   └── _quality.py       # AimbatEventQualityBase, AimbatSeismogramQualityBase
├── _tui/            # Textual TUI application
├── _types/          # Custom Pydantic types (PydanticTimestamp, enums for parameters)
├── io/              # File I/O — _base.py defines abstract base; sac.py implements SAC via pysmo
├── utils/           # Shared helpers (JSON→table, UUID truncation, styling, sample data)
├── _config.py       # Global Settings (pydantic-settings, env prefix AIMBAT_)
├── db.py            # SQLite engine singleton (foreign keys enforced via PRAGMA)
└── logger.py        # Loguru-based logging
```

### Data Flow

1. SAC files are ingested via `aimbat data add` → `core/_data.py` → `io/` → stored in SQLite
2. One event is set "active" at a time; all processing commands operate on the active event
3. ICCS (Iterative Cross-Correlation and Stack) aligns seismograms: `core/_iccs.py` wraps `pysmo.tools.iccs`; ICCS CC values are written to `AimbatSeismogramQuality` after each build
4. MCCC (Multi-Channel Cross-Correlation) refines arrival time picks; results are written to `AimbatEventQuality` and `AimbatSeismogramQuality`
5. Snapshots (`core/_snapshot.py`) capture a point-in-time copy of parameters **and** quality metrics

### Key Models

Parameters and quality follow the same three-layer pattern:

| Layer | Parameters | Quality |
|-------|-----------|---------|
| Base (fields only) | `AimbatEventParametersBase` / `AimbatSeismogramParametersBase` | `AimbatEventQualityBase` / `AimbatSeismogramQualityBase` |
| Live table (one row per event/seismogram) | `AimbatEventParameters` / `AimbatSeismogramParameters` | `AimbatEventQuality` / `AimbatSeismogramQuality` |
| Snapshot table (point-in-time copy) | `AimbatEventParametersSnapshot` / `AimbatSeismogramParametersSnapshot` | `AimbatEventQualitySnapshot` / `AimbatSeismogramQualitySnapshot` |

- **AimbatEvent** — seismic event with `is_default` flag (only one default at a time, enforced by DB trigger)
- **AimbatSeismogram** — links to AimbatEvent + AimbatStation; stores `t0` (initial pick); delegates `data` to the datasource
- **AimbatSeismogramQuality** — live quality: `iccs_cc` (written on every ICCS build), `mccc_error`, `mccc_cc_mean`, `mccc_cc_std` (written after MCCC runs, cleared when parameters change)
- **AimbatEventQuality** — live quality: `mccc_rmse` (written after MCCC runs)
- **AimbatSnapshot** — point-in-time container; holds parameter snapshots for all seismograms and, when available, quality snapshots
- **SAPandasTimestamp / SAPandasTimedelta** in `_types/_sqlalchemy.py` — custom SQLAlchemy type decorators storing pandas timestamps as UTC datetimes and timedeltas as nanosecond integers

### Quality lifecycle

- `AimbatSeismogramQuality.iccs_cc` is set whenever `create_iccs_instance` builds a fresh `BoundICCS`
- MCCC fields are set by `run_mccc` via `_write_mccc_quality`; cleared by `clear_mccc_quality` when parameters change (detected via `compute_parameters_hash`)
- `create_snapshot` reads the live quality tables; only seismograms with at least one non-None quality field get a quality snapshot record
- View functions (`get_quality_seismogram`, `get_quality_event`) read from the **most recent snapshot that has an event-level quality record** (i.e. the most recent snapshot taken after an MCCC run)
- Live quality fields are **automatically nulled by SQLite triggers** (triggers 5–7c in `core/_project.py`) when data-affecting parameters change — no application-layer code is needed for this
- MCCC inclusion is inferred from **live stats**, not `select`: a seismogram is considered to have been in the last MCCC run if and only if its `mccc_cc_mean IS NOT NULL`. This matters because MCCC can be run with `--all`, in which case deselected seismograms are also included.

#### Trigger nulling rules (triggers 5–7c)

| Trigger | Fires when | `iccs_cc` nulled | MCCC fields nulled | `mccc_rmse` nulled |
|---------|-----------|-----------------|-------------------|-------------------|
| 5 | `window_pre/post`, `ramp_width`, or `bandpass_*` changes on event | All seismograms | All seismograms | Yes |
| 6 | `mccc_damp` or `mccc_min_cc` changes on event | — | All seismograms | Yes |
| 7a | `flip` on a **selected** seismogram | All seismograms | All, if live MCCC stats | If live MCCC stats |
| 7a | `flip` on a **deselected** seismogram | That seismogram only | All, if live MCCC stats | If live MCCC stats |
| 7b | `t1` on a **selected** seismogram | All seismograms | All, if live MCCC stats | If live MCCC stats |
| 7b | `t1` on a **deselected** seismogram | That seismogram only | All, if live MCCC stats | If live MCCC stats |
| 7c | `select` changes (either direction) | All seismograms | All, if live MCCC stats | If live MCCC stats |

> **TODO**: Triggers 5–7c are SQLite-specific. If a second database backend is added, they will need porting:
> - Replace `IS NOT` with `IS DISTINCT FROM` (standard SQL, NULL-safe)
> - Replace `CREATE TRIGGER IF NOT EXISTS` with `CREATE OR REPLACE TRIGGER` (PostgreSQL syntax)
> - Replace SQLite date functions (`datetime('now')`, `strftime(...)`) with the target dialect's equivalents

> **TODO**: ICCS validation for `t1` (e.g., ensuring the pick is within seismogram bounds) is not currently performed when it is set directly via `set_seismogram_parameter`. This should be refactored to use a model-level validator and `ValidationContext`, similar to the implementation for event parameters.

### Configuration

Settings live in `_config.py` as a `pydantic-settings` class. All settings can be overridden via environment variables prefixed with `AIMBAT_` (e.g. `AIMBAT_LOG_LEVEL=DEBUG`) or a `.env` file. The default project file is `aimbat.db` in the current directory.

## Key Conventions

### Testing

- **Each test gets a fresh in-memory SQLite database** via the `engine` fixture in `tests/conftest.py`; never share state between tests
- **UUID generation is seeded** (`random.Random(42)`) in tests via `mock_uuid4` autouse fixture — do not rely on random UUIDs in assertions
- **`patch_settings` fixture** resets all settings to defaults before each test; use `@pytest.mark.parametrize` with `indirect=["patch_settings"]` to override specific settings
- Test assets (SAC files) live in `tests/assets/`; use `tmp_path_factory` copies to avoid mutating them
- Mirror `src/aimbat/` directory structure under `tests/` (e.g. `tests/unit/core/`, `tests/unit/models/`)
- Matplotlib comparison tests use `--mpl` flag; baseline images live in `baseline/`
- To simulate an MCCC run in tests, write directly to `AimbatEventQuality` / `AimbatSeismogramQuality`, call `session.refresh(event)`, then `create_snapshot` — do not mock `BoundICCS`

### CLI Pattern

Each CLI module in `_cli/` creates a Cyclopts `App` instance and registers it with the root app in `app.py`. CLI functions are thin wrappers that open a `Session` from `aimbat.db.engine` and delegate to `core/` functions.

### Custom Types

- Use `PydanticTimestamp` / `PydanticTimedelta` (from `aimbat._types`) for pandas-compatible time fields in models
- Use `PydanticNegativeTimedelta` / `PydanticPositiveTimedelta` for constrained sign validation
- Use `SAPandasTimestamp` / `SAPandasTimedelta` as the `sa_type` in SQLModel fields

## Code Style and Standards

### General Principles

- Write clean, readable, and maintainable code
- Write self-documenting code with clear variable and function names
- Suggest improvements to code style, efficiency, and readability in pull
  request reviews

### PEP 8 Compliance

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide for all Python code
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 88 characters
- Use blank lines to separate functions and classes
- Imports should be grouped: standard library, third-party, local

### Code Formatting

- All code must pass **Ruff** formatting and linting
  - Target Python versions: 3.12, 3.13, 3.14
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
- Don't add the args and return types in the docstring if they are already specified in the type hints.
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
- Use modern Python type syntax (Python 3.12+):
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

- Take the above Code Style and Standards into account when reviewing pull requests
- Suggest improvements to code style, efficiency, documentation, and testing
- Suggest improvements to variable names, function names, and overall code readability
- Suggest newer syntax features where appropriate
- Check spelling
- Check if docstrings in existing code follow Google style and suggest improvements if needed

## Project-Specific Guidelines

### Seismology Domain

- Follow seismological conventions for variable names
- Use proper units and document them
- Maintain scientific accuracy in all calculations

### Dependencies

- Minimum Python version: 3.12
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
