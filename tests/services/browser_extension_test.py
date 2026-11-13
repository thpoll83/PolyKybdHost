"""services/browser_extension.py: copying the extension for "Load unpacked"."""
import json
import os
import shutil
import tempfile
import unittest

from polyhost.services import browser_extension as be


class DeployTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.folder = os.path.join(self.tmp, "ext")

    def test_the_shipped_extension_is_complete(self):
        # The files a Chromium browser needs, from this checkout (user installs
        # have browser-extension/ too: updater.SPARSE_PATTERNS keeps it).
        version = be.deploy(self.folder)
        self.assertEqual(version, be.source_version())
        with open(os.path.join(self.folder, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["background"], {"service_worker": "background.js"})
        for name in ("background.js", "options.html", "options.js", be.MARKER):
            self.assertTrue(os.path.isfile(os.path.join(self.folder, name)), name)
        for size in (16, 32, 48, 128):
            self.assertTrue(os.path.isfile(os.path.join(self.folder, "icons", f"icon-{size}.png")))
        self.assertFalse([n for n in os.listdir(self.folder) if n.endswith(".tmp")])

    def test_a_folder_with_other_files_is_refused(self):
        os.makedirs(self.folder)
        with open(os.path.join(self.folder, "notes.txt"), "w", encoding="utf-8") as fh:
            fh.write("mine")
        with self.assertRaises(be.ExtensionError):
            be.deploy(self.folder)
        self.assertEqual(os.listdir(self.folder), ["notes.txt"])

    def test_copying_again_into_our_folder_works(self):
        be.deploy(self.folder)
        self.assertEqual(be.deploy(self.folder), be.source_version())

    def test_a_newer_version_is_copied_at_start(self):
        state = os.path.join(self.tmp, "state.json")
        be.deploy(self.folder)
        be.remember_folder(self.folder, state)
        self.assertEqual(be.remembered_folder(state), self.folder)
        self.assertEqual(be.update_if_outdated(state), "")          # already current
        manifest = os.path.join(self.folder, "manifest.json")
        with open(manifest, encoding="utf-8") as fh:
            data = json.load(fh)
        data["version"] = "0.9.0"
        with open(manifest, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        self.assertEqual(be.update_if_outdated(state), be.source_version())
        self.assertEqual(be.installed_version(self.folder), be.source_version())

    def test_nothing_happens_without_a_remembered_folder_of_ours(self):
        state = os.path.join(self.tmp, "state.json")
        self.assertEqual(be.update_if_outdated(state), "")          # no state file
        os.makedirs(self.folder)
        be.remember_folder(self.folder, state)
        self.assertEqual(be.update_if_outdated(state), "")          # not our folder
        self.assertEqual(os.listdir(self.folder), [])


if __name__ == "__main__":
    unittest.main()
