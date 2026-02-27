# GitHub Copilot Instructions for AIMBAT

## Build, Test, and Lint

Dependencies are managed with **uv**. All commands assume the virtualenv is active or are prefixed with `uv run`.

```bash
# Install all dependencies
make sync                          # uv sync --locked --all-extras

# Format and lint
make format                        # black .
make lint                          # black --check + ruff check .
uv run ruff check --fix .          # auto-fix ruff issues

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

Configuration: `pyproject.toml` (pytest, mypy, black, ruff, coverage). Tests run against Python 3.12–3.14 in CI via tox.

## Architecture

AIMBAT is a seismological tool for automated and interactive measurement of body-wave arrival times. It processes SAC-format seismograms and stores state in a SQLite database.

### Module Layout

```
src/aimbat/
├── app.py           # Cyclopts CLI root — registers all subcommands
├── _cli/             # CLI command definitions (thin layer, delegates to core/)
├── core/            # Business logic: ICCS/MCCC algorithms, event/seismogram ops
│   ├── _active_event.py  # Manages the single active event constraint
│   ├── _data.py          # SAC ingestion entry point
│   ├── _iccs.py          # ICCS alignment (wraps pysmo.tools.iccs)
│   └── _snapshot.py      # Parameter state capture for rollback/comparison
├── models/          # SQLModel ORM definitions (Events, Seismograms, Stations, etc.)
├── _types/          # Custom Pydantic types (PydanticTimestamp, enums for parameters)
├── io/              # File I/O — _base.py defines abstract base; sac.py implements SAC via pysmo
├── utils/           # Shared helpers (JSON→table, UUID truncation, styling, sample data)
├── _config.py       # Global Settings (pydantic-settings, env prefix AIMBAT_)
├── _lib/            # Internal mixins (EventParametersValidatorMixin)
├── _utils.py        # Top-level utility helpers
├── db.py            # SQLite engine singleton (foreign keys enforced via PRAGMA)
└── logger.py        # Loguru-based logging
```

### Data Flow

1. SAC files are ingested via `aimbat data add` → `core/_data.py` → `io/` → stored in SQLite
2. One event is set "active" at a time; all processing commands operate on the active event
3. ICCS (Iterative Cross-Correlation and Stack) aligns seismograms: `core/_iccs.py` wraps `pysmo.tools.iccs`
4. MCCC (Multi-Channel Cross-Correlation) refines arrival time picks: wraps `pysmo.tools.signal.mccc`
5. Snapshots (`core/_snapshot.py`) capture parameter state for rollback/comparison

### Key Models

- **AimbatEvent** — seismic event with `active` flag (only one active at a time, enforced by DB trigger)
- **AimbatSeismogram** — links to AimbatEvent + AimbatStation; stores `t0` (initial pick) and processing parameters
- **AimbatEventParameters** — per-event processing settings (window, bandpass, min_ccnorm)
- **AimbatSeismogramParameters** — per-seismogram flags (`select`, `flip`, `t1` pick)
- **SAPandasTimestamp / SAPandasTimedelta** in `models/_sqlalchemy.py` — custom SQLAlchemy type decorators storing pandas timestamps as UTC datetimes and timedeltas as nanosecond integers

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

### CLI Pattern

Each CLI module in `_cli/` creates a Cyclopts `App` instance and registers it with the root app in `app.py`. CLI functions are thin wrappers that open a `Session` from `aimbat.db.engine` and delegate to `core/` functions.

### Custom Types

- Use `PydanticTimestamp` / `PydanticTimedelta` (from `aimbat._types`) for pandas-compatible time fields in models
- Use `PydanticNegativeTimedelta` / `PydanticPositiveTimedelta` for constrained sign validation
- Use `SAPandasTimestamp` / `SAPandasTimedelta` (from `aimbat.models._sqlalchemy`) as the `sa_type` in SQLModel fields

## Code Style and Standards

### General Principles

- Write clean, readable, and maintainable code
- Write self-documenting code with clear variable and function names
- Suggest improvements to code style, efficiency, and readability in pull
  request reviews

### PEP 8 Compliance

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guide for all Python code
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 88 characters (Black default)
- Use blank lines to separate functions and classes
- Imports should be grouped: standard library, third-party, local

### Code Formatting

- All code must pass **Black** formatting
  - Target Python versions: 3.12, 3.13, 3.14
  - Line length: 88 characters
  - Run `black .` before committing

- All code must pass **Ruff** linting
  - Configuration in `pyproject.toml`
  - Run `ruff check .` before committing
  - Fix issues with `ruff check --fix .`

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
- Follow conventional commits format when appropriate
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

1. Run `black .` to format code
2. Run `ruff check --fix .` to check and fix linting issues
3. Run tests with `pytest`
4. Verify type hints with `mypy`
5. Check British English spelling
6. Ensure docstrings follow Google style
