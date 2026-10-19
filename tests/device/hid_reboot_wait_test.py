"""HidHelper.wait_for_reboot: the device must LEAVE the bus before "back" counts.

Driven with an injected enumeration sequence and a fake clock, no hardware.
The field case this guards (2026-10-19): FW_UP_APPLY acknowledged, the old
device still enumerated for a moment, the single-phase wait re-opened it and
reported "reconnected" 80 ms later while the keyboard was rebooting.
"""
import unittest

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.hid_helper import HidHelper


class _FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


class _Helper(HidHelper):
    """Enumeration answers come from a script: each call pops the next list,
    the last one repeats. _open records what it was handed."""

    def __init__(self, script):
        self.settings = DeviceSettings()
        self.lock = __import__("threading").Lock()
        self.interface = None
        self.script = list(script)
        self.opened = []

    def _enumerate(self, vid):
        if len(self.script) > 1:
            return self.script.pop(0)
        return self.script[0]

    def _open(self, info):
        self.opened.append(info)
        return object()


def _raw(settings):
    return [{"product_id": settings.KNOWN_PIDS[0], "usage_page": settings.HID_RAW_USAGE_PAGE,
             "usage": settings.HID_RAW_USAGE, "path": b"old"}]


class WaitForRebootTest(unittest.TestCase):
    def setUp(self):
        self.s = DeviceSettings()
        self.clock = _FakeClock()

    def _wait(self, script, **kw):
        h = _Helper(script)
        out = h.wait_for_reboot(clock=self.clock, sleep=self.clock.sleep, **kw)
        return h, out

    def test_present_then_gone_then_back_reconnects_once(self):
        raw = _raw(self.s)
        h, out = self._wait([raw, raw, [], [], raw])
        self.assertEqual(out, HidHelper.REBOOT_RECONNECTED)
        self.assertEqual(len(h.opened), 1)
        self.assertIsNotNone(h.interface)

    def test_a_device_that_stays_enumerated_is_never_left(self):
        raw = _raw(self.s)
        h, out = self._wait([raw], gone_timeout_s=10)
        self.assertEqual(out, HidHelper.REBOOT_NEVER_LEFT)
        self.assertEqual(h.opened, [])
        self.assertGreaterEqual(self.clock.t, 10)

    def test_gone_and_never_back_times_out(self):
        h, out = self._wait([[]], timeout_s=30)
        self.assertEqual(out, HidHelper.REBOOT_NO_RETURN)
        self.assertEqual(h.opened, [])
        self.assertGreaterEqual(self.clock.t, 30)

    def test_already_absent_counts_as_gone(self):
        raw = _raw(self.s)
        h, out = self._wait([[], raw])
        self.assertEqual(out, HidHelper.REBOOT_RECONNECTED)

    def test_waits_for_the_opened_device_not_another_keyboard(self):
        # Two keyboards: the flashed one ("old") leaves while the other stays.
        other = [dict(_raw(self.s)[0], path=b"other")]
        both = _raw(self.s) + other
        h = _Helper([both, other, other, both])
        h.interface = type("_Dev", (), {"close": lambda self: None})()
        h.interface_path = b"old"
        out = h.wait_for_reboot(clock=self.clock, sleep=self.clock.sleep, gone_timeout_s=10)
        self.assertEqual(out, HidHelper.REBOOT_RECONNECTED)
        self.assertLess(self.clock.t, 10)

    def test_an_enumeration_error_is_unknown_not_absent(self):
        # An error before the old device left must not end the gone phase
        # (the next good enumeration would reopen the OLD device); one after
        # it left is retried in the return phase.
        raw = _raw(self.s)

        class _Raising(_Helper):
            def _enumerate(self, vid):
                nxt = super()._enumerate(vid)
                if nxt == "raise":
                    raise OSError("usb churn")
                return nxt

        h = _Raising([raw, "raise", raw])          # error, then still there, for ever
        out = h.wait_for_reboot(clock=self.clock, sleep=self.clock.sleep, gone_timeout_s=10)
        self.assertEqual(out, HidHelper.REBOOT_NEVER_LEFT)
        self.assertEqual(h.opened, [])

        self.clock.t = 0.0
        h = _Raising([raw, [], "raise", "raise", raw])   # gone, errors, back
        out = h.wait_for_reboot(clock=self.clock, sleep=self.clock.sleep)
        self.assertEqual(out, HidHelper.REBOOT_RECONNECTED)
        self.assertEqual(len(h.opened), 1)

    def test_a_non_raw_interface_does_not_count_as_present(self):
        console = [{"product_id": self.s.KNOWN_PIDS[0], "usage_page": self.s.HID_CONSOLE_USAGE_PAGE,
                    "usage": self.s.HID_CONSOLE_USAGE, "path": b"console"}]
        raw = _raw(self.s)
        h, out = self._wait([console, raw])
        self.assertEqual(out, HidHelper.REBOOT_RECONNECTED)
        self.assertEqual(h.opened[0]["path"], b"old")


if __name__ == "__main__":
    unittest.main()
