"""Properties of the key-binding file readers in services/game_assets: the Source
engine bind lines (TF2, Apex), StarCraft II .SC2Hotkeys, Path of Exile
production_Config.ini, OpenRA settings.yaml and UT2004 User.ini.

The files are the player's own and the game rewrites them; any text must parse
without an exception, and a file written in the format must give the bindings it
holds."""
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services.game_assets import (apex_keys, key_files, openra_keys, poe2_keys,
                                           poe_keys, sc2_keys, tf2_keys)
from polyhost.services.game_assets.unreal2 import bindings as ut_bindings

load_profile()

# Line text without line breaks (str.splitlines also splits on \x1c-\x1e, \x85 ...).
LINE_CHARS = st.sampled_from(list("abcXYZ019 +-_;=,.[]#/\\'\"\t:") + ["é"])
LINE = st.text(LINE_CHARS, max_size=20)
ANY_TEXT = st.one_of(st.text(max_size=80), st.lists(LINE, max_size=8).map("\n".join))


def _lists_of_tokens(test, out):
    test.assertIsInstance(out, dict)
    for name, tokens in out.items():
        test.assertIsInstance(name, str)
        test.assertIsInstance(tokens, list)
        test.assertTrue(all(isinstance(t, str) and t for t in tokens))
        test.assertEqual(len(tokens), len(set(tokens)), tokens)


SOURCE_KEY = st.one_of(st.sampled_from(sorted(key_files.SOURCE_KEYS)),
                       st.sampled_from(["mouse1", "KP_END", "shift", "MWHEELUP", "a", "f12"]))
COMMAND = st.text(st.sampled_from(list("+-_abxyz019 .;")), max_size=16)


@st.composite
def source_files(draw):
    """(config text, directive check, the binds it must give)."""
    lines, want = [], {}
    for _ in range(draw(st.integers(0, 8))):
        if draw(st.integers(0, 3)) == 0:
            lines.append(draw(LINE))             # anything else in the file
            continue
        directive = draw(st.sampled_from(["bind", "BIND", "bindtoggle"]))
        key = draw(SOURCE_KEY)
        spelled = f'"{key}"' if draw(st.booleans()) or key == "\\" else key
        if key == "\\" and draw(st.booleans()):
            spelled = '"\\\\"'                  # the escaped backslash
        command = draw(COMMAND)
        lines.append(f'{draw(st.sampled_from(["", " ", chr(9)]))}{directive} {spelled} "{command}"')
        # The game writes `bind` in lower case and _BIND matches only that.
        if directive != "bind":
            continue
        token = key_files.SOURCE_KEYS.get(key.upper())
        for part in command.split(";"):
            cmd = " ".join(part.split())
            if cmd:
                keys = want.setdefault(cmd, [])
                if token is not None and token not in keys:
                    keys.append(token)
    return "\n".join(lines), want


class KeyFileFuzzTest(unittest.TestCase):
    @given(ANY_TEXT)
    def test_every_parser_on_arbitrary_text(self, text):
        for parse in (tf2_keys.parse, apex_keys.parse, sc2_keys.parse, poe_keys.parse,
                      poe2_keys.parse, openra_keys.parse):
            _lists_of_tokens(self, parse(text))
        out = ut_bindings.parse(text)
        self.assertTrue(all(name in ut_bindings.KEY_NAMES.values()
                            for names in out.values() for name in names))

    @given(st.binary(max_size=200))
    def test_bindings_on_arbitrary_bytes(self, data):
        for source in (tf2_keys, apex_keys, sc2_keys, poe_keys, poe2_keys, openra_keys):
            _lists_of_tokens(self, source.bindings("x.cfg", data))

    @given(st.binary(min_size=1, max_size=40), st.integers(0, 39))
    def test_read_text_refuses_a_file_over_its_limit(self, data, limit):
        if len(data) > limit:
            with self.assertRaises(ValueError):
                key_files.read_text("x.cfg", data, limit)
        else:
            self.assertEqual(key_files.read_text("x.cfg", data, limit),
                             data.decode("utf-8", errors="replace"))

    @given(source_files())
    def test_source_binds(self, generated):
        text, want = generated
        self.assertEqual(tf2_keys.parse(text), want)

    @given(st.lists(st.tuples(st.sets(st.sampled_from(sorted(sc2_keys.MODIFIERS)), max_size=3),
                              st.sampled_from(sorted(sc2_keys.KEYS) + ["MOUSEBUTTON1", "NUMPAD1"])),
                    max_size=3), st.sampled_from(["Hotkeys", "hotkeys", "Commands"]),
           st.text(st.sampled_from(list("ABCxyz_")), min_size=1, max_size=8))
    def test_sc2_hotkeys(self, keys, section, name):
        value = ",".join("+".join([m.title() for m in mods] + [key.title()]) for mods, key in keys)
        got = sc2_keys.parse(f"[Settings]\n{name}=Q\n[{section}]\n{name}={value}\n")
        if section.lower() != "hotkeys":
            self.assertEqual(got, {})
            return
        want = []
        for mods, key in keys:
            if key in sc2_keys.KEYS:
                t = "+".join(sorted(sc2_keys.MODIFIERS[m] for m in mods) + [sc2_keys.KEYS[key]])
                if t not in want:
                    want.append(t)
        self.assertEqual(got, {name: want})

    @given(st.dictionaries(st.text(st.sampled_from(list("abc_xyz")), min_size=1, max_size=8),
                           st.tuples(st.sampled_from(sorted(poe_keys.VK) + [0, 1, 160, 999]),
                                     st.sampled_from([0, 1, 2, 4])), max_size=5),
           st.booleans())
    def test_poe_config(self, actions, wasd):
        section = "WASD_ACTION_KEYS" if wasd else "ACTION_KEYS"
        body = "".join(f"{a}={vk} {mod}\n" for a, (vk, mod) in actions.items())
        text = f"[DISPLAY]\nx=1\n[{section}]\n{body}[UI]\nb=81 2\n"
        want = {a: (["+".join(poe_keys.MODIFIERS[mod] + (poe_keys.VK[vk],))]
                    if vk in poe_keys.VK and mod in poe_keys.MODIFIERS else [])
                for a, (vk, mod) in actions.items()}
        self.assertEqual(poe_keys.parse(text, section), want)

    @given(st.dictionaries(st.text(st.sampled_from(list("abc-xyz")), min_size=1, max_size=8),
                           st.one_of(st.none(), st.sampled_from(sorted(openra_keys.KEYCODES))),
                           max_size=5), st.sampled_from(["  ", "\t"]))
    def test_openra_settings(self, hotkeys, indent):
        body = "".join(f"{indent}{name}: {key or ''}\n{indent}{indent}Deeper: Q\n"
                       for name, key in hotkeys.items())
        text = f"Player:\n{indent}Name: x\nKeys:\n{body}Game:\n{indent}Mods: ra\n"
        want = {name: [openra_keys.KEYCODES[key]] if key else [] for name, key in hotkeys.items()}
        self.assertEqual(openra_keys.parse(text), want)

    @given(st.lists(st.tuples(st.sampled_from(sorted(ut_bindings.KEY_NAMES) + ["LeftMouse",
                                                                              "NumPad1"]),
                              st.text(st.sampled_from(list("JumpFire 4")), max_size=8)),
                    max_size=6), st.sampled_from(["Engine.Input", "engine.input", "Engine.Other"]))
    def test_ut2004_user_ini(self, keys, section):
        body = "".join(f"{k.title()}={c}\n" for k, c in keys)
        got = ut_bindings.parse(f"[{section}]\n{body}[Other]\nSpace=Duck\n")
        want = {}
        if section.lower() == "engine.input":
            for k, c in keys:
                if c.strip():
                    want.setdefault(c.strip(), []).append(ut_bindings.KEY_NAMES[k.lower()]
                                                          if k.lower() in ut_bindings.KEY_NAMES
                                                          else None)
            want = {c: [n for n in names if n] for c, names in want.items()}
            want = {c: names for c, names in want.items() if names}
        self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()
