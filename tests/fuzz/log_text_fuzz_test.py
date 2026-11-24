"""Properties of the log parsers: crash_log markers and log_bundle's line parsers.
Both read log files that any process may have written."""
import unittest
from datetime import datetime

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services import log_bundle
from polyhost.util import crash_log

load_profile()

FIXED = datetime(2026, 1, 1)


class CrashMarkerFuzzTest(unittest.TestCase):
    @given(st.text(max_size=80), st.integers(0, 2 ** 31))
    def test_marker_round_trip(self, what, pid):
        line = crash_log.format_marker(what, pid)
        parsed = crash_log.parse_marker(line)
        self.assertIsNotNone(parsed, line)
        self.assertEqual(parsed[1], pid)
        self.assertEqual(parsed[0], " ".join(what.splitlines()) or "<empty>")

    @given(st.text(max_size=120))
    def test_parse_marker_arbitrary_line(self, line):
        parsed = crash_log.parse_marker(line)
        if parsed is not None:
            self.assertIsInstance(parsed[1], int)


class LogBundleFuzzTest(unittest.TestCase):
    @given(st.text(max_size=80))
    def test_parse_timestamp_arbitrary_line(self, line):
        stamp = log_bundle.parse_timestamp(line)
        self.assertTrue(stamp is None or isinstance(stamp, datetime))

    @given(st.one_of(st.text(max_size=30),
                     st.from_regex(r"\d{1,400}(\.\d{1,20})?\s*[smhdw]?", fullmatch=True)))
    def test_parse_since_raises_only_value_error(self, spec):
        try:
            cutoff = log_bundle.parse_since(spec, now=FIXED)
        except ValueError:
            return
        self.assertTrue(cutoff is None or cutoff <= FIXED)

    @given(st.text(max_size=200))
    def test_redact_text_is_idempotent(self, text):
        once = log_bundle.redact_text(text)
        self.assertEqual(log_bundle.redact_text(once), once)

    @given(st.lists(st.text(max_size=40), max_size=20))
    def test_slice_lines_keeps_a_subsequence(self, lines):
        out = log_bundle.slice_lines(lines, FIXED)
        it = iter(lines)
        self.assertTrue(all(any(x == y for y in it) for x in out))


if __name__ == "__main__":
    unittest.main()
