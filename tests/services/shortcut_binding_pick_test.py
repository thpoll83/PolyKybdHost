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
    MOD_ALT, MOD_CTRL, MOD_SHIFT, UIA_MENU_TYPES, Accel,
    pick_binding, pick_win_binding)


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


if __name__ == "__main__":
    unittest.main()
