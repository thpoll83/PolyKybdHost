"""KDE as a fourth artwork set, and the `linux_kde` scope that produces it.

JetBrains ships a separate "Default for KDE" keymap that moves Stop, Reformat,
Back/Forward and the breakpoint keys away from the GNOME chords. One Linux set
cannot draw both, so the generator gained `linux_kde`: a MEMBER of the Linux
family rather than a peer of it.

What this pins:

* **Family semantics.** `only: [linux]` covers KDE and `except: [linux]` removes
  it, so every existing spec that scopes on `linux` keeps meaning "all of Linux".
  VS Code's `except: [linux]` for Show Output is exactly that case.
* **The carve-out.** "Linux but not KDE" is `only: [linux], except: [linux_kde]`,
  the only combination of the two keys that is allowed.
* **Silence.** A spec that never names `linux_kde` emits no KDE set and no
  `linux_kde:` branch; the matcher's KDE -> Linux fallback already fits it.
* **Four stems.** `output_kde` must differ from the other three, and a collision
  aborts before anything is written.

The shipped mapping's KDE routing is pinned in
tests/handler/hosted_app_routing_test.py, which can drive the real matcher.
"""

import pathlib
import tempfile
import unittest

from polyhost.device.keys import KeyCode, Modifier
from tests.device.overlay_platform_axis_test import (
    _keycodes, _load_gen, _run_generator, _stem_pngs)


class KdeScopeTest(unittest.TestCase):

    def setUp(self):
        self.gen = _load_gen()

    def applies(self, b, plat):
        return self.gen.binding_applies(b, plat)

    def test_kde_is_a_known_platform(self):
        self.assertIn("linux_kde", self.gen.PLATFORMS)

    def test_unscoped_binding_applies_on_kde(self):
        self.assertTrue(self.applies({"key": "A"}, self.gen.PLAT_LINUX_KDE))

    def test_only_linux_covers_kde(self):
        self.assertTrue(self.applies({"only": ["linux"]}, self.gen.PLAT_LINUX_KDE))

    def test_except_linux_removes_kde_too(self):
        self.assertFalse(self.applies({"except": ["linux"]}, self.gen.PLAT_LINUX_KDE))

    def test_only_kde_is_kde_alone(self):
        b = {"only": ["linux_kde"]}
        self.assertTrue(self.applies(b, self.gen.PLAT_LINUX_KDE))
        for plat in ("windows", "macos", "linux"):
            self.assertFalse(self.applies(b, plat), plat)

    def test_except_kde_leaves_linux_alone(self):
        b = {"except": ["linux_kde"]}
        self.assertFalse(self.applies(b, self.gen.PLAT_LINUX_KDE))
        for plat in ("windows", "macos", "linux"):
            self.assertTrue(self.applies(b, plat), plat)

    def test_carve_out_is_linux_without_kde(self):
        b = {"only": ["linux"], "except": ["linux_kde"]}
        self.assertTrue(self.applies(b, self.gen.PLAT_LINUX))
        self.assertFalse(self.applies(b, self.gen.PLAT_LINUX_KDE))
        self.assertFalse(self.applies(b, self.gen.PLAT_WINDOWS))

    def test_carve_out_without_the_family_is_refused(self):
        # except: [linux_kde] under only: [windows] removes nothing -- a typo.
        with self.assertRaisesRegex(ValueError, "family member"):
            self.applies({"only": ["windows"], "except": ["linux_kde"]},
                         self.gen.PLAT_WINDOWS)

    def test_kde_resolves_cmdctrl_to_ctrl(self):
        self.assertEqual(
            self.gen.resolve_modifier(["CMDCTRL"], platform=self.gen.PLAT_LINUX_KDE),
            Modifier.CTRL)

    def test_kde_set_needed_only_when_a_binding_names_it(self):
        need = self.gen.spec_needs_kde_set
        self.assertFalse(need({"bindings": [{"key": "A"}]}))
        self.assertFalse(need({"bindings": [{"key": "A", "except": ["linux"]}]}))
        self.assertFalse(need({"bindings": [{"key": "A", "only": ["linux"]}]}))
        self.assertTrue(need({"bindings": [{"key": "A", "except": ["linux_kde"]}]}))
        self.assertTrue(need({"bindings": [{"key": "A", "only": ["linux_kde"]}]}))


class KdeOutputCollisionTest(unittest.TestCase):

    def setUp(self):
        self.gen = _load_gen()

    def test_defaults_to_a_suffixed_stem(self):
        self.assertEqual(self.gen.kde_output({"output": "app"}), "app_kde")

    def test_refuses_each_of_the_other_three_stems(self):
        for stem, key in (("app", "output"), ("app_mac", "output_macos"),
                          ("app_linux", "output_linux")):
            with self.assertRaisesRegex(ValueError, key):
                self.gen.kde_output({"output": "app", "output_kde": stem})

    def test_collision_aborts_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            proc = _run_generator(
                tmp,
                ["  - { key: A, mods: [CTRL], icon: A.png, label: A, except: [linux_kde] }"],
                "clash", extra=["output_kde: clash"])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("output_kde must differ", proc.stderr)
            out = tmp / "out"
            self.assertEqual(list(out.glob("*.png")) if out.exists() else [], [])


class KdeSetRoundTripTest(unittest.TestCase):
    """The JetBrains Back shape: one icon on a different chord per platform, with
    GNOME and KDE disagreeing."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        bindings = [
            "  - { key: A, mods: [CMDCTRL], icon: A.png, label: A }",
            "  - { key: B, mods: [CTRL, ALT], icon: B.png, label: B, only: [windows, linux_kde] }",
            "  - { key: B, mods: [ALT, SHIFT], icon: B.png, label: B, only: [linux], except: [linux_kde] }",
            "  - { key: B, mods: [GUI], icon: B.png, label: B, only: [macos] }",
        ]
        cls.proc = _run_generator(tmp, bindings, "desk")
        cls.out = tmp / "out"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_all_four_sets_are_written(self):
        for stem in ("desk", "desk_mac", "desk_linux", "desk_kde"):
            self.assertTrue(_stem_pngs(self.out, stem), f"no PNGs for {stem}")

    def test_kde_and_gnome_draw_different_chords(self):
        b = KeyCode.KC_B.value
        self.assertIn(b, _keycodes(_stem_pngs(self.out, "desk_kde"), Modifier.CTRL_ALT))
        self.assertNotIn(b, _keycodes(_stem_pngs(self.out, "desk_kde"), Modifier.ALT_SHIFT))
        self.assertIn(b, _keycodes(_stem_pngs(self.out, "desk_linux"), Modifier.ALT_SHIFT))
        self.assertNotIn(b, _keycodes(_stem_pngs(self.out, "desk_linux"), Modifier.CTRL_ALT))

    def test_shared_binding_reaches_kde(self):
        self.assertIn(KeyCode.KC_A.value,
                      _keycodes(_stem_pngs(self.out, "desk_kde"), Modifier.CTRL))

    def test_mapping_stanza_carries_a_linux_kde_branch(self):
        self.assertIn("linux_kde:", self.proc.stdout)
        self.assertIn("desk_kde.mods.png", self.proc.stdout)


class NoKdeSetWithoutScopingTest(unittest.TestCase):

    def test_a_linux_scoped_spec_emits_no_kde_files_or_branch(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            proc = _run_generator(
                tmp, ["  - { key: A, mods: [CTRL], icon: A.png, label: A, except: [linux] }",
                      "  - { key: B, mods: [CTRL], icon: B.png, label: B }"],
                "plain")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(_stem_pngs(tmp / "out", "plain_kde"), [])
            self.assertNotIn("linux_kde:", proc.stdout)
            self.assertIn("plain_linux", proc.stdout)


if __name__ == "__main__":
    unittest.main()
