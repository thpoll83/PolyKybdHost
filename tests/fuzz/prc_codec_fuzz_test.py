"""Properties of polyhost/util/prc_codec.py (cmd 41 PRC images).

The encoder output goes to the keyboard and parse_records() mirrors the firmware's
parser, so a report the parser accepts must be one the firmware also reads safely."""
import unittest

import numpy as np
from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.util import prc_codec

load_profile()


@st.composite
def rois(draw, max_h=16, max_w=24):
    h = draw(st.integers(1, max_h))
    w = draw(st.integers(1, max_w))
    bits = draw(st.lists(st.booleans(), min_size=h * w, max_size=h * w))
    return np.array(bits, dtype=bool).reshape(h, w)


class PrcCodecFuzzTest(unittest.TestCase):
    @given(rois())
    def test_encode_decode_round_trip(self, roi):
        payload = prc_codec.encode(roi)
        out = prc_codec.decode(payload, *roi.shape)
        self.assertTrue(np.array_equal(out, roi))

    @given(st.binary(max_size=80), st.integers(1, 12), st.integers(1, 20))
    def test_decode_arbitrary_payload_gives_the_box(self, payload, h, w):
        out = prc_codec.decode(payload, h, w)
        self.assertEqual(out.shape, (h, w))

    @given(st.binary(max_size=128))
    def test_parse_records_stays_inside_the_frame(self, report):
        consumed = 0
        for kc, mod, top, left, h, w, payload in prc_codec.parse_records(report):
            self.assertNotEqual(kc, 0)
            self.assertLessEqual(mod, 0x0F)
            self.assertLessEqual(top + h, 40)
            self.assertLessEqual(left + w, 72)
            consumed += prc_codec.RECORD_HDR + len(payload)
        self.assertLessEqual(consumed, len(report))

    @given(st.lists(st.tuples(st.integers(1, 0xFF), st.integers(0, 0x0F),
                              st.integers(0, 39), st.integers(0, 71),
                              st.integers(1, 40), st.integers(1, 72),
                              st.binary(max_size=prc_codec.MAX_RECORD_PAYLOAD)),
                    max_size=4))
    def test_pack_parse_round_trip(self, recs):
        recs = [(kc, mod, t, l, min(h, 40 - t), min(w, 72 - l), p)
                for kc, mod, t, l, h, w, p in recs]
        report = b"".join(prc_codec.pack_record(*r) for r in recs)
        self.assertEqual(list(prc_codec.parse_records(report)), recs)


if __name__ == "__main__":
    unittest.main()
