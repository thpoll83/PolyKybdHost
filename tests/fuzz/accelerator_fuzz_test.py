"""Properties of the accelerator parsers in services/shortcut_source/model.py.

Their input is text another application wrote into its accessibility tree (AT-SPI,
UI Automation, the macOS AX API), so it can be anything. A parser answers None or
an Accel; a chord spelled the way a toolkit spells it reads back as that chord.
"""
import unittest

from hypothesis import assume, given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services.shortcut_source import model as m

load_profile()

ACCEL_ALPHABET = st.sampled_from(list("<>+-;:, ") + list("aAsSzZ09fF") + ["Ctrl", "Shift",
                                 "Control", "Alt", "Strg", "Alt Gr", "Page Up", "plus",
                                 "Return", "Enter", "é", "", "\t"])
ACCEL_TEXT = st.one_of(st.text(max_size=30),
                       st.lists(ACCEL_ALPHABET, max_size=10).map("".join))
NIBBLE = st.integers(0, 0x0F)

# One spelling per modifier bit, as each toolkit writes it.
GTK_MODS = {m.MOD_CTRL: ["Control", "Primary", "ctrl"], m.MOD_SHIFT: ["Shift"],
            m.MOD_ALT: ["Alt", "Mod1"], m.MOD_GUI: ["Super", "Meta", "Mod4"]}
WIN_MODS = {m.MOD_CTRL: ["Ctrl", "Strg", "Control"], m.MOD_SHIFT: ["Shift", "Umschalt", "Maj"],
            m.MOD_ALT: ["Alt"], m.MOD_GUI: ["Win", "Windows"]}
ARIA_MODS = {m.MOD_CTRL: ["Control"], m.MOD_SHIFT: ["Shift"], m.MOD_ALT: ["Alt"],
             m.MOD_GUI: ["Meta"]}


def _mod_names(table, mods, draw):
    return [draw(st.sampled_from(table[bit])) for bit in (1, 2, 4, 8) if mods & bit]


class AcceleratorFuzzTest(unittest.TestCase):
    def _check_accel(self, accel, hids):
        if accel is None:
            return
        self.assertIsInstance(accel, m.Accel)
        self.assertTrue(0 <= accel.mods <= 0x0F)
        self.assertTrue(accel.keysym)
        self.assertTrue(accel.hid is None or accel.hid in hids)

    @given(ACCEL_TEXT)
    def test_parsers_on_arbitrary_text(self, text):
        self._check_accel(m.parse_win_accel(text), set(m.WINKEY_TO_HID.values()))
        self._check_accel(m.parse_aria_accel(text), set(m.KEYSYM_TO_HID.values()))
        # parse_accel falls back to the Windows parser for Qt's display strings.
        self._check_accel(m.parse_accel(text),
                          set(m.KEYSYM_TO_HID.values()) | set(m.WINKEY_TO_HID.values()))

    @given(NIBBLE, st.sampled_from(sorted(m.KEYSYM_TO_HID)), st.data())
    def test_gtk_round_trip(self, mods, keysym, data):
        names = _mod_names(GTK_MODS, mods, data.draw)
        assume(names)       # a bare key name is read as ARIA or Windows text too
        text = "".join(f"<{n}>" for n in names) + keysym
        accel = m.parse_accel(text)
        self.assertEqual((accel.mods, accel.keysym, accel.hid),
                         (mods, keysym, m.KEYSYM_TO_HID[keysym]))

    @given(NIBBLE, st.sampled_from(sorted(m.WINKEY_TO_HID)), st.data())
    def test_windows_round_trip(self, mods, key, data):
        names = _mod_names(WIN_MODS, mods, data.draw)
        sep = data.draw(st.sampled_from(["+", "-"]))
        text = "".join(n + sep for n in names) + data.draw(st.sampled_from([key, key.upper()]))
        assume("," not in key)          # a comma starts a second chord or a KeyTip
        accel = m.parse_win_accel(text)
        self.assertIsNotNone(accel, text)
        self.assertEqual((accel.mods, accel.hid), (mods, m.WINKEY_TO_HID[key]), text)

    @given(NIBBLE, st.sampled_from(sorted(m.ARIA_KEY_TO_KEYSYM) + list("aZ7+-/.[")
                                   + sorted(m.ARIA_CHAR_TO_KEYSYM)), st.data())
    def test_aria_round_trip(self, mods, key, data):
        names = _mod_names(ARIA_MODS, mods, data.draw)
        text = "+".join(names + [key])
        if data.draw(st.booleans()):
            text += " " + data.draw(st.sampled_from(["Control+Q", "F1", "x"]))
        accel = m.parse_aria_accel(text)
        keysym = m.aria_key_to_keysym(key)
        self.assertEqual((accel.mods, accel.keysym, accel.hid),
                         (mods, keysym, m.KEYSYM_TO_HID.get(keysym)), text)

    @given(ACCEL_TEXT, st.sampled_from(["", "menu", "menu item", "check menu item",
                                        "push button"]),
           st.text(max_size=8), st.sampled_from(["", "menu bar", "menu"]))
    def test_pick_binding(self, raw, role, name, parent_role):
        accel, kind = m.pick_binding(raw, role, name, parent_role)
        if accel is None:
            self.assertEqual(kind, "")
            return
        self.assertIn(kind, ("accelerator", "menu"))
        self.assertTrue(accel)
        self.assertIn(accel, raw)
        if ";" in raw or "<" in raw:
            parts = [x.strip() for x in raw.split(";")]
            if len(parts) >= 3 and parts[2]:
                self.assertEqual((accel, kind), (parts[2], "accelerator"))
            else:
                self.assertEqual(role, "menu")
                self.assertEqual(kind, "menu")
                self.assertNotIn(":", accel)
        else:
            self.assertIn("menu item", role)
            self.assertNotIn(", ", accel)

    @given(st.text(max_size=12), st.text(max_size=4), st.integers(49990, 50040))
    def test_pick_win_binding(self, accelerator, access_key, control_type):
        got = m.pick_win_binding(accelerator, access_key, control_type)
        if accelerator.strip():
            want = (accelerator.strip(), "accelerator")
        elif access_key.strip() and control_type in m.UIA_MENU_TYPES:
            want = (access_key.strip(), "menu")
        else:
            want = (None, "")
        self.assertEqual(got, want)

    @given(st.text(max_size=3), st.none() | st.integers(0, 0x7F), st.none() | st.integers(0, 0xFF))
    def test_mac_accel(self, char, virtual_key, modifiers):
        accel = m.parse_mac_accel(char, virtual_key, modifiers)
        if accel is None:
            # No name: no character it reads (empty, a control or private-use
            # character it has no entry for) and no virtual key to fall back on.
            self.assertIsNone(virtual_key)
            return
        self.assertEqual(accel.mods, m.mac_mods_to_qmk(modifiers or 0))
        self.assertTrue(accel.hid is None or m.displayable_hid(accel.hid))

    @given(st.integers(0, 0xFF))
    def test_mac_mods_command_bit_is_inverted(self, mask):
        mods = m.mac_mods_to_qmk(mask)
        self.assertEqual(bool(mods & m.MOD_GUI), not mask & m.MAC_MOD_NO_COMMAND)
        self.assertEqual(bool(mods & m.MOD_SHIFT), bool(mask & m.MAC_MOD_SHIFT))
        self.assertEqual(bool(mods & m.MOD_ALT), bool(mask & m.MAC_MOD_OPTION))
        self.assertEqual(bool(mods & m.MOD_CTRL), bool(mask & m.MAC_MOD_CONTROL))


if __name__ == "__main__":
    unittest.main()
