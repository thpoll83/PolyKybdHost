"""Per-binding platform scoping (`only:` / `except:`) and the Linux artwork set.

`CMDCTRL` gave the generator two platforms — "Ctrl here, Cmd on macOS" — but the
default set serves BOTH Windows and Linux from one PNG, so an action VS Code
remaps on only one of them had nowhere to go. `Show Output` is the worked
example: `Ctrl+Shift+U` on Windows and `⇧⌘U` on macOS, but Linux moves it to the
two-stroke chord `Ctrl+K Ctrl+H` because Ubuntu reserves `Ctrl+Shift+U` for
unicode input. Before this axis the only choices were to draw it wrong on Linux
or to drop a cell that was correct on the other two.

Three things make this worth a contract test rather than a unit test of the
filter:

* **Silence is the whole design.** A Linux set is emitted ONLY when a binding
  actually distinguishes Linux from the default — `CMDCTRL` alone never does,
  since it is Ctrl on both. Every one of the 17 shipped specs must therefore keep
  rendering byte-identically with no `os: linux:` branch appearing. A regression
  here is invisible in review (the artwork is correct) and shows up as an
  unexplained third PNG set on every app.

* **Scoping is ONE primitive that must express two things.** Omission is the easy
  half; re-chording is the half that decides whether the design holds — the same
  icon written twice with disjoint `only:` lists has to land on DIFFERENT cells
  per platform. Go Back / Go Forward are the real case (`Alt+←/→` on Windows,
  `Ctrl+Alt+-` on Linux), and they are why an "omit here" flag alone would have
  been the wrong primitive.

* **Three stems can collide, not two.** `output_linux` has to differ from both
  `output` and `output_macos`, and the failure is silent in the worst way: the
  sets are written in sequence, so a collision means whichever is written last
  becomes both, with a mapping stanza that reads as though per-OS selection were
  working.
"""

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter
from polyhost.device.keys import KeyCode, Modifier
# Installs logging.Logger.debug_detailed used by ImageConverter.
from polyhost.util import log_util  # noqa: F401

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_app_overlays.py"
GENERATOR_TIMEOUT = 120


def _load_gen():
    spec = importlib.util.spec_from_file_location("_gen_plat", GENERATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_generator(tmp: pathlib.Path, bindings: list[str], output: str,
                   keys: str = "ABCD",
                   extra: list[str] | None = None) -> subprocess.CompletedProcess:
    icons = tmp / "icons"
    icons.mkdir(exist_ok=True)
    for key in keys:
        img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        ImageDraw.Draw(img).rectangle([10, 10, 86, 86], fill=(255, 255, 255, 255))
        img.save(icons / f"{key}.png")

    lines = [f"app: {output}", f"match: [{output}]", f"output: {output}",
             "icon_dir: icons", "mode: alpha"]
    lines.extend(extra or [])
    lines.append("bindings:")
    lines.extend(bindings)
    (tmp / f"{output}.yaml").write_text("\n".join(lines) + "\n")

    return subprocess.run(
        [sys.executable, str(GENERATOR), str(tmp / f"{output}.yaml"),
         "--out-dir", str(tmp / "out")],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=GENERATOR_TIMEOUT)


def _keycodes(pngs, mod: Modifier) -> set[int]:
    """Keycodes the loader reports for `mod` across a set of PNGs."""
    found: set[int] = set()
    for png in pngs:
        conv = ImageConverter(DeviceSettings())
        assert conv.open(str(png)), f"loader rejected {png.name}"
        found.update(conv.extract_overlays(mod) or {})
    return found


def _stem_pngs(out: pathlib.Path, stem: str):
    """PNGs belonging to exactly `stem` — `x_linux.*` shares the `x` prefix, so a
    glob would silently fold the platform sets into the default one."""
    return [p for p in out.glob("*.png") if p.name.split(".")[0] == stem]


class BindingAppliesTest(unittest.TestCase):
    """Unit-level: the scoping filter and the combinations it refuses."""

    def setUp(self):
        self.gen = _load_gen()

    def test_unscoped_binding_applies_everywhere(self):
        for plat in self.gen.PLATFORMS:
            self.assertTrue(self.gen.binding_applies({"key": "A"}, plat))

    def test_only_restricts_to_the_listed_platforms(self):
        b = {"key": "A", "only": ["linux"]}
        self.assertTrue(self.gen.binding_applies(b, self.gen.PLAT_LINUX))
        self.assertFalse(self.gen.binding_applies(b, self.gen.PLAT_WINDOWS))
        self.assertFalse(self.gen.binding_applies(b, self.gen.PLAT_MACOS))

    def test_except_removes_the_listed_platforms(self):
        b = {"key": "A", "except": ["linux"]}
        self.assertFalse(self.gen.binding_applies(b, self.gen.PLAT_LINUX))
        self.assertTrue(self.gen.binding_applies(b, self.gen.PLAT_WINDOWS))
        self.assertTrue(self.gen.binding_applies(b, self.gen.PLAT_MACOS))

    def test_a_bare_string_is_accepted_like_a_one_element_list(self):
        self.assertTrue(self.gen.binding_applies({"only": "linux"}, self.gen.PLAT_LINUX))
        self.assertFalse(self.gen.binding_applies({"only": "linux"}, self.gen.PLAT_WINDOWS))

    def test_only_and_except_together_are_refused(self):
        # They express the same thing and can contradict each other outright
        # (only: [linux] + except: [linux]); silently picking one would make the
        # binding's platform set depend on evaluation order.
        with self.assertRaisesRegex(ValueError, "use one"):
            self.gen.binding_applies({"only": ["linux"], "except": ["macos"]},
                                     self.gen.PLAT_LINUX)

    def test_unknown_platform_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unknown platform"):
            self.gen.binding_applies({"only": ["bsd"]}, self.gen.PLAT_LINUX)

    def test_empty_platform_list_is_refused(self):
        # `only: []` would mean "draw nowhere", which is a typo, not an intent.
        with self.assertRaisesRegex(ValueError, "empty"):
            self.gen.binding_applies({"only": []}, self.gen.PLAT_LINUX)


class CmdCtrlAcrossThreePlatformsTest(unittest.TestCase):
    """Linux resolves CMDCTRL exactly as Windows does — that is what keeps the
    Linux set from being generated for apps that never scope a binding."""

    def setUp(self):
        self.gen = _load_gen()

    def test_cmdctrl_is_ctrl_on_windows_and_linux_and_cmd_on_macos(self):
        g = self.gen
        self.assertEqual(g.resolve_modifier(["CMDCTRL"], platform=g.PLAT_WINDOWS), Modifier.CTRL)
        self.assertEqual(g.resolve_modifier(["CMDCTRL"], platform=g.PLAT_LINUX), Modifier.CTRL)
        self.assertEqual(g.resolve_modifier(["CMDCTRL"], platform=g.PLAT_MACOS), Modifier.GUI_KEY)

    def test_legacy_macos_keyword_still_selects_macos(self):
        # Existing callers (and tests/device/overlay_cmdctrl_test.py) pass the
        # older two-platform spelling; it must keep resolving the same way.
        self.assertEqual(self.gen.resolve_modifier(["CMDCTRL"], macos=True), Modifier.GUI_KEY)
        self.assertEqual(self.gen.resolve_modifier(["CMDCTRL"], macos=False), Modifier.CTRL)

    def test_unknown_platform_is_refused(self):
        with self.assertRaisesRegex(ValueError, "unknown platform"):
            self.gen.resolve_modifier(["CTRL"], platform="bsd")


class NoLinuxSetWithoutScopingTest(unittest.TestCase):
    """The no-churn guarantee: CMDCTRL alone must NOT produce a Linux set."""

    def setUp(self):
        self.gen = _load_gen()

    def test_plain_spec_needs_no_linux_set(self):
        spec = {"bindings": [{"key": "A", "mods": ["CTRL"]}]}
        self.assertFalse(self.gen.spec_needs_linux_set(spec))

    def test_cmdctrl_alone_needs_no_linux_set(self):
        spec = {"bindings": [{"key": "A", "mods": ["CMDCTRL"]},
                             {"key": "B", "mods": ["CMDCTRL", "SHIFT"]}]}
        self.assertFalse(self.gen.spec_needs_linux_set(spec))

    def test_macos_only_scoping_needs_no_linux_set(self):
        # Scoping that does not separate Windows from Linux still leaves them
        # sharing one PNG, so no third set is warranted.
        spec = {"bindings": [{"key": "A", "mods": ["CMDCTRL"], "only": ["macos"]}]}
        self.assertFalse(self.gen.spec_needs_linux_set(spec))

    def test_linux_scoping_needs_a_linux_set(self):
        spec = {"bindings": [{"key": "A", "mods": ["CMDCTRL"], "except": ["linux"]}]}
        self.assertTrue(self.gen.spec_needs_linux_set(spec))

    def test_unscoped_spec_emits_no_linux_files_or_branch(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            proc = _run_generator(
                tmp, ["  - { key: A, mods: [CMDCTRL], icon: A.png, label: A }"], "plain")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = tmp / "out"
            self.assertEqual(_stem_pngs(out, "plain_linux"), [])
            self.assertNotIn("linux:", proc.stdout)
            # ...while the macOS branch it always had is untouched.
            self.assertIn("macos:", proc.stdout)


class LinuxSetRoundTripTest(unittest.TestCase):
    """A scoped spec: omission on one platform, and the same icon re-chorded."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        bindings = [
            # Shared everywhere.
            "  - { key: A, mods: [CMDCTRL], icon: A.png, label: A }",
            # The Show Output shape: right on Windows and macOS, absent on Linux.
            "  - { key: B, mods: [CMDCTRL, SHIFT], icon: B.png, label: B, except: [linux] }",
            # The Go Back shape: one icon, a different chord per platform.
            "  - { key: C, mods: [ALT], icon: C.png, label: C, only: [windows, macos] }",
            "  - { key: C, mods: [CTRL, ALT], icon: C.png, label: C, only: [linux] }",
        ]
        cls.proc = _run_generator(tmp, bindings, "scoped")
        cls.out = tmp / "out"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def test_all_three_sets_are_written(self):
        for stem in ("scoped", "scoped_mac", "scoped_linux"):
            self.assertTrue(_stem_pngs(self.out, stem), f"no PNGs for {stem}")

    def test_excepted_binding_is_absent_from_linux_only(self):
        win = _keycodes(_stem_pngs(self.out, "scoped"), Modifier.CTRL_SHIFT)
        lnx = _keycodes(_stem_pngs(self.out, "scoped_linux"), Modifier.CTRL_SHIFT)
        mac = _keycodes(_stem_pngs(self.out, "scoped_mac"), Modifier.GUI_SHIFT)
        self.assertIn(KeyCode.KC_B.value, win)
        self.assertIn(KeyCode.KC_B.value, mac)
        self.assertNotIn(KeyCode.KC_B.value, lnx)

    def test_rechorded_binding_lands_on_a_different_variant_per_platform(self):
        # This is the assertion that justifies scoping as the single primitive:
        # C is Alt on Windows but Ctrl+Alt on Linux, from one icon.
        win_alt = _keycodes(_stem_pngs(self.out, "scoped"), Modifier.ALT)
        lnx_alt = _keycodes(_stem_pngs(self.out, "scoped_linux"), Modifier.ALT)
        lnx_ctrl_alt = _keycodes(_stem_pngs(self.out, "scoped_linux"), Modifier.CTRL_ALT)
        self.assertIn(KeyCode.KC_C.value, win_alt)
        self.assertIn(KeyCode.KC_C.value, lnx_ctrl_alt)
        self.assertNotIn(KeyCode.KC_C.value, lnx_alt)

    def test_shared_binding_is_present_on_every_platform(self):
        self.assertIn(KeyCode.KC_A.value,
                      _keycodes(_stem_pngs(self.out, "scoped"), Modifier.CTRL))
        self.assertIn(KeyCode.KC_A.value,
                      _keycodes(_stem_pngs(self.out, "scoped_linux"), Modifier.CTRL))
        self.assertIn(KeyCode.KC_A.value,
                      _keycodes(_stem_pngs(self.out, "scoped_mac"), Modifier.GUI_KEY))

    def test_mapping_stanza_carries_both_os_branches(self):
        self.assertIn("macos:", self.proc.stdout)
        self.assertIn("linux:", self.proc.stdout)
        self.assertIn("scoped_linux.mods.png", self.proc.stdout)


class LinuxOutputCollisionTest(unittest.TestCase):
    """Three stems can collide; the generator must refuse before writing."""

    def setUp(self):
        self.gen = _load_gen()

    def test_defaults_to_a_suffixed_stem(self):
        self.assertEqual(self.gen.linux_output({"output": "app_template"}),
                         "app_template_linux")

    def test_explicit_stem_is_honoured(self):
        self.assertEqual(
            self.gen.linux_output({"output": "app_template", "output_linux": "app_lnx"}),
            "app_lnx")

    def test_refuses_to_collide_with_the_default_stem(self):
        with self.assertRaisesRegex(ValueError, "must differ from output"):
            self.gen.linux_output({"output": "app_template", "output_linux": "app_template"})

    def test_refuses_to_collide_with_the_macos_stem(self):
        with self.assertRaisesRegex(ValueError, "output_macos"):
            self.gen.linux_output({"output": "app_template",
                                   "output_linux": "app_template_mac"})

    def test_collision_aborts_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            proc = _run_generator(
                tmp,
                ["  - { key: A, mods: [CMDCTRL], icon: A.png, label: A, except: [linux] }"],
                "clash", extra=["output_linux: clash"])
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("output_linux must differ", proc.stderr)
            out = tmp / "out"
            self.assertEqual(list(out.glob("*.png")) if out.exists() else [], [])


if __name__ == "__main__":
    unittest.main()
