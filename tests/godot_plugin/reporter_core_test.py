"""The Godot plugin's editor-free core (godot-plugin/addons/polykybd_reporter/reporter_core.gd).

GDScript needs Godot to run, so the unit tests of the core are a GDScript file,
godot-plugin/tests/test_reporter_core.gd. This module runs it when a `godot`
binary is found (POLYKYBD_GODOT, or `godot` / `godot4` on PATH) and skips that
test otherwise. The other checks read the GDScript source and run everywhere:
the constants agree with the host, and every route of the mapping is a token
the plugin can send.
"""
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from polyhost.handler.browser_url import DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "godot-plugin"
CORE = PLUGIN / "addons" / "polykybd_reporter" / "reporter_core.gd"
MAPPING = ROOT / "polyhost" / "res" / "overlay-mapping.poly.yaml"


def _godot():
    exe = os.environ.get("POLYKYBD_GODOT")
    if exe and Path(exe).is_file():
        return exe
    return shutil.which("godot") or shutil.which("godot4")


def _const(src, name):
    m = re.search(rf"^const {name} := (.+)$", src, re.M)
    if m is None:
        raise AssertionError(f"no const {name} in {CORE.name}")
    return m.group(1).strip()


def _dict(src, name):
    m = re.search(rf"^const {name} := \{{(.*?)^\}}", src, re.M | re.S)
    if m is None:
        raise AssertionError(f"no const {name} in {CORE.name}")
    return dict(re.findall(r'"([^"]+)":\s*"([^"]*)"', m.group(1)))


class CoreSourceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.src = CORE.read_text(encoding="utf-8")

    def test_constants_agree_with_the_host(self):
        self.assertEqual(_const(self.src, "APP"), '"godot"')
        self.assertEqual(int(_const(self.src, "DEFAULT_PORT").split()[0]),
                         DEFAULT_BROWSER_REPORT_PORT)
        # Two keep-alives may be lost before the host drops the report.
        self.assertLess(2 * float(_const(self.src, "KEEPALIVE_S")), DEFAULT_MAX_AGE_S)

    def test_every_route_is_a_token_the_plugin_sends(self):
        tokens = set(_dict(self.src, "SCREEN_TOKENS").values())
        self.assertEqual(set(_dict(self.src, "SCREEN_CLASSES").values()), tokens)
        raw = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))
        entry = next(v for k, v in raw.items() if k.split(",")[0] == "godot")
        for e in (entry, entry["os"]["macos"]):
            for url in e["urls-contains"]:
                self.assertTrue(url.startswith("godot://"), url)
                self.assertIn(url[len("godot://"):], tokens, url)

    def test_plugin_cfg_names_the_script(self):
        cfg = (PLUGIN / "addons" / "polykybd_reporter" / "plugin.cfg").read_text(encoding="utf-8")
        self.assertIn('script="plugin.gd"', cfg)
        self.assertTrue((CORE.parent / "plugin.gd").is_file())


@unittest.skipUnless(_godot(), "no Godot binary (set POLYKYBD_GODOT)")
class GdscriptUnitTest(unittest.TestCase):

    def test_gdscript_unit_tests_pass(self):
        r = subprocess.run(
            [_godot(), "--headless", "--script", "tests/test_reporter_core.gd"],
            cwd=PLUGIN, capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out)
        self.assertRegex(out, r"reporter_core: \d+ checks, 0 failed")


if __name__ == "__main__":
    unittest.main()
