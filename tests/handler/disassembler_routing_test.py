"""The SHIPPED IDA Pro and Binary Ninja routing in `overlay-mapping.poly.yaml`.

Both are Qt applications, so a "Ctrl" shortcut is Cmd on macOS and each has
a Windows/Linux set and a macOS set. What it pins:

* every IDA process name (ida, ida64, idaq, idaq64) on Windows and Linux,
  and the macOS bundle names with a version, load the IDA set for that OS;
* binaryninja on Windows and Linux, and "Binary Ninja" on macOS, load the
  Binary Ninja set for that OS;
* the Ghidra route is unchanged;
* every named file exists.
"""

import unittest
from pathlib import Path

import yaml

from polyhost.handler.common import find_matching_entry, mapping_key

RES = Path(__file__).resolve().parents[2] / "polyhost" / "res"
MAPPING = RES / "overlay-mapping.poly.yaml"

IDA = ["ida_template.mods.png", "ida_template.combo.mods.png"]
IDA_MAC = ["ida_template_mac.mods.png", "ida_template_mac.combo.mods.png",
           "ida_template_mac.extra.mods.png"]
BINJA = ["binaryninja_template.mods.png", "binaryninja_template.combo.mods.png"]
BINJA_MAC = ["binaryninja_template_mac.mods.png", "binaryninja_template_mac.combo.mods.png",
             "binaryninja_template_mac.extra.mods.png"]
GHIDRA = ["ghidra_template.mods.png", "ghidra_template.combo.mods.png"]

NOT_MAC = ("windows", "linux", "linux_gnome", "linux_kde")


def _overlay_handler_class():
    """`OverlayHandler`, or SkipTest when the window backend cannot load here.

    A missing module of this project is a real error, not a missing backend,
    so a ModuleNotFoundError naming `polyhost...` is raised again."""
    try:
        from polyhost.handler.active_window import OverlayHandler
    except SystemExit as e:
        raise unittest.SkipTest(f"window backend exited at import: {e!r}")
    except Exception as e:
        if isinstance(e, ModuleNotFoundError) and (e.name or "").startswith("polyhost"):
            raise
        if not (isinstance(e, ModuleNotFoundError)
                or type(e).__module__.split(".")[0] == "Xlib"):
            raise
        raise unittest.SkipTest(f"active_window needs a display: {e}")
    return OverlayHandler


class DisassemblerRoutingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mapping = _overlay_handler_class()(
            yaml.safe_load(MAPPING.read_text(encoding="utf-8"))).mapping

    def _route(self, app, os_name, title="sample.exe"):
        key = mapping_key(app, self.mapping)
        if key is None:
            return None
        m = find_matching_entry(title, self.mapping[key], None, os_name)
        return None if m is None else m["overlay"]

    def test_ida_process_names_load_the_ida_set(self):
        for app in ("ida", "ida64", "idaq", "idaq64"):
            for os_name in NOT_MAC:
                self.assertEqual(self._route(app, os_name, "IDA - sample.exe.i64"), IDA,
                                 (app, os_name))

    def test_ida_on_macos_loads_the_mac_set(self):
        for app in ("ida", "ida64", "ida pro 9.0", "ida professional 9.1",
                    "ida home 9.2", "ida free 9.2", "ida classroom 9.1"):
            self.assertEqual(self._route(app, "macos", "IDA - sample.i64"), IDA_MAC, app)

    def test_binary_ninja_loads_its_set(self):
        for os_name in NOT_MAC:
            self.assertEqual(self._route("binaryninja", os_name), BINJA, os_name)
        self.assertEqual(self._route("binary ninja", "macos"), BINJA_MAC)
        self.assertEqual(self._route("binaryninja", "macos"), BINJA_MAC)

    def test_ghidra_is_unchanged(self):
        self.assertEqual(self._route("javaw", "windows", "CodeBrowser: proj:/a.exe"), GHIDRA)

    def test_every_named_file_exists(self):
        missing = [f for f in IDA + IDA_MAC + BINJA + BINJA_MAC
                   if not (RES / "overlays" / f).is_file()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
