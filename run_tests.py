#!/usr/bin/env python3
"""Unified test runner for agent-search-sdk."""

import sys
import unittest
from pathlib import Path

# Ensure project root in sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_models import TestModels
from tests.test_cascade import TestCascade
from tests.test_providers import TestProviders
from tests.test_cli import TestCLI


def suite():
    s = unittest.TestSuite()
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestModels))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestCascade))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestProviders))
    s.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestCLI))
    return s


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite())
    sys.exit(0 if result.wasSuccessful() else 1)
