"""The Obsidian plugin's app-free core (obsidian-plugin/src/core.ts).

The core is TypeScript; its tests are Node's test runner
(`obsidian-plugin/test/core.test.mjs`), which loads the .ts file directly
(type stripping, Node 22.18+). This module runs them in the host suite and
skips when no such Node is installed. It also pins the plugin's constants
against the host's.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from polyhost.handler.browser_url import CONTEXT_REPORTERS, DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

PLUGIN = Path(__file__).resolve().parents[2] / "obsidian-plugin"
CORE = (PLUGIN / "src" / "core.ts").read_text(encoding="utf-8")


def _node_major():
    node = shutil.which("node")
    if not node:
        return None, None
    out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    m = re.match(r"v(\d+)\.(\d+)", out.stdout.strip())
    return node, (int(m.group(1)), int(m.group(2))) if m else None


class CoreConstantsTest(unittest.TestCase):
    """Read from the source, so they hold without Node."""

    def _const(self, name):
        m = re.search(rf"export const {name} = ([^;]+);", CORE)
        self.assertIsNotNone(m, name)
        return m.group(1).strip()

    def test_app_token_is_on_the_allow_list(self):
        app = json.loads(self._const("APP"))
        self.assertIn(app, set(CONTEXT_REPORTERS.values()))
        self.assertEqual(CONTEXT_REPORTERS["obsidian"], app)

    def test_port_and_keepalive_fit_the_host(self):
        self.assertEqual(int(self._const("DEFAULT_PORT")), DEFAULT_BROWSER_REPORT_PORT)
        self.assertLess(int(self._const("KEEPALIVE_MS")) * 2, DEFAULT_MAX_AGE_S * 1000)

    def test_manifest_matches_the_package(self):
        manifest = json.loads((PLUGIN / "manifest.json").read_text(encoding="utf-8"))
        package = json.loads((PLUGIN / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], package["version"])
        self.assertEqual(manifest["id"], package["name"])
        self.assertTrue(manifest["isDesktopOnly"])


class NodeCoreTest(unittest.TestCase):
    def test_node_suite_passes(self):
        node, version = _node_major()
        if node is None or version is None or version < (22, 18):
            self.skipTest(f"needs Node 22.18+ (type stripping), found {version}")
        r = subprocess.run([node, "--test", str(PLUGIN / "test" / "core.test.mjs")],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-4000:] + r.stderr[-2000:])
        self.assertRegex(r.stdout, r"# pass [1-9]")
        self.assertIn("# fail 0", r.stdout)


if __name__ == "__main__":
    unittest.main()
