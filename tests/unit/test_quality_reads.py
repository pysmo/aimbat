"""Stored quality values are read only where validity is checked.

A stored `iccs_cc` or MCCC result says nothing on its own: it counts only if
`aimbat.core._validity.Validity` says it matches the current parameters. This
test fails on any read of a quality column outside the functions listed
below. Add a function only if it checks validity, reads snapshot rows, or
reads values that have already been checked.

Reads by name only: `getattr` with a computed name and `model_validate` copies
are not seen.
"""

import ast
from pathlib import Path

import aimbat

_QUALITY_FIELDS = frozenset(
    {"iccs_cc", "mccc_cc_mean", "mccc_cc_std", "mccc_error", "mccc_rmse"}
)

_ALLOWED: dict[str, frozenset[str]] = {
    # Live quality, checked against a `Validity`.
    "models/_readers.py": frozenset(
        {
            "SeismogramQualityStats.from_phase",
            "SeismogramQualityStats.from_station",
            "AimbatStationRead.from_station",
            "AimbatSeismogramRead.from_seismogram",
            # Snapshot rows.
            "SeismogramQualityStats.from_snapshot",
            "AimbatSnapshotRead.from_snapshot",
            "SnapshotSeismogramResult.from_snapshot_records",
            # Statistics already built from checked values.
            "SeismogramQualityStats.mccc_cc_mean_display",
            "SeismogramQualityStats.mccc_cc_std_display",
            "SeismogramQualityStats.mccc_error_display",
            "SeismogramQualityStats.mccc_rmse_display",
        }
    ),
    "core/_snapshot.py": frozenset(
        {
            # Freezes live quality, checked against a `Validity`.
            "create_snapshot",
            # Snapshot rows.
            "resync_quality",
            "_restore_iccs_cc",
            "dump_snapshot_results",
        }
    ),
    # Statistics already built from checked values.
    "_tui/_format.py": frozenset({"format_quality_panel"}),
}


class _Reads(ast.NodeVisitor):
    """Collect the enclosing function of every read of a quality field."""

    def __init__(self) -> None:
        self._scope: list[str] = []
        self.found: set[str] = set()

    def _visit_scope(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope
    visit_ClassDef = _visit_scope

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _QUALITY_FIELDS and isinstance(node.ctx, ast.Load):
            self.found.add(".".join(self._scope) or "<module>")
        self.generic_visit(node)


def _quality_reads() -> dict[str, set[str]]:
    root = Path(aimbat.__file__).parent
    reads: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.py")):
        if "_migrations" in path.parts:
            continue
        visitor = _Reads()
        visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
        if visitor.found:
            reads[path.relative_to(root).as_posix()] = visitor.found
    return reads


def test_quality_is_read_only_where_allowed() -> None:
    """No function outside the allowlist reads a quality column."""
    unexpected = {
        f"{module}: {function}"
        for module, functions in _quality_reads().items()
        for function in functions - _ALLOWED.get(module, frozenset())
    }
    assert not unexpected, "Quality values read without a validity check: " + ", ".join(
        sorted(unexpected)
    )


def test_allowlist_is_current() -> None:
    """Every allowed function still reads a quality column."""
    reads = _quality_reads()
    stale = {
        f"{module}: {function}"
        for module, functions in _ALLOWED.items()
        for function in functions - reads.get(module, set())
    }
    assert not stale, "Allowlist entries with no quality read: " + ", ".join(
        sorted(stale)
    )
