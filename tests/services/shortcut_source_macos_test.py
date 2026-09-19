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
        with patch.object(macos, "_trusted", return_value=True), \
             patch.object(macos, "_api", return_value=(
                 lambda pid: app, fake_copy_attr, lambda: True, FakeWorkspace())):
            return macos.shortcuts_for_app("anything", budget=budget)

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
    def sharedWorkspace(self):
        return self

    def frontmostApplication(self):
        return self

    def processIdentifier(self):
        return 4242


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
