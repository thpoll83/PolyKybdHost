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
    r"\((\d+) call\(s\), median ([\d.]+) ms, max ([\d.]+) ms\) \+ host (\d+) ms "
    r"\((\d+) ms before the first report\)")


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
        m = LINE.search(lines[0])
        self.assertIsNotNone(m, lines[0])
        return [float(x) for x in m.groups()]

    def test_device_calls_equal_the_reports_and_the_parts_add_up(self):
        kb = PolyKybdMock(DeviceSettings(), protocol=21)
        cache = OverlayMRUCache(64)
        for name, n in (("@cold", 12), ("@warm", 12)):
            with self.subTest(name=name):
                (image, mapping, control, total, wall, pauses, pause_ms, device_ms,
                 calls, median, mx, host_ms, prep_ms) = self.switch(kb, cache, name, n)
                self.assertEqual(calls, total)
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


if __name__ == "__main__":
    unittest.main()
