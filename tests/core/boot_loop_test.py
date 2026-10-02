"""The boot-loop diagnostic (PolyCore.start_boot_loop) against the emulated keyboard.

Reboot over cmd 43, wait for the GET_ID fresh-boot marker, read cmd 39, repeat. It
hunts the intermittent boot stall the late-boot watchdog guard recovers from, which
leaves a FRESH `kind=watchdog phase=boot` record (fw 1.3.2 in the field: 0x16e1,
"63%, 4 / 4"). Driven end to end through the real core, worker and reconnect probe
over MockFirmware, so the wait-for-reconnect is the real one, not a stub.
"""
import threading
import unittest
import unittest.mock as mock

from polyhost._version import __protocol__
from polyhost.core.poly_core import PolyCore
from polyhost.settings import PolySettings


class BootLoopTest(unittest.TestCase):

    def _core(self, protocol=0, **faults):
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": protocol}

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        for p in (mock.patch.object(PolySettings, "get", get),
                  mock.patch.object(PolySettings, "save", lambda *a, **k: True),
                  mock.patch.object(PolyCore, "_compute_daylight_value", lambda self: 20),
                  mock.patch.object(PolyCore, "BOOT_LOOP_RECONNECT_TIMEOUT_S", 4.0),
                  mock.patch.object(PolyCore, "BOOT_LOOP_SLAVE_WAIT_S", 0.3),
                  mock.patch.object(PolyCore, "BOOT_LOOP_POLL_S", 0.1)):
            p.start()
            self.addCleanup(p.stop)
        # As the daemon runs it; in-process the tray applies the probe, through
        # the same core.apply_reconnect(), which is where the loop's signal is set.
        core = PolyCore(mock.MagicMock(), start_worker=False, apply_reconnect_in_core=True)
        for k, v in faults.items():
            setattr(core.keeb.firmware.faults, k, v)
        core.worker.start()
        self.addCleanup(core.shutdown)
        core.apply_reconnect(core._reconnect_probe(threading.Event()))
        core.worker.run_sync("barrier", lambda c: None, timeout=30)
        self.assertTrue(core.connected)
        self.events = []
        self.done = threading.Event()

        def on(name, payload):
            if name.startswith("boot_loop"):
                self.events.append((name, payload))
            if name == "boot_loop_done":
                self.done.set()
        core.subscribe(on)
        return core

    def _run(self, core, rounds):
        ok, info = core.start_boot_loop(rounds)
        self.assertTrue(ok, info)
        self.assertTrue(self.done.wait(60), "the loop never finished")
        return dict(self.events)["boot_loop_done"]

    def test_clean_rounds_reboot_each_time_and_report_clean(self):
        core = self._core()
        done = self._run(core, 3)
        self.assertEqual(done["result"], "clean", done)
        self.assertTrue(done["ok"])
        self.assertEqual(done["rounds_done"], 3)
        self.assertEqual(len(done["boot_times"]), 3)
        self.assertEqual(core.keeb.firmware.reboot_count, 3)

    def test_it_stops_at_the_first_boot_that_left_a_fresh_record(self):
        core = self._core(boot_crash_on_reboot=2)
        done = self._run(core, 50)
        self.assertEqual(done["result"], "crash", done)
        self.assertFalse(done["ok"])
        self.assertEqual(done["rounds_done"], 2)
        self.assertEqual(core.keeb.firmware.reboot_count, 2, "it must not reboot again")
        rec = done["record"]
        self.assertEqual(rec["kind"], "watchdog")
        self.assertEqual((rec["phase"], rec["phase_arg"]), (1, 0x16E1))

    def test_a_lost_reboot_ack_does_not_stop_it(self):
        # The firmware ACKs before it resets, but the ACK can still be lost.
        from polyhost.device.command_ids import Cmd
        core = self._core(drop_replies={Cmd.REBOOT.value: 1})
        done = self._run(core, 2)
        self.assertEqual(done["result"], "clean", done)
        self.assertEqual(core.keeb.firmware.reboot_count, 2)

    def test_a_refused_reboot_stops_it(self):
        from polyhost.device.command_ids import Cmd
        core = self._core(nack={Cmd.REBOOT.value: 1})
        done = self._run(core, 3)
        self.assertEqual(done["result"], "error", done)
        self.assertIn("refused", done["msg"])

    def test_an_unreadable_crash_record_is_an_error_not_clean(self):
        from polyhost.device.command_ids import Cmd
        core = self._core(nack={Cmd.CRASH_RECORD.value: 99})
        done = self._run(core, 3)
        self.assertEqual(done["result"], "error", done)
        self.assertIn("master crash record unreadable", done["msg"])
        self.assertEqual(done["rounds_done"], 0)

    def test_one_missed_read_is_retried(self):
        from polyhost.device.command_ids import Cmd
        core = self._core(nack={Cmd.CRASH_RECORD.value: 1})
        done = self._run(core, 2)
        self.assertEqual(done["result"], "clean", done)

    def test_an_old_record_does_not_stop_it(self):
        core = self._core()
        fw = core.keeb.firmware
        from polyhost.device.mock_firmware import _watchdog_boot_record
        fw.crash_record, fw.crash_fresh = _watchdog_boot_record(fw.version), False
        done = self._run(core, 2)
        self.assertEqual(done["result"], "clean", done)

    def test_a_board_that_never_comes_back_is_a_timeout(self):
        core = self._core(boot_hang_on_reboot=1)
        done = self._run(core, 5)
        self.assertEqual(done["result"], "timeout", done)
        self.assertEqual(done["rounds_done"], 0)

    def test_cancel_stops_it(self):
        core = self._core()
        with mock.patch.object(PolyCore, "BOOT_LOOP_RECONNECT_TIMEOUT_S", 30.0):
            core.keeb.firmware.faults.boot_hang_on_reboot = 1   # it would wait 30 s
            ok, _ = core.start_boot_loop(5)
            self.assertTrue(ok)
            self.assertTrue(core.cancel_boot_loop()[0])
            self.assertTrue(self.done.wait(10))
        self.assertEqual(dict(self.events)["boot_loop_done"]["result"], "cancelled")

    def test_one_loop_at_a_time_and_the_limits(self):
        core = self._core()
        self.assertFalse(core.start_boot_loop(0)[0])
        self.assertFalse(core.start_boot_loop(51)[0])
        self.assertFalse(core.start_boot_loop("x")[0])
        self.assertFalse(core.cancel_boot_loop()[0])
        core.keeb.firmware.faults.boot_hang_on_reboot = 1
        self.assertTrue(core.start_boot_loop(1)[0])
        self.assertIn("already running", core.start_boot_loop(1)[1])
        core.cancel_boot_loop()
        self.assertTrue(self.done.wait(10))

    def test_old_firmware_is_refused_before_anything_is_sent(self):
        core = self._core(protocol=__protocol__ - 1)
        ok, msg = core.start_boot_loop(3)
        self.assertFalse(ok)
        self.assertIn("v22", msg)
        self.assertEqual(core.keeb.firmware.reboot_count, 0)


if __name__ == "__main__":
    unittest.main()
