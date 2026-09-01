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
from polyhost.services import preview_data as pdata
from polyhost.services import macro_label as ml
from polyhost.gui.layout_dialog import keycap_preview as kp
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
        p._loaded, p._ok, p._fw_dir, p._source = True, False, "", ""
        self.assertEqual(p.source_info(), "")

    def test_a_checkout_with_no_git_still_names_the_path(self):
        """Best-effort by design: the PATH is the half that answers "whose copy is
        this", and it must survive a checkout git cannot describe."""
        d = tempfile.mkdtemp()
        p = object.__new__(KeycapPreview)
        # ⚠️ `_source` is set explicitly rather than left to a getattr default:
        # a fixture that tolerates a missing attribute would keep passing if the
        # loader stopped setting it, which is the state that decides the branch.
        p._loaded, p._ok, p._fw_dir, p._tag_drift = True, True, d, ""
        p._source = "checkout"
        self.assertEqual(p.source_info(), d)

    def test_a_failing_git_is_logged_not_swallowed_silently(self):
        """⚠️ The `except` is deliberate -- a tooltip must not fail, and the PATH is
        still worth showing -- but a bare `pass` would hide the one thing that says
        why the commit line is missing, in the very method added to make a stale
        checkout diagnosable. Caught by CodeQL on #207."""
        p = object.__new__(KeycapPreview)
        p._loaded, p._ok, p._fw_dir, p._tag_drift = True, True, "/nowhere", ""
        p._source = "checkout"
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
        # ⚠️ BOTH mocks are required, and the second one is the whole reason this
        # test broke once. source="checkout" makes the checkout the source at all.
        # But the drift warning is deliberately SUPPRESSED for a checkout that won
        # by being NEWER (a firmware developer's tree disagreeing with LAYER_TAGS is
        # expected), and `authoritative` is computed from the AMBIENT checkout's
        # FW_VERSION against the shipped export's. So this test's outcome tracked
        # whichever branch ../qmk_firmware happened to be on: green all morning at
        # 0.16.21, red the moment merges took it to 0.16.23 past the export. Pin the
        # version too, or the test measures the environment instead of the contract.
        with unittest.mock.patch.object(qh, "parse_layers_h", return_value=self.OLD), \
             unittest.mock.patch.object(kp, "_checkout_version", return_value="0.0.1"):
            p = KeycapPreview(source="checkout")
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




class PreviewSourceTest(unittest.TestCase):
    """WHICH data the previews draw from -- the fix for the whole field report.

    Until 2026-09-01 the only source was a firmware clone beside the install, so
    the feature was unavailable to anyone who is not a firmware developer and
    silently WRONG for anyone whose clone had drifted: a blank Fn key, blank
    emoji/Intl keys and retired moon brightness icons, all one stale clone.
    """

    def test_the_shipped_data_alone_previews_the_whole_board(self):
        """The deliverable: no firmware checkout, no openpyxl, previews anyway.

        ⚠️ Forced to "shipped" rather than hiding the checkout, because the point
        is what the shipped data can do ON ITS OWN. A test that merely let the
        version comparison pick would pass on a machine with no clone and prove
        nothing on the one that has one.
        """
        p = KeycapPreview(source="shipped")
        if not p._load():
            self.skipTest(f"no shipped preview data: {p.reason}")
        self.assertEqual(p.source, "shipped")
        self.assertGreater(len(p._legends), 150)
        self.assertTrue(p._lang_ok)
        self.assertGreater(len(p.languages), 100)
        # a custom PolyKybd keycode (the browser names it QK_KB_0), a decoded layer
        # key, and a letter -- the three families that each need a different table
        for kc, nm in ((0x7E00, "QK_KB_0"), (0x5225, None), (0x0004, "KC_A")):
            self.assertIsNotNone(p.render(kc, nm), f"no preview for {kc:#06x}")

    def test_a_forced_source_does_NOT_fall_back(self):
        """⚠️ The fallback is right for the automatic pick and wrong here: a
        comparison of the two sources that silently substituted one for the other
        would report them identical for the least interesting reason."""
        p = KeycapPreview(source="checkout")
        p._load()
        self.assertIn(p.source, ("checkout", ""))

    def test_source_info_names_the_shipped_data_and_its_firmware(self):
        """A preview that cannot say where its legends came from is one nobody can
        diagnose -- the gap that cost three rounds of guessing."""
        p = KeycapPreview(source="shipped")
        if not p._load():
            self.skipTest(f"no shipped preview data: {p.reason}")
        info = p.source_info()
        self.assertIn("shipped with this host", info)
        self.assertIn(p._fw_version, info)

    def test_the_automatic_pick_IS_the_version_comparison(self):
        """⚠️ THE regression test for the field bug: a clone that is not newer must
        not be read. Reading it unconditionally is what produced a blank Fn key,
        blank emoji/Intl keys and moon brightness icons off one stale clone.

        ⚠️ The expected source is DERIVED here from the two versions rather than
        skipped past. An earlier version of this test skipped whenever the source
        was not "shipped" -- so a mutation pinning the pick to "checkout" made it
        SKIP instead of fail, i.e. the one test guarding the bug passed against the
        bug (mutation-checked, 2026-09-01). A skip that the code under test can
        cause is not a gate.
        """
        p = KeycapPreview()
        if not p._load():
            self.skipTest(f"previews unavailable: {p.reason}")
        shipped = pdata.PreviewData()
        shipped_v = shipped.fw_version if shipped.load() else ""
        pk = kp._checkout_dir()
        checkout_v = kp._checkout_version(pk) if pk else ""
        if not (shipped_v or checkout_v):
            self.skipTest("neither source is present")
        self.assertEqual(p.source, pdata.choose_source(shipped_v, checkout_v))
        if p.source == "shipped" and checkout_v:
            # Silence here reads as "my clone is being used" and sends the next
            # round after the clone. EQUAL versions lose too -- the shipped export
            # is the copy that was tested.
            self.assertTrue(p._checkout_unused)
            self.assertIn("not newer", p.source_info())

    def test_the_two_sources_draw_the_SAME_keycaps(self):
        """⚠️ Checked by DRAWING, over every keycode the editor can show.

        The export resolves legends with the same code the checkout path does, so
        a comparison of the two data structures would agree by construction. The
        pixels are the only claim worth making, and they are what a user sees.
        """
        pk = os.path.dirname(os.path.dirname(ml.default_font_dir()))
        if not os.path.exists(os.path.join(pk, "keycode_helper.c")):
            self.skipTest("no firmware checkout beside this repo")
        a, b = KeycapPreview(source="shipped"), KeycapPreview(source="checkout")
        if not (a._load() and b._load()):
            self.skipTest(f"a source would not load: {a.reason or b.reason}")

        by_val = {}
        for nm, val in qh.parse_qmk_keycodes(qh.HEADER_FILE).items():
            by_val.setdefault(val, nm)
        codes = set(by_val)
        for lo, _hi, _kind in b._layer_ranges:
            codes.update(range(lo, lo + 12))       # the layer keys are decoded

        def raw(img):
            return None if img is None else img.bits().asstring(img.byteCount())

        drawn, mismatch = 0, []
        for kc in sorted(codes):
            ia, ib = a.render(kc, by_val.get(kc)), b.render(kc, by_val.get(kc))
            if ia is None and ib is None:
                continue
            drawn += 1
            if raw(ia) != raw(ib):
                mismatch.append((hex(kc), by_val.get(kc),
                                 "shipped-only" if ib is None else
                                 "checkout-only" if ia is None else "differs"))
        self.assertGreater(drawn, 150, "nothing was compared")
        self.assertEqual(mismatch, [], f"{len(mismatch)} of {drawn} keycaps differ")


class DrawableFailsClosedTest(unittest.TestCase):
    """⚠️ The op check must refuse what it could not verify, not keep it.

    It was `except Exception: pass`, so a raising `unsupported_ops` KEPT the
    legend -- the one check whose job is to refuse what would render wrong let it
    through silently, which is the outcome the check exists to prevent (CodeQL,
    #207). A refused keycap falls back to keycode text, which is honest.
    """

    class _Raises:
        def unsupported_ops(self, cps):
            raise RuntimeError("boom")

    class _Clean:
        def unsupported_ops(self, cps):
            return set()

    def _preview(self, renderer):
        p = object.__new__(KeycapPreview)
        p.log = logging.getLogger("test_drawable")
        p._R = renderer
        return p

    def test_a_legend_the_check_could_not_read_is_DROPPED(self):
        p = self._preview(self._Raises())
        with self.assertLogs(p.log, level="WARNING") as caught:
            self.assertEqual(p._drawable({"KC_X": [65]}), {})
        self.assertTrue(any("KC_X" in m for m in caught.output), caught.output)

    def test_a_clean_legend_still_survives(self):
        """⚠️ The other direction matters as much: fail-closed that refuses
        everything is a preview feature that draws nothing."""
        p = self._preview(self._Clean())
        self.assertEqual(p._drawable({"KC_X": [65, 66]}), {"KC_X": [65, 66]})


class ReportedKeycapsRenderTest(unittest.TestCase):
    """The three keycaps the truncated glyph loader broke (field, 2026-09-01).

    Two were reported — the Context-menu key drew NOTHING and Scroll Lock drew
    "Scr" with its lock badge missing. Pause was broken the same way and nobody
    had noticed. All three are pinned against the SHIPPED data, because that is
    what an ordinary install draws from.
    """

    KEYS = (("KC_APP", 0x0065, "context menu"),
            ("KC_SCROLL_LOCK", 0x0047, "scroll lock"),
            ("KC_PAUSE", 0x0048, "pause"))

    def _preview(self):
        p = KeycapPreview(source="shipped")
        if not p._load():
            self.skipTest(f"no shipped preview data: {p.reason}")
        return p

    def test_each_one_draws_ink(self):
        """⚠️ Ink, not just "an image came back". `ICON_CONTEXT_MENU` was truncated
        to `U" "` — a SPACE — so it resolved, drew, and produced a perfectly valid
        blank keycap. A None check would have passed throughout."""
        p = self._preview()
        for name, kc, label in self.KEYS:
            with self.subTest(key=label):
                img = p.render(kc, name)
                self.assertIsNotNone(img, f"{label}: no preview at all")
                lit = sum(1 for y in range(img.height()) for x in range(img.width())
                          if img.pixel(x, y) & 0xFFFFFF != 0x080A0E)
                self.assertGreater(lit, 20, f"{label}: only {lit} lit pixels")

    def test_scroll_lock_draws_MORE_than_its_three_letters(self):
        """The reported symptom exactly: "Scr" rendered and the badge did not. The
        text alone is ~90px of ink, so a count that only just clears the blank
        threshold above would still be the bug."""
        p = self._preview()
        img = p.render(0x0047, "KC_SCROLL_LOCK")
        self.assertIsNotNone(img)
        # the badge sits right of x=40 (HINT_POS_SCRBOX is x=72); "Scr" ends well
        # before that, so ink out there IS the badge.
        right = sum(1 for y in range(img.height()) for x in range(40, img.width())
                    if img.pixel(x, y) & 0xFFFFFF != 0x080A0E)
        self.assertGreater(right, 40, f"no badge beside the text ({right} px)")
