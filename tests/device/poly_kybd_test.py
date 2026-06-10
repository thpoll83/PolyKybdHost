"""Unit tests for PolyKybd.enumerate_lang multi-packet reading.

The firmware sends 6 HID reports in sequence for GET_LANG_LIST.
These tests verify that all 6 are consumed and parsed, not just the first.
"""
import unittest
from unittest.mock import MagicMock

from polyhost.device.poly_kybd import PolyKybd, PACKED_LANG_LIST_MIN_PROTOCOL
from polyhost.device.device_settings import DeviceSettings
from polyhost.settings import PolySettings
from polyhost.services import iso_lang_country as iso


def _pad(data: bytes, size: int = 64) -> bytes:
    return data + b'\x00' * (size - len(data))


# Exact firmware GET_LANG_LIST response packets (from hid_com.c case 8)
_P1 = _pad(b"P\x08.enUSdeDEfrFResESptPTitITtrTRkoKRjaJParSAelGRukUAruRUbeBYkkKZ")
_P2 = _pad(b"P\x08.bgBGplPLroROzhCNnlNLheILsvSEfiFInnNOdaDKhuHUcsCZhrHRskSKltLT")
_P3 = _pad(b"P\x08.lvLVetEEptBRsrRSmkMKfaIRhiINmrINneNPmnMNurPKenGBesMXdeCHfrBE")
_P4 = _pad(b"P\x08.frCAthTHbnINteINtaINzhTWkaGEhyAMidIDazAZisISviVNzhHKenAUenNZ")
_P5 = _pad(b"P\x08.miNZsmWSfjFJtlPHhwUSenZAafZAarEGswKEamETyoNGenNGarMAarIQkuIQ")
_P6 = _pad(b"P\x08.msMYuzUZenCAesARenPGtyPF")
_GET_LANG_ACK = _pad(b"P\x07.enUS")  # response to GET_LANG (query_current_lang)


def _make_keeb() -> PolyKybd:
    keeb = PolyKybd(DeviceSettings(), PolySettings())
    hid = MagicMock()
    hid.send_and_read_validate.return_value = (True, _GET_LANG_ACK)
    keeb.hid = hid
    return keeb


class TestEnumerateLangMultiPacket(unittest.TestCase):

    def _setup_reads(self, keeb: PolyKybd, extra_packets: list[bytes] = None):
        packets = [_P2, _P3, _P4, _P5, _P6] + (extra_packets or []) + [b'']
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, _P1, None)
        keeb.hid.read_with_lock.side_effect = [(True, p, None) for p in packets]

    def test_all_six_packets_consumed(self):
        keeb = _make_keeb()
        self._setup_reads(keeb)
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        # 5 follow-up reads (P2..P6) + 1 empty sentinel = 6 total
        self.assertEqual(keeb.hid.read_with_lock.call_count, 6)

    def test_languages_from_all_packets_present(self):
        keeb = _make_keeb()
        self._setup_reads(keeb)
        keeb.enumerate_lang()
        langs = keeb.get_lang_list()
        self.assertIn("enUS", langs)   # packet 1
        self.assertIn("kkKZ", langs)   # last in packet 1
        self.assertIn("bgBG", langs)   # packet 2
        self.assertIn("ltLT", langs)   # last in packet 2
        self.assertIn("lvLV", langs)   # packet 3
        self.assertIn("frBE", langs)   # last in packet 3
        self.assertIn("frCA", langs)   # packet 4
        self.assertIn("enNZ", langs)   # last in packet 4
        self.assertIn("miNZ", langs)   # packet 5
        self.assertIn("kuIQ", langs)   # last in packet 5
        self.assertIn("msMY", langs)   # packet 6
        self.assertIn("tyPF", langs)   # last in packet 6

    def test_only_first_packet_if_reads_time_out_early(self):
        keeb = _make_keeb()
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, _P1, None)
        keeb.hid.read_with_lock.side_effect = [(True, b'', None)]
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        langs = keeb.get_lang_list()
        self.assertIn("enUS", langs)
        self.assertNotIn("bgBG", langs)  # P2 was never read

    def test_unexpected_prefix_stops_loop(self):
        keeb = _make_keeb()
        junk = _pad(b"X\x00.garbage")
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, _P1, None)
        keeb.hid.read_with_lock.side_effect = [(True, junk, None)]
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        langs = keeb.get_lang_list()
        self.assertIn("enUS", langs)   # P1 was processed
        self.assertNotIn("bgBG", langs)  # loop stopped before P2

    def test_unexpected_prefix_mid_stream_stops_loop(self):
        """Bad prefix after a valid follow-up packet: earlier langs kept, later ones dropped."""
        keeb = _make_keeb()
        junk = _pad(b"X\x00.garbage")
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, _P1, None)
        keeb.hid.read_with_lock.side_effect = [(True, _P2, None), (True, junk, None)]
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        langs = keeb.get_lang_list()
        self.assertIn("enUS", langs)   # P1 retained
        self.assertIn("bgBG", langs)   # P2 retained (arrived before junk)
        self.assertNotIn("lvLV", langs)  # P3 never reached


# Full firmware language list reconstructed from the ASCII reference packets.
_ALL_LANGS = [
    "".join(p[3:].rstrip(b"\x00").decode())
    for p in (_P1, _P2, _P3, _P4, _P5, _P6)
]
_ALL_LANGS = [c for chunk in _ALL_LANGS for c in
              [chunk[i:i + 4] for i in range(0, len(chunk), 4)]]


def _packed_reports(codes, cmd_val=27):
    """Split iso.encode_packed(codes) into firmware-style HID reports:
    each report = 'P<cmd>.' header + up to 61 payload bytes, padded to 64."""
    payload = iso.encode_packed(codes)
    header = b"P" + bytes([cmd_val]) + b"."
    reports = []
    for i in range(0, len(payload), 61):
        reports.append(_pad(header + payload[i:i + 61]))
    return reports


class TestEnumerateLangPacked(unittest.TestCase):

    def _make_keeb(self, protocol):
        keeb = PolyKybd(DeviceSettings(), PolySettings())
        keeb.protocol_version = protocol
        keeb.hid = MagicMock()
        keeb.hid.send_and_read_validate.return_value = (True, _GET_LANG_ACK)
        return keeb

    def test_packed_path_decodes_all_languages(self):
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        reports = _packed_reports(_ALL_LANGS)
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, reports[0], None)
        keeb.hid.read_with_lock.side_effect = [(True, r, None) for r in reports[1:]]

        ok, value = keeb.enumerate_lang()
        self.assertTrue(ok)
        self.assertEqual(keeb.get_lang_list(), _ALL_LANGS)
        for tricky in ("enUS", "hwUS", "kuIQ", "tyPF", "amET"):
            self.assertIn(tricky, keeb.get_lang_list())

    def test_packed_uses_packed_command_not_ascii(self):
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        reports = _packed_reports(_ALL_LANGS)
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, reports[0], None)
        keeb.hid.read_with_lock.side_effect = [(True, r, None) for r in reports[1:]]
        keeb.enumerate_lang()
        sent_cmd = keeb.hid.send_and_read_validate_with_lock.call_args[0][0]
        self.assertEqual(sent_cmd[1], 27)  # Cmd.GET_LANG_LIST_PACKED

    def test_old_protocol_uses_ascii_path(self):
        keeb = self._make_keeb(1)  # below the packed threshold
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, _P1, None)
        keeb.hid.read_with_lock.side_effect = [(True, b'', None)]
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        sent_cmd = keeb.hid.send_and_read_validate_with_lock.call_args[0][0]
        self.assertEqual(sent_cmd[1], 8)  # Cmd.GET_LANG_LIST (ASCII)

    def test_no_protocol_version_uses_ascii_path(self):
        keeb = self._make_keeb(None)  # old firmware, no protocol field
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, _P1, None)
        keeb.hid.read_with_lock.side_effect = [(True, b'', None)]
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        sent_cmd = keeb.hid.send_and_read_validate_with_lock.call_args[0][0]
        self.assertEqual(sent_cmd[1], 8)

    def test_packed_nack_falls_back_to_ascii(self):
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        nack = _pad(b"P\x1b!")  # firmware NACKs the packed command
        # First call (packed) -> NACK; second call (ASCII fallback) -> P1.
        keeb.hid.send_and_read_validate_with_lock.side_effect = [
            (True, nack, None), (True, _P1, None)]
        keeb.hid.read_with_lock.side_effect = [(True, b'', None)]
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        self.assertIn("enUS", keeb.get_lang_list())
        self.assertEqual(keeb.hid.send_and_read_validate_with_lock.call_count, 2)
