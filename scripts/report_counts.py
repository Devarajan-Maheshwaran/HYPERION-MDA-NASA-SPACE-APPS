"""Print the project counts that documentation quotes, computed from the code itself.

Usage (from the repository root, standard library only):

    python scripts/report_counts.py

Sources:
  * channels       -> hyperion_mda.signal_registry.CHANNELS (imported, not parsed)
  * tests/         -> unittest discovery when it imports cleanly, else an AST count
  * m6 tests       -> AST count of ``def test_*`` methods; unittest discovery of that
                      directory needs numpy/scipy, which the core app does not require.

Nothing here is written to any file: paste the output into the docs, or run it to check
whether a quoted number is still true. It performs no scoring and loads no dataset.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from hyperion_mda import signal_registry as reg  # noqa: E402


def ast_test_count(directory: Path) -> int:
    """Count ``def test_*`` methods in test classes, without importing the modules."""
    total = 0
    for path in sorted(directory.rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                total += sum(1 for item in node.body
                             if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                             and item.name.startswith("test"))
    return total


def suite_count(directory: Path) -> tuple[int, str]:
    """Prefer unittest discovery; fall back to an AST count if imports are unavailable."""
    loader = unittest.TestLoader()
    try:
        suite = loader.discover(str(directory))
        if not loader.errors:
            return suite.countTestCases(), "unittest discovery"
    except Exception:  # ImportError or anything else the test modules raise at import time
        pass
    return ast_test_count(directory), "AST count (discovery needs extra dependencies)"


def main() -> int:
    counts = reg.status_counts()
    ordered = [reg.MEASURED_LAB_SAMPLE, reg.RECORDED_NON_ASTRONAUT, reg.SIMULATED, reg.UNAVAILABLE]
    breakdown = ", ".join(f"{counts.get(status, 0)} {status}" for status in ordered)
    main_n, main_how = suite_count(REPO_ROOT / "tests")
    m6_n, m6_how = suite_count(REPO_ROOT / "experiments" / "m6" / "tests")

    print(f"channels: {len(reg.CHANNELS)} total - {breakdown}")
    print("  source: signal_registry.CHANNELS (value-free registry)")
    print(f"tests/: {main_n} collected [{main_how}]")
    print(f"experiments/m6/tests/: {m6_n} collected [{m6_how}]")
    print(f"combined: {main_n + m6_n} collected")
    print("Note: collected != executed. Class-level skips (no Tkinter, no dataset cache)")
    print("reduce the number unittest reports as run. Quote the command output for runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
