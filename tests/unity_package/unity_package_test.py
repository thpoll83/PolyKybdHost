"""The Unity Editor package (unity-package/): its files, and its C# core.

The C# runs only where Mono is installed (`mcs` and `mono` on PATH); without
it those tests skip. What it pins:

* the package is a valid UPM package: package.json, an Editor-only assembly
  definition, and a .meta file with a unique GUID next to every file and
  folder Unity imports (a package from a git URL is read-only, and Unity
  ignores a file without one);
* the window tokens the C# sends are the ones the `unity` mapping routes on;
* `Tests~/run_tests.sh` passes (unit tests of ReporterCore.cs, and a compile
  check of the Unity glue against stubs);
* a report sent by the C# Sender is accepted by the host's real loopback
  receiver, token included, and reaches `on_report` with `app: unity`.
"""
import json
import logging
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

import yaml

from polyhost.server.browser_report_server import BrowserReportServer

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "unity-package"
CORE = PKG / "Editor" / "ReporterCore.cs"
MAPPING = ROOT / "polyhost" / "res" / "overlay-mapping.poly.yaml"

# The server logs via .debug_detailed (a PolyHost logger extension).
_log = logging.getLogger("unity_package_test")
if not hasattr(_log, "debug_detailed"):
    _log.debug_detailed = lambda *a, **k: None

HAVE_MONO = bool(shutil.which("mcs") and shutil.which("mono") and shutil.which("bash"))


class PackageFilesTest(unittest.TestCase):

    def test_package_json(self):
        data = json.loads((PKG / "package.json").read_text(encoding="utf-8"))
        self.assertRegex(data["name"], r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
        self.assertRegex(data["version"], r"^\d+\.\d+\.\d+$")
        self.assertRegex(data["unity"], r"^\d{4}\.\d$")

    def test_assembly_is_editor_only(self):
        asm = json.loads((PKG / "Editor" / "PolyKybd.ContextReporter.Editor.asmdef")
                         .read_text(encoding="utf-8"))
        self.assertEqual(asm["includePlatforms"], ["Editor"])

    def test_every_imported_file_has_a_meta_with_a_unique_guid(self):
        guids = {}
        for p in sorted(PKG.rglob("*")):
            rel = p.relative_to(PKG).as_posix()
            if rel.startswith("Tests~") or p.suffix == ".meta":
                continue
            meta = p.with_name(p.name + ".meta")
            self.assertTrue(meta.is_file(), f"{rel} has no .meta")
            g = re.search(r"^guid: ([0-9a-f]{32})$", meta.read_text(encoding="utf-8"), re.M)
            self.assertIsNotNone(g, meta)
            self.assertNotIn(g.group(1), guids, rel)
            guids[g.group(1)] = rel
        for meta in PKG.rglob("*.meta"):
            self.assertTrue(meta.with_name(meta.name[:-5]).exists(), f"orphan {meta}")

    def test_routed_tokens_are_ones_the_package_sends(self):
        src = CORE.read_text(encoding="utf-8")
        sent = set(re.findall(r'\{ "\w+", "(\w+)" \}', src))
        self.assertIn("scene", sent)
        entry = yaml.safe_load(MAPPING.read_text(encoding="utf-8"))["unity"]
        for needle in entry["urls-contains"]:
            m = re.fullmatch(r"(?:unity://(?:edit|play))?/(\w+)", needle)
            if m:
                self.assertIn(m.group(1), sent, needle)
        self.assertIn('"unity://" + (playing ? "play" : "edit") + "/"', src)


@unittest.skipUnless(HAVE_MONO, "needs Mono (mcs, mono)")
class CSharpTest(unittest.TestCase):

    def test_run_tests_script(self):
        r = subprocess.run(["bash", str(PKG / "Tests~" / "run_tests.sh")],
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Ran 7 tests, 0 failed", r.stdout)

    def test_a_report_reaches_the_real_receiver(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "core_tests.exe"
            subprocess.run(["mcs", "-nologo", f"-out:{exe}", str(CORE),
                            str(PKG / "Tests~" / "CoreTests.cs")], check=True, timeout=300)
            got, seen = [], threading.Event()

            def on_report(**report):
                got.append(report)
                seen.set()

            server = BrowserReportServer(on_report, _log,
                                         port=0, token="s3cret")
            server.start()
            try:
                port = server._httpd.server_address[1]
                r = subprocess.run(["mono", str(exe), "post", str(port),
                                    "unity://play/game", "s3cret"],
                                   capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertTrue(seen.wait(5))
                self.assertEqual(got[0].get("app"), "unity")
                self.assertEqual(got[0].get("url"), "unity://play/game")
                self.assertEqual(got[0].get("pid"), 4242)
                # A wrong token is refused (HTTP 403): the sender reports it.
                r = subprocess.run(["mono", str(exe), "post", str(port),
                                    "unity://edit/scene", "wrong"],
                                   capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("403", r.stdout)
                self.assertEqual(len(got), 1)
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
