"""Tests for the frozen ISO 639-1 / ISO 3166-1 alpha-2 code tables and the
packed (2-byte-per-language) GET_LANG_LIST codec."""
import unittest

from polyhost.services import iso_lang_country as iso

# A representative slice of the firmware's real language list, including the
# tricky cases: hw (private pseudo-code), ku/ty (real ISO 639-1), am (Ethiopic).
SAMPLE = ["enUS", "deDE", "frFR", "arSA", "zhCN", "hwUS", "kuIQ", "tyPF",
          "amET", "miNZ", "ptBR", "enPG"]


class TestIsoTables(unittest.TestCase):

    def test_indices_fit_one_byte(self):
        self.assertLessEqual(len(iso.LANG_CODES), 256)
        self.assertLessEqual(len(iso.COUNTRY_CODES), 256)

    def test_codes_are_unique(self):
        self.assertEqual(len(iso.LANG_CODES), len(set(iso.LANG_CODES)))
        self.assertEqual(len(iso.COUNTRY_CODES), len(set(iso.COUNTRY_CODES)))

    def test_private_hw_appended_after_standard_block(self):
        self.assertIn("hw", iso.PRIVATE_LANGS)
        # hw has no ISO 639-1 entry, so it must sit above the standard codes.
        self.assertGreaterEqual(iso.LANG_CODES.index("hw"),
                                len(iso.LANG_CODES) - len(iso.PRIVATE_LANGS))

    def test_every_lang_index_round_trips(self):
        for idx, code in enumerate(iso.LANG_CODES):
            self.assertEqual(iso.decode_pair(idx, 0)[:2], code)

    def test_every_country_index_round_trips(self):
        for idx, code in enumerate(iso.COUNTRY_CODES):
            self.assertEqual(iso.decode_pair(0, idx)[2:], code)


class TestPairCodec(unittest.TestCase):

    def test_pair_round_trip(self):
        for code in SAMPLE:
            lang_idx, country_idx = iso.encode_pair(code)
            self.assertEqual(iso.decode_pair(lang_idx, country_idx), code)

    def test_encode_pair_is_two_bytes(self):
        self.assertEqual(len(iso.encode_pair("enUS")), 2)

    def test_unknown_code_raises(self):
        with self.assertRaises(KeyError):
            iso.encode_pair("zzZZ")  # zz is not an assigned ISO 639-1 code


class TestPackedCodec(unittest.TestCase):

    def test_packed_round_trip(self):
        buf = iso.encode_packed(SAMPLE)
        self.assertEqual(iso.decode_packed(buf), SAMPLE)

    def test_packed_length_and_count(self):
        buf = iso.encode_packed(SAMPLE)
        self.assertEqual(buf[0], len(SAMPLE))            # count byte
        self.assertEqual(len(buf), 1 + 2 * len(SAMPLE))  # count + 2B per code

    def test_packed_empty(self):
        buf = iso.encode_packed([])
        self.assertEqual(buf, b"\x00")
        self.assertEqual(iso.decode_packed(buf), [])


if __name__ == "__main__":
    unittest.main()
