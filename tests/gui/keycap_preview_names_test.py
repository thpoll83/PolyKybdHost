"""`KeycapPreview._resolve_name` -- which of a keycode's names the preview draws by.

Qt-free in effect: the method touches only plain dicts, so the instance is built
without `__init__` and its fields set directly. No firmware checkout is read.
"""
import logging
import os
import pathlib
import re
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
        p._loaded, p._ok, p._fw_dir = True, True, d
        self.assertEqual(p.source_info(), d)

    def test_a_failing_git_is_logged_not_swallowed_silently(self):
        """⚠️ The `except` is deliberate -- a tooltip must not fail, and the PATH is
        still worth showing -- but a bare `pass` would hide the one thing that says
        why the commit line is missing, in the very method added to make a stale
        checkout diagnosable. Caught by CodeQL on #207."""
        p = object.__new__(KeycapPreview)
        p._loaded, p._ok, p._fw_dir = True, True, "/nowhere"
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
    """Where the layer tags come from -- one shipped constant, checked against the
    firmware by this suite rather than read from anywhere at runtime."""

    def test_the_shipped_tags_decode_the_layer_keys_the_keymap_binds(self):
        """No dialog, no checkout read: a bare preview names the base layer's three
        layer keys, which is what the editor draws them by."""
        p = KeycapPreview()
        self.assertEqual(p._layer_token(0x5225), "MO(_FL)")        # QK_MOMENTARY + 5
        self.assertEqual(p._layer_token(0x5226), "MO(_NL)")        # + 6
        self.assertEqual(p._layer_token(0x522A), "MO(_ADDLANG1)")  # + 10
        self.assertEqual(p._layer_token(0x520B), "TO(_EMJ)")       # QK_TO + 11

    def test_the_shipped_tags_match_the_firmware_enum(self):
        """⚠️ The guard that makes hardcoding safe -- and the one thing neither
        earlier scheme had.

        `LAYER_TAGS` is a constant precisely so a stale artifact or a stale checkout
        cannot rename the connected keyboard's layers under the editor; the cost is
        that it can itself fall behind `layers.h`. Nothing at runtime can notice
        that, so the suite does: when a firmware checkout is present, the two must
        agree exactly. A skip here means no checkout, not agreement.
        """
        # Resolved the way the preview itself does -- <fw>/base/fonts -> <fw>/
        # keyboards/polykybd -- so the test reads the same enum the legends came
        # from rather than a path of its own that can quietly miss.
        pk = os.path.dirname(os.path.dirname(ml.default_font_dir()))
        fw = os.path.join(pk, "layers.h")
        if not os.path.exists(fw):
            self.skipTest("no firmware checkout beside this repo")
        text = pathlib.Path(fw).read_text(encoding="utf-8")
        body = re.search(r"enum\s+kb_layers\s*\{(.*?)\}", text, re.S).group(1)
        idx, tags = 0, {}
        for tok in (t.strip() for t in body.split(",")):
            name = tok.split("=")[0].strip()
            if not name.startswith("_"):
                continue
            if "=" in tok:                       # `_BL = 0x00` / the `_L0 = _BL` alias
                val = tok.split("=", 1)[1].strip()
                if val.startswith("_"):          # an alias keeps the current index
                    tags.setdefault(idx - 1, name.lstrip("_"))
                    continue
                idx = int(val, 0)
            tags[idx] = name.lstrip("_")
            idx += 1
        # `_L0 = _BL` aliases index 0; the editor wants the tag the legends use.
        tags[0] = "L0"
        self.assertEqual(qh.LAYER_TAGS, tags)


