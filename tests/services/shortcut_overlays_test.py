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
        cp, _icon, _ = so.shortcut_icons.LEXICON["bold"]
        self.assertIsNone(cp)
        (slot,) = so.plan([sc("Bold", hid=KC_B)])
        # ⚠️ QUALIFIED, and resolved through `icon_for` rather than read off the
        # lexicon tuple: which catalog draws a concept is the concept's own
        # property, so a test reading the raw Material spelling would pass while
        # the render drew from the other face.
        self.assertEqual((slot.concept, slot.icon),
                         ("bold", so.shortcut_icons.icon_for("bold")))

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

    @staticmethod
    def _face_of(concept):
        """The face `plan` will qualify this concept with — never hardcoded, or
        the test pins today's curation rather than the mechanism."""
        return so.icon_catalog.split_face(so.shortcut_icons.icon_for(concept))[0]

    def test_one_mask_per_CONCEPT_however_many_keys_it_lands_on(self):
        plan = so.plan([sc("Save"), sc("Save", hid=KC_B)])
        face, bare = so.icon_catalog.split_face(plan[0].icon)
        out = so.render(plan, "font.ttf", {}, height=32, placement="lower_left",
                        face=face)
        self.assertEqual(self.drawn, [bare])            # rendered once
        (keys,) = out.values()
        self.assertEqual(set(keys), {(CTRL, KC_S), (CTRL, KC_B)})

    def test_icon_names_by_face_SPLITS_the_two_catalogs(self):
        """⚠️ What stops one catalog being asked for the other's names.

        The fetcher turns this into one subset request per face. Flattened, it
        would send Fluent stems (`arrow_undo`, `dismiss`) to Google's
        `icon_names=` endpoint, which answers with a font that simply lacks
        them — every Fluent concept then renders nothing, with no error.

        Mutation-checked: this test is the only thing that fails when the
        grouping collapses to a single bucket.
        """
        plan = so.plan([sc("Save"), sc("Copy", hid=KC_B)])
        by_face = so.icon_names_by_face(plan)
        self.assertGreater(len(by_face), 1, "the fixture must span both faces")
        for face, names in by_face.items():
            for name in names:
                with self.subTest(face=face, name=name):
                    self.assertNotIn(":", name, "names must arrive BARE")
        # Every planned slot is accounted for, in its own face's bucket.
        for slot in plan:
            want_face, bare = so.icon_catalog.split_face(slot.icon)
            self.assertIn(bare, by_face[want_face])

    def test_a_slot_from_ANOTHER_FACE_is_skipped_not_drawn(self):
        """⚠️ The property that makes one font per call safe. A plan routinely
        mixes faces, and `font_path` belongs to exactly one of them — drawing a
        Fluent slot out of the Material subset would look up a codepoint from
        the wrong table and render whatever glyph happens to live there."""
        plan = so.plan([sc("Save")])
        other = next(f for f in so.icon_catalog.FACES
                     if f != so.icon_catalog.split_face(plan[0].icon)[0])
        out = so.render(plan, "font.ttf", {}, height=32, placement="lower_left",
                        face=other)
        self.assertEqual(self.drawn, [])
        self.assertEqual(out, {})

    def test_the_MRU_name_carries_the_face(self):
        """⚠️ `get_or_allocate` takes an exact key hit BEFORE comparing bytes, so
        a name without the face would keep serving whichever face filled that
        slot first — switching catalogs would change nothing on the device."""
        plan = so.plan([sc("Save")])
        face, _ = so.icon_catalog.split_face(plan[0].icon)
        out = so.render(plan, "font.ttf", {}, height=32, placement="lower_left",
                        face=face)
        (name,) = out
        self.assertIn(face, name.split(":"))
        self.assertNotEqual(name, so.source_name("save", 32, "lower_left",
                                                 face="not-a-face"))

    def test_a_concept_the_font_lacks_is_DROPPED_not_drawn(self):
        """A missing glyph renders as `.notdef` — a filled box that wipes the
        legend underneath — so `render_overlay` returning None must not become
        an overlay."""
        plan = [so.Slot(CTRL, KC_S, "gone", "missing", "Gone", 1.0)]
        self.assertEqual(so.render(plan, "font.ttf", {}), {})

    def test_icon_names_are_deduped_for_one_subset_request(self):
        plan = so.plan([sc("Save"), sc("Save", hid=KC_B), sc("Bold", hid=0x08)])
        self.assertEqual(so.icon_names(plan), sorted(set(so.icon_names(plan))))


class TestDerivedNameFallback(unittest.TestCase):
    """The no-config half: a label the lexicon never heard of still gets an icon.

    ⚠️ The table here is SYNTHETIC, not `icon_catalog.load_codepoints()`. The
    real one is a fetched cache, so a test against it passes or fails on whether
    this machine has downloaded a font -- which is not what these pin. What they
    pin is the ORDER (curated beats derived), the REJECT (a derivation the
    catalog does not carry draws nothing) and the DEGRADATION (no table, no
    fall-back).
    """

    # Just enough of Material Symbols to answer the labels below.
    TABLE = {"save": 1, "file_export": 2, "rotate_right": 3, "search": 4}

    def test_the_lexicon_still_wins_where_it_has_an_opinion(self):
        """Derivation is RECALL; the lexicon is precision, and precision leads.

        Both resolve "Save". The curated answer must be the one that ships, and
        must outrank a derived one when two shortcuts contend for a key.
        """
        slots = so.plan([sc("Save")], known_names=self.TABLE)
        self.assertEqual(slots[0].icon, so.shortcut_icons.icon_for("save"))
        self.assertGreater(slots[0].confidence, so.DERIVED_CONFIDENCE)

    def test_a_label_the_lexicon_does_not_know_is_DERIVED(self):
        """`Export as PDF` is in no concept's phrase list; `file_export` is in
        the catalog. Before this it was refused as NO_CONCEPT."""
        slots = so.plan([sc("Export as PDF")], known_names=self.TABLE)
        # ⚠️ MATERIAL by construction: `known_names` IS the Material table, and
        # nothing derives into Fluent's vocabulary (see FLUENT_ICONS).
        self.assertEqual(slots[0].icon,
                         f"{so.icon_catalog.MATERIAL}:file_export")
        self.assertEqual(slots[0].confidence, so.DERIVED_CONFIDENCE)

    def test_a_derivation_the_CATALOG_LACKS_draws_nothing(self):
        """⚠️ The reject, and the reason derivation is safe to guess with: it
        proposes, the catalog disposes. Without this a made-up name would reach
        the renderer and the keycap would come back blank with nothing to say
        why -- the failure mode this whole area is built to avoid."""
        self.assertEqual(so.plan([sc("Frobnicate The Widget")],
                                 known_names=self.TABLE), [])

    def test_with_NO_table_the_fallback_is_skipped_entirely(self):
        """A caller that cannot load the codepoints gets the old behaviour, not
        a crash and not an unvalidated guess."""
        self.assertEqual(so.plan([sc("Export as PDF")]), [])

    # --- the focused app reaches the derivation ------------------------------

    APP_TABLE = {"terminal": 5, "file_export": 2}

    # ⚠️ "Reveal Terminal", NOT "Hide Terminal". `hide` is itself a catalog name
    # and the HEAD is offered before the tail, so on a Hide label the planner
    # answers `hide` whether or not it passed the app -- the test would pass
    # against the unwired planner and pin nothing. The label has to be one whose
    # ONLY viable candidate is the app's name. Found by the mutation sweep,
    # which is exactly the escape it exists to catch.
    def test_a_derivation_in_the_PLANNER_never_names_the_app(self):
        """⚠️ The WIRING, not the rule -- `derive_names` is tested directly in
        shortcut_icons_test. What this pins is that `plan_report` actually HANDS
        it the app, which is the half that was missing for three attempts."""
        self.assertEqual(so.plan([sc("Reveal Terminal")],
                                 known_names=self.APP_TABLE, app="Terminal"), [])

    def test_the_app_name_really_is_on_offer_without_it(self):
        """⚠️ Otherwise the test above passes for the wrong reason: `terminal`
        must be BOTH derivable and in the table, or nothing is being rejected —
        and without the app it must actually DRAW, or the planner is refusing
        for some unrelated reason."""
        self.assertIn("terminal",
                      so.shortcut_icons.derive_names("Reveal Terminal"))
        self.assertIn("terminal", self.APP_TABLE)
        slots = so.plan([sc("Reveal Terminal")], known_names=self.APP_TABLE)
        self.assertEqual(slots[0].icon,
                         f"{so.icon_catalog.MATERIAL}:terminal")

    def test_planning_without_an_app_is_unchanged(self):
        """Every existing caller passes no app and must plan as it always did."""
        slots = so.plan([sc("Export as PDF")], known_names=self.APP_TABLE)
        self.assertEqual(slots[0].icon,
                         f"{so.icon_catalog.MATERIAL}:file_export")




class PlanReportTest(unittest.TestCase):
    """What the log prints, and why each refusal is named separately.

    ⚠️ A single "no icon" count cannot be acted on. "The keyboard has no keycap
    for that key" is nothing anyone can fix; "no icon concept matched the label"
    is a curation entry; "the concept has no catalog icon" is a lexicon gap. The
    report exists so a user can say which of the three they are looking at.
    """

    def test_each_refusal_is_reported_under_its_OWN_reason(self):
        report = so.plan_report([
            sc("Save"),                                  # drawn
            sc("Frobnicate"),                            # no concept
            sc("Save", hid=0x80),                        # no keycap
        ])
        self.assertEqual(len(report.slots), 1)
        # ⚠️ Compare against the LITERAL reasons, not against the constants.
        # `{so.NO_CONCEPT, so.NO_KEYCAP}` collapses to one element if the two
        # constants are ever made equal, and the assertion then passes over
        # exactly the merge it exists to forbid — mutation-checked.
        self.assertEqual(sorted(report.refused), sorted([
            "no icon concept matched the label",
            "the keyboard has no keycap for that key"]))
        self.assertEqual([len(v) for _, v in sorted(report.refused.items())], [1, 1])

    def test_the_reasons_are_DISTINCT_strings(self):
        """Each names a different fix — nothing to do, a curation entry, a
        lexicon gap, a cap — so two that read alike are one that cannot be
        acted on."""
        reasons = [so.NO_KEYCAP, so.NO_CONCEPT, so.NO_CATALOG_ICON, so.OVER_CAP]
        self.assertEqual(len(set(reasons)), len(reasons))

    def test_a_refusal_names_the_KEY_and_the_LABEL(self):
        """Either alone is unusable: the key without the label does not say what
        was meant, and the label without the key does not say where to look."""
        report = so.plan_report([sc("Frobnicate", mods=CTRL | SHIFT, hid=KC_B)])
        (item,) = report.refused[so.NO_CONCEPT]
        self.assertIn("Ctrl+Shift+B", item)
        self.assertIn("Frobnicate", item)

    def test_the_cap_reports_what_it_dropped(self):
        """Silently drawing 48 of 60 would read as the other 12 having failed."""
        report = so.plan_report([sc("Save", hid=h) for h in range(0x04, 0x30)],
                                limit=3)
        self.assertEqual(len(report.slots), 3)
        self.assertEqual(len(report.refused[so.OVER_CAP]), 0x30 - 0x04 - 3)

    def test_the_summary_counts_both_halves(self):
        report = so.plan_report([sc("Save"), sc("Frobnicate")])
        self.assertIn("1 drawn", report.summary())
        self.assertIn(so.NO_CONCEPT, report.summary())

    def test_plan_is_just_the_slots_of_a_report(self):
        """So the two can never disagree about what gets drawn."""
        shortcuts = [sc("Save"), sc("Frobnicate"), sc("Bold", hid=KC_B)]
        self.assertEqual(so.plan(shortcuts), so.plan_report(shortcuts).slots)


class BareKeypressTest(unittest.TestCase):
    """⚠️ A bare-key "shortcut" on a letter is always wrong on this keyboard.

    The overlay for an unmodified chord is drawn on the UNMODIFIED layer — over
    the letter the key actually types. Reported from the field (macOS Safari,
    2026-09-21): `D`, `E` and `F` each drew an icon, and in a browser those keys
    just type `d`, `e`, `f`. The menu items are real; their bindings need a
    modifier this backend cannot see (fn/globe is absent from the Carbon mask,
    so it decodes as no modifiers at all).
    """

    def test_the_FIELD_CASE_is_refused(self):
        for hid, key in ((0x07, "D"), (0x08, "E"), (0x09, "F")):
            with self.subTest(key=key):
                self.assertTrue(so.needs_a_modifier(hid, 0))

    def test_SHIFT_ALONE_is_not_a_modifier_for_this_purpose(self):
        """Shift+E is a capital E — its overlay lands on the Shift layer of a
        key that still types."""
        self.assertTrue(so.needs_a_modifier(0x08, model.MOD_SHIFT))

    def test_a_REAL_modifier_is_accepted(self):
        for mod in (model.MOD_CTRL, model.MOD_ALT, model.MOD_GUI):
            with self.subTest(mod=mod):
                self.assertFalse(so.needs_a_modifier(0x08, mod))
                self.assertFalse(so.needs_a_modifier(0x08,
                                                     mod | model.MOD_SHIFT))

    def test_a_key_that_TYPES_NOTHING_keeps_its_bare_shortcut(self):
        """⚠️ The half that stops this being a blunt "drop every bare chord".
        F5 refresh, bare Home, a bare arrow: those keys insert nothing, so an
        icon on them is honest and must survive."""
        for hid, key in ((0x3A, "F1"), (0x3E, "F5"), (0x4A, "Home"),
                         (0x4F, "Right"), (0x52, "Up"), (0x29, "Esc")):
            with self.subTest(key=key):
                self.assertFalse(so.needs_a_modifier(hid, 0))

    def test_SPACE_and_the_punctuation_are_typing_keys(self):
        for hid, key in ((0x2C, "Space"), (0x2D, "-"), (0x38, "/"),
                         (0x1E, "1"), (0x28, "Enter"), (0x2B, "Tab")):
            with self.subTest(key=key):
                self.assertTrue(so.needs_a_modifier(hid, 0))

    def test_a_MISSING_hid_is_not_this_rule_s_business(self):
        """`displayable_hid` refuses it first and says so with its own reason;
        answering True here would relabel that refusal."""
        self.assertFalse(so.needs_a_modifier(None, 0))

    def test_the_PLANNER_refuses_it_and_names_the_reason(self):
        report = so.plan_report([
            NS(label="Emoji & Symbols", hid=0x08, mods=0),
            NS(label="Copy", hid=0x06, mods=model.MOD_GUI),
        ])
        self.assertEqual([s.keycode for s in report.slots], [0x06])
        self.assertIn(so.NO_MODIFIER, report.refused)
        self.assertEqual(len(report.refused[so.NO_MODIFIER]), 1)

    def test_it_is_refused_BEFORE_the_icon_lookup(self):
        """⚠️ Whether the label happens to match a concept is irrelevant, and
        refusing early also keeps it out of the MAX_SLOTS budget, where it would
        displace a real shortcut."""
        bare = [NS(label="Copy", hid=0x06, mods=0)]      # a label that DOES match
        report = so.plan_report(bare)
        self.assertEqual(report.slots, [])
        self.assertIn(so.NO_MODIFIER, report.refused)


class KeyNameTest(unittest.TestCase):
    """The log is only useful if the key it names is the key on the keyboard."""

    def test_letters_digits_and_the_zero_that_is_not_where_you_expect(self):
        self.assertEqual(so.key_name(0x04), "A")
        self.assertEqual(so.key_name(0x1D), "Z")
        self.assertEqual(so.key_name(0x1E), "1")
        self.assertEqual(so.key_name(0x26), "9")
        # ⚠️ HID puts 0 AFTER 9, not before 1 — deriving it from the digit run
        # would print "0" as ":" or shift every digit by one.
        self.assertEqual(so.key_name(0x27), "0")

    def test_the_function_row_and_the_nav_cluster(self):
        self.assertEqual(so.key_name(0x3A), "F1")
        self.assertEqual(so.key_name(0x45), "F12")
        self.assertEqual(so.key_name(0x4C), "Delete")

    def test_an_unnamed_usage_prints_its_id_rather_than_guessing(self):
        self.assertEqual(so.key_name(0x99), "0x99")

    def test_modifiers_print_in_a_STABLE_order(self):
        """So two lines about the same chord read the same in a pasted log."""
        self.assertEqual(so.pretty_key(CTRL | SHIFT | ALT, KC_S), "Ctrl+Shift+Alt+S")
        self.assertEqual(so.pretty_key(0, KC_S), "S")


class LexiconNamesByFace(unittest.TestCase):
    """The stable icon set that makes the Material subset ONE cached file."""

    def test_every_concept_the_lexicon_can_pick_is_in_the_floor(self):
        """A concept missing here is one whose icon silently stops drawing on
        an app that needs nothing else -- the union at the call site would then
        be the floor exactly, so the stable font would be fetched WITHOUT it."""
        floor = so.lexicon_names_by_face()
        for concept in so.shortcut_icons.LEXICON:
            qualified = so.shortcut_icons.icon_for(concept)
            if not qualified:
                continue
            face, name = so.icon_catalog.split_face(qualified)
            self.assertIn(name, floor.get(face, ()),
                          "%s (%s) is not in the floor" % (concept, qualified))

    def test_an_icon_hint_outside_the_lexicon_is_in_the_floor_too(self):
        floor = so.lexicon_names_by_face({"whatever": "icon:rocket_launch",
                                          "other": "icon:fluent:toolbox"})
        self.assertIn("rocket_launch", floor["material"])
        self.assertIn("toolbox", floor["fluent"])

    def test_the_names_are_BARE_because_that_is_what_a_subset_request_takes(self):
        floor = so.lexicon_names_by_face()
        for names in floor.values():
            for name in names:
                self.assertNotIn(":", name, "%s carries a face prefix" % name)

    def test_TWO_APPS_that_need_only_lexicon_icons_ask_for_the_SAME_SET(self):
        """The property the whole thing exists for. `subset_path` keys its
        cache on the set requested, so two apps asking for different sets are
        two files and two HTTPS round-trips. Measured against Google's
        endpoint: one app subset is 4,428 bytes and a fetch is 300-450 ms, paid
        again on first sight of every application, forever."""
        floor = so.lexicon_names_by_face()
        material = floor["material"]
        one = sorted(set(material[:1]) | set(material))
        two = sorted(set(material[-1:]) | set(material))
        self.assertEqual(one, two)
        self.assertEqual(so.icon_catalog.subset_path(one, "/c"),
                         so.icon_catalog.subset_path(two, "/c"))

    def test_a_DERIVED_name_outside_the_floor_still_gets_its_own_font(self):
        """The floor is a floor, not a ceiling: an app whose label derived a
        catalog name the tables do not carry must still have it fetched."""
        material = so.lexicon_names_by_face()["material"]
        self.assertNotEqual(
            so.icon_catalog.subset_path(sorted(set(material) | {"rocket_launch"}), "/c"),
            so.icon_catalog.subset_path(material, "/c"))


if __name__ == "__main__":
    unittest.main()
