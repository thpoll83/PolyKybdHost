"""Contract test: the overlay *authoring* tool and the overlay *loader* must agree
on which colour channel of which file carries which modifier variant.

`scripts/generate_app_overlays.py` writes a stamp into (file, channel);
`polyhost/device/im_converter.py` reads (file, channel) back out as a
`Modifier`. The two keep separate hard-coded tables — PRIMARY_CH/COMBO_CH/
EXTRA_CH/GUI_CH in the script, and the if-chain in `ImageConverter.open()`.

Nothing enforces that they match, and a mismatch **fails silently**: the PNG is
written, the loader reads it, every byte is valid — the artwork just lands on a
different modifier variant than the binding file asked for. On hardware that
shows up as "the Cmd+Shift overlay appears when I hold Cmd+Alt", which is a long
way from the diff that caused it.

This became a live risk with protocol v12, which assigned the previously
reserved GUI-combo variants: the four tiers now carry all 16 variants, and the
channel order inside the extra/gui tiers is deliberate rather than obvious (the
least-important variant of each tier goes in A, because a 3-channel PNG drops
alpha entirely).

The test round-trips every one of the 16 variants through the real generator
subprocess and the real loader, using a distinct key per variant so a
mis-channelled stamp is detected rather than merely a missing one.
"""

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

# (modifier, binding-file `mods:` list). All 16 representable variants.
VARIANTS = [
    (Modifier.NO_MOD, []),
    (Modifier.CTRL, ["CTRL"]),
    (Modifier.ALT, ["ALT"]),
    (Modifier.SHIFT, ["SHIFT"]),
    (Modifier.CTRL_SHIFT, ["CTRL", "SHIFT"]),
    (Modifier.CTRL_ALT, ["CTRL", "ALT"]),
    (Modifier.ALT_SHIFT, ["ALT", "SHIFT"]),
    (Modifier.GUI_KEY, ["GUI"]),
    (Modifier.CTRL_ALT_SHIFT, ["CTRL", "ALT", "SHIFT"]),
    (Modifier.GUI_CTRL, ["GUI", "CTRL"]),
    (Modifier.GUI_SHIFT, ["GUI", "SHIFT"]),
    (Modifier.GUI_ALT, ["GUI", "ALT"]),
    (Modifier.GUI_CTRL_SHIFT, ["GUI", "CTRL", "SHIFT"]),
    (Modifier.GUI_ALT_SHIFT, ["GUI", "ALT", "SHIFT"]),
    (Modifier.GUI_CTRL_ALT, ["GUI", "CTRL", "ALT"]),
    (Modifier.GUI_CTRL_ALT_SHIFT, ["GUI", "CTRL", "ALT", "SHIFT"]),
]
# One distinct key per variant, so a stamp landing in the wrong channel shows up
# as the wrong *keycode* rather than just a missing overlay.
KEYS = list("ABCDEFGHIJKLMNOP")


class OverlayGeneratorChannelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls._tmp.name)
        icons = tmp / "icons"
        icons.mkdir()
        for key in KEYS:
            img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            ImageDraw.Draw(img).rectangle([10, 10, 86, 86], fill=(255, 255, 255, 255))
            img.save(icons / f"{key}.png")

        lines = ["app: rt", "match: [rt]", "output: rt_template",
                 "icon_dir: icons", "mode: alpha", "bindings:"]
        for (mod, mods), key in zip(VARIANTS, KEYS):
            lines.append(f"  - {{ key: {key}, mods: {mods}, "
                         f"icon: {key}.png, label: {mod.name} }}")
        (tmp / "b.yaml").write_text("\n".join(lines) + "\n")

        cls.out = tmp / "out"
        cls.proc = subprocess.run(
            [sys.executable, str(GENERATOR), str(tmp / "b.yaml"), "--out-dir", str(cls.out)],
            capture_output=True, text=True, cwd=str(REPO_ROOT))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_generator_accepts_every_variant(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        skipped = [ln for ln in self.proc.stdout.splitlines() if ln.strip().startswith("!")]
        self.assertEqual(skipped, [], f"generator refused a representable variant: {skipped}")

    def test_all_four_tiers_are_emitted(self):
        self.assertEqual(
            sorted(p.name for p in self.out.glob("*.png")),
            ["rt_template.combo.mods.png", "rt_template.extra.mods.png",
             "rt_template.gui.mods.png", "rt_template.mods.png"])

    def test_every_variant_round_trips_to_the_loader(self):
        """The key the binding asked for is the key the loader reports, per variant."""
        found: dict[Modifier, set[int]] = {}
        for png in sorted(self.out.glob("*.png")):
            conv = ImageConverter(DeviceSettings())
            self.assertTrue(conv.open(str(png)), f"loader rejected {png.name}")
            for mod, _ in VARIANTS:
                overlays = conv.extract_overlays(mod)
                if overlays:
                    found.setdefault(mod, set()).update(overlays)

        for (mod, _), key in zip(VARIANTS, KEYS):
            expected = KeyCode[f"KC_{key}"].value
            self.assertEqual(
                found.get(mod, set()), {expected},
                f"{mod.name} (variant {mod.value}) round-tripped to the wrong cell — "
                f"the generator's channel table and im_converter.py disagree")


if __name__ == "__main__":
    unittest.main()
