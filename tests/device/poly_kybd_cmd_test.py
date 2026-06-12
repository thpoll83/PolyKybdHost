"""Characterization tests for the PolyKybd command surface.

Each test drives a real PolyKybd through a REAL HidHelper wired to a
FakeHidDevice (see tests/device/fake_hid.py), pinning the exact HID payloads,
reply parsing, error handling, and lock discipline of every command ahead of
the HID worker-thread / command-queue refactoring.

Invariant asserted throughout: after any PolyKybd call returns, the HID lock
must be free — a held lock here means a leaked lock in production.
"""
import unittest
from unittest import mock
from unittest.mock import MagicMock

import numpy as np

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd import PolyKybd
from polyhost.input.unicode_input import InputMethod

from tests.device.fake_hid import FakeHidDevice, make_hid_helper, pad, ack, nack

POLY = 0x50  # HidId.ID_POLYKYBD


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
    """OverlayData from a synthetic 40x72 image (same patterns as overlay_mock_test)."""
    img = np.zeros((40, 72), dtype=bool)
    if pattern == "dot":
        img[0, 0] = True
    elif pattern == "rect":
        img[5:20, 10:60] = True
    elif pattern == "noisy":
        rng = np.random.default_rng(seed=42)   # incompressible -> plain wins
        img[:] = rng.integers(0, 2, size=(40, 72), dtype=np.uint8).astype(bool)
    return OverlayData(DeviceSettings(), img)


class LockCheckMixin:
    def assert_lock_free(self, keeb):
        self.assertFalse(keeb.hid.lock.locked(), "HID lock leaked by command")


# ---------------------------------------------------------------------------
# Identity / version
# ---------------------------------------------------------------------------

class TestQueryId(unittest.TestCase, LockCheckMixin):

    def test_ack_returns_id_string(self):
        keeb, device = make_keeb(replies=[ack(0x06, b'PolyKybd Split72 0.8.6 P7 HW1')])
        ok, msg = keeb.query_id()
        self.assertTrue(ok)
        self.assertEqual(msg, 'PolyKybd Split72 0.8.6 P7 HW1')
        self.assertFalse(keeb.pop_fresh_boot())
        self.assert_lock_free(keeb)

    def test_request_payload(self):
        keeb, device = make_keeb(replies=[ack(0x06, b'x')])
        keeb.query_id()
        self.assertEqual(device.payloads()[0][:2], bytes([POLY, 0x06]))

    def test_fresh_boot_marker_sets_flag_once(self):
        keeb, device = make_keeb(replies=[pad(b'P\x06*PolyKybd Split72 0.8.6 P7 HW1')])
        ok, msg = keeb.query_id()
        self.assertTrue(ok)
        self.assertTrue(keeb.pop_fresh_boot())
        self.assertFalse(keeb.pop_fresh_boot())  # cleared after pop

    def test_no_reply_returns_false(self):
        keeb, device = make_keeb()
        ok, msg = keeb.query_id()
        self.assertFalse(ok)
        self.assert_lock_free(keeb)

    def test_exception_returns_false(self):
        keeb, device = make_keeb()
        device.write_exception = RuntimeError("USB gone")
        ok, msg = keeb.query_id()
        self.assertFalse(ok)
        self.assertIn("Exception", msg)
        self.assert_lock_free(keeb)


class TestQueryVersionInfo(unittest.TestCase, LockCheckMixin):

    def test_parses_name_version_protocol_hw(self):
        keeb, device = make_keeb(replies=[ack(0x06, b'PolyKybd Split72 0.8.6 P7 HW1')])
        ok, msg = keeb.query_version_info()
        self.assertTrue(ok)
        self.assertEqual(keeb.get_name(), 'PolyKybd Split72')
        self.assertEqual(keeb.get_sw_version(), '0.8.6')
        self.assertEqual(keeb.get_sw_version_number(), [0, 8, 6])
        self.assertEqual(keeb.get_protocol_version(), 7)
        self.assertEqual(keeb.get_hw_version(), '1')
        self.assert_lock_free(keeb)

    def test_old_format_without_protocol(self):
        keeb, device = make_keeb(replies=[ack(0x06, b'PolyKybd Split72 0.7.0 HW1')])
        ok, msg = keeb.query_version_info()
        self.assertTrue(ok)
        self.assertIsNone(keeb.get_protocol_version())
        self.assertEqual(keeb.get_sw_version(), '0.7.0')

    def test_unparseable_version_string_fails(self):
        keeb, device = make_keeb(replies=[ack(0x06, b'garbage')])
        ok, msg = keeb.query_version_info()
        self.assertFalse(ok)
        self.assertIn("update firmware", msg)


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

class TestLanguageCommands(unittest.TestCase, LockCheckMixin):

    def test_query_current_lang(self):
        keeb, device = make_keeb(replies=[ack(0x07, b'enUS')])
        ok, lang = keeb.query_current_lang()
        self.assertTrue(ok)
        self.assertEqual(lang, 'enUS')
        self.assertEqual(keeb.get_current_lang(), 'enUS')
        self.assert_lock_free(keeb)

    def test_query_current_lang_no_reply(self):
        keeb, device = make_keeb()
        ok, msg = keeb.query_current_lang()
        self.assertFalse(ok)
        self.assert_lock_free(keeb)

    def test_change_language_success(self):
        keeb, device = make_keeb(replies=[ack(0x09, b'deDE')])
        keeb.all_languages = ['enUS', 'deDE']
        ok, lang = keeb.change_language('deDE')
        self.assertTrue(ok)
        self.assertEqual(lang, 'deDE')
        # payload: ID + CHANGE_LANG + ASCII language code
        self.assertEqual(device.payloads()[0][:6], bytes([POLY, 0x09]) + b'deDE')
        self.assert_lock_free(keeb)

    def test_change_language_not_in_list_sends_nothing(self):
        keeb, device = make_keeb()
        keeb.all_languages = ['enUS']
        ok, msg = keeb.change_language('xxXX')
        self.assertFalse(ok)
        self.assertEqual(len(device.writes), 0)

    def test_change_language_nack(self):
        keeb, device = make_keeb(replies=[nack(0x09)])
        keeb.all_languages = ['deDE']
        ok, msg = keeb.change_language('deDE')
        # The NACK reply 'P\x09!' passes the 2-byte prefix validation in the
        # HID layer; change_language must reject it via the ACK marker byte.
        self.assertFalse(ok)
        self.assertIn('deDE', msg)
        self.assert_lock_free(keeb)


# ---------------------------------------------------------------------------
# Simple state commands — exact payload bytes
# ---------------------------------------------------------------------------

class TestSimpleCommandPayloads(unittest.TestCase, LockCheckMixin):
    """Pin the exact bytes each command puts on the wire."""

    def _payload(self, call, *args):
        keeb, device = make_keeb(auto_ack=True)
        ok, _ = getattr(keeb, call)(*args)
        self.assertTrue(ok)
        self.assert_lock_free(keeb)
        return device.payloads()[0]

    def test_enable_overlays(self):
        self.assertEqual(self._payload('enable_overlays')[:3], bytes([POLY, 11, 0x01]))

    def test_disable_overlays(self):
        self.assertEqual(self._payload('disable_overlays')[:3], bytes([POLY, 12, 0x01]))

    def test_reset_overlays(self):
        self.assertEqual(self._payload('reset_overlays')[:3], bytes([POLY, 11, 0x20]))

    def test_reset_overlay_usage(self):
        self.assertEqual(self._payload('reset_overlay_usage')[:3], bytes([POLY, 11, 0x40]))

    def test_reset_overlay_mapping(self):
        self.assertEqual(self._payload('reset_overlay_mapping')[:3], bytes([POLY, 11, 0x80]))

    def test_reset_overlays_and_usage(self):
        self.assertEqual(self._payload('reset_overlays_and_usage')[:3], bytes([POLY, 11, 0x60]))

    def test_reset_overlay_mapping_and_usage(self):
        self.assertEqual(self._payload('reset_overlay_mapping_and_usage')[:3], bytes([POLY, 11, 0xC0]))

    def test_prepare_for_mru_send_combines_mirror_and_resets(self):
        self.assertEqual(self._payload('prepare_for_mru_send')[:3], bytes([POLY, 11, 0xC4]))

    def test_set_all_overlay_usage(self):
        self.assertEqual(self._payload('set_all_overlay_usage')[:3], bytes([POLY, 11, 0x02]))

    def test_mirror_overlays_on(self):
        self.assertEqual(self._payload('set_mirror_overlays', True)[:3], bytes([POLY, 11, 0x04]))

    def test_mirror_overlays_off(self):
        self.assertEqual(self._payload('set_mirror_overlays', False)[:3], bytes([POLY, 12, 0x04]))

    def test_set_unicode_mode(self):
        self.assertEqual(self._payload('set_unicode_mode', InputMethod.WinCompose)[:3],
                         bytes([POLY, 20, 3]))

    def test_set_idle_on_off(self):
        self.assertEqual(self._payload('set_idle', True)[:3], bytes([POLY, 15, 1]))
        self.assertEqual(self._payload('set_idle', False)[:3], bytes([POLY, 15, 0]))

    def test_save_mru(self):
        self.assertEqual(self._payload('save_mru')[:2], bytes([POLY, 26]))

    def test_brightness_payload(self):
        self.assertEqual(self._payload('set_brightness', 30)[:3], bytes([POLY, 13, 30]))

    def test_brightness_clipped_to_max_50(self):
        self.assertEqual(self._payload('set_brightness', 100)[2], 50)

    def test_brightness_clipped_to_min_0(self):
        self.assertEqual(self._payload('set_brightness', -5)[2], 0)


class TestSendOnlyCommands(unittest.TestCase, LockCheckMixin):
    """Bootloader / handedness reset the device immediately: send, no ACK wait."""

    def test_activate_bootloader_sends_without_reply(self):
        keeb, device = make_keeb()   # no replies queued — must still succeed
        ok, _ = keeb.activate_bootloader()
        self.assertTrue(ok)
        self.assertEqual(device.payloads()[0][:2], bytes([POLY, 23]))
        self.assert_lock_free(keeb)

    def test_set_handedness_master_left(self):
        keeb, device = make_keeb()
        ok, _ = keeb.set_handedness(True)
        self.assertTrue(ok)
        self.assertEqual(device.payloads()[0][:3], bytes([POLY, 25, 0]))

    def test_set_handedness_master_right(self):
        keeb, device = make_keeb()
        ok, _ = keeb.set_handedness(False)
        self.assertTrue(ok)
        self.assertEqual(device.payloads()[0][:3], bytes([POLY, 25, 1]))


class TestKeypressCommands(unittest.TestCase, LockCheckMixin):

    def test_press_key_payload(self):
        keeb, device = make_keeb(auto_ack=True)
        ok, _ = keeb.press_key(0x1234)
        self.assertTrue(ok)
        self.assertEqual(device.payloads()[0][:5], bytes([POLY, 14, 0x12, 0x34, 0]))
        self.assert_lock_free(keeb)

    def test_release_key_payload(self):
        keeb, device = make_keeb(auto_ack=True)
        ok, _ = keeb.release_key(0x1234)
        self.assertTrue(ok)
        self.assertEqual(device.payloads()[0][:5], bytes([POLY, 14, 0x12, 0x34, 1]))

    @mock.patch("polyhost.device.poly_kybd.time.sleep")
    def test_press_and_release_holds_for_duration(self, sleep):
        keeb, device = make_keeb(auto_ack=True)
        ok, _ = keeb.press_and_release_key(0x0029, 0.25)
        self.assertTrue(ok)
        sleep.assert_called_once_with(0.25)
        payloads = device.payloads()
        self.assertEqual(payloads[0][:5], bytes([POLY, 14, 0x00, 0x29, 0]))  # press
        self.assertEqual(payloads[1][:5], bytes([POLY, 14, 0x00, 0x29, 1]))  # release
        self.assert_lock_free(keeb)


# ---------------------------------------------------------------------------
# Dynamic keymap (VIA-style requests)
# ---------------------------------------------------------------------------

class TestDynamicKeymap(unittest.TestCase, LockCheckMixin):

    def test_get_default_layer(self):
        keeb, device = make_keeb(replies=[ack(22, bytes([3]))])
        ok, layer = keeb.get_default_layer()
        self.assertTrue(ok)
        self.assertEqual(layer, 3)
        self.assert_lock_free(keeb)

    def test_get_default_layer_nack_returns_zero(self):
        keeb, device = make_keeb(replies=[nack(22)])
        ok, layer = keeb.get_default_layer()
        self.assertFalse(ok)
        self.assertEqual(layer, 0)

    def test_get_dynamic_keycode(self):
        reply = pad(bytes([4, 1, 2, 3, 0x12, 0x34]))   # echo + keycode hi/lo
        keeb, device = make_keeb(replies=[reply])
        ok, keycode = keeb.get_dynamic_keycode(1, 2, 3)
        self.assertTrue(ok)
        self.assertEqual(keycode, 0x1234)
        self.assertEqual(device.payloads()[0][:4], bytes([4, 1, 2, 3]))
        self.assert_lock_free(keeb)

    def test_set_dynamic_keycode_payload(self):
        keeb, device = make_keeb(auto_ack=True)   # echo reply validates
        ok, _ = keeb.set_dynamic_keycode(2, 4, 6, 0x1234)
        self.assertTrue(ok)
        self.assertEqual(device.payloads()[0][:6], bytes([5, 2, 4, 6, 0x12, 0x34]))
        self.assert_lock_free(keeb)

    def test_get_dynamic_layer_count_cached_after_first_query(self):
        keeb, device = make_keeb(replies=[pad(bytes([17, 9]))])
        ok, count = keeb.get_dynamic_layer_count()
        self.assertTrue(ok)
        self.assertEqual(count, 9)
        ok, count = keeb.get_dynamic_layer_count()   # second call: no HID traffic
        self.assertEqual(count, 9)
        self.assertEqual(len(device.writes), 1)

    def test_reset_dynamic_keymap(self):
        keeb, device = make_keeb()
        ok, _ = keeb.reset_dynamic_keymap()
        self.assertTrue(ok)
        self.assertEqual(device.payloads()[0][0], 6)

    def test_get_dynamic_buffer_chunks_and_byte_order(self):
        # 1 layer x 10 rows x 8 cols x 2 bytes = 160 bytes, rounded up to
        # 3 requests x 60 bytes = 180; keycodes are big-endian on the wire.
        keeb, device = make_keeb()
        keeb.num_layers = 1
        data = bytes([i % 256 for i in range(180)])
        for offset in range(0, 180, 60):
            reply = bytes([18, offset >> 8, offset & 0xFF, 60]) + data[offset:offset + 60]
            device.replies.append(pad(reply))
        ok, buffer = keeb.get_dynamic_buffer()
        self.assertTrue(ok)
        self.assertEqual(len(buffer), 90)
        self.assertEqual(buffer[0], 0x0001)          # bytes 0x00,0x01 big-endian
        self.assertEqual(buffer[1], 0x0203)
        # offsets requested in order
        offsets = [(p[1] << 8) | p[2] for p in device.payloads()]
        self.assertEqual(offsets, [0, 60, 120])
        self.assert_lock_free(keeb)

    def test_get_dynamic_buffer_partial_failure_returns_false(self):
        keeb, device = make_keeb()
        keeb.num_layers = 1
        device.replies.append(pad(bytes([18, 0, 0, 60]) + bytes(60)))
        # second/third request get no reply -> failure mid-transfer
        ok, partial = keeb.get_dynamic_buffer()
        self.assertFalse(ok)
        self.assertEqual(len(partial), 30)   # one 60-byte chunk = 30 keycodes
        self.assert_lock_free(keeb)


# ---------------------------------------------------------------------------
# Overlay mapping
# ---------------------------------------------------------------------------

class TestSendOverlayMapping(unittest.TestCase, LockCheckMixin):

    def test_single_chunk_padded_with_noop_keys(self):
        keeb, device = make_keeb(auto_ack=True)
        ok, msg = keeb.send_overlay_mapping({1: 100, 2: 200})
        self.assertTrue(ok)
        self.assertEqual(len(device.writes), 1)
        payload = device.payloads()[0]
        self.assertEqual(payload[:2], bytes([POLY, 21]))
        # 24 pairs x 2 x 10 bit = 60 packed bytes after the 2 command bytes
        self.assertEqual(len(payload), 64)
        self.assert_lock_free(keeb)

    def test_more_pairs_than_chunk_size_split_into_two_messages(self):
        keeb, device = make_keeb(auto_ack=True)
        mapping = {i: i + 100 for i in range(25)}   # chunk size is 24 pairs
        ok, msg = keeb.send_overlay_mapping(mapping)
        self.assertTrue(ok)
        self.assertEqual(len(device.writes), 2)
        self.assert_lock_free(keeb)

    def test_write_failure_aborts_and_frees_lock(self):
        keeb, device = make_keeb()
        device.write_exception = RuntimeError("USB gone")
        ok, msg = keeb.send_overlay_mapping({1: 100})
        self.assertFalse(ok)
        self.assert_lock_free(keeb)

    def test_mapping_send_performs_no_reads(self):
        # Protocol v3: cmd 21 is fire-and-forget (firmware sends no per-chunk
        # ACK), so the host must not read or drain after sending. A queued
        # sentinel reply surviving the call proves no read happened.
        sentinel = ack(0x06, b'sentinel')
        keeb, device = make_keeb(replies=[sentinel])
        ok, msg = keeb.send_overlay_mapping({1: 100, 2: 200})
        self.assertTrue(ok)
        self.assertEqual(len(device.replies), 1)
        self.assertEqual(device.replies[0], sentinel)
        self.assert_lock_free(keeb)


# ---------------------------------------------------------------------------
# Overlay transmission paths
# ---------------------------------------------------------------------------

class TestOverlaySendPaths(unittest.TestCase, LockCheckMixin):

    def test_send_smallest_overlay_dispatches_by_message_count(self):
        keeb, _ = make_keeb()
        keeb.send_overlay_roi_for_keycode = MagicMock(return_value=1)
        keeb.send_overlay_for_keycode_compressed = MagicMock(return_value=1)
        keeb.send_overlay_for_keycode = MagicMock(return_value=1)

        class Counts:
            pass

        ov = Counts()
        ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs = 6, 3, 1, 2
        keeb.send_smallest_overlay(0x29, Modifier.NO_MOD, {0x29: ov})
        keeb.send_overlay_roi_for_keycode.assert_called_once_with(
            0x29, Modifier.NO_MOD, {0x29: ov}, False)

        ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs = 6, 1, 3, 2
        keeb.send_smallest_overlay(0x29, Modifier.NO_MOD, {0x29: ov})
        keeb.send_overlay_for_keycode_compressed.assert_called_once()

        ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs = 6, 3, 4, 1
        keeb.send_smallest_overlay(0x29, Modifier.NO_MOD, {0x29: ov})
        keeb.send_overlay_roi_for_keycode.assert_called_with(
            0x29, Modifier.NO_MOD, {0x29: ov}, True)

        ov.all_msgs, ov.compressed_msgs, ov.roi_msgs, ov.compressed_roi_msgs = 1, 3, 4, 2
        keeb.send_smallest_overlay(0x29, Modifier.NO_MOD, {0x29: ov})
        keeb.send_overlay_for_keycode.assert_called_once()

    def test_plain_overlay_skips_empty_reports_but_sends_last(self):
        # single top-left pixel: report 0 has data, 1-4 are empty (skipped),
        # the final report is always sent as the end marker.
        keeb, device = make_keeb()
        overlay = _overlay("dot")
        count = keeb.send_overlay_for_keycode(0x29, Modifier.NO_MOD, {0x29: overlay})
        self.assertEqual(count, 2)
        payloads = device.payloads()
        self.assertEqual(payloads[0][:5], bytes([POLY, 10, 0x29, 0, 0]))   # msg_num 0
        self.assertEqual(payloads[1][:5], bytes([POLY, 10, 0x29, 0, 5]))   # last msg_num
        self.assert_lock_free(keeb)

    def test_plain_overlay_without_skip_sends_all_reports(self):
        keeb, device = make_keeb()
        overlay = _overlay("dot")
        count = keeb.send_overlay_for_keycode(0x29, Modifier.NO_MOD, {0x29: overlay},
                                              skip_empty=False)
        settings = DeviceSettings()
        self.assertEqual(count, settings.OVERLAY_PLAIN_DATA_REPORT_COUNT)
        self.assertEqual(len(device.writes), settings.OVERLAY_PLAIN_DATA_REPORT_COUNT)

    def test_compressed_overlay_header_and_continuation(self):
        keeb, device = make_keeb()
        overlay = _overlay("rect")
        count = keeb.send_overlay_for_keycode_compressed(0x29, Modifier.SHIFT, {0x29: overlay})
        self.assertEqual(count, overlay.compressed_msgs)
        payloads = device.payloads()
        self.assertEqual(payloads[0][:4], bytes([POLY, 16, 0x29, Modifier.SHIFT.value]))
        for cont in payloads[1:]:
            self.assertEqual(cont[:2], bytes([POLY, 17]))
        self.assert_lock_free(keeb)

    def test_roi_overlay_header_and_continuation(self):
        keeb, device = make_keeb()
        overlay = _overlay("rect")
        count = keeb.send_overlay_roi_for_keycode(0x29, Modifier.NO_MOD, {0x29: overlay},
                                                  compressed=False)
        self.assertEqual(count, overlay.roi_msgs)
        payloads = device.payloads()
        self.assertEqual(payloads[0][:3], bytes([POLY, 18, 0x29]))
        for cont in payloads[1:]:
            self.assertEqual(cont[:2], bytes([POLY, 19]))
        self.assert_lock_free(keeb)

    def test_roi_overlay_without_roi_falls_back_to_compressed(self):
        keeb, _ = make_keeb()
        keeb.send_overlay_for_keycode_compressed = MagicMock(return_value=4)

        class NoRoi:
            roi = None

        count = keeb.send_overlay_roi_for_keycode(0x29, Modifier.NO_MOD, {0x29: NoRoi()},
                                                  compressed=True)
        self.assertEqual(count, 4)
        keeb.send_overlay_for_keycode_compressed.assert_called_once()

    def test_overlay_write_failure_frees_lock(self):
        keeb, device = make_keeb()
        device.write_exception = RuntimeError("USB gone")
        overlay = _overlay("rect")
        keeb.send_overlay_for_keycode_compressed(0x29, Modifier.NO_MOD, {0x29: overlay})
        self.assert_lock_free(keeb)

    def test_overlay_write_failure_returns_negative(self):
        # A failed send must be distinguishable from a successful one — the
        # ROI sender used to return num_msgs (the success value) on failure,
        # so send_overlays/send_overlays_mru could not detect it.
        keeb, device = make_keeb()
        device.write_exception = RuntimeError("USB gone")
        overlay = _overlay("rect")
        self.assertEqual(
            keeb.send_overlay_for_keycode(0x29, Modifier.NO_MOD, {0x29: overlay}), -1)
        self.assertEqual(
            keeb.send_overlay_for_keycode_compressed(0x29, Modifier.NO_MOD, {0x29: overlay}), -1)
        self.assertEqual(
            keeb.send_overlay_roi_for_keycode(0x29, Modifier.NO_MOD, {0x29: overlay},
                                              compressed=False), -1)
        self.assert_lock_free(keeb)


class TestSendOverlays(unittest.TestCase, LockCheckMixin):
    """send_overlays end-to-end with a patched ImageConverter."""

    def _converter(self, overlay_map):
        converter = MagicMock()
        converter.open.return_value = True
        converter.extract_overlays.side_effect = (
            lambda mod: dict(overlay_map) if mod == Modifier.NO_MOD else None)
        return converter

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_esc_sent_first_then_enable_then_rest(self, MockConverter):
        esc, key_a = KeyCode.KC_ESCAPE.value, KeyCode.KC_A.value
        MockConverter.return_value = self._converter(
            {key_a: _overlay("rect"), esc: _overlay("dot")})
        keeb, device = make_keeb(auto_ack=True)
        self.assertTrue(keeb.send_overlays(["fake.png"]))

        payloads = device.payloads()
        enable_idx = next(i for i, p in enumerate(payloads)
                          if p[:3] == bytes([POLY, 11, 0x01]))
        esc_idx = next(i for i, p in enumerate(payloads)
                       if p[1] in (10, 16, 18) and p[2] == esc)
        a_idx = next(i for i, p in enumerate(payloads)
                     if p[1] in (10, 16, 18) and p[2] == key_a)
        # ESC image first, then overlays enabled, then the remaining keys
        self.assertLess(esc_idx, enable_idx)
        self.assertLess(enable_idx, a_idx)
        self.assertEqual(sum(1 for p in payloads if p[:3] == bytes([POLY, 11, 0x01])), 1)
        self.assert_lock_free(keeb)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_enable_sent_even_without_esc_overlay(self, MockConverter):
        MockConverter.return_value = self._converter({KeyCode.KC_A.value: _overlay("dot")})
        keeb, device = make_keeb(auto_ack=True)
        self.assertTrue(keeb.send_overlays(["fake.png"]))
        enables = [p for p in device.payloads() if p[:3] == bytes([POLY, 11, 0x01])]
        self.assertEqual(len(enables), 1)

    @mock.patch("polyhost.device.poly_kybd.time.sleep")
    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_rate_limit_sleep_after_max_messages(self, MockConverter, sleep):
        MockConverter.return_value = self._converter({KeyCode.KC_A.value: _overlay("rect")})
        settings = StubPolySettings(max_hid_message_before_delay=0,
                                    delay_time_after_max_hid_messages=0.123)
        keeb, device = make_keeb(auto_ack=True, settings=settings)
        self.assertTrue(keeb.send_overlays(["fake.png"]))
        sleep.assert_called_with(0.123)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_unreadable_file_returns_false(self, MockConverter):
        converter = MockConverter.return_value
        converter.open.return_value = False
        keeb, device = make_keeb()
        self.assertFalse(keeb.send_overlays(["missing.png"]))
        self.assertEqual(len(device.writes), 0)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_send_failure_aborts_and_returns_false(self, MockConverter):
        MockConverter.return_value = self._converter({KeyCode.KC_A.value: _overlay("dot")})
        keeb, device = make_keeb()
        device.write_exception = RuntimeError("USB gone")
        self.assertFalse(keeb.send_overlays(["fake.png"]))
        # aborted before enable_overlays
        self.assertNotIn(bytes([POLY, 11, 0x01]), device.payloads())
        self.assert_lock_free(keeb)


class TestSendOverlaysMruFailure(unittest.TestCase, LockCheckMixin):
    """send_overlays_mru must abort (and skip the mapping commit) when the
    prepare command or a pool upload fails — recording a mapping for an image
    that never reached the keyboard becomes a permanent stale MRU hit."""

    def _converter(self, overlay_map):
        converter = MagicMock()
        converter.open.return_value = True
        converter.extract_overlays.side_effect = (
            lambda mod: dict(overlay_map) if mod == Modifier.NO_MOD else None)
        return converter

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_prepare_failure_returns_false_without_uploads(self, MockConverter):
        MockConverter.return_value = self._converter({KeyCode.KC_A.value: _overlay("dot")})
        keeb, device = make_keeb()   # no replies: prepare's read times out
        cache = OverlayMRUCache(20)
        self.assertFalse(keeb.send_overlays_mru(["fake.png"], cache))
        self.assertEqual(len(device.payloads()), 1)   # only the prepare command
        self.assert_lock_free(keeb)

    @mock.patch("polyhost.device.poly_kybd.ImageConverter")
    def test_upload_failure_skips_mapping_commit(self, MockConverter):
        MockConverter.return_value = self._converter({KeyCode.KC_A.value: _overlay("dot")})
        # Let the prepare command succeed, then fail every later write.
        keeb, device = make_keeb(replies=[ack(11)])
        cache = OverlayMRUCache(20)
        original_write = device.write
        state = {"writes": 0}

        def write_fails_after_prepare(report):
            state["writes"] += 1
            if state["writes"] > 1:    # write 1 = prepare command
                raise RuntimeError("USB gone")
            return original_write(report)
        device.write = write_fails_after_prepare

        self.assertFalse(keeb.send_overlays_mru(["fake.png"], cache))
        self.assertNotIn(21, [p[1] for p in device.payloads()])   # no mapping cmd
        self.assertNotIn(bytes([POLY, 11, 0x01]), device.payloads())  # no enable
        self.assert_lock_free(keeb)


# ---------------------------------------------------------------------------
# Connect / reconnect
# ---------------------------------------------------------------------------

class TestConnect(unittest.TestCase):

    @mock.patch("polyhost.device.poly_kybd.SerialHelper")
    @mock.patch("polyhost.device.poly_kybd.HidHelper")
    def test_first_connect_opens_interfaces(self, MockHid, MockSerial):
        keeb = PolyKybd(DeviceSettings(), StubPolySettings())
        self.assertTrue(keeb.connect())
        MockHid.assert_called_once()
        MockSerial.assert_called_once()

    @mock.patch("polyhost.device.poly_kybd.SerialHelper")
    @mock.patch("polyhost.device.poly_kybd.HidHelper")
    def test_first_connect_failure_leaves_clean_state(self, MockHid, MockSerial):
        MockHid.side_effect = RuntimeError("no permission")
        keeb = PolyKybd(DeviceSettings(), StubPolySettings())
        self.assertFalse(keeb.connect())
        self.assertIsNone(keeb.hid)
        self.assertIsNone(keeb.serial)

    def test_reconnect_succeeds_when_device_answers(self):
        keeb, device = make_keeb(auto_ack=True)
        self.assertTrue(keeb.connect())
        self.assertEqual(len(device.writes), 1)   # single GET_ID, no re-enumeration

    def test_reconnect_reenumerates_after_exhausted_retries(self):
        keeb, device = make_keeb()    # no replies: every query_id times out
        keeb._open_interfaces = MagicMock(return_value=False)
        self.assertFalse(keeb.connect())
        # hid_reconnect_retries=2 in StubPolySettings
        self.assertEqual(len(device.writes), 2)
        keeb._open_interfaces.assert_called_once()


# ---------------------------------------------------------------------------
# Command file execution & console
# ---------------------------------------------------------------------------

class TestExecuteCommands(unittest.TestCase):

    def _instrumented_keeb(self):
        keeb, device = make_keeb()
        for name in ("press_key", "release_key", "send_overlays", "reset_overlays",
                     "reset_overlay_usage", "reset_overlay_mapping"):
            setattr(keeb, name, MagicMock(return_value=(True, "")))
        return keeb

    @mock.patch("polyhost.device.poly_kybd.time.sleep")
    def test_dispatch(self, sleep):
        keeb = self._instrumented_keeb()
        keeb.execute_commands([
            "wait 0.5",
            "press 0x29",
            "release 0x29",
            "overlay send foo.png",
            "overlay reset",
            "overlay reset-usage",
            "overlay reset-mapping",
        ])
        sleep.assert_called_once_with(0.5)
        keeb.press_key.assert_called_once_with(0x29)
        keeb.release_key.assert_called_once_with(0x29)
        keeb.send_overlays.assert_called_once_with(["foo.png"])
        keeb.reset_overlays.assert_called_once()
        keeb.reset_overlay_usage.assert_called_once()
        keeb.reset_overlay_mapping.assert_called_once()

    def test_unknown_and_malformed_commands_do_not_raise(self):
        keeb = self._instrumented_keeb()
        keeb.execute_commands(["bogus", "press notanumber", "overlay frobnicate x"])
        keeb.press_key.assert_not_called()


class TestConsoleOutput(unittest.TestCase):

    def test_accumulates_and_flushes(self):
        keeb, _ = make_keeb()
        console = FakeHidDevice(replies=[pad(b'boot ok'), b''])
        keeb.hid = make_hid_helper(FakeHidDevice(), console=console)
        out = keeb.get_console_output()
        self.assertEqual(out, 'boot ok')

    def test_no_flush_buffers_for_later(self):
        keeb, _ = make_keeb()
        console = FakeHidDevice(replies=[pad(b'part1'), b''])
        keeb.hid = make_hid_helper(FakeHidDevice(), console=console)
        self.assertIsNone(keeb.get_console_output(flush_and_return=False))
        console.replies.extend([pad(b'part2'), b''])
        self.assertEqual(keeb.get_console_output(), 'part1part2')


if __name__ == '__main__':
    unittest.main()
