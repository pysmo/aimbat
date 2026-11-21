# Testing

The general expectations for tests are described in pysmo's
[Code standards](https://docs.pysmo.org/development/standards/#tests). This page
covers the layout and fixtures of the AIMBAT test suite.

## Layout

| Directory            | Contents                                                          |
| :------------------- | :---------------------------------------------------------------- |
| `tests/unit/`        | Tests of single functions and classes, mostly without a database. |
| `tests/integration/` | Tests against a project database, mostly of `core` and `actions`. |
| `tests/functional/`  | Tests of the CLI, the shell and the TUI as a whole.               |
| `tests/testsupport/` | Helpers shared between test modules.                              |

Within `unit/` and `integration/`, the directories mirror the layout of
`src/aimbat/`, so the tests of `aimbat.core._snapshot` are found in
`tests/integration/core/test_snapshots.py`. The tests of the shared helpers
in `tests/testsupport/` are in `tests/unit/testsupport/`.

Most rules of an operation are tested against its `core` function.
`tests/integration/actions/` covers what an action adds: one transaction per
call, all-or-nothing handling of ID lists, and results that remain usable after
the session closes. CLI tests cover argument parsing and the wiring to the
action or read behind each command, not the behaviour itself.

## Fixtures

The shared fixtures are defined in `tests/conftest.py`, and
`uv run pytest --fixtures` lists them with their descriptions. The project
fixtures come in a few families:

- `engine` provides a new, empty project in an in-memory database.
- The `loaded_*` fixtures provide a project with the multi-event test data
    added.
- The `multi_phase_*` fixtures provide a project with one event and two phases,
    P and pP, added from labelled picks. One station has no pP pick.
- Every project fixture other than `engine` also installs its project as
    `aimbat.db.engine`, so that actions and CLI commands use it.
    `patched_engine` is `engine` installed in this way.
- The `*_from_file` variants keep the project in a temporary file, for code that
    opens sessions from other threads, such as TUI workers.

Every test receives its own database. The loaded fixtures do not repeat the
ingestion for each test. The data are added once per worker process, and each
test receives a copy of the resulting database.

The test data come from [testkit](https://github.com/pysmo/testkit), which pysmo
and AIMBAT share. Tests work on temporary copies of the files, never on the
originals.

Some fixtures in `conftest.py` apply to every test automatically. Among them,
UUIDs come from a fixed sequence, so IDs are the same on every run, the caches
are cleared after each test, and no plot window opens.

## Shared helpers

The test directories are not packages, so one test module cannot import from
another. Helpers needed by more than one module live in the `tests/testsupport/`
package instead. `testsupport.cli` runs commands and reads their output,
`testsupport.project` builds and reads project state, and `testsupport.sources`
holds the contents of data sources written by tests. Project functions that
take a session and write flush it and leave the commit to the test. Those that
take an engine open their own session and commit if they write.

## Rules for robust tests

Line endings, console encodings, box drawing and process scheduling differ
between Linux, macOS and Windows, and the tests run on all three. A test that
passes on one platform and fails on another usually breaks one of these rules:

1. Behaviour is checked through state: dump commands, actions or the database.
    Printed text is matched only where the text itself is under test, such as an
    error message, a status line or help. Text that may be drawn in a panel or
    wrapped across lines is compared after `testsupport.cli.error_text`, which
    removes panel borders and joins wrapped lines.
2. An absence is asserted against state. A `not in` check on printed output also
    passes when the output is wrong or appears elsewhere.
3. Output from different writers has no order. In a shell subprocess, the
    shell's own lines (status and errors) and the output of each command come
    from different consoles and may interleave. Tests match the shell's own
    lines by content and read the results of commands with
    `testsupport.cli.project_dump`.
4. CLI commands that contain paths are passed as lists of arguments.
    `shlex.split()` treats the backslashes of Windows paths as escapes.
5. Tests wait for workers and never sleep. A wait also covers the workers
    started while waiting, because a finished worker can start another.

## Settings

A setting is changed for one test by patching the settings object:

```python
import pytest

import aimbat


def test_something(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aimbat.settings, "min_cc", 0.8)
```

## Running the tests

The tests run in parallel with pytest-xdist. Tests that start a subprocess,
download data or drive the TUI are marked `slow`. `make tests` skips them, and
`make tests-full` includes them. A single test file or test runs directly:

```bash
uv run pytest tests/integration/core/test_snapshots.py
uv run pytest tests/integration/core/test_snapshots.py::test_name
```

The number of worker processes can be limited, for example with
`make tests PYTEST_WORKERS=4`.
