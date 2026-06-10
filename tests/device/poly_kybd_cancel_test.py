"""Cancellation tests for PolyKybd device operations (HID-worker refactor Phase A).

These pin the cancel-event behaviour added to send_overlays, send_overlays_mru,
execute_commands, and press_and_release_key:

  - a set cancel aborts promptly, between keycodes (never mid-keycap),
  - it interrupts the rate-limit pause via cancel.wait() instead of time.sleep(),
  - on abort the HID lock is free and enable_overlays() / the mapping commit are
    NOT sent (the superseding send repaints everything),
  - press_and_release_key always emits the release even when cancelled,
  - cancel=None reproduces the pre-refactor behaviour exactly.

Same harness/style as poly_kybd_cmd_test.py: a real PolyKybd over a real
HidHelper wired to a FakeHidDevice, ImageConverter patched at module scope.
"""
import threading
import time
import unittest
from unittest import mock
from unittest.mock import MagicMock

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd import PolyKybd

from tests.device.fake_hid import FakeHidDevice, make_hid_helper

POLY = 0x50  # HidId.ID_POLYKYBD
ENABLE_OVERLAYS = bytes([POLY, 11, 0x01])   # OVERLAY_FLAGS_ON | 0x01
SEND_OVERLAY_MAPPING = 21                    # Cmd.SEND_OVERLAY_MAPPING


class StubPolySettings:
    """Minimal stand-in for PolySettings: just the keys PolyKybd reads."""

    def __init__(self, **overrides):
        self.values = {
            "hid_reconnect_retries": 2,
            "max_hid_message_before_delay": 15,
            "delay_time_after_max_hid_messages": 0.3,
        }
        self.values.update(overrides)

    def get(self, key):
        return self.values[key]


def make_keeb(replies=None, auto_ack=False, settings=None):
    keeb = PolyKybd(DeviceSettings(), settings or StubPolySettings())
    device = FakeHidDevice(replies=replies, auto_ack=auto_ack)
    keeb.hid = make_hid_helper(device)
    return keeb, device


def _overlay(pattern: str = "dot") -> OverlayData:
    img = np.zeros((40, 72), dtype=bool)
    if pattern == "dot":
        img[0, 0] = True
    elif pattern == "rect":
        img[5:20, 10:60] = True
    return OverlayData(DeviceSettings(), img)


def _converter(overlay_map):
    """Patched ImageConverter returning overlay_map for NO_MOD only."""
    converter = MagicMock()
    converter.open.return_value = True
    converter.extract_overlays.side_effect = (
        lambda mod: dict(overlay_map) if mod == Modifier.NO_MOD else None)
    return converter


class LockCheckMixin:
    def assert_lock_free(self, keeb):
        self.assertFalse(keeb.hid.lock.locked(), "HID lock leaked by command")


# ---------------------------------------------------------------------------
# send_overlays
# ---------------------------------------------------------------------------

class TestSendOverlaysCancel(unittest.TestCase, LockCheckMixin):

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_cancel_set_before_start_returns_false_no_writes(self, MockConverter):
        MockConverter.return_value = _converter({KeyCode.KC_A.value: _overlay("dot")})
        keeb, device = make_keeb(auto_ack=True)
        cancel = threading.Event()
        cancel.set()

        self.assertFalse(keeb.send_overlays(["fake.png"], cancel))
        self.assertEqual(len(device.writes), 0)
        self.assert_lock_free(keeb)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_cancel_after_first_keycode_skips_rest_and_enable(self, MockConverter):
        keys = {
            KeyCode.KC_A.value: _overlay("dot"),
            KeyCode.KC_B.value: _overlay("dot"),
            KeyCode.KC_C.value: _overlay("dot"),
        }
        MockConverter.return_value = _converter(keys)
        keeb, device = make_keeb(auto_ack=True)
        cancel = threading.Event()

        # Cancel as soon as the first keycap image has gone out; the loop checks
        # cancel before each subsequent keycode, so only the first is sent.
        real_send = keeb.send_smallest_overlay
        sent_keycodes = []

        def tracking_send(keycode, modifier, mapping):
            sent_keycodes.append(keycode)
            count = real_send(keycode, modifier, mapping)
            cancel.set()
            return count

        keeb.send_smallest_overlay = tracking_send

        self.assertFalse(keeb.send_overlays(["fake.png"], cancel))
        self.assertEqual(len(sent_keycodes), 1)   # remaining keycodes not sent
        self.assertNotIn(ENABLE_OVERLAYS,
                         [p[:3] for p in device.payloads()])  # no enable_overlays
        self.assert_lock_free(keeb)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_cancel_interrupts_rate_limit_pause_promptly(self, MockConverter):
        # max=0 => the rate-limit pause fires after the first modifier batch;
        # delay=30s would hang the test if cancel.wait() were a plain sleep.
        keys = {KeyCode.KC_A.value: _overlay("rect")}
        MockConverter.return_value = _converter(keys)
        settings = StubPolySettings(max_hid_message_before_delay=0,
                                    delay_time_after_max_hid_messages=30)
        keeb, device = make_keeb(auto_ack=True, settings=settings)
        cancel = threading.Event()

        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)

        start = time.perf_counter()
        result = keeb.send_overlays(["fake.png"], cancel)
        elapsed = time.perf_counter() - start

        self.assertFalse(result)
        self.assertLess(elapsed, 5.0)   # well under the 30s delay
        self.assertNotIn(ENABLE_OVERLAYS, [p[:3] for p in device.payloads()])
        self.assert_lock_free(keeb)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_cancel_none_behaves_as_before(self, MockConverter):
        MockConverter.return_value = _converter({KeyCode.KC_A.value: _overlay("dot")})
        keeb, device = make_keeb(auto_ack=True)

        self.assertTrue(keeb.send_overlays(["fake.png"], cancel=None))
        enables = [p for p in device.payloads() if p[:3] == ENABLE_OVERLAYS]
        self.assertEqual(len(enables), 1)   # enable sent exactly once
        self.assert_lock_free(keeb)


# ---------------------------------------------------------------------------
# press_and_release_key
# ---------------------------------------------------------------------------

class TestPressAndReleaseCancel(unittest.TestCase, LockCheckMixin):

    def test_cancel_shortens_hold_but_release_still_sent(self):
        keeb, device = make_keeb(auto_ack=True)
        cancel = threading.Event()
        cancel.set()   # already set: the hold wait returns immediately

        start = time.perf_counter()
        ok, _ = keeb.press_and_release_key(0x0029, 30, cancel)
        elapsed = time.perf_counter() - start

        self.assertTrue(ok)
        self.assertLess(elapsed, 5.0)   # hold cut short, not a 30s sleep
        payloads = device.payloads()
        self.assertEqual(payloads[0][:5], bytes([POLY, 14, 0x00, 0x29, 0]))  # press
        self.assertEqual(payloads[1][:5], bytes([POLY, 14, 0x00, 0x29, 1]))  # release
        self.assert_lock_free(keeb)


# ---------------------------------------------------------------------------
# execute_commands
# ---------------------------------------------------------------------------

class TestExecuteCommandsCancel(unittest.TestCase):

    def test_wait_interrupted_and_following_commands_skipped(self):
        keeb, device = make_keeb()
        keeb.press_key = MagicMock(return_value=(True, ""))
        cancel = threading.Event()

        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        self.addCleanup(timer.cancel)

        start = time.perf_counter()
        keeb.execute_commands(["wait 30", "press 0x29"], cancel)
        elapsed = time.perf_counter() - start

        self.assertLess(elapsed, 5.0)            # the wait was interrupted
        keeb.press_key.assert_not_called()       # command after cancel not run


# ---------------------------------------------------------------------------
# send_overlays_mru
# ---------------------------------------------------------------------------

class TestSendOverlaysMruCancel(unittest.TestCase, LockCheckMixin):

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_cancel_after_first_image_skips_mapping_and_enable(self, MockConverter):
        keys = {
            KeyCode.KC_A.value: _overlay("dot"),
            KeyCode.KC_B.value: _overlay("dot"),
            KeyCode.KC_C.value: _overlay("dot"),
        }
        MockConverter.return_value = _converter(keys)
        keeb, device = make_keeb(auto_ack=True)
        cache = OverlayMRUCache(20)
        cancel = threading.Event()

        real_send = keeb.send_smallest_overlay
        sent = []

        def tracking_send(keycode, modifier, mapping):
            sent.append(keycode)
            count = real_send(keycode, modifier, mapping)
            cancel.set()   # cancel right after the first image is transferred
            return count

        keeb.send_smallest_overlay = tracking_send

        self.assertFalse(keeb.send_overlays_mru(["fake.png"], cache, cancel))
        self.assertEqual(len(sent), 1)   # remaining images not sent

        cmd_ids = [p[1] for p in device.payloads()]
        self.assertNotIn(SEND_OVERLAY_MAPPING, cmd_ids)   # no mapping command
        self.assertNotIn(ENABLE_OVERLAYS,
                         [p[:3] for p in device.payloads()])  # no enable_overlays
        self.assert_lock_free(keeb)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_cancel_none_sends_mapping_and_enable(self, MockConverter):
        MockConverter.return_value = _converter({KeyCode.KC_A.value: _overlay("dot")})
        keeb, device = make_keeb(auto_ack=True)
        cache = OverlayMRUCache(20)

        self.assertTrue(keeb.send_overlays_mru(["fake.png"], cache, cancel=None))
        cmd_ids = [p[1] for p in device.payloads()]
        self.assertIn(SEND_OVERLAY_MAPPING, cmd_ids)
        enables = [p for p in device.payloads() if p[:3] == ENABLE_OVERLAYS]
        self.assertEqual(len(enables), 1)
        self.assert_lock_free(keeb)


if __name__ == '__main__':
    unittest.main()
