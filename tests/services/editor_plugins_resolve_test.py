"""editor_plugins: copying the DaVinci Resolve page reporter (resolve-plugin/).

Every test works in a temporary home, so nothing touches a real Resolve
scripts folder. The shipped file is the repository's own
resolve-plugin/polykybd_context_reporter.py.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from polyhost.services import editor_plugins as ep

NAME = "polykybd_context_reporter.py"


class ResolvePathsTest(unittest.TestCase):

    def test_scripts_folder_per_platform(self):
        self.assertEqual(
            ep.resolve_scripts_dir(home="/h", env={}, system="Linux"),
            Path("/h/.local/share/DaVinciResolve/Fusion/Scripts"))
        self.assertEqual(
            ep.resolve_scripts_dir(home="/h", env={}, system="Darwin"),
            Path("/h/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"))
        self.assertEqual(
            ep.resolve_scripts_dir(home="/h", env={"APPDATA": "/a"}, system="Windows"),
            Path("/a/Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts"))
        self.assertEqual(
            ep.resolve_scripts_dir(home="/h", env={}, system="Windows"),
            Path("/h/AppData/Roaming/Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts"))

    def test_copy_goes_to_a_utility_subfolder_of_its_own(self):
        self.assertEqual(ep.resolve_plugin_dir(home="/h", env={}, system="Linux"),
                         Path("/h/.local/share/DaVinciResolve/Fusion/Scripts/Utility/PolyKybd"))

    def test_shipped_file_is_the_reporter(self):
        files = ep.shipped_files(ep.RESOLVE)
        self.assertEqual(list(files), [NAME])
        self.assertIn(b"GetCurrentPage", files[NAME])

    def test_listed_in_editors(self):
        self.assertIn(ep.RESOLVE, ep.EDITORS)
        self.assertNotIn(ep.RESOLVE, ep.INIT_EDITORS)


class ResolveInstallTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.fusion = self.home / ".local/share/DaVinciResolve/Fusion"
        self.folder = self.fusion / "Scripts/Utility/PolyKybd"

    def kw(self):
        return dict(home=self.home, env={}, which=lambda _n: None, system="Linux")

    def status(self):
        return ep.status([ep.RESOLVE], **self.kw())[0]

    def test_not_present_without_the_fusion_folder(self):
        self.assertEqual(self.status().state, ep.STATE_NOT_PRESENT)

    def test_install_status_remove(self):
        self.fusion.mkdir(parents=True)
        self.assertEqual(self.status().state, ep.STATE_NOT_INSTALLED)
        self.assertTrue(ep.default_selection(self.status()))
        [r] = ep.install([ep.RESOLVE], **self.kw())
        self.assertTrue(r.ok and r.changed, r.message)
        self.assertEqual((self.folder / NAME).read_bytes(),
                         ep.shipped_files(ep.RESOLVE)[NAME])
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)
        [r] = ep.remove([ep.RESOLVE], **self.kw())
        self.assertTrue(r.ok and r.changed, r.message)
        self.assertFalse(self.folder.exists())
        # The user's own scripts folder stays.
        self.assertTrue((self.fusion / "Scripts/Utility").is_dir())

    def test_other_scripts_in_utility_are_left_alone(self):
        utility = self.fusion / "Scripts/Utility"
        utility.mkdir(parents=True)
        (utility / "mine.py").write_text("print('x')\n")
        ep.install([ep.RESOLVE], **self.kw())
        ep.remove([ep.RESOLVE], **self.kw())
        self.assertEqual((utility / "mine.py").read_text(), "print('x')\n")

    def test_hand_edited_copy_is_left_alone(self):
        self.fusion.mkdir(parents=True)
        ep.install([ep.RESOLVE], **self.kw())
        (self.folder / NAME).write_text("# my edit\n")
        self.assertEqual(self.status().state, ep.STATE_MODIFIED)
        [r] = ep.remove([ep.RESOLVE], **self.kw())
        self.assertFalse(r.ok)
        self.assertTrue((self.folder / NAME).exists())

    def test_refresh_replaces_an_older_copy(self):
        self.folder.mkdir(parents=True)
        old = b"# older reporter\n"
        (self.folder / NAME).write_bytes(old)
        (self.folder / ep.STAMP_NAME).write_text(
            json.dumps({"files": {NAME: ep._sha(old)}}), encoding="utf-8")
        self.assertEqual(self.status().state, ep.STATE_OUTDATED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.RESOLVE])
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)


if __name__ == "__main__":
    unittest.main()
