"""The SHIPPED VICE and Amiga emulator routing in `overlay-mapping.poly.yaml`.

These entries also ask for a keycap face (`glyph_script`,
`glyph_script_position`). The matcher returns the deepest matching entry, so on
macOS it returns the `os: macos:` branch, not its parent: a face set only on the
parent would be lost there. What it pins:

* every VICE binary loads the VICE set, and the macOS set on macOS;
* the C64 family and the VIC-20 ask for the C64 keycap lettering, top left,
  on every platform; Plus/4, PET and CBM-II ask for no face;
* FS-UAE, WinUAE and Amiberry load their sets and ask for the Amiga face,
  top left, on every platform;
* every face value names a GlyphScript, and every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.device.command_ids import GlyphScript
from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"
PLATFORMS = ("windows", "macos", "linux")

VICE = ["vice_template.mods.png", "vice_template.combo.mods.png"]
VICE_MAC = ["vice_template_mac.mods.png", "vice_template_mac.combo.mods.png",
            "vice_template_mac.extra.mods.png"]
FSUAE = "fs_uae_template.mods.png"
FSUAE_MAC = ["fs_uae_template_mac.mods.png", "fs_uae_template_mac.combo.mods.png"]
WINUAE = "winuae_template.mods.png"
AMIBERRY = "amiberry_template.mods.png"

C64_FACE = ("c64keys", "top-left")
AMIGA_FACE = ("amiga", "top-left")


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as qutebrowser_routing_test)."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}") from e
    except Exception as e:
        if not ((isinstance(e, ModuleNotFoundError)
                 and not (e.name or "").startswith("polyhost"))
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}") from e
    return OverlayHandler


class RetroEmulatorRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _entry(self, app, os_name, title="emulator window"):
        key = mapping_key(app, self.mapping)
        self.assertIsNotNone(key, f"{app} has no mapping entry")
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        self.assertIsNotNone(m, f"{app} on {os_name} matched nothing")
        return m

    def _check(self, apps, overlay, overlay_mac, face):
        for app in apps:
            for os_name in PLATFORMS:
                with self.subTest(app=app, os=os_name):
                    m = self._entry(app, os_name)
                    self.assertEqual(m["overlay"], overlay_mac if os_name == "macos" else overlay)
                    got = (m.get("glyph_script"), m.get("glyph_script_position"))
                    self.assertEqual(got, face or (None, None))

    def test_vice_c64_family_and_vic20(self):
        self._check(["x64sc", "x64", "x128", "xscpu64", "x64dtv", "xvic"],
                    VICE, VICE_MAC, C64_FACE)

    def test_vice_other_machines_keep_the_users_face(self):
        self._check(["xplus4", "xpet", "xcbm2", "xcbm5x0"], VICE, VICE_MAC, None)

    def test_fs_uae(self):
        self._check(["fs-uae"], FSUAE, FSUAE_MAC, AMIGA_FACE)

    def test_winuae_and_amiberry(self):
        self._check(["winuae", "winuae64"], WINUAE, WINUAE, AMIGA_FACE)
        self._check(["amiberry", "amiberry-lite"], AMIBERRY, AMIBERRY, AMIGA_FACE)

    def test_face_values_name_a_glyph_script(self):
        names = {s.name.lower() for s in GlyphScript}
        for script, _ in (C64_FACE, AMIGA_FACE):
            self.assertIn(script, names)

    def test_every_named_file_exists(self):
        files = [*VICE, *VICE_MAC, FSUAE, *FSUAE_MAC, WINUAE, AMIBERRY]
        missing = [f for f in files if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
