#!/usr/bin/env python3
"""Unified hermetic test runner for agent-search-sdk.

Discovers every ``tests/test_*.py`` except ``test_live*`` (network), runs it
under the single sandbox owner (``tests/_sandbox.py``), and prints the counts
a reader needs to trust the green: files graded, tests run, skipped, and
whether the real credential cache stayed untouched.

Live tests: ``python3 tests/test_live.py`` (needs real credentials; sequential).
"""

from __future__ import annotations

import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests._sandbox as sandbox  # noqa: E402  (must precede any search_sdk import)

TESTS_DIR = ROOT / "tests"


def build_suite() -> tuple[unittest.TestSuite, list[str]]:
    files = sorted(p.name for p in TESTS_DIR.glob("test_*.py") if not p.name.startswith("test_live"))
    suite = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    for name in files:
        suite.addTests(loader.loadTestsFromName(f"tests.{name[:-3]}"))
    return suite, files


def main() -> int:
    warnings.simplefilter("ignore", ResourceWarning)
    suite, files = build_suite()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    untouched = sandbox.real_cache_untouched()
    print(f"\n[run_tests] files={len(files)} tests={result.testsRun} failures={len(result.failures)} "
          f"errors={len(result.errors)} skipped={len(result.skipped)} real_cache_untouched={untouched}")
    for test, reason in result.skipped:
        print(f"[run_tests] SKIPPED {test.id()}: {reason}")
    if not untouched:
        print("[run_tests] FAIL: the real credential cache changed during the hermetic suite", file=sys.stderr)
        return 1
    if result.testsRun == 0:
        print("[run_tests] FAIL: zero tests ran", file=sys.stderr)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
