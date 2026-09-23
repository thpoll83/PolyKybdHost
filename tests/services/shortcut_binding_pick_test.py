"""Which string on an accessibility node is a SHORTCUT, per backend.

⚠️ These two functions are where a real machine's menu tree becomes a keycap,
and both were **0% covered** -- the only thing that had ever run them was a
probe on a live desktop, which is to say nothing that runs in CI. They are pure
string logic, so the excuse for leaving them to the probes does not hold.

⚠️ The distinction they draw is not cosmetic. An ACCELERATOR is a chord the user
can press anywhere; a MNEMONIC only works while a menu is already posted, and a
menu PATH ("Alt+F then M") is not one press at all. Reporting either as a
shortcut turns a true zero into a plausible-looking number -- measured on gedit,
13 popover mnemonics reported as shortcuts while its real Ctrl+S and Ctrl+O were
absent from the tree entirely. That is the worst available outcome, because
nothing downstream can tell a wrong answer from a right one.
"""

import unittest

from polyhost.services.shortcut_source.model import (
    MOD_ALT, MOD_CTRL, MOD_GUI, MOD_SHIFT, UIA_MENU_TYPES, Accel,
    parse_accel, pick_binding, pick_win_binding)


class AtspiPickTest(unittest.TestCase):
    """AT-SPI packs three fields into one ';'-separated action string."""

    def test_part_THREE_is_the_shortcut_and_wins(self):
        # 'mnemonic;menu-path;shortcut'
        self.assertEqual(pick_binding("m;<Alt>f:m;<Control>s"),
                         ("<Control>s", "accelerator"))

    def test_a_MENU_PATH_is_not_a_shortcut(self):
        """⚠️ 35 of mousepad's 67 items look like this. Falling back to part 2
        would advertise a traversal no keycap can show; the ':' is what rules a
        candidate out."""
        self.assertEqual(pick_binding("m;<Alt>f:m;"), (None, ""))

    def test_a_menu_ROLE_still_refuses_a_TRAVERSAL(self):
        """⚠️ The `":" not in part` guard, on the only path that reaches it.

        Found by mutation: my first version of this file tested the traversal
        case with NO role, so the menu branch never ran and deleting the guard
        escaped. The rule only applies where the role fallback applies, so that
        is where it has to be tested -- "Alt+F then M" is two presses however
        menu-ish the node is."""
        self.assertEqual(pick_binding("m;<Alt>f:m;", role="menu"), (None, ""))

    def test_a_top_level_MENUBAR_item_IS_one_press(self):
        """The one fallback worth taking: a single chord, no ':', on a menu."""
        self.assertEqual(pick_binding("<Alt>f;<Alt>f;", role="menu"),
                         ("<Alt>f", "menu"))

    def test_ROLE_IS_LOAD_BEARING_the_same_string_on_a_BUTTON_is_refused(self):
        """⚠️ The gedit case. A GtkPopover button carries a byte-identical
        string, and it is a mnemonic that works only while the popover is open.
        Same input, opposite answer -- which is why the role cannot be dropped
        'because the string already says what it is'."""
        self.assertEqual(pick_binding("<Alt>s;<Alt>s;", role="push button"),
                         (None, ""))

    def test_an_EMPTY_action_string_yields_nothing(self):
        self.assertEqual(pick_binding(""), (None, ""))
        self.assertEqual(pick_binding(None), (None, ""))

    def test_a_SHORTCUT_beats_a_menu_role_fallback(self):
        """Part 3 is checked before the role fallback, so a menu item that has
        a real accelerator reports the accelerator."""
        self.assertEqual(pick_binding("<Alt>f;<Alt>f;<Control>n", role="menu"),
                         ("<Control>n", "accelerator"))


class UiaPickTest(unittest.TestCase):
    """UI Automation gives the two as separate properties."""

    def test_AcceleratorKey_always_wins(self):
        self.assertEqual(pick_win_binding("Ctrl+S", "S", sorted(UIA_MENU_TYPES)[0]),
                         ("Ctrl+S", "accelerator"))

    def test_AccessKey_counts_only_on_a_MENU_control(self):
        menu = sorted(UIA_MENU_TYPES)[0]
        self.assertEqual(pick_win_binding("", "F", menu), ("F", "menu"))

    def test_AccessKey_on_a_NON_menu_control_is_refused(self):
        """⚠️ The same distinction AT-SPI draws by role, and the reason the two
        functions have to agree: a mnemonic on a button is not a shortcut on
        either platform."""
        not_a_menu = max(UIA_MENU_TYPES) + 1
        self.assertEqual(pick_win_binding("", "F", not_a_menu), (None, ""))

    def test_WHITESPACE_is_not_a_binding(self):
        """A blank-but-present property is what an element with no shortcut
        actually reports, and `if accelerator` alone would take it."""
        self.assertEqual(pick_win_binding("   ", "  ", sorted(UIA_MENU_TYPES)[0]),
                         (None, ""))

    def test_the_two_backends_AGREE_on_the_same_situation(self):
        """The property that matters across the pair: a real accelerator reads
        as one on both, and a mnemonic on a non-menu control reads as nothing on
        both. A divergence here is a keyboard that behaves differently depending
        on which machine the app runs on."""
        menu = sorted(UIA_MENU_TYPES)[0]
        self.assertEqual(pick_binding("m;<Alt>f:m;<Control>s")[1],
                         pick_win_binding("Ctrl+S", "S", menu)[1])
        self.assertEqual(pick_binding("<Alt>s;<Alt>s;", role="push button")[1],
                         pick_win_binding("", "S", max(UIA_MENU_TYPES) + 1)[1])


class AccelDisplayTest(unittest.TestCase):

    def test_pretty_names_the_modifiers_in_a_FIXED_order(self):
        """The order is the table's, not the bitmask's -- so the same chord
        always reads the same way in a log."""
        accel = Accel(mods=MOD_CTRL | MOD_SHIFT | MOD_ALT, keysym="s", hid=22)
        self.assertEqual(accel.pretty(), "Ctrl+Shift+Alt+s")

    def test_pretty_of_a_BARE_key_has_no_separator(self):
        self.assertEqual(Accel(mods=0, keysym="F5", hid=62).pretty(), "F5")


class AriaAccelTest(unittest.TestCase):
    """GTK 4.22 answers GetKeyBinding with 'S;;Control+S' -- the WAI-ARIA
    spelling from gtk_accelerator_get_accessible_label() -- where 4.18-4.20
    sent 'S;;<Control>s'. Both must land on the same key, or the icon lookup
    and the dedupe see two different shortcuts."""

    def _key(self, text):
        a = parse_accel(text)
        return None if a is None else (a.mods, a.keysym, a.hid)

    def test_part_three_is_picked_in_the_aria_form(self):
        self.assertEqual(pick_binding("S;;Control+S", role="menu item"),
                         ("Control+S", "accelerator"))

    def test_the_two_gtk_spellings_are_the_same_key(self):
        pairs = [
            ("Control+S", "<Control>s"),
            ("Control+Shift+Z", "<Control><Shift>z"),
            ("Alt+ArrowLeft", "<Alt>Left"),
            ("Control+PageDown", "<Control>Page_Down"),
            ("Control+Enter", "<Control>Return"),
            ("Control+Space", "<Control>space"),
            ("Control+/", "<Control>slash"),
            ("Control+,", "<Control>comma"),
            ("Super+L", "<Super>l"),
            ("F11", "F11"),
            ("Shift+F10", "<Shift>F10"),
            ("Delete", "Delete"),
            ("Escape", "Escape"),
            ("Control+1", "<Control>1"),
        ]
        for aria, gtk in pairs:
            with self.subTest(aria=aria):
                self.assertIsNotNone(self._key(gtk))
                self.assertEqual(self._key(aria), self._key(gtk))

    def test_the_plus_KEY_is_the_trailing_plus(self):
        """Zoom-in is genuinely Ctrl and '+', so a split on '+' alone would
        leave an empty key."""
        self.assertEqual(self._key("Control++"), (MOD_CTRL, "plus", 0x2E))

    def test_modifiers_fold_onto_one_nibble(self):
        self.assertEqual(parse_accel("Control+Alt+Shift+Meta+X").mods,
                         MOD_CTRL | MOD_ALT | MOD_SHIFT | MOD_GUI)

    def test_only_the_first_of_several_shortcuts_is_read(self):
        # aria-keyshortcuts allows a space-separated list.
        self.assertEqual(self._key("Control+S Control+Shift+S"),
                         self._key("Control+S"))

    def test_no_key_or_unknown_modifier_is_refused(self):
        self.assertIsNone(parse_accel("Control+Shift"))
        self.assertIsNone(parse_accel("Control+"))
        self.assertIsNone(parse_accel("Wibble+S"))

    def test_an_undrawable_key_parses_without_a_hid(self):
        """GTK writes 'Unidentified' for a key it cannot name; that is a
        shortcut the keycaps cannot show, not a parse error."""
        accel = parse_accel("Control+Unidentified")
        self.assertIsNotNone(accel)
        self.assertFalse(accel.displayable)


if __name__ == "__main__":
    unittest.main()
