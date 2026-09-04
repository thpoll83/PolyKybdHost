"""polyctl crash show|clear."""
import json
import unittest

from polyhost.server import protocol
from tests.cli.polyctl_test import run_main

RECORD = {
    "side": "master", "kind": "hardfault", "core": 0, "pc": 0x10012345,
    "lr": 0x1000ABCD, "sp": 0x20040FF0, "xpsr": 0x21000003, "icsr": 3,
    "phase": 3, "phase_arg": 0x15, "uptime_ms": 123456, "consecutive": 1,
    "reset_reason": 0x22, "fw": "0.18.0", "line": "", "fresh": True,
}


class CrashCliTest(unittest.TestCase):
    def test_show_prints_summary_and_the_console_line(self):
        rc, out, _, server = run_main(["crash", "show"], {protocol.M_CRASH_GET: RECORD})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_CRASH_GET], {"which": 0})
        self.assertIn("HardFault", out)
        self.assertIn("crash: side=master kind=hardfault", out)
        self.assertIn("fresh", out)

    def test_show_slave_asks_for_which_1(self):
        rc, out, _, server = run_main(["crash", "show", "--slave"], {protocol.M_CRASH_GET: None})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_CRASH_GET], {"which": 1})
        self.assertIn("no crash record on the slave half", out)

    def test_show_json_is_the_raw_record(self):
        rc, out, _, _ = run_main(["crash", "show", "--json"], {protocol.M_CRASH_GET: RECORD})
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), RECORD)

    def test_clear_calls_the_clear_method(self):
        rc, out, _, server = run_main(["crash", "clear"], {protocol.M_CRASH_CLEAR: True})
        self.assertEqual(rc, 0)
        self.assertIn(protocol.M_CRASH_CLEAR, [m for m, _ in server.received])
        self.assertIn("cleared", out)


if __name__ == "__main__":
    unittest.main()
