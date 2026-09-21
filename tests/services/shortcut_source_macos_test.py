"""The macOS backend: the AX menu walk, and the parser that reads a key equivalent.

⚠️ **These tests are the ONLY thing standing behind this backend.** The AX calls
have never run against a real application, so the fake tree below is my idea of
what macOS hands back, not a measurement — which is exactly why the tests that
matter are the ones pinning the three counter-intuitive rules in
`model.py`'s macOS section. Each of those, got wrong, produces a keycap that is
confidently wrong rather than missing:

  1. Command is IMPLIED; bit 3 is its ABSENCE.
  2. A menu shows its letter upper case whatever the binding is, so case is not Shift.
  3. `AXMenuItemCmdVirtualKey` 0 is `kVK_ANSI_A`, so it needs `is None`.

A round trip through a fake tree can only prove the walk is self-consistent. It
cannot prove the tree is shaped the way a Mac shapes it.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from polyhost.services import shortcut_source as ss
from polyhost.services.shortcut_source import macos
from polyhost.services.shortcut_source.model import (
    MOD_ALT, MOD_CTRL, MOD_GUI, MOD_SHIFT, mac_mods_to_qmk, parse_mac_accel)


class ModifierMaskTest(unittest.TestCase):
    """Carbon's mask, including the bit that means the opposite of what it says."""

    def test_a_ZERO_mask_is_Command_alone(self):
        # ⚠️ The whole platform hangs off this. Read as a plain bitmask, 0 means
        # "no modifiers" and every ⌘-shortcut on the machine becomes a bare key.
        self.assertEqual(mac_mods_to_qmk(0), MOD_GUI)

    def test_bit_3_means_Command_is_ABSENT(self):
        self.assertEqual(mac_mods_to_qmk(macos_no_command()), 0)

    def test_each_carbon_bit_maps_to_its_own_qmk_bit(self):
        self.assertEqual(mac_mods_to_qmk(0x01), MOD_GUI | MOD_SHIFT)
        self.assertEqual(mac_mods_to_qmk(0x02), MOD_GUI | MOD_ALT)
        self.assertEqual(mac_mods_to_qmk(0x04), MOD_GUI | MOD_CTRL)

    def test_a_full_mask_without_command_is_the_other_three(self):
        self.assertEqual(mac_mods_to_qmk(0x0F), MOD_SHIFT | MOD_ALT | MOD_CTRL)

    def test_every_mask_stays_inside_the_qmk_nibble(self):
        # plan_report() refuses anything outside 0..0x0F, so a mask that escaped
        # the nibble would be dropped later and silently.
        for mask in range(0x10):
            self.assertLessEqual(mac_mods_to_qmk(mask), 0x0F)


def macos_no_command() -> int:
    return 0x08


class KeyEquivalentTest(unittest.TestCase):
    """`AXMenuItemCmdChar` / `AXMenuItemCmdVirtualKey` -> a drawable key."""

    def test_an_UPPER_CASE_letter_is_display_and_not_Shift(self):
        # ⚠️ A Mac menu renders ⌘S with a capital S, so inferring Shift from the
        # case would put Shift on essentially every shortcut on the platform.
        accel = parse_mac_accel("S", None, 0)
        self.assertEqual(accel.mods, MOD_GUI)
        self.assertNotEqual(accel.mods & MOD_SHIFT, MOD_SHIFT)
        self.assertEqual(accel.hid, 0x16)                      # the 's' key

    def test_upper_and_lower_case_reach_the_same_key(self):
        self.assertEqual(parse_mac_accel("S", None, 0).hid,
                         parse_mac_accel("s", None, 0).hid)

    def test_a_shifted_binding_takes_Shift_from_the_MASK(self):
        accel = parse_mac_accel("S", None, 0x01)
        self.assertEqual(accel.mods, MOD_GUI | MOD_SHIFT)

    def test_virtual_key_ZERO_is_the_A_key_and_not_an_absent_key(self):
        # ⚠️ kVK_ANSI_A is 0x00, so a truthiness test here drops every ⌘A.
        accel = parse_mac_accel("", 0x00, 0)
        self.assertIsNotNone(accel)
        self.assertEqual(accel.hid, 0x04)
        self.assertEqual(accel.keysym, "a")

    def test_an_arrow_arrives_as_a_private_use_character(self):
        # Cocoa stores a key equivalent as a CHARACTER, so an arrow is
        # NSUpArrowFunctionKey (U+F700) rather than a virtual key.
        self.assertEqual(parse_mac_accel(chr(0xF700), None, 0).hid, 0x52)
        self.assertEqual(parse_mac_accel(chr(0xF703), None, 0).keysym, "Right")

    def test_the_PUA_block_carries_the_function_keys(self):
        self.assertEqual(parse_mac_accel(chr(0xF704), None, 0).keysym, "F1")
        self.assertEqual(parse_mac_accel(chr(0xF704 + 11), None, 0).keysym, "F12")
        self.assertEqual(parse_mac_accel(chr(0xF704 + 11), None, 0).hid, 0x45)

    def test_the_literal_control_characters(self):
        self.assertEqual(parse_mac_accel("\r", None, 0).hid, 0x28)   # Return
        self.assertEqual(parse_mac_accel("\t", None, 0).hid, 0x2B)   # Tab
        self.assertEqual(parse_mac_accel("\x1b", None, 0).hid, 0x29)  # Escape
        self.assertEqual(parse_mac_accel("\x7f", None, 0).hid, 0x2A)  # ⌫

    def test_space_is_a_key_and_not_an_empty_binding(self):
        accel = parse_mac_accel(" ", None, 0)
        self.assertIsNotNone(accel)
        self.assertEqual(accel.hid, 0x2C)

    def test_no_character_and_no_virtual_key_is_no_shortcut(self):
        self.assertIsNone(parse_mac_accel("", None, 0))
        self.assertIsNone(parse_mac_accel("", None, None))

    def test_an_unknown_virtual_key_is_NAMED_but_not_displayable(self):
        # Reported rather than guessed: the label still reaches the curation
        # file, and `displayable` False keeps it off a keycap.
        accel = parse_mac_accel("", 0xFE, 0)
        self.assertIsNotNone(accel)
        self.assertIsNone(accel.hid)
        self.assertFalse(accel.displayable)

    def test_the_character_wins_over_the_virtual_key(self):
        # Both present is what an app that sets each does; the character is what
        # the menu is telling the user to press.
        self.assertEqual(parse_mac_accel("S", 0x0C, 0).keysym, "S")

    def test_the_glyph_argument_is_accepted_and_ignored(self):
        # It is in the signature so the backend can pass it without the call
        # site changing when the table is eventually measured on a Mac.
        with_glyph = parse_mac_accel("S", None, 0, glyph=23)
        without = parse_mac_accel("S", None, 0)
        self.assertEqual(with_glyph, without)

    def test_a_missing_modifier_mask_still_means_Command(self):
        # An item with a key equivalent always reports a mask; None is the
        # defensive path and must not decay to "no modifiers".
        self.assertEqual(parse_mac_accel("S", None, None).mods, MOD_GUI)


class FakeElement:
    """One AX element: a bag of attributes, as `AXUIElementCopyAttributeValue` sees it."""

    def __init__(self, **attrs):
        self.attrs = attrs


def fake_copy_attr(element, name, _placeholder):
    """pyobjc's `(error, value)` shape, including its commonest answer.

    ⚠️ An UNSUPPORTED attribute is the normal case here -- most menu items have
    no key equivalent -- so this returns the error code rather than raising, and
    the backend has to treat that as data.
    """
    if not isinstance(element, FakeElement) or name not in element.attrs:
        return (-25205, None)                      # kAXErrorAttributeUnsupported
    return (0, element.attrs[name])


def menu_item(title, char="", vkey=None, mods=None, children=None):
    attrs = {"AXTitle": title}
    if char:
        attrs["AXMenuItemCmdChar"] = char
    if vkey is not None:
        attrs["AXMenuItemCmdVirtualKey"] = vkey
    if mods is not None:
        attrs["AXMenuItemCmdModifiers"] = mods
    if children:
        attrs["AXChildren"] = children
    return FakeElement(**attrs)


def menu_bar(*bar_items):
    return FakeElement(AXChildren=list(bar_items))


def bar_item(title, *items):
    return FakeElement(AXTitle=title,
                       AXChildren=[FakeElement(AXChildren=list(items))])


APPLE_MENU = bar_item("Apple", menu_item("Force Quit…", chr(0x1B), mods=0x02))


class MenuWalkTest(unittest.TestCase):
    """The tree walk, against a fake AX tree."""

    def walk(self, bar, budget=macos.DEFAULT_NODE_BUDGET):
        # ⚠️ The application element is NOT the menu bar -- the backend asks it
        # for `AXMenuBar` first. Handing the bar back directly made all four
        # positive cases return [], which is what an app with no menu looks
        # like, so a fixture shortcut here reads as the walk being broken.
        app = FakeElement(AXMenuBar=bar)
        # ⚠️ The requested name must AGREE with what the fake workspace reports
        # as frontmost, or the focus-race guard refuses before the walk starts.
        # These four cases are about the walk; the guard has its own class. That
        # they went red when the guard landed is the guard being live.
        with patch.object(macos, "_trusted", return_value=True), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: app, fake_copy_attr, lambda: True,
                 FakeWorkspace("Mousepad"))):
            return macos.shortcuts_for_app("Mousepad", budget=budget)

    def test_it_reads_a_plain_menu_item(self):
        found = self.walk(menu_bar(APPLE_MENU,
                                   bar_item("File", menu_item("Save", "S", mods=0))))
        self.assertEqual([(s.label, s.mods, s.hid) for s in found],
                         [("Save", MOD_GUI, 0x16)])

    def test_the_APPLE_MENU_is_skipped(self):
        # ⚠️ Its items are the SYSTEM's, on every app on the machine -- the same
        # defect WINDOW_MANAGER_CHORDS exists to prevent on Windows.
        found = self.walk(menu_bar(APPLE_MENU,
                                   bar_item("File", menu_item("Save", "S", mods=0))))
        self.assertNotIn("Force Quit…", [s.label for s in found])

    def test_the_skip_is_POSITIONAL_and_not_a_title_test(self):
        # The Apple menu's title is not "Apple" on a real Mac (it is an empty
        # string or the Apple glyph), and it is localized. Position is the only
        # stable handle, so a renamed first menu must still be skipped.
        found = self.walk(menu_bar(bar_item("", menu_item("Sleep", "S", mods=0)),
                                   bar_item("File", menu_item("Open", "O", mods=0))))
        self.assertEqual([s.label for s in found], ["Open"])

    def test_a_SUBMENU_is_walked_and_its_path_recorded(self):
        deep = menu_item("Export…", children=[FakeElement(AXChildren=[
            menu_item("As PDF", "P", mods=0x01)])])
        found = self.walk(menu_bar(APPLE_MENU, bar_item("File", deep)))
        self.assertEqual([s.label for s in found], ["As PDF"])
        self.assertEqual(found[0].path, ["File", "Export…"])

    def test_an_item_with_no_key_equivalent_is_not_a_shortcut(self):
        found = self.walk(menu_bar(APPLE_MENU,
                                   bar_item("File", menu_item("Recent Items"))))
        self.assertEqual(found, [])

    def test_an_item_with_no_TITLE_is_refused(self):
        # A separator, or an item whose title has not been set yet. There is
        # nothing to match an icon against, so it would occupy a keycap and
        # draw nothing.
        found = self.walk(menu_bar(APPLE_MENU,
                                   bar_item("File", menu_item("", "S", mods=0))))
        self.assertEqual(found, [])

    def test_the_FIRST_binding_wins_a_duplicated_chord(self):
        found = self.walk(menu_bar(APPLE_MENU, bar_item(
            "File", menu_item("Save", "S", mods=0), menu_item("Send", "S", mods=0))))
        self.assertEqual([s.label for s in found], ["Save"])

    def test_the_budget_bounds_the_walk(self):
        items = [menu_item("Item %d" % i, chr(ord("a") + i % 26), mods=0)
                 for i in range(50)]
        found = self.walk(menu_bar(APPLE_MENU, bar_item("File", *items)), budget=5)
        self.assertLessEqual(len(found), 5)

    def test_an_untrusted_process_harvests_NOTHING(self):
        app = FakeElement(AXMenuBar=menu_bar(
            APPLE_MENU, bar_item("File", menu_item("Save", "S", mods=0))))
        with patch.object(macos, "_trusted", return_value=False), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: app, fake_copy_attr, lambda: False, FakeWorkspace())):
            self.assertEqual(macos.shortcuts_for_app("anything"), [])

    def test_every_failure_costs_an_empty_list_and_never_raises(self):
        with patch.object(macos, "_api", side_effect=RuntimeError("no pyobjc")):
            self.assertEqual(macos.shortcuts_for_app("anything"), [])

    def test_no_frontmost_application_is_an_empty_list(self):
        class NoApp:
            @staticmethod
            def sharedWorkspace():
                return NoApp()

            @staticmethod
            def frontmostApplication():
                return None

        with patch.object(macos, "_trusted", return_value=True), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: None, fake_copy_attr, lambda: True, NoApp())):
            self.assertEqual(macos.shortcuts_for_app("anything"), [])


class FakeWorkspace:
    def __init__(self, name="Mousepad"):
        self.name = name

    def sharedWorkspace(self):
        return self

    def frontmostApplication(self):
        return self

    def processIdentifier(self):
        return 4242

    def localizedName(self):
        return self.name


class FocusRaceTest(unittest.TestCase):
    """The harvest runs on a worker thread; focus can move under it.

    ⚠️ The fetcher caches the result under the name it ASKED about, so a moved
    focus files app B's shortcuts under app A's key and draws them every time A
    is focused until the cache clears.
    """

    def harvest(self, requested, frontmost):
        app = FakeElement(AXMenuBar=menu_bar(
            APPLE_MENU, bar_item("File", menu_item("Save", "S", mods=0))))
        with patch.object(macos, "_trusted", return_value=True), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: app, fake_copy_attr, lambda: True,
                 FakeWorkspace(frontmost))):
            return macos.shortcuts_for_app(requested)

    def test_a_MOVED_focus_harvests_nothing(self):
        self.assertEqual(self.harvest("Mail", "Xcode"), [])

    def test_the_matching_app_still_harvests(self):
        self.assertEqual([s.label for s in self.harvest("Mousepad", "Mousepad")],
                         ["Save"])

    def test_a_DIFFERENT_SPELLING_of_the_same_app_is_accepted(self):
        # ⚠️ Fails OPEN. The handler's name and AppKit's localizedName are not
        # guaranteed to match for one app, and refusing on an unfamiliar
        # convention turns a rare mislabel into a total failure.
        for requested, frontmost in (("Code", "Visual Studio Code"),
                                     ("Safari.app", "Safari"),
                                     ("mousepad", "Mousepad")):
            with self.subTest(requested=requested):
                self.assertEqual(len(self.harvest(requested, frontmost)), 1)

    def test_an_UNREADABLE_name_is_accepted_rather_than_refused(self):
        self.assertEqual(len(self.harvest("Mail", "")), 1)
        self.assertEqual(len(self.harvest("", "Xcode")), 1)

    def test_names_agree_is_symmetric(self):
        self.assertTrue(macos.names_agree("Code", "Visual Studio Code"))
        self.assertTrue(macos.names_agree("Visual Studio Code", "Code"))
        self.assertFalse(macos.names_agree("Mail", "Xcode"))


class EmptyHarvestReasonTest(unittest.TestCase):
    """⚠️ SIX ways of returning [], and the caller could tell none of them apart.

    Its one sentence — *"the app exposes no accelerators"* — is true of exactly
    one, and reads as settled fact for the other five. The field log that
    prompted this had four macOS apps reporting it on a machine where Chrome
    harvested 65 in the same session, so the pyobjc import and the Accessibility
    grant were both provably fine and the line narrowed nothing (2026-09-21).

    `retry` is the half a human does not read: true means THIS harvest never
    looked, so the empty answer says nothing about the app and must not be
    cached as if it did.
    """

    def why(self, requested="Mousepad", frontmost="Mousepad", app=..., **kw):
        if app is ...:
            app = FakeElement(AXMenuBar=menu_bar(
                APPLE_MENU, bar_item("File", menu_item("Save", "S", mods=0))))
        reason = {}
        with patch.object(macos, "_trusted", return_value=kw.pop("trusted", True)), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: app, fake_copy_attr, lambda: True,
                 FakeWorkspace(frontmost))):
            got = macos.shortcuts_for_app(requested, reason=reason, **kw)
        return got, reason

    def test_a_MISSING_PERMISSION_names_the_setting(self):
        got, reason = self.why(trusted=False)
        self.assertEqual(got, [])
        self.assertIn("Accessibility", reason["why"])
        # Not retryable: the grant needs a restart, so asking again this session
        # can only produce the same answer.
        self.assertFalse(reason["retry"])

    def test_a_MOVED_FOCUS_names_both_apps_and_asks_to_RETRY(self):
        got, reason = self.why(requested="Mail", frontmost="Xcode")
        self.assertEqual(got, [])
        self.assertIn("Mail", reason["why"])
        self.assertIn("Xcode", reason["why"])
        self.assertTrue(reason["retry"])

    def test_NO_FRONTMOST_APP_asks_to_RETRY(self):
        class NoApp:
            @staticmethod
            def sharedWorkspace():
                return NoApp()

            @staticmethod
            def frontmostApplication():
                return None

        reason = {}
        with patch.object(macos, "_trusted", return_value=True), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: None, fake_copy_attr, lambda: True, NoApp())):
            self.assertEqual(macos.shortcuts_for_app("x", reason=reason), [])
        self.assertIn("frontmost", reason["why"])
        self.assertTrue(reason["retry"])

    def test_NO_MENU_BAR_says_so_and_is_NOT_retryable(self):
        got, reason = self.why(app=FakeElement())
        self.assertEqual(got, [])
        self.assertIn("AXMenuBar", reason["why"])
        self.assertFalse(reason["retry"])

    def test_an_AX_FAILURE_names_the_exception_and_asks_to_RETRY(self):
        reason = {}
        with patch.object(macos, "_api", side_effect=RuntimeError("no pyobjc")):
            self.assertEqual(macos.shortcuts_for_app("x", reason=reason), [])
        self.assertIn("RuntimeError", reason["why"])
        self.assertIn("no pyobjc", reason["why"])
        self.assertTrue(reason["retry"])

    def test_a_REAL_EMPTY_MENU_reports_the_COUNTS_and_is_NOT_retryable(self):
        """The one empty answer that is CORRECT — and the counts are what
        separate its two causes. A bar the walk never entered is not the same as
        a full menu with no key equivalents in it, and a toolkit that populates
        a submenu only when it is first SHOWN looks like the second while being
        the first (module docstring)."""
        got, reason = self.why(app=FakeElement(AXMenuBar=menu_bar(
            APPLE_MENU,
            bar_item("File", menu_item("Save")),          # no key equivalent
            bar_item("Edit", menu_item("Undo")))))
        self.assertEqual(got, [])
        self.assertIn("2 menu(s) past the Apple menu", reason["why"])
        self.assertIn("node(s) walked", reason["why"])
        self.assertFalse(reason["retry"])

    def test_an_EMPTY_BAR_is_distinguishable_from_a_full_one(self):
        """Both are "no key equivalents"; only the counts say which."""
        _, reason = self.why(app=FakeElement(AXMenuBar=menu_bar(APPLE_MENU)))
        self.assertIn("0 menu(s) past the Apple menu", reason["why"])

    def test_a_SUCCESSFUL_harvest_leaves_the_reason_ALONE(self):
        got, reason = self.why()
        self.assertEqual([s.label for s in got], ["Save"])
        self.assertEqual(reason, {})

    def test_the_reason_is_OPTIONAL(self):
        """Every existing caller passes nothing; filling it must not be what
        makes the harvest work."""
        with patch.object(macos, "_trusted", return_value=True), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: FakeElement(), fake_copy_attr, lambda: True,
                 FakeWorkspace("Mousepad"))):
            self.assertEqual(macos.shortcuts_for_app("Mousepad"), [])


class ProbeLabellingTest(unittest.TestCase):
    """`shortcut_probe --backend macos` must not label a harvest with a SECOND
    frontmost lookup.

    ⚠️ Two independent lookups are two observations of a value the user changes
    at will, so a focus switch between them reported app A's shortcuts under
    app B's name -- and `--watch --unmatched` then filed A's unmatched labels
    under B for the life of the log. The fix is not a third lookup: it is to
    read the name FIRST and hand it to `shortcuts_for_app`, whose `name`
    argument exists precisely to verify focus has not moved. The probe was
    opting out of that guard by passing "" (Greptile, #248).
    """

    def run_probe(self, frontmost_name, name_at_harvest=None, raises=False):
        """Drive main_macos with a fake backend; returns (report, name_passed)."""
        from tools import shortcut_probe

        from polyhost.services.shortcut_source.model import Shortcut

        seen = {}

        def fake_shortcuts_for_app(name="", budget=0):
            """The backend's CONTRACT, not a re-entry into the real one.

            Calling `macos.shortcuts_for_app` here would recurse, because the
            probe imports that module AS `_macos` -- patching one patches both.
            What is under test is the probe's wiring, and the contract it leans
            on is the one `FocusRaceTest` above pins directly: the harvest
            refuses when the name it was given no longer matches the frontmost.
            """
            seen["name"] = name
            moved = (name_at_harvest if name_at_harvest is not None
                     else frontmost_name)
            if not macos.names_agree(name, moved):
                return []
            return [Shortcut(label="Save", role="menu item", accel="Cmd+S",
                             mods=MOD_GUI, keysym="s", hid=0x16,
                             displayable=True)]

        def fake_frontmost_name(_workspace):
            if raises:
                raise RuntimeError("AppKit is unreadable")
            return frontmost_name

        args = type("A", (), {"max_nodes": 500, "delay": 0,
                              "icons": False, "quiet": True})()
        with patch.object(shortcut_probe._macos, "unavailable_reason",
                          return_value=None), \
             patch.object(shortcut_probe._macos, "_api",
                          return_value=(None, None, None, object())), \
             patch.object(shortcut_probe._macos, "_frontmost_name",
                          side_effect=fake_frontmost_name), \
             patch.object(shortcut_probe._macos, "shortcuts_for_app",
                          side_effect=fake_shortcuts_for_app):
            out = shortcut_probe.main_macos(args)
        return out[0], seen.get("name")

    def test_the_harvest_is_told_WHICH_app_the_label_will_name(self):
        """The whole fix: one observation, used for both."""
        rep, passed = self.run_probe("Mousepad")
        self.assertEqual(passed, "Mousepad")
        self.assertEqual(rep["app"], "Mousepad")

    def test_a_focus_switch_yields_NO_shortcuts_rather_than_wrong_ones(self):
        """Mail was focused; the user switched to Xcode mid-harvest.

        The honest outcome is "Mail: nothing" -- NOT Xcode's shortcuts filed
        under Mail, which is what a second lookup produced.
        """
        rep, passed = self.run_probe("Mail", name_at_harvest="Xcode")
        self.assertEqual(passed, "Mail")
        self.assertEqual(rep["app"], "Mail")
        self.assertEqual(rep["total"], 0)

    def test_an_UNREADABLE_name_degrades_to_generic_not_to_a_lie(self):
        """`names_agree` fails open on an empty name, so the race stays open
        here -- but the label is then generic rather than somebody else's."""
        rep, passed = self.run_probe("", raises=True)
        self.assertEqual(passed, "")
        self.assertEqual(rep["app"], "frontmost application")


class AttributeReadTest(unittest.TestCase):

    def test_an_unsupported_attribute_yields_the_default(self):
        self.assertEqual(
            macos._attr(fake_copy_attr, FakeElement(), "AXTitle", "fallback"),
            "fallback")

    def test_a_raising_accessor_yields_the_default(self):
        def boom(*_a):
            raise RuntimeError("the app quit mid-walk")

        self.assertIsNone(macos._attr(boom, FakeElement(), "AXTitle"))

    def test_a_present_attribute_comes_back(self):
        self.assertEqual(
            macos._attr(fake_copy_attr, FakeElement(AXTitle="File"), "AXTitle"),
            "File")


class UnavailableReasonTest(unittest.TestCase):
    """The two causes need OPPOSITE fixes, so they must not share a sentence."""

    def setUp(self):
        macos._TRUST_CACHE = None

    def tearDown(self):
        macos._TRUST_CACHE = None

    def test_missing_pyobjc_says_so_and_names_the_packages(self):
        with patch.object(macos, "_api", side_effect=ImportError("No module named 'AppKit'")):
            reason = macos.unavailable_reason()
        self.assertIn("pyobjc", reason)
        self.assertIn("pip install", reason)

    def test_a_denied_PERMISSION_is_a_different_sentence(self):
        with patch.object(macos, "_api", return_value=(None, None, lambda: False, None)):
            reason = macos.unavailable_reason()
        self.assertIn("Accessibility", reason)
        self.assertNotIn("pip install", reason)

    def test_the_permission_sentence_says_where_to_go_and_to_restart(self):
        with patch.object(macos, "_api", return_value=(None, None, lambda: False, None)):
            reason = macos.unavailable_reason()
        self.assertIn("System Settings", reason)
        self.assertIn("restart", reason)

    def test_a_working_setup_has_no_reason(self):
        with patch.object(macos, "_api", return_value=(None, None, lambda: True, None)):
            self.assertIsNone(macos.unavailable_reason())
            self.assertTrue(macos.available())

    def test_the_trust_answer_is_asked_ONCE(self):
        calls = []

        def counting():
            calls.append(1)
            return True

        with patch.object(macos, "_api", return_value=(None, None, counting, None)):
            macos._trusted()
            macos._trusted()
        self.assertEqual(len(calls), 1)


class BackendWiringTest(unittest.TestCase):

    def test_darwin_names_the_macos_backend(self):
        with patch.object(ss.sys, "platform", "darwin"):
            self.assertEqual(ss.backend_name(), "macos")

    def test_every_name_backend_name_can_return_is_importable(self):
        # ⚠️ The mapping used to be an if/else with `atspi` as the fallback, so
        # a new name silently resolved to the WRONG backend rather than failing.
        for platform, expected in (("darwin", "macos"), ("win32", "uia"),
                                   ("linux", "atspi")):
            with patch.object(ss.sys, "platform", platform):
                name = ss.backend_name()
            self.assertEqual(name, expected)
            self.assertEqual(ss._backend_module(name).__name__.rsplit(".", 1)[-1],
                             expected)

    def test_macos_is_no_longer_the_platform_with_no_backend(self):
        with patch.object(ss.sys, "platform", "darwin"):
            reason = ss.unavailable_reason()
        # It may well be unavailable here (no pyobjc on Linux), but the reason
        # must now be about THIS BACKEND rather than "macOS is not built".
        self.assertIsNotNone(reason)
        self.assertNotIn("not built", reason)


if __name__ == "__main__":
    unittest.main()
