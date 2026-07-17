"""Unit tests for the per-feature protocol capability model and the
version-dependent plain-overlay header encoding.

The host connects across a RANGE of firmware protocols (see
polyhost.core.decisions.decide_reconnect_apply) and gates each feature by its
minimum protocol via FEATURE_MIN_PROTOCOL. Additive features simply enable when
supported; the plain-overlay upload (the one core command whose wire format
changed at protocol 11) must instead be *encoded for the device's protocol* so
an older keyboard still receives the header it understands.
"""
import unittest
from unittest.mock import MagicMock

from polyhost.device.poly_kybd import (
    PolyKybd, protocol_supports, FEATURE_MIN_PROTOCOL, MIN_SUPPORTED_PROTOCOL,
    OVERLAY_PACKED_HEADER_MIN_PROTOCOL,
)
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.command_ids import HidId, Cmd
from polyhost.device.keys import Modifier
from polyhost.settings import PolySettings


class _Overlay:
    """Minimal stand-in for the object send_overlay_for_keycode consumes."""
    def __init__(self, all_bytes):
        self.all_bytes = all_bytes


class TestProtocolSupports(unittest.TestCase):
    def test_min_supported_is_the_packed_lang_list_floor(self):
        self.assertEqual(MIN_SUPPORTED_PROTOCOL, FEATURE_MIN_PROTOCOL["packed_lang_list"])

    def test_none_protocol_supports_nothing_gated(self):
        for feature in FEATURE_MIN_PROTOCOL:
            self.assertFalse(protocol_supports(None, feature))

    def test_threshold_is_inclusive(self):
        for feature, minp in FEATURE_MIN_PROTOCOL.items():
            self.assertTrue(protocol_supports(minp, feature), feature)
            self.assertFalse(protocol_supports(minp - 1, feature), feature)

    def test_high_protocol_supports_everything(self):
        highest = max(FEATURE_MIN_PROTOCOL.values())
        for feature in FEATURE_MIN_PROTOCOL:
            self.assertTrue(protocol_supports(highest, feature))


class TestCapabilities(unittest.TestCase):
    def _keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        return keeb

    def test_supports_matches_table(self):
        keeb = self._keeb(9)  # glyph_script threshold
        self.assertTrue(keeb.supports("glyph_script"))
        self.assertTrue(keeb.supports("os"))          # 7 <= 9
        self.assertFalse(keeb.supports("overlay_packed_header"))  # 11 > 9

    def test_capabilities_is_cached_only_no_io(self):
        keeb = self._keeb(4)
        caps = keeb.capabilities()
        # No device query was triggered (protocol was already known).
        keeb.hid.send_and_read_validate.assert_not_called()
        self.assertEqual(set(caps), set(FEATURE_MIN_PROTOCOL))
        self.assertTrue(caps["idle_style"])      # 4 <= 4
        self.assertFalse(caps["os"])             # 7 > 4

    def test_supports_lazily_queries_when_protocol_unknown(self):
        keeb = self._keeb(None)
        # query_version_info populates protocol_version from a GET_ID reply.
        keeb.query_version_info = MagicMock(
            side_effect=lambda: setattr(keeb, "protocol_version", 11) or (True, "x"))
        self.assertTrue(keeb.supports("overlay_packed_header"))
        keeb.query_version_info.assert_called_once()


class TestOverlayHeaderEncoding(unittest.TestCase):
    """The plain-overlay header must match the DEVICE's protocol.

    Protocol 11+: [id, cmd, keycode, (segment<<4)|modifier] + 60 data = 64 bytes.
    Pre-v11:      [id, cmd, keycode, modifier, segment]      + 60 data = 65 bytes.
    """
    KEYCODE = 0x04
    MOD = Modifier.SHIFT

    def _capture(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        keeb.hid.send_multiple.return_value = (True, b"")
        # 360 non-zero bytes so no segment is skipped as empty -> all 6 sent.
        data = bytes(((i % 250) + 1) for i in range(360))
        mapping = {self.KEYCODE: _Overlay(data)}
        sent = keeb.send_overlay_for_keycode(self.KEYCODE, self.MOD, mapping)
        self.assertEqual(sent, keeb.device_settings.OVERLAY_PLAIN_DATA_REPORT_COUNT)
        return [c.args[0] for c in keeb.hid.send_multiple.call_args_list]

    def test_packed_header_at_protocol_11(self):
        reports = self._capture(OVERLAY_PACKED_HEADER_MIN_PROTOCOL)
        for msg_num, rep in enumerate(reports):
            self.assertEqual(rep[0], HidId.ID_POLYKYBD.value)
            self.assertEqual(rep[1], Cmd.SEND_OVERLAY.value)
            self.assertEqual(rep[2], self.KEYCODE)
            # One packed header byte: (segment << 4) | modifier.
            self.assertEqual(rep[3], (msg_num << 4) | self.MOD.value)
            self.assertEqual(len(rep), 64)  # 4-byte header + 60 data

    def test_separate_header_pre_protocol_11(self):
        reports = self._capture(OVERLAY_PACKED_HEADER_MIN_PROTOCOL - 1)
        for msg_num, rep in enumerate(reports):
            self.assertEqual(rep[2], self.KEYCODE)
            # Two separate header bytes: modifier, then segment index.
            self.assertEqual(rep[3], self.MOD.value)
            self.assertEqual(rep[4], msg_num)
            self.assertEqual(len(rep), 65)  # 5-byte header + 60 data (pre-v11 form)

    def test_unknown_protocol_uses_pre_v11_form(self):
        # protocol_version None (pre-protocol firmware) -> the pre-v11 header.
        reports = self._capture(None)
        self.assertEqual(reports[0][3], self.MOD.value)
        self.assertEqual(reports[0][4], 0)


if __name__ == "__main__":
    unittest.main()
