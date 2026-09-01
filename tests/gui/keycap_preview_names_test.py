"""`KeycapPreview._resolve_name` -- which of a keycode's names the preview draws by.

Qt-free in effect: the method touches only plain dicts, so the instance is built
without `__init__` and its fields set directly. No firmware checkout is read.
"""
import logging
import os
import pathlib
import tempfile
import unittest
import unittest.mock

from polyhost.gui.layout_dialog import qmk_keycode_helper as qh
from polyhost.services import macro_label as ml
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
    p._ranges = None           # the layer ranges resolve lazily from the header
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


class SourceInfoTest(unittest.TestCase):
    """Which checkout the legends came from -- the thing nothing used to say."""

    def test_an_unloaded_preview_names_nothing(self):
        p = object.__new__(KeycapPreview)
        p._loaded, p._ok, p._fw_dir = True, False, ""
        self.assertEqual(p.source_info(), "")

    def test_a_checkout_with_no_git_still_names_the_path(self):
        """Best-effort by design: the PATH is the half that answers "whose copy is
        this", and it must survive a checkout git cannot describe."""
        d = tempfile.mkdtemp()
        p = object.__new__(KeycapPreview)
        p._loaded, p._ok, p._fw_dir, p._tag_drift = True, True, d, ""
        self.assertEqual(p.source_info(), d)

    def test_a_failing_git_is_logged_not_swallowed_silently(self):
        """⚠️ The `except` is deliberate -- a tooltip must not fail, and the PATH is
        still worth showing -- but a bare `pass` would hide the one thing that says
        why the commit line is missing, in the very method added to make a stale
        checkout diagnosable. Caught by CodeQL on #207."""
        p = object.__new__(KeycapPreview)
        p._loaded, p._ok, p._fw_dir, p._tag_drift = True, True, "/nowhere", ""
        p.log = logging.getLogger("test_source_info")
        with unittest.mock.patch("subprocess.run", side_effect=OSError("no git")):
            with self.assertLogs(p.log, level="DEBUG") as caught:
                self.assertEqual(p.source_info(), "/nowhere")
        self.assertTrue(any("no git" in m for m in caught.output), caught.output)


class LayerRangeTest(unittest.TestCase):
    """The layer-switch ranges, read from the header rather than hand-listed."""

    def _p(self):
        p = object.__new__(KeycapPreview)
        p._ranges = None
        p._layer_tags = {5: "FL"}
        return p

    def test_all_six_of_qmks_layer_switch_kinds_are_covered(self):
        """⚠️ The bounds used to be four hand-listed pairs, and `DF` and `TT` were
        simply absent -- `_layer_token` returned None for them, so no legend could
        ever be found, silently and indistinguishably from "the firmware has none"."""
        kinds = {k for _lo, _hi, k in self._p()._layer_ranges}
        self.assertEqual(kinds, {"TO", "MO", "DF", "TG", "OSL", "TT"})

    def test_each_range_decodes_its_own_layer(self):
        p = self._p()
        for lo, _hi, kind in p._layer_ranges:
            self.assertEqual(p._layer_token(lo + 5), f"{kind}(_FL)")

    def test_a_keycode_outside_every_range_is_not_a_layer_key(self):
        self.assertIsNone(self._p()._layer_token(0x0004))

    def test_an_untagged_layer_yields_no_token(self):
        """The tag map comes from the firmware's own enum; without an entry there is
        no token to look a legend up by, and inventing one would name a layer that
        does not exist."""
        p = self._p()
        p._layer_tags = {}
        self.assertIsNone(p._layer_token(0x5225))


class LayerTagSourceTest(unittest.TestCase):
    """Where the layer tags come from, and what happens when that source is stale.

    ⚠️ They come from the firmware CHECKOUT's `layers.h`, not from the shipped
    `LAYER_TAGS` -- because the token they build has to match the spelling the SAME
    tree's `keycode_helper.c` switches on. Hardcoding was tried for one commit and
    broke every layer key on an older checkout, which has no `case MO(_FL)` at all.
    """

    # The enum from before the Fn merge (2026-08-26): two function layers, so every
    # index from 5 up names a different layer than the current firmware does.
    OLD = {0: "L0", 1: "L1", 2: "L2", 3: "L3", 4: "L4", 5: "FL0", 6: "FL1",
           7: "NL", 8: "UL", 9: "SL", 10: "LL", 11: "ADDLANG1", 12: "EMJ"}

    def _fw(self):
        pk = os.path.dirname(os.path.dirname(ml.default_font_dir()))
        if not os.path.exists(os.path.join(pk, "layers.h")):
            self.skipTest("no firmware checkout beside this repo")
        return pk

    def test_the_tags_decode_the_layer_keys_the_keymap_binds(self):
        """The end result, on a checkout that is in step: the base layer's layer
        keys resolve to tokens the legends actually carry."""
        self._fw()
        p = KeycapPreview()
        if not p._load():
            self.skipTest(f"previews unavailable: {p.reason}")
        for kc, tok in ((0x5225, "MO(_FL)"), (0x5226, "MO(_NL)"),
                        (0x522A, "MO(_ADDLANG1)"), (0x520B, "TO(_EMJ)")):
            self.assertEqual(p._layer_token(kc), tok)
            self.assertIn(tok, p._known)

    def test_the_shipped_tags_match_the_firmware_enum(self):
        """`LAYER_TAGS` is the fallback AND the yardstick the drift warning measures
        against, so it has to describe the current firmware. Nothing at runtime can
        notice it falling behind; this does. A skip means no checkout, not agreement.
        """
        pk = self._fw()
        self.assertEqual(
            qh.LAYER_TAGS,
            qh.parse_layers_h(pathlib.Path(pk) / "layers.h"))

    def test_a_checkout_out_of_step_with_the_host_is_REPORTED(self):
        """⚠️ The part that was missing, and it cost three rounds of guessing.

        An old checkout cannot be made to preview correctly -- its legends are old
        too -- but the preview must not present that as its own failure. Reported
        from the field as "L5 is gone", "the brightness icons are the old ones" and
        "is it related to fontpacks", none of which points at the checkout.
        """
        self._fw()
        with unittest.mock.patch.object(qh, "parse_layers_h", return_value=self.OLD):
            p = KeycapPreview()
            if not p._load():
                self.skipTest(f"previews unavailable: {p.reason}")
            self.assertEqual(p._layer_tags, self.OLD)      # the tree's, not ours
            self.assertIn("index 5", p._tag_drift)
            self.assertIn("FL0", p._tag_drift)
            self.assertIn(p._tag_drift, p.source_info())   # reaches the tooltip

    def test_an_in_step_checkout_reports_no_drift(self):
        """The warning must stay silent on a healthy install, or it is one more
        banner people learn to scroll past."""
        self._fw()
        p = KeycapPreview()
        if not p._load():
            self.skipTest(f"previews unavailable: {p.reason}")
        self.assertEqual(p._tag_drift, "")
        self.assertNotIn("\u26a0", p.source_info())


