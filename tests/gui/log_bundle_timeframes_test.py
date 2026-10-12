"""The timeframe choices of the log bundle and problem report dialogs.

Both dialogs share TIMEFRAMES. Their defaults are looked up by spec, so adding
an entry in front of one (5 minutes went in front of 15) cannot move it.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from polyhost.services import log_bundle

try:
    from polyhost.gui import log_bundle_dialog, report_problem_dialog
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt available
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TimeframesTest(unittest.TestCase):

    def _specs(self):
        return [spec for _label, spec in log_bundle_dialog.TIMEFRAMES]

    def test_defaults_point_at_their_spec(self):
        specs = self._specs()
        self.assertEqual(specs[log_bundle_dialog.DEFAULT_INDEX], "24h")
        self.assertEqual(specs[report_problem_dialog.DEFAULT_TIMEFRAME_INDEX], "1h")

    def test_five_minutes_is_the_smallest_choice(self):
        self.assertEqual(self._specs()[0], "5m")

    def test_every_spec_parses_and_the_list_widens(self):
        cutoffs = [log_bundle.parse_since(spec) for spec in self._specs()]
        self.assertIsNone(cutoffs[-1])                 # "all" is last
        windows = [c.timestamp() for c in cutoffs[:-1]]
        self.assertEqual(windows, sorted(windows, reverse=True))


if __name__ == "__main__":
    unittest.main()
