"""Per-desktop Linux artwork sets: the `linux_gnome` / `linux_kde` scopes.

JetBrains ships three Linux keymaps: "Default for GNOME", "Default for KDE" and
"Default for XWin" for every other desktop. KDE moves Stop, Reformat,
Back/Forward and the breakpoint keys; GNOME moves Find Usages, Back/Forward and
the debugger chords. One Linux set cannot draw all three, so the generator
gained `linux_gnome` and `linux_kde`: MEMBERS of the Linux family rather than
peers of it, with plain `linux` as the fallback for every other desktop.

What this pins:

* **Family semantics.** `only: [linux]` covers KDE and `except: [linux]` removes
  it, so every existing spec that scopes on `linux` keeps meaning "all of Linux".
  VS Code's `except: [linux]` for Show Output is exactly that case.
* **The carve-out.** "Linux but not KDE" is `only: [linux], except: [linux_kde]`,
  the only combination of the two keys that is allowed.
* **Silence.** A spec that never names a desktop emits no set and no branch for
  it; the matcher's desktop -> Linux fallback already fits it.
* **Five stems.** `output_gnome` / `output_kde` must differ from every other
  stem, and a collision aborts before anything is written.

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

    def test_both_desktops_are_known_platforms(self):
        self.assertIn("linux_kde", self.gen.PLATFORMS)
        self.assertIn("linux_gnome", self.gen.PLATFORMS)

    def test_only_linux_covers_gnome_too(self):
        self.assertTrue(self.applies({"only": ["linux"]}, self.gen.PLAT_LINUX_GNOME))

    def test_a_gnome_scope_does_not_reach_kde_or_plain_linux(self):
        b = {"only": ["linux_gnome"]}
        self.assertTrue(self.applies(b, self.gen.PLAT_LINUX_GNOME))
        for plat in ("windows", "macos", "linux", "linux_kde"):
            self.assertFalse(self.applies(b, plat), plat)

    def test_carving_out_BOTH_desktops_leaves_the_fallback(self):
        # The XWin shape: plain Linux only, not GNOME or KDE.
        b = {"only": ["windows", "linux"], "except": ["linux_gnome", "linux_kde"]}
        self.assertTrue(self.applies(b, self.gen.PLAT_LINUX))
        self.assertTrue(self.applies(b, self.gen.PLAT_WINDOWS))
        self.assertFalse(self.applies(b, self.gen.PLAT_LINUX_GNOME))
        self.assertFalse(self.applies(b, self.gen.PLAT_LINUX_KDE))

    def test_unscoped_binding_applies_on_kde(self):
        self.assertTrue(self.applies({"key": "A"}, self.gen.PLAT_LINUX_KDE))

    def test_only_linux_covers_kde(self):
        self.assertTrue(self.applies({"only": ["linux"]}, self.gen.PLAT_LINUX_KDE))

    def test_except_linux_removes_kde_too(self):
        self.assertFalse(self.applies({"except": ["linux"]}, self.gen.PLAT_LINUX_KDE))

    def test_only_kde_is_kde_alone(self):
        b = {"only": ["linux_kde"]}
        self.assertTrue(self.applies(b, self.gen.PLAT_LINUX_KDE))
        for plat in ("windows", "macos", "linux", "linux_gnome"):
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

    def test_a_desktop_set_is_needed_only_when_a_binding_names_it(self):
        def need(spec):
            return self.gen.spec_needs_member_set(spec, self.gen.PLAT_LINUX_KDE)
        self.assertFalse(need({"bindings": [{"key": "A"}]}))
        self.assertFalse(need({"bindings": [{"key": "A", "except": ["linux"]}]}))
        self.assertFalse(need({"bindings": [{"key": "A", "only": ["linux"]}]}))
        self.assertTrue(need({"bindings": [{"key": "A", "except": ["linux_kde"]}]}))
        self.assertTrue(need({"bindings": [{"key": "A", "only": ["linux_kde"]}]}))
        # Naming GNOME makes a GNOME set, not a KDE one.
        gnome_only = {"bindings": [{"key": "A", "only": ["linux_gnome"]}]}
        self.assertFalse(need(gnome_only))
        self.assertTrue(self.gen.spec_needs_member_set(gnome_only, self.gen.PLAT_LINUX_GNOME))


class DesktopOutputCollisionTest(unittest.TestCase):

    def setUp(self):
        self.gen = _load_gen()

    def test_defaults_to_a_suffixed_stem(self):
        self.assertEqual(self.gen.member_output({"output": "app"}, "linux_kde"), "app_kde")
        self.assertEqual(self.gen.member_output({"output": "app"}, "linux_gnome"), "app_gnome")

    def test_refuses_each_of_the_other_four_stems(self):
        for stem, key in (("app", "output"), ("app_mac", "output_macos"),
                          ("app_linux", "output_linux"), ("app_gnome", "output_gnome")):
            with self.assertRaisesRegex(ValueError, key):
                self.gen.member_output({"output": "app", "output_kde": stem}, "linux_kde")

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


class DesktopSetsRoundTripTest(unittest.TestCase):
    """The JetBrains shape: Back is Ctrl+Alt+Left on Windows, XWin and KDE but
    Alt+Shift+Left on GNOME; KDE drops a chord the others keep; and one chord
    exists only on the XWin fallback."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        bindings = [
            "  - { key: A, mods: [CMDCTRL], icon: A.png, label: A }",
            "  - { key: B, mods: [CTRL, ALT], icon: B.png, label: B, only: [windows, linux], except: [linux_gnome] }",
            "  - { key: B, mods: [ALT, SHIFT], icon: B.png, label: B, only: [linux_gnome] }",
            "  - { key: C, mods: [CTRL, SHIFT], icon: C.png, label: C, except: [linux_kde] }",
            "  - { key: D, mods: [ALT], icon: D.png, label: D, only: [linux], except: [linux_gnome, linux_kde] }",
        ]
        cls.proc = _run_generator(tmp, bindings, "desk")
        cls.out = tmp / "out"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def keys(self, stem, mod):
        return _keycodes(_stem_pngs(self.out, stem), mod)

    def test_all_five_sets_are_written(self):
        for stem in ("desk", "desk_mac", "desk_linux", "desk_gnome", "desk_kde"):
            self.assertTrue(_stem_pngs(self.out, stem), f"no PNGs for {stem}")

    def test_gnome_draws_its_own_chord_and_kde_follows_the_fallback(self):
        b = KeyCode.KC_B.value
        self.assertIn(b, self.keys("desk_gnome", Modifier.ALT_SHIFT))
        self.assertNotIn(b, self.keys("desk_gnome", Modifier.CTRL_ALT))
        for stem in ("desk_linux", "desk_kde"):
            self.assertIn(b, self.keys(stem, Modifier.CTRL_ALT), stem)
            self.assertNotIn(b, self.keys(stem, Modifier.ALT_SHIFT), stem)

    def test_a_kde_exception_leaves_gnome_and_the_fallback_alone(self):
        c = KeyCode.KC_C.value
        self.assertNotIn(c, self.keys("desk_kde", Modifier.CTRL_SHIFT))
        for stem in ("desk_linux", "desk_gnome"):
            self.assertIn(c, self.keys(stem, Modifier.CTRL_SHIFT), stem)

    def test_a_fallback_only_chord_reaches_neither_desktop(self):
        d = KeyCode.KC_D.value
        self.assertIn(d, self.keys("desk_linux", Modifier.ALT))
        for stem in ("desk", "desk_gnome", "desk_kde"):
            self.assertNotIn(d, self.keys(stem, Modifier.ALT), stem)

    def test_shared_binding_reaches_every_desktop(self):
        for stem in ("desk_linux", "desk_gnome", "desk_kde"):
            self.assertIn(KeyCode.KC_A.value, self.keys(stem, Modifier.CTRL), stem)

    def test_mapping_stanza_carries_every_linux_branch(self):
        for branch in ("linux:", "linux_gnome:", "linux_kde:"):
            self.assertIn(branch, self.proc.stdout)
        self.assertIn("desk_gnome.mods.png", self.proc.stdout)
        self.assertIn("desk_kde.mods.png", self.proc.stdout)


class NoDesktopSetWithoutScopingTest(unittest.TestCase):

    def test_a_linux_scoped_spec_emits_no_desktop_files_or_branch(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            proc = _run_generator(
                tmp, ["  - { key: A, mods: [CTRL], icon: A.png, label: A, except: [linux] }",
                      "  - { key: B, mods: [CTRL], icon: B.png, label: B }"],
                "plain")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for desk in ("kde", "gnome"):
                self.assertEqual(_stem_pngs(tmp / "out", f"plain_{desk}"), [])
                self.assertNotIn(f"linux_{desk}:", proc.stdout)
            self.assertIn("plain_linux", proc.stdout)


if __name__ == "__main__":
    unittest.main()
