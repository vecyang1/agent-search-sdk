"""Structural gates: the denominators other tests silently depend on.

* every registered provider has a live test and a unit test module;
* every CLI subcommand is exercised as a process;
* every hermetic test module imports the sandbox before the SDK;
* no test is defined below ``if __name__ == "__main__"`` (unreachable under direct run).
Each gate prints how many subjects it graded so a selector that narrows later shows up as a number.
"""

import tests._sandbox as sandbox  # noqa: F401

import ast
import re
import unittest
from pathlib import Path

from search_sdk.cli import _SUBCOMMANDS
from search_sdk.providers import PROVIDER_REGISTRY

TESTS = Path(__file__).resolve().parent
TEST_FILES = sorted(p for p in TESTS.glob("test_*.py"))
HERMETIC_FILES = [p for p in TEST_FILES if not p.name.startswith("test_live")]
LIVE_FILE = TESTS / "test_live.py"


class TestGates(unittest.TestCase):
    def test_every_registered_provider_has_a_live_test(self):
        source = LIVE_FILE.read_text(encoding="utf-8")
        missing = [name for name in PROVIDER_REGISTRY if not re.search(rf"def test_live_{name}\b", source)]
        print(f"[gate] graded {len(PROVIDER_REGISTRY)} providers for live coverage")
        self.assertGreater(len(PROVIDER_REGISTRY), 0)
        self.assertEqual(missing, [], f"providers without a live test: {missing}")

    def test_every_cli_subcommand_runs_as_a_process(self):
        source = (TESTS / "test_cli_process.py").read_text(encoding="utf-8")
        missing = [cmd for cmd in _SUBCOMMANDS if f'"{cmd}"' not in source]
        print(f"[gate] graded {len(_SUBCOMMANDS)} CLI subcommands for process coverage")
        self.assertEqual(missing, [], f"subcommands never run as a process: {missing}")

    def test_hermetic_modules_import_sandbox_before_the_sdk(self):
        offenders = []
        for path in HERMETIC_FILES:
            lines = path.read_text(encoding="utf-8").splitlines()
            sandbox_line = next((i for i, l in enumerate(lines) if l.startswith("import tests._sandbox")), None)
            sdk_line = next((i for i, l in enumerate(lines) if re.match(r"^(from|import) search_sdk", l)), None)
            if sandbox_line is None or (sdk_line is not None and sdk_line < sandbox_line):
                offenders.append(path.name)
        print(f"[gate] graded {len(HERMETIC_FILES)} hermetic test modules for sandbox import order")
        self.assertGreater(len(HERMETIC_FILES), 0)
        self.assertEqual(offenders, [])

    def test_live_module_does_not_import_sandbox(self):
        self.assertNotIn("tests._sandbox", LIVE_FILE.read_text(encoding="utf-8"))

    def test_nothing_defined_below_main_guard(self):
        offenders = []
        for path in TEST_FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            guard_index = next((i for i, node in enumerate(tree.body) if isinstance(node, ast.If) and "__main__" in ast.dump(node.test)), None)
            if guard_index is not None and any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) for n in tree.body[guard_index + 1:]):
                offenders.append(path.name)
        print(f"[gate] graded {len(TEST_FILES)} test files for code below the main guard")
        self.assertEqual(offenders, [])

    def test_every_provider_module_has_a_unit_test_module_or_case(self):
        sources = "\n".join(p.read_text(encoding="utf-8") for p in HERMETIC_FILES)
        missing = [name for name, cls in PROVIDER_REGISTRY.items() if cls.__name__ not in sources]
        print(f"[gate] graded {len(PROVIDER_REGISTRY)} provider classes for unit coverage")
        self.assertEqual(missing, [], f"provider classes never instantiated in a unit test: {missing}")


if __name__ == "__main__":
    unittest.main()
