"""Unit tests for PolyKybd.enumerate_lang multi-packet reading.

The firmware sends 4 HID reports in sequence for GET_LANG_LIST.
These tests verify that all 4 are consumed and parsed, not just the first.
"""
import unittest
from unittest.mock import MagicMock

from polyhost.device.poly_kybd import PolyKybd
from polyhost.device.device_settings import DeviceSettings
from polyhost.settings import PolySettings


def _pad(data: bytes, size: int = 64) -> bytes:
    return data + b'\x00' * (size - len(data))


# Exact firmware GET_LANG_LIST response packets (from hid_com.c case 8)
_P1 = _pad(b"P\x08.enUSdeDEfrFResESptPTitITtrTRkoKRjaJParSAelGRukUAruRUbeBYkkKZ")
_P2 = _pad(b"P\x08.bgBGplPLroROzhCNnlNLheILsvSEfiFInnNOdaDKhuHUcsCZhrHRskSKltLT")
_P3 = _pad(b"P\x08.lvLVetEEptBRsrRSmkMKfaIRhiINmrINneNPmnMNurPKenGBesMXdeCHfrBE")
_P4 = _pad(b"P\x08.frCAthTHbnINteINtaINzhTWkaGEhyAMidIDazAZisISviVNzhHK")
_GET_LANG_ACK = _pad(b"P\x07.enUS")  # response to GET_LANG (query_current_lang)


def _make_keeb() -> PolyKybd:
    keeb = PolyKybd(DeviceSettings(), PolySettings())
    hid = MagicMock()
    hid.send_and_read_validate.return_value = (True, _GET_LANG_ACK)
    keeb.hid = hid
    return keeb


class TestEnumerateLangMultiPacket(unittest.TestCase):

    def _setup_reads(self, keeb: PolyKybd, extra_packets: list[bytes] = None):
        packets = [_P2, _P3, _P4] + (extra_packets or []) + [b'']
        keeb.hid.send_and_read_validate_with_lock.return_value = (True, _P1, None)
        keeb.hid.read_with_lock.side_effect = [(True, p, None) for p in packets]

    def test_all_four_packets_consumed(self):
        keeb = _make_keeb()
        self._setup_reads(keeb)
        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        # 3 follow-up reads (P2, P3, P4) + 1 empty sentinel = 4 total
        self.assertEqual(keeb.hid.read_with_lock.call_count, 4)

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
        self.assertIn("zhHK", langs)   # last in packet 4

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
