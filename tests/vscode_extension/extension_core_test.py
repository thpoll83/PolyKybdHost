"""The VS Code extension's editor-free core (vscode-extension/src/core.ts).

Runs the extension's own Node tests (vscode-extension/test/core.test.ts) when a
Node that can run TypeScript directly (22.6 or newer) is installed, and checks
the parts of the contract the host depends on from the source text: the port
and keep-alive agree with the host's receiver, and the URL tokens are the ones
the mapping routes on.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from polyhost.handler.browser_url import CONTEXT_REPORTERS, DEFAULT_MAX_AGE_S
from polyhost.server.browser_report_server import DEFAULT_BROWSER_REPORT_PORT

EXT = Path(__file__).resolve().parents[2] / "vscode-extension"
CORE = (EXT / "src" / "core.ts").read_text(encoding="utf-8")


def _node_version():
    node = shutil.which("node")
    if not node:
        return None, None
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True,
                             timeout=10, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None, None
    m = re.match(r"v(\d+)\.(\d+)", out)
    return node, (int(m.group(1)), int(m.group(2))) if m else None


class SourceContractTest(unittest.TestCase):
    def test_port_is_the_hosts(self):
        m = re.search(r"DEFAULT_PORT = (\d+);", CORE)
        self.assertEqual(int(m.group(1)), DEFAULT_BROWSER_REPORT_PORT)

    def test_keepalive_is_inside_the_freshness_window(self):
        m = re.search(r"KEEPALIVE_MS = (\d+);", CORE)
        self.assertLessEqual(int(m.group(1)) * 2, DEFAULT_MAX_AGE_S * 1000)

    def test_app_tokens_are_on_the_allow_list(self):
        body = re.search(r"export function appToken\(.*?\n}\n", CORE, re.S).group(0)
        tokens = set(re.findall(r'return "(\w+)";', body))
        self.assertEqual(tokens, {"vscode", "cursor", "windsurf"})
        self.assertLessEqual(tokens, set(CONTEXT_REPORTERS.values()))

    def test_extension_runs_on_the_local_side(self):
        # A remote (SSH, WSL, container) extension host cannot reach the
        # loopback receiver on the user's computer.
        pkg = (EXT / "package.json").read_text(encoding="utf-8")
        self.assertRegex(pkg, r'"extensionKind":\s*\[\s*"ui"\s*\]')


class NodeUnitTest(unittest.TestCase):
    def test_node_suite_passes(self):
        node, ver = _node_version()
        if node is None or ver is None or ver < (22, 6):
            self.skipTest(f"needs Node 22.6+ to run TypeScript directly (found {ver})")
        r = subprocess.run(
            # TAP output: the default reporter is spec on Node 23+. Module
            # detection: Node 22.6 treats core.ts as CommonJS without it (on by
            # default from 22.7). The compiled out/extension.js stays CommonJS.
            [node, "--experimental-strip-types", "--experimental-detect-module",
             "--no-warnings", "--test", "--test-reporter=tap",
             str(EXT / "test" / "core.test.ts")],
            capture_output=True, text=True, timeout=120, cwd=EXT)
        self.assertEqual(r.returncode, 0, r.stdout[-4000:] + r.stderr[-2000:])
        self.assertRegex(r.stdout, r"# pass [1-9]")
        self.assertRegex(r.stdout, r"# fail 0")


if __name__ == "__main__":
    unittest.main()
