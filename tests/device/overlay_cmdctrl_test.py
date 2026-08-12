"""CMDCTRL — the OS-relative command modifier — resolves to Ctrl off macOS and to
Cmd (GUI) on it, and a literal CTRL binding stays literal on both.

Authoring a cross-platform overlay set once was the remaining half of the
"primary modifier" request: an app's shortcuts belong to its platform, so a
Ctrl-authored set is simply wrong on a Mac. `os:` (per-OS artwork selection) is
the runtime half and already exists; CMDCTRL is the authoring half — one binding
file, two generated sets, and the `os: macos:` branch that selects between them.

Two things make this worth a contract test rather than a unit test of the
resolver:

* **The macOS destinations cross tier AND channel.** Ctrl is primary R, but Cmd
  is combo A; Ctrl+Shift is combo R, but Cmd+Shift is extra G. So a wrong
  resolution does not fail — it writes valid artwork into a different variant,
  which on hardware reads as "the Cmd+Shift overlay appears under Cmd+Alt".
  Round-tripping through the real loader is what pins it.

* **CMDCTRL must NOT be a blanket Ctrl->Cmd swap.** macOS binds real Ctrl chords
  of its own (Ctrl+A / Ctrl+E line nav, Ctrl+Space input switch, Ctrl+arrows for
  Spaces), so a plain `CTRL` binding has to survive into the macOS set unchanged.
  That is the one behaviour QMK's equivalent — the global, symmetric CG_SWAP
  magic keycode — cannot express, and it is the assertion most likely to be
  broken by a future "simplification".
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

TITLE = r".* Demo"

# key -> (mods in the binding file, variant in the DEFAULT set, variant in the
# macOS set). E and F are the literal-Ctrl controls: same variant in both.
CASES = {
    "A": (["CMDCTRL"], Modifier.CTRL, Modifier.GUI_KEY),
    "B": (["CMDCTRL", "SHIFT"], Modifier.CTRL_SHIFT, Modifier.GUI_SHIFT),
    "C": (["CMDCTRL", "ALT"], Modifier.CTRL_ALT, Modifier.GUI_ALT),
    "D": (["CMDCTRL", "ALT", "SHIFT"], Modifier.CTRL_ALT_SHIFT, Modifier.GUI_ALT_SHIFT),
    "E": (["CTRL"], Modifier.CTRL, Modifier.CTRL),
    "F": (["CTRL", "SHIFT"], Modifier.CTRL_SHIFT, Modifier.CTRL_SHIFT),
}


def _load_variants(pngs) -> dict[Modifier, set[int]]:
    """Every (variant -> keycodes) the loader reports across a set of PNGs."""
    found: dict[Modifier, set[int]] = {}
    for png in pngs:
        conv = ImageConverter(DeviceSettings())
        assert conv.open(str(png)), f"loader rejected {png.name}"
        for mod in Modifier:
            overlays = conv.extract_overlays(mod)
            if overlays:
                found.setdefault(mod, set()).update(overlays)
    return found


def _run_generator(tmp: pathlib.Path, bindings: list[str], output: str,
                   title: str | None = None,
                   extra: list[str] | None = None) -> subprocess.CompletedProcess:
    icons = tmp / "icons"
    icons.mkdir(exist_ok=True)
    for key in CASES:
        img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        ImageDraw.Draw(img).rectangle([10, 10, 86, 86], fill=(255, 255, 255, 255))
        img.save(icons / f"{key}.png")

    lines = [f"app: {output}", f"match: [{output}]", f"output: {output}",
             "icon_dir: icons", "mode: alpha"]
    if title:
        lines.append(f"title: {title}")
    lines.extend(extra or [])
    lines.append("bindings:")
    lines.extend(bindings)
    (tmp / f"{output}.yaml").write_text("\n".join(lines) + "\n")

    return subprocess.run(
        [sys.executable, str(GENERATOR), str(tmp / f"{output}.yaml"),
         "--out-dir", str(tmp / "out")],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=GENERATOR_TIMEOUT)


class CmdCtrlRoundTripTest(unittest.TestCase):
    """One binding file -> two artwork sets, each round-tripped through the loader."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        bindings = [f"  - {{ key: {key}, mods: {mods}, icon: {key}.png, label: {key} }}"
                    for key, (mods, _, _) in CASES.items()]
        cls.proc = _run_generator(tmp, bindings, "cc", TITLE)
        cls.out = tmp / "out"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def setUp(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)

    def _pngs(self, macos: bool):
        # `cc_mac.*` shares the `cc` prefix, so select on the stem explicitly
        # rather than globbing — otherwise the default set silently includes the
        # macOS files and every variant assertion below passes vacuously.
        stem = "cc_mac" if macos else "cc"
        return [p for p in sorted(self.out.glob("*.png"))
                if p.name.split(".", 1)[0] == stem]

    def test_generator_accepted_every_binding(self):
        skipped = [ln for ln in self.proc.stdout.splitlines() if ln.strip().startswith("!")]
        self.assertEqual(skipped, [], f"generator refused a binding: {skipped}")

    def test_both_artwork_sets_are_written(self):
        self.assertTrue(self._pngs(macos=False), "no default artwork set")
        self.assertTrue(self._pngs(macos=True), "no macOS artwork set")

    def test_default_set_resolves_cmdctrl_to_ctrl(self):
        found = _load_variants(self._pngs(macos=False))
        for key, (_, want, _) in CASES.items():
            with self.subTest(key=key, variant=want.name):
                self.assertIn(
                    KeyCode[f"KC_{key}"].value, found.get(want, set()),
                    f"{key} should be on {want.name} (variant {want.value}) "
                    f"in the default set")

    def test_macos_set_resolves_cmdctrl_to_gui(self):
        found = _load_variants(self._pngs(macos=True))
        for key, (_, _, want) in CASES.items():
            with self.subTest(key=key, variant=want.name):
                self.assertIn(
                    KeyCode[f"KC_{key}"].value, found.get(want, set()),
                    f"{key} should be on {want.name} (variant {want.value}) "
                    f"in the macOS set")

    def test_literal_ctrl_is_not_swapped_on_macos(self):
        """The assertion CMDCTRL exists for: `CTRL` means Ctrl on a Mac too.

        A blanket Ctrl->Cmd swap would move E and F off Ctrl and this would fail.
        """
        found = _load_variants(self._pngs(macos=True))
        self.assertIn(KeyCode.KC_E.value, found.get(Modifier.CTRL, set()))
        self.assertIn(KeyCode.KC_F.value, found.get(Modifier.CTRL_SHIFT, set()))
        # ...and the CMDCTRL bindings have vacated Ctrl entirely.
        self.assertNotIn(KeyCode.KC_A.value, found.get(Modifier.CTRL, set()))
        self.assertNotIn(KeyCode.KC_B.value, found.get(Modifier.CTRL_SHIFT, set()))

    def test_mapping_stanza_selects_the_macos_set_by_os(self):
        out = self.proc.stdout
        self.assertIn("  os:", out)
        self.assertIn("    macos:", out)
        self.assertIn("cc_mac.mods.png", out)

    def test_mapping_stanza_repeats_the_title_inside_the_os_branch(self):
        """A matched `os:` branch is returned INSTEAD of the outer entry, so a
        title constraint that is not repeated inside it stops applying to macOS."""
        stanza = self.proc.stdout.split("--- paste into", 1)[1]
        os_branch = stanza.split("    macos:", 1)[1]
        self.assertIn(f"title: {TITLE}", os_branch)


class NoCmdCtrlIsUnchangedTest(unittest.TestCase):
    """A spec that never says CMDCTRL emits exactly what it did before: one
    artwork set and a stanza with no `os:` branch to keep in sync."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        cls.proc = _run_generator(
            tmp, ["  - { key: E, mods: ['CTRL'], icon: E.png, label: E }"], "plain")
        cls.out = tmp / "out"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_no_macos_set_is_written(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        names = sorted(p.name for p in self.out.glob("*.png"))
        self.assertEqual(names, ["plain.mods.png"])

    def test_no_os_branch_in_the_stanza(self):
        self.assertNotIn("  os:", self.proc.stdout)


class CollidingMacosOutputTest(unittest.TestCase):
    """An `output_macos` equal to `output` aborts before anything is written.

    The macOS set is saved *second*, so the collision would overwrite the default
    artwork and leave a mapping stanza whose two `os:` branches point at the same
    Cmd-resolved files — per-OS selection that reads as working while serving Mac
    shortcuts to every platform. Raised by CodeRabbit on #161.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        cls.proc = _run_generator(
            tmp, ["  - { key: A, mods: ['CMDCTRL'], icon: A.png, label: A }"],
            "clash", extra=["output_macos: clash"])
        cls.out = tmp / "out"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_generator_fails(self):
        self.assertNotEqual(self.proc.returncode, 0)
        self.assertIn("output_macos must differ from output", self.proc.stderr)

    def test_nothing_is_written(self):
        self.assertEqual(list(self.out.glob("*.png")) if self.out.exists() else [], [])


class ResolveModifierTest(unittest.TestCase):
    """Unit-level: the resolver itself, including the combinations it refuses."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("_gen_cc", GENERATOR)
        self.gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gen)

    def test_cmdctrl_resolves_per_platform(self):
        self.assertEqual(self.gen.resolve_modifier(["CMDCTRL"]), Modifier.CTRL)
        self.assertEqual(self.gen.resolve_modifier(["CMDCTRL"], macos=True), Modifier.GUI_KEY)

    def test_spelling_aliases(self):
        for alias in ("CMDCTRL", "CmdCtrl", "cmd_or_ctrl", "CMDORCTRL"):
            with self.subTest(alias=alias):
                self.assertEqual(self.gen.resolve_modifier([alias], macos=True),
                                 Modifier.GUI_KEY)

    def test_other_modifiers_are_platform_independent(self):
        for mods in (["CTRL"], ["SHIFT"], ["ALT"], ["GUI"], ["CTRL", "ALT", "SHIFT"]):
            with self.subTest(mods=mods):
                self.assertEqual(self.gen.resolve_modifier(mods),
                                 self.gen.resolve_modifier(mods, macos=True))

    def test_cmdctrl_with_ctrl_or_gui_is_refused_on_both_platforms(self):
        """Either spelling would silently collapse to one bit on one platform, so
        the error must not depend on which set happens to be generated first."""
        for mods in (["CMDCTRL", "CTRL"], ["CMDCTRL", "GUI"], ["CMDCTRL", "CMD"]):
            for macos in (False, True):
                with self.subTest(mods=mods, macos=macos):
                    with self.assertRaisesRegex(ValueError, "mixes CMDCTRL"):
                        self.gen.resolve_modifier(mods, macos=macos)

    def test_macos_output_defaults_to_a_suffixed_stem(self):
        self.assertEqual(self.gen.macos_output({"output": "app_template"}),
                         "app_template_mac")
        self.assertEqual(
            self.gen.macos_output({"output": "app_template", "output_macos": "app_mac"}),
            "app_mac")

    def test_macos_output_refuses_to_collide_with_the_default_stem(self):
        with self.assertRaisesRegex(ValueError, "must differ from output"):
            self.gen.macos_output({"output": "app_template", "output_macos": "app_template"})

    def test_uses_cmdctrl_detects_the_token(self):
        self.assertTrue(self.gen.uses_cmdctrl(["SHIFT", "CMDCTRL"]))
        self.assertFalse(self.gen.uses_cmdctrl(["CTRL", "SHIFT"]))
        self.assertFalse(self.gen.uses_cmdctrl([]))

    def test_unknown_modifier_still_reports_unknown(self):
        with self.assertRaisesRegex(ValueError, "unknown modifier"):
            self.gen.resolve_modifier(["HYPER"])


if __name__ == "__main__":
    unittest.main()
