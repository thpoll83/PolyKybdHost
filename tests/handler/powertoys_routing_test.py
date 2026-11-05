"""The SHIPPED overlay mapping routes the two PowerToys launcher windows.

This drives `polyhost/res/overlay-mapping.poly.yaml` itself, not a fixture.
Windows cuts a process name at its first dot, so Command Palette
(`Microsoft.CmdPal.UI.exe`) arrives as `microsoft` and every PowerToys window
(`PowerToys.PowerLauncher.exe`, `PowerToys.Settings.exe`, the editors) as
`powertoys`. Only the window title tells them apart, so these tests pin both
directions: the launcher titles get their set, and other windows under the
same names get nothing.
"""

import unittest
from pathlib import Path

import yaml

try:
    from polyhost.handler.active_window import OverlayHandler
    _IMPORT_ERR = None
except Exception as e:
    # Narrow on purpose: only a missing dependency or Xlib refusing a missing
    # display may skip. Anything else is a real regression and re-raises.
    if not (isinstance(e, ModuleNotFoundError)
            or type(e).__module__.split(".")[0] == "Xlib"):
        raise
    _IMPORT_ERR = e

MAPPING = Path(__file__).resolve().parents[2] / "polyhost" / "res" / "overlay-mapping.poly.yaml"


def windows_name(exe):
    """The app name the Windows path derives from an executable name."""
    return exe.split(".")[0].lower()


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class PowerToysRoutingTest(unittest.TestCase):

    def _overlays(self, exe, title):
        """The overlay files the shipped mapping resolves, or None."""
        handler = OverlayHandler(yaml.safe_load(MAPPING.read_text(encoding="utf-8")))
        app = windows_name(exe)
        entry = handler.mapping.get(app)
        if entry is None:
            return None
        handler.title = title
        matched, _cmd = handler.try_to_match_window(app, entry)
        if not matched:
            return None
        overlay = handler.current_entry.get("overlay")
        return [str(f) for f in (overlay if isinstance(overlay, list) else [overlay])]

    def test_COMMAND_PALETTE_gets_its_set(self):
        for title in ("Command Palette", "Command Palette Dev"):
            with self.subTest(title=title):
                self.assertEqual(self._overlays("Microsoft.CmdPal.UI.exe", title),
                                 ["powertoys_cmdpal_template.mods.png",
                                  "powertoys_cmdpal_template.combo.mods.png"])

    def test_POWERTOYS_RUN_gets_its_set(self):
        self.assertEqual(self._overlays("PowerToys.PowerLauncher.exe", "PowerToys Run"),
                         ["powertoys_run_template.mods.png",
                          "powertoys_run_template.combo.mods.png"])

    def test_other_MICROSOFT_dot_apps_get_nothing(self):
        # Media Player is Microsoft.Media.Player.exe: the same cut name.
        for title in ("Media Player", "Command Palette notes - Notepad", ""):
            with self.subTest(title=title):
                self.assertIsNone(self._overlays("Microsoft.Media.Player.exe", title))

    def test_other_POWERTOYS_windows_get_nothing(self):
        for exe, title in (("PowerToys.Settings.exe", "PowerToys Settings"),
                           ("PowerToys.FancyZonesEditor.exe", "FancyZones Layout"),
                           ("PowerToys.KeyboardManagerEditor.exe", "Remap keys"),
                           # A full-screen tool window can have an EMPTY title,
                           # and a parent `title:` gate is skipped for one.
                           ("PowerToys.ColorPickerUI.exe", ""),
                           ("PowerToys.PowerOCR.exe", "")):
            with self.subTest(exe=exe):
                self.assertIsNone(self._overlays(exe, title))


if __name__ == "__main__":
    unittest.main()
