"""polyctl reboot | bootloop (cmd 43 + cmd 39, firmware v22+)."""
import unittest

from polyhost.server import protocol
from tests.cli.polyctl_test import run_main, run_streaming

RECORD = {
    "side": "master", "kind": "watchdog", "core": 0, "pc": 0, "lr": 0, "sp": 0,
    "xpsr": 0, "icsr": 0, "phase": 1, "phase_arg": 0x16E1, "uptime_ms": 0,
    "consecutive": 1, "reset_reason": 0x11, "fw": "1.3.2", "line": "", "fresh": True,
}


class BootLoopCliTest(unittest.TestCase):
    def test_reboot_calls_the_reboot_method(self):
        rc, out, _, server = run_main(["reboot"], {protocol.M_REBOOT: "rebooting"})
        self.assertEqual(rc, 0)
        self.assertIn(protocol.M_REBOOT, [m for m, _ in server.received])

    def test_a_clean_run_streams_rounds_and_exits_0(self):
        events = [("boot_loop_progress", {"round": 1, "rounds": 2, "msg": "rebooting"}),
                  ("boot_loop_progress", {"round": 1, "rounds": 2, "msg": "clean boot in 3.1 s"}),
                  ("boot_loop_done", {"ok": True, "result": "clean", "msg": "2 reboot(s), no boot problem.",
                                      "rounds_done": 2, "boot_times": [3.1, 3.0], "record": None})]
        rc, out, _ = run_streaming(["bootloop", "--rounds", "2"], protocol.M_BOOT_LOOP_START,
                                   {"rounds": 2}, events)
        self.assertEqual(rc, 0)
        self.assertIn("[1/2] clean boot in 3.1 s", out)
        self.assertIn("no boot problem", out)

    def test_a_found_crash_prints_the_record_and_exits_1(self):
        events = [("boot_loop_done", {"ok": False, "result": "crash", "msg": "Round 7: a boot problem",
                                      "rounds_done": 7, "boot_times": [], "record": RECORD})]
        rc, out, _ = run_streaming(["bootloop"], protocol.M_BOOT_LOOP_START, {"rounds": 50}, events)
        self.assertEqual(rc, 1)
        self.assertIn("Round 7", out)
        self.assertIn("phase=1:0x16e1", out)

    def test_cancel_calls_the_cancel_method(self):
        rc, out, _, server = run_main(["bootloop", "--cancel"],
                                      {protocol.M_BOOT_LOOP_CANCEL: "cancelling"})
        self.assertEqual(rc, 0)
        self.assertIn(protocol.M_BOOT_LOOP_CANCEL, [m for m, _ in server.received])


if __name__ == "__main__":
    unittest.main()
