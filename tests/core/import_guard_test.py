"""The headless tree must be importable without PyQt5 (headless-core plan §6).

Poison PyQt5 in a fresh interpreter and import the core package — any
direct or transitive Qt import fails loudly. This is the contract that
makes --headless (H3) possible; it must hold from H1 onward.
"""
import subprocess
import sys
import unittest

_POISON = r"""
import sys
class _Poison:
    def find_module(self, name, path=None):
        if name == "PyQt5" or name.startswith("PyQt5."):
            return self
    def load_module(self, name):
        raise ImportError(f"Qt import attempted from the headless core: {name}")
sys.meta_path.insert(0, _Poison())

import polyhost.core.poly_core
import polyhost.core.decisions
import polyhost.core.events
print("CORE_OK")
"""


class TestCoreImportsWithoutQt(unittest.TestCase):

    def test_core_package_never_imports_qt(self):
        proc = subprocess.run(
            [sys.executable, "-c", _POISON],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("CORE_OK", proc.stdout)


if __name__ == '__main__':
    unittest.main()
