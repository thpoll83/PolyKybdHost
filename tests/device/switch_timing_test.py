"""The overlay switch summary splits its wall time: pauses + device calls + host.

Over the emulated keyboard (PolyKybdMock drives the real PolyKybd send loop
through a real HidHelper), so the device-call count in the line is the number
of reports the switch really sent, and the three parts add up to the wall time.
"""
import re
import threading
import unittest

from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd_mock import PolyKybdMock
from tests.device.pool_overflow_test import _image

LINE = re.compile(
    r"reports: image (\d+) \+ mapping (\d+) \+ control (\d+) = (\d+) .*\| "
    r"wall (\d+) ms = (\d+) rate-limit pause\(s\) (\d+) ms \+ device (\d+) ms "
    r"\((\d+) call\(s\), median ([\d.]+) ms, max ([\d.]+) ms; "
    r"write-only (\d+) call\(s\) (\d+) ms, median ([\d.]+) ms, max ([\d.]+) ms; "
    r"with reply (\d+) call\(s\) (\d+) ms, median ([\d.]+) ms, max ([\d.]+) ms\) "
    r"\+ host (\d+) ms \((\d+) ms before the first report\)")


class SwitchTimingTest(unittest.TestCase):

    def switch(self, kb, cache, name, n_images):
        ds = DeviceSettings()
        keys = [k.value for k in KeyCode if 0x04 <= k.value <= 0x43][:n_images]
        by_mod = {Modifier.NO_MOD: {k: OverlayData(ds, _image(i)) for i, k in enumerate(keys)}}
        with self.assertLogs("PolyHost", level="INFO") as cm:
            ok = kb.send_overlays_mru([name], cache, threading.Event(),
                                      synthetic={name: syn.SyntheticConverter(by_mod)})
        self.assertTrue(ok)
        lines = [l for l in cm.output if "Overlay switch stats:" in l]
        self.assertEqual(len(lines), 1, cm.output)
        self.last_line = lines[0]
        m = LINE.search(lines[0])
        self.assertIsNotNone(m, lines[0])
        return [float(x) for x in m.groups()]

    def test_device_calls_equal_the_reports_and_the_parts_add_up(self):
        kb = PolyKybdMock(DeviceSettings(), protocol=21)
        cache = OverlayMRUCache(64)
        for name, n in (("@cold", 12), ("@warm", 12)):
            with self.subTest(name=name):
                (image, mapping, control, total, wall, pauses, pause_ms, device_ms,
                 calls, median, mx, w_calls, w_ms, w_med, w_max, r_calls, r_ms, r_med, r_max,
                 host_ms, prep_ms) = self.switch(kb, cache, name, n)
                self.assertEqual(calls, total)
                self.assertEqual(w_calls + r_calls, calls)
                # Image and mapping reports are writes; prepare/enable wait for a
                # reply. The mock keyboard has no icon library, so no cmd 42
                # fills (the other kind that waits) appear here.
                self.assertIn("[fill 0,", self.last_line)
                self.assertEqual(w_calls, image + mapping)
                self.assertEqual(r_calls, control)
                self.assertAlmostEqual(w_ms + r_ms, device_ms, delta=2)
                self.assertGreater(calls, 0)
                self.assertLessEqual(mx, device_ms + 1)
                self.assertLessEqual(median, mx)
                self.assertLessEqual(prep_ms, host_ms + 1)
                # rounding: each part is printed to the millisecond
                self.assertAlmostEqual(wall, pause_ms + device_ms + host_ms, delta=3)
        # the mock's wire has no rate-limit pause
        self.assertEqual(pauses, 0)

    def test_no_meter_without_a_measuring_hid(self):
        """A stand-in hid with only the two send methods (the rig's app-switch
        recorder) still gets a summary, with a zero device part."""
        kb = PolyKybdMock(DeviceSettings(), protocol=21)
        real = kb._wire.hid

        class Recorder:
            interface = object()

            def send_multiple(self, data):
                return real.send_multiple(data)

            def send_and_read_validate(self, data, timeout=100, expected_prefix=None):
                return real.send_and_read_validate(data, timeout, expected_prefix)

        kb._wire.hid = Recorder()
        try:
            parts = self.switch(kb, OverlayMRUCache(64), "@rec", 4)
        finally:
            kb._wire.hid = real
        self.assertEqual(parts[8], 0)       # calls
        self.assertEqual(parts[7], 0)       # device ms
        self.assertEqual(parts[11], 0)      # write-only calls
        self.assertEqual(parts[15], 0)      # calls with a reply


class EachPartIsMeasuredTest(unittest.TestCase):
    """Review, Greptile: host time is the remainder, so a test that only checks
    the sum would pass with device time mis-scaled or a pause booked as host
    work. Here every device call takes a known time and the switch pauses, and
    each printed part is checked on its own."""

    CALL_S = 0.004
    PAUSE_S = 0.25

    def test_pauses_device_calls_and_host_work_land_in_their_own_parts(self):
        import time
        from polyhost.device.poly_kybd import PolyKybd
        from tests.device.fake_hid import FakeHidDevice, make_hid_helper
        from tests.device.poly_kybd_cancel_test import StubPolySettings

        call_s = self.CALL_S

        class SlowDevice(FakeHidDevice):
            def write(self, report):
                time.sleep(call_s)
                return super().write(report)

        keeb = PolyKybd(DeviceSettings(), StubPolySettings(
            max_hid_message_before_delay=2, delay_time_after_max_hid_messages=self.PAUSE_S))
        keeb.hid = make_hid_helper(SlowDevice(auto_ack=True))
        keeb.supports = lambda f: f != "overlay_icons"
        ds = DeviceSettings()
        keys = [k.value for k in KeyCode if 0x04 <= k.value <= 0x43][:12]
        by_mod = {Modifier.NO_MOD: {k: OverlayData(ds, _image(i)) for i, k in enumerate(keys)}}
        with self.assertLogs("PolyHost", level="INFO") as cm:
            ok = keeb.send_overlays_mru(["@slow"], OverlayMRUCache(64), threading.Event(),
                                        synthetic={"@slow": syn.SyntheticConverter(by_mod)})
        self.assertTrue(ok)
        line = [l for l in cm.output if "Overlay switch stats:" in l][0]
        m = LINE.search(line)
        self.assertIsNotNone(m, line)
        (image, mapping, control, total, wall, pauses, pause_ms, device_ms,
         calls, median, mx, w_calls, w_ms, w_med, w_max, r_calls, r_ms, r_med, r_max,
         host_ms, prep_ms) = [float(x) for x in m.groups()]
        self.assertGreaterEqual(pauses, 1, line)
        # Each pause is one sleep of PAUSE_S: booked as pause, not as host work.
        self.assertGreaterEqual(pause_ms, pauses * self.PAUSE_S * 1000 - 1, line)
        self.assertLess(pause_ms, pauses * self.PAUSE_S * 1000 + 50 * pauses, line)
        self.assertLess(host_ms, self.PAUSE_S * 1000, line)
        # Each call takes CALL_S: device time is the calls' own time, in ms.
        self.assertEqual(calls, total, line)
        self.assertGreaterEqual(device_ms, calls * self.CALL_S * 1000 - 1, line)
        self.assertLess(device_ms, calls * self.CALL_S * 1000 + 100, line)
        self.assertGreaterEqual(w_med, self.CALL_S * 1000 - 0.1, line)
        self.assertAlmostEqual(wall, pause_ms + device_ms + host_ms, delta=3)


if __name__ == "__main__":
    unittest.main()
