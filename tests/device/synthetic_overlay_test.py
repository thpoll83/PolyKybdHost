"""The generic program mark rides the real transport, on EVERY modifier.

The claim these hold is a COST claim, and it is the one that decides whether the
feature is affordable: the mark must appear under every modifier — a
template-covered app already draws it on every channel, so a generic app going
blank the moment you hold Ctrl is the same key behaving two ways — while costing
ONE pool slot and ONE upload. The pool holds 600 and one menubar app already
takes ~20 for its shortcuts, so a slot per variant is not a rounding error.

Nothing here touches a keyboard: `send_overlays_mru` runs against a fake HID
device and the assertions are on the cache and the mapping it produces.
"""
import unittest
import unittest.mock as mock

import numpy as np

from polyhost.device import synthetic_overlay as syn
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.keys import (KeyCode, Modifier, LEGACY_MAX_MODIFIER_VALUE,
                                  MODIFIER_ANY)
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.overlay_data import OverlayData
from polyhost.device.poly_kybd import PolyKybd
from tests.device.fake_hid import FakeHidDevice, make_hid_helper
from tests.device.poly_kybd_cancel_test import StubPolySettings

ESC = KeyCode.KC_ESCAPE.value


def _mask(row: int = 0):
    img = np.zeros((40, 72), dtype=bool)
    img[row, 34:70] = True          # inside the right-hand box, and NOT all-black
    return img


def _keeb(gui_combos: bool = True):
    keeb = PolyKybd(DeviceSettings(), StubPolySettings())
    keeb.hid = make_hid_helper(FakeHidDevice(auto_ack=True))
    # `supports()` reads the negotiated protocol; the variant filter is the only
    # thing this suite cares about, so drive it directly rather than staging a
    # whole GET_ID exchange.
    keeb.supports = lambda feature: gui_combos if feature == "gui_combo_modifiers" else True
    return keeb


def _template(overlays):
    """A stand-in for `ImageConverter` — a real file-backed source."""
    converter = mock.MagicMock()
    converter.open.return_value = True
    converter.extract_overlays.side_effect = lambda mod: dict(overlays.get(mod, {})) or None
    # A real converter has no such attribute at all; that absence is what the
    # send loop's getattr default stands for.
    del converter.modifier_invariant
    return converter


class ProgramConverterTest(unittest.TestCase):

    def test_the_mark_is_offered_under_EVERY_modifier(self):
        # The fix itself. A template draws `program_icon:` on every channel, so
        # a generic app offering NO_MOD alone is the same keycap behaving two
        # ways depending on which app is focused.
        conv = syn.program_converter(DeviceSettings(), ESC, _mask())
        for modifier in Modifier:
            self.assertEqual(list(conv.extract_overlays(modifier) or {}), [ESC],
                             f"missing under {modifier}")

    def test_it_declares_itself_modifier_invariant(self):
        # The flag is what lets the send loop key it once. Without it the same
        # bytes would be filed under 16 keys.
        conv = syn.program_converter(DeviceSettings(), ESC, _mask())
        self.assertTrue(conv.modifier_invariant)

    def test_ONE_OverlayData_is_shared_across_the_variants(self):
        # It is a read-only value object, and rebuilding it per modifier would
        # re-run the RLE and ROI encoders 16 times on identical pixels.
        conv = syn.program_converter(DeviceSettings(), ESC, _mask())
        seen = {id(conv.extract_overlays(m)[ESC]) for m in Modifier}
        self.assertEqual(len(seen), 1)

    def test_an_INKLESS_mask_yields_no_converter_at_all(self):
        # An empty overlay costs a pool slot and a send to draw nothing.
        self.assertIsNone(syn.program_converter(
            DeviceSettings(), ESC, np.zeros((40, 72), dtype=bool)))

    def test_a_file_backed_converter_is_NOT_invariant(self):
        # The default has to be off: a `*.mods.png` carries a different picture
        # in each channel, and keying those once would show one of them everywhere.
        conv = syn.SyntheticConverter({Modifier.NO_MOD: {ESC: object()}})
        self.assertFalse(conv.modifier_invariant)


class OnePoolSlotTest(unittest.TestCase):
    """The cost claim, measured through the real send path."""

    def _send(self, gui_combos=True, extra_sources=()):
        keeb = _keeb(gui_combos)
        cache = OverlayMRUCache(600)
        name = syn.program_name("inkscape")
        conv = syn.program_converter(DeviceSettings(), ESC, _mask())
        uploads = []
        real = keeb.send_smallest_overlay

        def counting(keycode, modifier, mapping):
            uploads.append((keycode, modifier))
            return real(keycode, modifier, mapping)

        keeb.send_smallest_overlay = counting
        mapping_sent = {}
        keeb.send_overlay_mapping = lambda m: (mapping_sent.update(m), (True, ""))[1]
        keeb.prepare_for_mru_send = lambda: (True, "")
        keeb.enable_overlays = lambda: True
        cache.record_transferred_mapping = lambda m: None

        names = [n for n, _ in extra_sources] + [name]
        synthetic = {name: conv}
        with mock.patch("polyhost.device.poly_kybd.ImageConverter") as MockConverter:
            MockConverter.side_effect = [c for _, c in extra_sources]
            ok = keeb.send_overlays_mru(names, cache, synthetic=synthetic)
        self.assertTrue(ok)
        return uploads, mapping_sent, cache

    def test_ONE_upload_and_SIXTEEN_mappings_on_a_current_keyboard(self):
        # The whole point: N display indices may point at one pool slot, so the
        # variants after the first are cache HITS that send nothing.
        uploads, mapping, _ = self._send(gui_combos=True)
        self.assertEqual(len(uploads), 1)
        self.assertEqual(len(mapping), len(Modifier))

    def test_ONE_upload_and_NINE_mappings_on_a_pre_v12_keyboard(self):
        # An older board folds every GUI+x chord onto GUI_KEY and has no flat
        # index space above 90*9, so the send loop drops 9..15 — leaving exactly
        # the nine legacy variants, still from one upload.
        uploads, mapping, _ = self._send(gui_combos=False)
        self.assertEqual(len(uploads), 1)
        self.assertEqual(len(mapping), LEGACY_MAX_MODIFIER_VALUE + 1)
        self.assertEqual(len(mapping), 9)      # the plan's number, spelled out

    def test_every_variant_points_at_the_SAME_pool_slot(self):
        # A per-variant slot would also produce a full mapping, so counting
        # mappings alone cannot tell the two apart.
        _, mapping, _ = self._send()
        self.assertEqual(len(set(mapping.values())), 1)

    def test_the_cache_holds_ONE_entry_for_the_mark(self):
        # Keyed on MODIFIER_ANY rather than 16 times on a real variant value.
        _, _, cache = self._send()
        keys = [k for k in cache._cache if k[0].startswith(syn.PROGRAM_PREFIX)]
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys[0][1], MODIFIER_ANY)

    def test_a_REAL_TEMPLATE_wins_the_keys_it_draws(self):
        # The hand-made design always beats the generic mark, and the mark still
        # fills the variants the template left alone — so ESC is never blank.
        template = _template({Modifier.NO_MOD: {ESC: OverlayData(DeviceSettings(), _mask(3))}})
        _, mapping, _ = self._send(extra_sources=[("app.mods.png", template)])
        no_mod = OverlayMRUCache.display_flat_idx(ESC, Modifier.NO_MOD)
        ctrl = OverlayMRUCache.display_flat_idx(ESC, Modifier.CTRL)
        self.assertNotEqual(mapping[no_mod], mapping[ctrl])


class SummaryLogTest(unittest.TestCase):
    """What the log says about what just reached the keyboard.

    This is the only record of where the generic mark went — the keycaps are the
    other one, and they are on a desk somewhere.
    """

    def setUp(self):
        self.keeb = _keeb()
        self.lines = []
        self.keeb.log = mock.MagicMock()
        self.keeb.log.info.side_effect = lambda fmt, *a: self.lines.append(fmt % a)

    def test_ONE_key_on_many_variants_NAMES_the_key(self):
        # ⚠️ The E3 case, and a bare count is useless for it: the mark is one key
        # on up to 16 variants, and "15 keycap(s)" cannot be told apart from
        # fifteen DIFFERENT keys — which is the whole behaviour of the feature.
        keys = [(ESC, m) for m in list(Modifier)[:15]]
        self.assertEqual(
            self.keeb._describe_sources({syn.program_name("inkscape"): keys}),
            "mark inkscape=ESC on 15 modifier variant(s)")

    def test_a_few_DIFFERENT_keys_are_still_spelled_out(self):
        self.assertEqual(
            self.keeb._describe_sources({"app.mods.png": [
                (ESC, Modifier.NO_MOD), (KeyCode.KC_S.value, Modifier.CTRL)]}),
            "app=ESC, Ctrl+S")

    def test_MANY_different_keys_fall_back_to_a_count(self):
        # A template covers most of the board; listing it would bury the line.
        keys = [(kc, Modifier.NO_MOD) for kc in range(4, 4 + 31)]
        self.assertIn("31 keycap(s)",
                      self.keeb._describe_sources({"app.mods.png": keys}))

    def test_the_summary_is_TWO_lines_however_many_sources_there_are(self):
        """⚠️ A gap-filled app has a template plus five or six synthetic
        sources, and a line each buried the one question a reader has -- which
        generic icons were taken and which were not -- under a paragraph they
        had to reassemble by eye."""
        per = {"app.mods.png": [(kc, Modifier.NO_MOD) for kc in range(4, 37)]}
        for concept in ("bookmark", "help", "edit", "description", "visibility"):
            per["@sc:fluent:%s:36lower_right" % concept] = [(ESC, Modifier.ALT)]
        self.keeb._log_overlay_summary(per, uploaded=19, mapped=38, deferred={})
        self.assertEqual(len(self.lines), 2, self.lines)
        self.assertIn("fluent:bookmark=", self.lines[1])

    def test_the_GEOMETRY_is_dropped_and_the_FACE_is_kept(self):
        """The height and corner are user settings and identical for every
        source in one send, so repeating them six times on a line is noise. The
        face is not: it says whether a concept came from Fluent or from the
        Material fall-back. ⚠️ A concept may itself contain `:`, so the last
        segment comes off rather than the name being split from the front."""
        self.assertEqual(
            self.keeb._short_source("@sc:material:icon:description:36lower_right"),
            "material:icon:description")

    def test_a_WINDOWS_template_path_is_shortened_off_Windows_too(self):
        """These paths are built on the machine that owns the keyboard, but the
        log is read elsewhere — and `posixpath.basename` does not split a
        Windows path, so it hands back the whole `C:\\...` that this line
        exists to remove."""
        self.assertEqual(
            self.keeb._short_source(
                "C:\\Users\\t\\res\\overlays\\sevenzip_template.mods.png"),
            "sevenzip_template")

    def test_a_PARTIAL_deferral_is_reported_even_though_the_source_DREW(self):
        # ⚠️ The first cut skipped any source present in `per_source`, so on a
        # template-covered app the mark drawing 15 variants and losing the bare
        # ESC was reported as drawing 15 and nothing else. "It lost ESC to the
        # template" is exactly the question a reader has when the keycap shows
        # the hand-made design instead of the app's own icon.
        name = syn.program_name("inkscape")
        self.keeb._log_overlay_summary(
            per_source={name: [(ESC, Modifier.CTRL)]},
            uploaded=1, mapped=1,
            deferred={name: [(ESC, Modifier.NO_MOD)]})
        self.assertTrue(any("deferred to the template" in line for line in self.lines),
                        self.lines)

    def test_a_source_that_drew_NOTHING_is_still_named(self):
        # Its silent absence reads as "the icon was never fetched" (field, 2026-09-10).
        name = syn.program_name("word")
        self.keeb._log_overlay_summary(per_source={}, uploaded=0, mapped=0,
                                       deferred={name: [(ESC, Modifier.NO_MOD)]})
        self.assertTrue(any("mark word" in line and "deferred" in line
                            for line in self.lines), self.lines)

    def test_NOTHING_deferred_still_SAYS_so(self):
        """⚠️ "Which were not taken" is the question, and an omitted clause
        answers it only if the reader knows the clause exists."""
        self.keeb._log_overlay_summary({"app.mods.png": [(ESC, Modifier.NO_MOD)]},
                                       uploaded=1, mapped=1, deferred={})
        self.assertIn("deferred to the template: none", self.lines[1])

    def test_the_two_adjacent_COUNTS_do_not_both_say_upload(self):
        # ⚠️ `MRU: N ...` counts HID MESSAGES and `Overlays: ... N uploaded`
        # counts KEYCAPS, so two adjacent lines both reading "N upload(s)" are a
        # contradiction at a glance (measured on a real send: 4 against 2). This
        # regressed once by porting the second line next to the older first one.
        import inspect
        source = inspect.getsource(type(self.keeb).send_overlays_mru)
        self.assertIn("HID message(s) of image data", source)
        self.assertNotIn("image upload(s)", source)


class CacheKeyPairingTest(unittest.TestCase):
    """Each source is keyed under ITS OWN name."""

    def test_two_sources_are_not_keyed_under_the_LAST_filename(self):
        # ⚠️ A bare `for converter in converters` leaves `filename` at the last
        # entry of the decode loop for every source, so two files collide in the
        # MRU cache — the second app's keycap silently serves the first's image,
        # with no upload and nothing in the log. Harmless only while the shipped
        # naming convention keeps each file's variants disjoint; the program mark
        # breaks that, because it offers every variant of ESC.
        keeb = _keeb()
        cache = OverlayMRUCache(600)
        a = _template({Modifier.NO_MOD: {KeyCode.KC_A.value: OverlayData(DeviceSettings(), _mask(1))}})
        b = _template({Modifier.NO_MOD: {KeyCode.KC_B.value: OverlayData(DeviceSettings(), _mask(2))}})
        keeb.send_overlay_mapping = lambda m: (True, "")
        keeb.prepare_for_mru_send = lambda: (True, "")
        keeb.enable_overlays = lambda: True
        cache.record_transferred_mapping = lambda m: None
        with mock.patch("polyhost.device.poly_kybd.ImageConverter") as MockConverter:
            MockConverter.side_effect = [a, b]
            self.assertTrue(keeb.send_overlays_mru(["one.png", "two.png"], cache))
        self.assertEqual({k[0] for k in cache._cache}, {"one.png", "two.png"})


if __name__ == "__main__":
    unittest.main()
