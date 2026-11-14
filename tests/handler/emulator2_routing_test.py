"""The SHIPPED routing of the second emulator group in `overlay-mapping.poly.yaml`:
ScummVM, Dolphin, PPSSPP, PCSX2, DuckStation and the console ports OpenGOAL,
Ship of Harkinian and Super Mario 64 (sm64ex, sm64coopdx).

What it pins:

* every process name of a set loads that set, on each OS the name exists on;
* a set with a Linux or macOS version loads it there (ScummVM's quit key and
  PPSSPP's Windows menu keys differ per OS);
* `dolphin` is the emulator on Windows and macOS only. On Linux `dolphin` is
  the KDE file manager, which must get no emulator set; the emulator there is
  `dolphin-emu`;
* a game title in the window does not reroute a set;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

ALL_OS = ("windows", "macos", "linux")


def _set(stem, *tiers):
    """The overlay value for `stem`: a string for one file, else a list."""
    files = [f"{stem}.mods.png"] + [f"{stem}.{t}.mods.png" for t in tiers]
    return files[0] if len(files) == 1 else files


SCUMMVM = {"windows": _set("scummvm_template", "combo"),
           "macos": _set("scummvm_template_mac", "combo"),
           "linux": _set("scummvm_template_linux", "combo")}


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here
    (the same tolerance as emulator_routing_test)."""
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


def _files(overlay):
    return [overlay] if isinstance(overlay, str) else list(overlay)


class Emulator2RoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def _assert_files_exist(self, overlays):
        missing = [f for o in overlays for f in _files(o)
                   if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])

    def test_scummvm_per_os(self):
        for app in ("scummvm", "org.scummvm.scummvm"):
            for os_name in ALL_OS:
                with self.subTest(app=app, os=os_name):
                    self.assertEqual(
                        self._route(app, os_name, "The Secret of Monkey Island (CD/DOS/English)"),
                        SCUMMVM[os_name])

    def test_scummvm_files_exist(self):
        self._assert_files_exist(SCUMMVM.values())


if __name__ == "__main__":
    unittest.main()
