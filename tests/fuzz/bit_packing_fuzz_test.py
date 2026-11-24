"""Properties of polyhost/device/bit_packing.py (overlay mapping reports)."""
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.device import bit_packing as bp

load_profile()

DATA_BYTES = 28   # a mapping report's data size; any value works for the properties


class BitPackingFuzzTest(unittest.TestCase):
    @given(st.integers(bp.WIDTH_MIN, bp.WIDTH_MAX), st.data())
    def test_pack_values_unpack_round_trip(self, width, data):
        pairs = data.draw(st.lists(
            st.tuples(st.integers(0, (1 << width) - 1), st.integers(0, (1 << width) - 1)),
            max_size=bp.pairs_per_report(DATA_BYTES, width), unique_by=lambda p: p[0]))
        flat = [v for p in pairs for v in p]
        packed = bp.pack_values(flat, DATA_BYTES, width)
        self.assertEqual(len(packed), DATA_BYTES)
        self.assertEqual(bp.unpack_bytes_to_dict(bytes(packed), len(pairs), width), dict(pairs))

    @given(st.dictionaries(st.integers(0, 0x7FF), st.integers(0, 0x7FF), max_size=300))
    def test_plan_sends_every_pair_once_at_a_width_it_fits(self, mapping):
        reports = bp.plan_mapping_reports(mapping, DATA_BYTES)
        sent = {}
        for width, pairs in reports:
            self.assertLessEqual(len(pairs), bp.pairs_per_report(DATA_BYTES, width))
            for f, t in pairs:
                self.assertLessEqual(bp.pair_width(f, t), width)
                self.assertNotIn(f, sent)
                sent[f] = t
            packed = bp.pack_report(pairs, DATA_BYTES, width)
            n = bp.pairs_per_report(DATA_BYTES, width)
            self.assertEqual(bp.unpack_bytes_to_dict(bytes(packed), n, width), dict(pairs))
        self.assertEqual(sent, mapping)

    @given(st.dictionaries(st.integers(0, 0x3FF), st.integers(0, 0x3FF), max_size=100))
    def test_pack_dict_10_bit_round_trip(self, mapping):
        packed = bp.pack_dict_10_bit(mapping)
        self.assertEqual(bp.unpack_bytes_to_dict(bytes(packed), len(mapping)), mapping)


if __name__ == "__main__":
    unittest.main()
