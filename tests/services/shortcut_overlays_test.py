"""The Phase-2 planner: harvested shortcuts in, keycap masks out.

Offline by construction — no device, no network, no accessibility bridge. The
half that cannot be tested here is the harvest itself, which is also the half
that yields nothing in this container, so everything the planner decides is
pinned rather than argued.
"""

import unittest
from types import SimpleNamespace as NS

from polyhost.device.keys import Modifier
from polyhost.services import shortcut_overlays as so
from polyhost.services.shortcut_source import model

CTRL, SHIFT, ALT, GUI = model.MOD_CTRL, model.MOD_SHIFT, model.MOD_ALT, model.MOD_GUI
KC_S, KC_B, KC_F3 = 0x16, 0x05, 0x3C


def sc(label, mods=CTRL, hid=KC_S):
    return NS(label=label, mods=mods, hid=hid)


class TheNibbleIsShared(unittest.TestCase):
    """⚠️ `Shortcut.mods` is used AS a `Modifier` value with no mapping between.

    The two were written independently — `shortcut_source.model` against the
    GTK/UIA accelerator formats, `device.keys` against the firmware's
    `overlay_mod_variant()` — and both landed on the same L/R-folded nibble. The
    planner and `shortcut_converter` both rely on that, silently, so it is pinned
    here: if either side is ever renumbered, an icon would appear under the wrong
    modifier rather than not at all.
    """

    def test_every_harvested_bit_is_the_same_bit_the_device_uses(self):
        self.assertEqual(model.MOD_CTRL, Modifier.CTRL.value)
        self.assertEqual(model.MOD_SHIFT, Modifier.SHIFT.value)
        self.assertEqual(model.MOD_ALT, Modifier.ALT.value)
        self.assertEqual(model.MOD_GUI, Modifier.GUI_KEY.value)

    def test_a_combination_composes_the_same_way(self):
        self.assertEqual(Modifier(CTRL | SHIFT), Modifier.CTRL_SHIFT)


class PlanTest(unittest.TestCase):

    def test_a_matched_label_lands_on_its_own_modifier_and_key(self):
        (slot,) = so.plan([sc("Save")])
        self.assertEqual((slot.modifier, slot.keycode), (CTRL, KC_S))
        self.assertEqual(slot.concept, "save")
        self.assertTrue(slot.icon)

    def test_an_unmatched_label_is_DROPPED_not_guessed(self):
        """A wrong icon is worse than none — the same rule as app-slug matching."""
        self.assertEqual(so.plan([sc("Frobnicate the widget")]), [])

    def test_a_key_with_no_keycap_slot_is_dropped(self):
        """0x80 is a media key: the firmware has no overlay slot for it."""
        self.assertEqual(so.plan([sc("Save", hid=0x80)]), [])

    def test_a_shortcut_with_NO_modifier_is_kept(self):
        """F3 = Find is a real accelerator; its overlay is simply always up,
        which is what the hand-made templates already do for those keys."""
        (slot,) = so.plan([sc("Find", mods=0, hid=KC_F3)])
        self.assertEqual(slot.modifier, 0)

    def test_a_concept_with_only_a_CODEPOINT_is_dropped(self):
        """This path renders pixels from the CATALOG, so a concept that has only
        a font-pack glyph cannot be drawn by it — the glyph route needs a bundle
        this module cannot flash.

        ⚠️ Driven through a stubbed `match` because NO SHIPPED LEXICON ENTRY has
        this shape: measured, all 47 carry an icon name. So the guard is
        unreachable from the data today and this test says what it is for rather
        than pretending to exercise it from outside. The first attempt used a
        `0x1F4BE` hint and passed for the wrong reason — that string is not a
        valid hint at all, so `match()` refused it before the guard was reached.
        """
        real = so.shortcut_icons.match
        so.shortcut_icons.match = lambda *a, **k: so.shortcut_icons.IconMatch(
            0x1F4BE, "widget", 1.0, "stub", icon="")
        try:
            self.assertEqual(so.plan([sc("Widget")]), [])
        finally:
            so.shortcut_icons.match = real

    def test_a_CATALOG_ONLY_concept_IS_planned(self):
        """The inverse, and the reason the catalog route exists: `bold` has no
        font-pack codepoint and never will without a bundle reship, so it is
        exactly the case a glyph-only implementation could not serve."""
        cp, icon, _ = so.shortcut_icons.LEXICON["bold"]
        self.assertIsNone(cp)
        (slot,) = so.plan([sc("Bold", hid=KC_B)])
        self.assertEqual((slot.concept, slot.icon), ("bold", icon))

    def test_two_shortcuts_on_one_key_keep_the_MORE_CONFIDENT(self):
        """An exact hit and a fuzzy one on the same key: the exact one wins, and
        the loser does not get a slot of its own."""
        plan = so.plan([sc("Preference"), sc("Save")])
        self.assertEqual([(s.concept, s.confidence) for s in plan],
                         [("save", 1.0)])

    def test_the_same_label_on_two_keys_gets_two_slots(self):
        plan = so.plan([sc("Save"), sc("Save", hid=KC_B)])
        self.assertEqual(len(plan), 2)
        self.assertEqual({s.concept for s in plan}, {"save"})

    def test_the_slot_cap_keeps_the_most_confident(self):
        many = [sc("Save", hid=h) for h in range(0x04, 0x30)]
        plan = so.plan(many, limit=3)
        self.assertEqual(len(plan), 3)

    def test_a_blank_label_is_dropped(self):
        """Decided by `match()`, which normalizes to "" and refuses — so there
        is no separate guard here to keep in step with it."""
        self.assertEqual(so.plan([sc("   ")]), [])
        self.assertEqual(so.plan([sc("")]), [])

    def test_an_out_of_range_modifier_is_dropped(self):
        """The nibble is four bits; anything else did not come from a harvest
        this code understands, and inventing a variant for it would address a
        flat index the firmware does not have."""
        self.assertEqual(so.plan([sc("Save", mods=0x10)]), [])


class SourceNameTest(unittest.TestCase):
    """⚠️ The name is the MRU CACHE KEY and a key hit skips the byte compare."""

    def test_the_render_settings_are_PART_of_the_key(self):
        self.assertNotEqual(so.source_name("save", 32, "lower_left"),
                            so.source_name("save", 16, "lower_left"))
        self.assertNotEqual(so.source_name("save", 32, "lower_left"),
                            so.source_name("save", 32, "upper_right"))

    def test_two_apps_sharing_a_concept_share_the_name(self):
        """Which is the whole point of keying on the concept rather than the
        app: Word and Notepad both drawing Save on Ctrl+S is one pool slot and
        one upload, and switching between them re-sends nothing."""
        self.assertEqual(so.source_name("save", 32, "lower_left"),
                         so.source_name("save", 32, "lower_left"))

    def test_it_survives_basename(self):
        """`send_overlays_mru` keys on `os.path.basename(filename)`, so a name
        carrying a separator would collapse to its tail and two concepts could
        collide."""
        import os
        name = so.source_name("save", 32, "lower_left")
        self.assertEqual(os.path.basename(name), name)


class RenderTest(unittest.TestCase):
    """The render half, against a stub catalog — no font, no network."""

    def setUp(self):
        self.drawn = []
        self.real = so.icon_catalog.render_overlay
        so.icon_catalog.render_overlay = self._fake

    def tearDown(self):
        so.icon_catalog.render_overlay = self.real

    def _fake(self, name, font_path, codepoints, height=None, placement=None):
        self.drawn.append(name)
        return None if name == "missing" else f"mask:{name}"

    def test_one_mask_per_CONCEPT_however_many_keys_it_lands_on(self):
        plan = so.plan([sc("Save"), sc("Save", hid=KC_B)])
        out = so.render(plan, "font.ttf", {}, height=32, placement="lower_left")
        self.assertEqual(self.drawn, ["save"])          # rendered once
        (keys,) = out.values()
        self.assertEqual(set(keys), {(CTRL, KC_S), (CTRL, KC_B)})

    def test_a_concept_the_font_lacks_is_DROPPED_not_drawn(self):
        """A missing glyph renders as `.notdef` — a filled box that wipes the
        legend underneath — so `render_overlay` returning None must not become
        an overlay."""
        plan = [so.Slot(CTRL, KC_S, "gone", "missing", "Gone", 1.0)]
        self.assertEqual(so.render(plan, "font.ttf", {}), {})

    def test_icon_names_are_deduped_for_one_subset_request(self):
        plan = so.plan([sc("Save"), sc("Save", hid=KC_B), sc("Bold", hid=0x08)])
        self.assertEqual(so.icon_names(plan), sorted(set(so.icon_names(plan))))


if __name__ == "__main__":
    unittest.main()
