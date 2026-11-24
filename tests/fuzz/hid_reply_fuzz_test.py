"""Properties of the HID and serial reply parsers: replies come from the keyboard,
which may run any firmware version, and a short or garbled report must not crash
the HID worker."""
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.device import bulk_pipe, hid_fontpack
from polyhost.device.poly_kybd import decode_layer_names

load_profile()

REPLY = st.binary(max_size=64)


class HidReplyFuzzTest(unittest.TestCase):
    @given(REPLY)
    def test_get_id_blocks(self, reply):
        versions = hid_fontpack.parse_id_version_block(reply)
        self.assertTrue(all(0 <= v <= 0xFFFF for v in versions.values()))
        gen = hid_fontpack.parse_id_state_generation(reply)
        self.assertTrue(gen is None or 0 <= gen <= 0xFFFF)
        anim = hid_fontpack.parse_id_anim_state(reply)
        self.assertTrue(anim is None or 0 <= anim <= 0xFF)

    @given(st.binary(max_size=40), st.binary(max_size=24))
    def test_get_id_blocks_after_an_id_string(self, ident, blocks):
        reply = b"P\x06." + ident.replace(b"\0", b"") + b"\0" + blocks
        hid_fontpack.parse_id_version_block(reply)
        hid_fontpack.parse_id_state_generation(reply)
        hid_fontpack.parse_id_anim_state(reply)

    @given(REPLY)
    def test_layer_names(self, payload):
        names = decode_layer_names(payload)
        if names is not None:
            self.assertEqual(len(names), payload[1])

    @given(st.binary(max_size=128))
    def test_fontpack_header(self, data):
        ok, info = hid_fontpack.parse_fontpack_header(data)
        self.assertEqual(ok, "error" not in info)

    @given(REPLY)
    def test_bulk_pipe_replies(self, payload):
        for parse in (bulk_pipe.parse_stat, bulk_pipe.parse_ping):
            try:
                parse(payload)
            except ValueError:
                # ValueError is the documented rejection of a short or
                # malformed reply; any other exception fails the test.
                pass
        reply = bulk_pipe.parse_fw_chunk_reply(payload)
        self.assertEqual(reply is None, len(payload) < 5)


if __name__ == "__main__":
    unittest.main()
