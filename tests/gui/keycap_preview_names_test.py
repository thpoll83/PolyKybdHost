"""`KeycapPreview._resolve_name` -- which of a keycode's names the preview draws by.

Qt-free in effect: the method touches only plain dicts, so the instance is built
without `__init__` and its fields set directly. No firmware checkout is read.
"""
import unittest

from polyhost.gui.layout_dialog.keycap_preview import KeycapPreview


class _Lang:
    """Stand-in for `lang_demo`: the fold this preview passes through."""

    def __init__(self, aliases=None):
        self._aliases = aliases or {}

    def normalize_kc(self, tok, known=None):
        if known is not None and tok not in known:
            alt = self._aliases.get(tok)
            if alt is not None and alt in known:
                return alt
        return tok


def _preview(known, custom=None, alt_names=None, layer_tags=None, aliases=None):
    p = object.__new__(KeycapPreview)
    p._known = set(known)
    p._custom = custom or {}
    p._alt_names = alt_names or {}
    p._layer_tags = layer_tags or {}
    p._ld = _Lang(aliases)
    return p


class ResolveNameTest(unittest.TestCase):
    def test_the_browsers_pick_is_used_when_it_is_drawable(self):
        p = _preview({"KC_A"})
        self.assertEqual(p._resolve_name(0x04, "KC_A"), "KC_A")

    def test_a_custom_keycode_falls_back_to_the_firmwares_name(self):
        """⚠️ The browser shows every PolyKybd custom keycode as `QK_KB_n`, while
        `keycode_helper.h` and every legend call it `KC_LANG`, `KC_DMIN`, ... Taking
        the browser's pick and giving up left 34 keys -- the whole settings,
        brightness and layout set -- blank."""
        p = _preview({"KC_LANG"}, custom={0x7E00: "KC_LANG"})
        self.assertEqual(p._resolve_name(0x7E00, "QK_KB_0"), "KC_LANG")

    def test_a_synthetic_display_name_falls_back_to_a_real_one(self):
        """⚠️ `DISPLAY_NAME_OVERRIDE` invents `KC_SCRL_BRMD` to show both meanings of
        a dual-purpose key. It exists in NO header, so no alias table can ever
        contain it -- only the keycode's other names resolve."""
        p = _preview({"KC_SCROLL_LOCK"},
                     alt_names={0x47: ["KC_BRMD", "KC_SCRL", "KC_SCROLL_LOCK"]})
        self.assertEqual(p._resolve_name(0x47, "KC_SCRL_BRMD"), "KC_SCROLL_LOCK")

    def test_a_layer_keycode_is_decoded_since_it_has_no_name_at_all(self):
        p = _preview({"MO(_FL)"}, layer_tags={5: "FL"})
        self.assertEqual(p._resolve_name(0x5225, None), "MO(_FL)")

    def test_the_alias_fold_still_applies_to_a_candidate(self):
        p = _preview({"KC_AUDIO_MUTE"}, aliases={"KC_MUTE": "KC_AUDIO_MUTE"})
        self.assertEqual(p._resolve_name(0xA8, "KC_MUTE"), "KC_AUDIO_MUTE")

    def test_a_keycode_nothing_can_draw_returns_None(self):
        """Not the browser's name as a consolation: the caller renders None as the
        keycode text, and returning an undrawable name would take it down the legend
        path to fail there instead."""
        p = _preview({"KC_A"}, custom={0x7E13: "KC_LAT0"},
                     alt_names={0x7E13: ["QK_KB_19"]})
        self.assertIsNone(p._resolve_name(0x7E13, "QK_KB_19"))

    def test_order_is_most_specific_first(self):
        """When several candidates are drawable the tile's own label wins, so the
        preview matches what the tile says."""
        p = _preview({"KC_PAUSE", "KC_BRK"},
                     custom={0x48: "KC_BRK"},
                     alt_names={0x48: ["KC_PAUSE"]})
        self.assertEqual(p._resolve_name(0x48, "KC_PAUSE"), "KC_PAUSE")

    def test_every_candidate_names_the_same_keycode(self):
        """The safety property: a fallback can only ever pull up a legend belonging
        to this keycode, never a neighbour's, because each candidate is another name
        for the same value."""
        p = _preview({"KC_SCROLL_LOCK"},
                     custom={0x47: "KC_SCRL"},
                     alt_names={0x47: ["KC_SCROLL_LOCK"], 0x48: ["KC_PAUSE"]})
        self.assertEqual(p._resolve_name(0x47, "KC_SCRL_BRMD"), "KC_SCROLL_LOCK")


if __name__ == "__main__":
    unittest.main()
