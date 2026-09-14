"""Every shipped overlay draws a cell for every binding it declares.

⚠️ THE FAILURE THIS EXISTS FOR IS SILENT, and CLAUDE.md already documents it
once: much of the icon art is **white on transparent**, so a binding left on
`luma` -- which composites over white and lights the DARK linework -- renders
**0 lit pixels**. No error, no warning from the generator, just a blank keycap
in the layer you just built. It shipped again while adding the 2026-09 Windows
batch: four PuTTY cells and two paint.net cells came out empty, and the only
thing that caught them was looking at the preview by eye.

So this compares the DECLARED bindings against the cells the REAL loader
(`ImageConverter`, the same code the device path runs) reads back. A binding
that drew nothing is a binding the keyboard will never show.

⚠️ It asks the GENERATOR where a binding lands rather than re-deriving it:
`resolve_key`, `resolve_modifier`, `binding_applies` and the four channel tables
are imported, not copied. A second copy of that mapping is exactly the guard
shape this repo keeps getting caught by -- and the first draft of this file WAS
that copy, which promptly reported a false failure against `sublime_mac` because
it did not know about the protocol-12 GUI tiers.
"""
import os
import sys
import unittest

import yaml

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import ImageConverter

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_HERE, "scripts"))
import generate_app_overlays as gen  # noqa: E402

SOURCES = os.path.join(_HERE, "polyhost", "res", "overlay_sources")
OVERLAYS = os.path.join(_HERE, "polyhost", "res", "overlays")

# file kind -> the modifiers it carries, straight from the generator's tables.
KINDS = (("mods", gen.PRIMARY_CH), ("combo.mods", gen.COMBO_CH),
         ("extra.mods", gen.EXTRA_CH), ("gui.mods", gen.GUI_CH))


def _binding_files():
    for app in sorted(os.listdir(SOURCES)):
        path = os.path.join(SOURCES, app, "bindings.yaml")
        if os.path.isfile(path):
            yield app, path


class OverlayCellsTest(unittest.TestCase):

    def test_every_binding_actually_draws_a_cell(self):
        checked = 0
        for app, path in _binding_files():
            with open(path, encoding="utf-8") as fh:
                spec = yaml.safe_load(fh)

            # Which modifier each binding asks for, per file kind. `platform` is
            # left at the generator's default: a CMDCTRL binding then resolves the
            # same way the shipped PNGs were generated.
            want = {}
            for b in spec["bindings"]:
                if not gen.binding_applies(b, gen.PLAT_WINDOWS):
                    continue          # a macOS/Linux-only binding is not in this set
                try:
                    kc = gen.resolve_key(b["key"])
                    mod = gen.resolve_modifier(b.get("mods"), platform=gen.PLAT_WINDOWS)
                except (KeyError, ValueError) as e:
                    # ⚠️ FAIL rather than `continue`. The generator does skip such a
                    # binding -- but it skips it LOUDLY, appending to `warnings`,
                    # and a silent skip here is how a shortcut that never reaches a
                    # keycap comes to read as covered. Nothing in the tree raises
                    # today (measured: 0 of 1205), so this costs nothing until
                    # somebody mistypes a key or asks for a chord with no channel.
                    self.fail(f"{app}: binding {b!r} is not renderable: {e}")
                want.setdefault(mod, {}).setdefault(kc.value, []).append(
                    b.get("label") or b["key"])

            for suffix, table in KINDS:
                name = f"{spec['output']}.{suffix}.png"
                full = os.path.join(OVERLAYS, name)
                here = {m: k for m, k in want.items() if m in table}
                if not here:
                    continue
                self.assertTrue(os.path.exists(full),
                                f"{app}: declares {sum(len(k) for k in here.values())} binding(s) on "
                                f"the {suffix} tier but {name} was never generated")
                conv = ImageConverter(DeviceSettings())
                self.assertTrue(conv.open(full), f"{app}: cannot open {name}")

                # ⚠️ Per BINDING, not per count. Comparing `len(cells)` against the
                # number declared needs the program icon subtracted back out, and
                # that subtraction is wrong in both directions: it undercounts when
                # a binding sits on the program-icon key (one cell, counted twice),
                # and any lit cell that is not a binding's hides a binding that drew
                # nothing. Asking whether THIS keycode is lit needs neither.
                for mod, keys in sorted(here.items(), key=lambda kv: kv[0].name):
                    cells = conv.extract_overlays(mod) or {}
                    for kc_value, labels in sorted(keys.items()):
                        self.assertTrue(
                            kc_value in cells,
                            f"{app}: {' / '.join(labels)} is declared on the "
                            f"{mod.name} layer of {name} (keycode 0x{kc_value:02x}) "
                            f"but that cell has NO lit pixels. A cell that drew "
                            f"nothing is almost always `mode`, not the artwork: "
                            f"white-on-transparent art needs `alpha`, while `luma` "
                            f"lights the dark linework and finds none.")
                        checked += 1
                        if len(labels) > 1:
                            self.fail(f"{app}: {len(labels)} bindings share "
                                      f"{mod.name}+keycode 0x{kc_value:02x} "
                                      f"({' / '.join(labels)}); the later one silently "
                                      f"overdraws the earlier.")

        # Guard the guard: a discovery bug that found no bindings would satisfy
        # every assertion above without having checked anything.
        self.assertGreater(checked, 400, "found suspiciously few bindings to check")


if __name__ == "__main__":
    unittest.main()
