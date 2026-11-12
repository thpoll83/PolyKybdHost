"""The window accept delay has one definition, in polyhost/core/window_timing.py.

The core's tick, the tray's tick and the forwarder each kept their own
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000, so a change to one would have left the
others behind. This reads the source instead of importing it, because
polyhost/forwarder.py imports pywinctl at load and cannot be imported here.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2] / "polyhost"
DEFINITION = re.compile(r"^NEW_WINDOW_ACCEPT_TIME_MSEC\s*=", re.M)
IMPORT = "from polyhost.core.window_timing import NEW_WINDOW_ACCEPT_TIME_MSEC"


class WindowAcceptDelayTest(unittest.TestCase):
    def test_only_window_timing_defines_it(self):
        defining = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py")
                          if DEFINITION.search(p.read_text(encoding="utf-8")))
        self.assertEqual(defining, ["core/window_timing.py"])

    def test_every_window_tick_imports_it(self):
        for rel in ("core/poly_core.py", "host.py", "forwarder.py"):
            with self.subTest(rel):
                self.assertIn(IMPORT, (ROOT / rel).read_text(encoding="utf-8"))

    def test_the_value_is_500_ms(self):
        from polyhost.core.window_timing import NEW_WINDOW_ACCEPT_TIME_MSEC
        self.assertEqual(NEW_WINDOW_ACCEPT_TIME_MSEC, 500)


if __name__ == "__main__":
    unittest.main()
