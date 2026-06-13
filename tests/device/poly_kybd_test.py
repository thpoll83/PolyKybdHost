"""Unit tests for PolyKybd.enumerate_lang.

The language list is read exclusively via GET_LANG_LIST_PACKED (cmd 27,
protocol v2+): a count byte followed by two ISO index bytes per language, split
across 64-byte HID reports. The legacy ASCII GET_LANG_LIST (cmd 8) has been
retired — the firmware NACKs it — so there is no ASCII fallback and firmware
older than protocol v2 is unsupported. These tests verify multi-report packed
reassembly and that old firmware is rejected cleanly rather than silently
downgraded to the retired command.
"""
import unittest
from unittest.mock import MagicMock

from polyhost.device.poly_kybd import PolyKybd, PACKED_LANG_LIST_MIN_PROTOCOL
from polyhost.device.device_settings import DeviceSettings
from polyhost.settings import PolySettings
from polyhost.services import iso_lang_country as iso


def _pad(data: bytes, size: int = 64) -> bytes:
    return data + b'\x00' * (size - len(data))


# A representative slice of the firmware language list, as 4-char codes in
# firmware order. Used purely as a round-trip fixture: encoded to the packed
# wire format below, then expected back out of the decoder unchanged. The exact
# count is irrelevant to the multi-report parsing logic under test.
_LANG_CODES = (
    "enUSdeDEfrFResESptPTitITtrTRkoKRjaJParSAelGRukUAruRUbeBYkkKZ"
    "bgBGplPLroROzhCNnlNLheILsvSEfiFInnNOdaDKhuHUcsCZhrHRskSKltLT"
    "lvLVetEEptBRsrRSmkMKfaIRhiINmrINneNPmnMNurPKenGBesMXdeCHfrBE"
    "frCAthTHbnINteINtaINzhTWkaGEhyAMidIDazAZisISviVNzhHKenAUenNZ"
    "miNZsmWSfjFJtlPHhwUSenZAafZAarEGswKEamETyoNGenNGarMAarIQkuIQ"
    "msMYuzUZenCAesARenPGtyPF"
)
_ALL_LANGS = [_LANG_CODES[i:i + 4] for i in range(0, len(_LANG_CODES), 4)]

_GET_LANG_ACK = _pad(b"P\x07.enUS")  # response to GET_LANG (query_current_lang)


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
        # GET_LANG (query_current_lang) runs before the list read; let it succeed.
        keeb.hid.send_and_read_validate.return_value = (True, _GET_LANG_ACK)
        return keeb

    def _arm_packed(self, keeb, reports):
        """Wire the mock: query_current_lang's GET_LANG via send_and_read_validate,
        then the packed list — first report via send_and_read_validate, the
        remaining reports via plain read()."""
        keeb.hid.send_and_read_validate.side_effect = [
            (True, _GET_LANG_ACK), (True, reports[0])]
        keeb.hid.read.side_effect = [(True, r) for r in reports[1:]]

    def test_packed_path_decodes_all_languages(self):
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        reports = _packed_reports(_ALL_LANGS)
        self._arm_packed(keeb, reports)

        ok, _ = keeb.enumerate_lang()
        self.assertTrue(ok)
        self.assertEqual(keeb.get_lang_list(), _ALL_LANGS)
        # Spot-check pseudo-codes / multi-packet entries decode correctly.
        for tricky in ("enUS", "hwUS", "kuIQ", "tyPF"):
            self.assertIn(tricky, keeb.get_lang_list())

    def test_packed_uses_packed_command(self):
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        reports = _packed_reports(_ALL_LANGS)
        self._arm_packed(keeb, reports)
        keeb.enumerate_lang()
        # The packed list is the second send_and_read_validate call (after GET_LANG).
        sent_cmd = keeb.hid.send_and_read_validate.call_args_list[1][0][0]
        self.assertEqual(sent_cmd[1], 27)  # Cmd.GET_LANG_LIST_PACKED

    def test_old_protocol_is_unsupported(self):
        """Protocol below v2: the ASCII fallback is gone, so enumeration fails
        cleanly and the host never sends a list command (no downgrade to cmd 8)."""
        keeb = self._make_keeb(1)
        ok, _ = keeb.enumerate_lang()
        self.assertFalse(ok)
        # Only GET_LANG (query_current_lang) was sent; no packed list command.
        self.assertEqual(keeb.hid.send_and_read_validate.call_count, 1)

    def test_no_protocol_version_is_unsupported(self):
        """Firmware that reports no protocol version (very old) is likewise
        unsupported — the retired ASCII command is not attempted."""
        keeb = self._make_keeb(None)
        # query_version_info() runs to refresh the (still missing) protocol;
        # let its reads no-op so it leaves protocol_version unset.
        keeb.hid.send_and_read_validate.return_value = (False, _pad(b""))
        ok, _ = keeb.enumerate_lang()
        self.assertFalse(ok)

    def test_packed_truncated_empty_continuation_terminates(self):
        """A continuation read() that times out (True, b'') must NOT spin the
        worker loop forever — it breaks and reports a truncated list."""
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        reports = _packed_reports(_ALL_LANGS)   # spans several reports
        keeb.hid.send_and_read_validate.side_effect = [
            (True, _GET_LANG_ACK), (True, reports[0])]
        # One empty continuation, then exhaustion (StopIteration) — if the fix
        # regressed and looped, the test would hang or raise StopIteration.
        keeb.hid.read.side_effect = [(True, _pad(b""))]
        ok, msg = keeb.enumerate_lang()
        self.assertFalse(ok)
        self.assertEqual(keeb.hid.read.call_count, 1)

    def test_packed_nack_continuation_terminates(self):
        """A NACK/garbage continuation (no 'P<cmd>.' header) also breaks."""
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        reports = _packed_reports(_ALL_LANGS)
        keeb.hid.send_and_read_validate.side_effect = [
            (True, _GET_LANG_ACK), (True, reports[0])]
        keeb.hid.read.side_effect = [(True, _pad(b"P\x1b!"))]
        ok, _ = keeb.enumerate_lang()
        self.assertFalse(ok)
        self.assertEqual(keeb.hid.read.call_count, 1)

    def test_packed_nack_does_not_fall_back(self):
        """A NACK to the packed command on a v2 board is a hard failure — it is
        NOT retried as the retired ASCII list. Exactly one list command is sent."""
        keeb = self._make_keeb(PACKED_LANG_LIST_MIN_PROTOCOL)
        nack = _pad(b"P\x1b!")  # firmware NACKs the packed command
        keeb.hid.send_and_read_validate.side_effect = [
            (True, _GET_LANG_ACK), (True, nack)]
        ok, _ = keeb.enumerate_lang()
        self.assertFalse(ok)
        # Two send_and_read_validate calls total: GET_LANG + the packed list.
        self.assertEqual(keeb.hid.send_and_read_validate.call_count, 2)


if __name__ == "__main__":
    unittest.main()
