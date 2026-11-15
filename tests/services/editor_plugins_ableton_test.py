"""editor_plugins: copying the Ableton Live remote script into the User Library.

Works in a temporary home, so nothing touches a real User Library.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from polyhost.services import editor_plugins as ep

FILES = ("__init__.py", "core.py", "reporter.py")


class TestAbleton(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.src = self.tmp / "ableton-remote-script" / "PolyKybd"
        self.src.mkdir(parents=True)
        for name in FILES:
            (self.src / name).write_text(f"# {name} v1\n")
        (self.src / "settings.json").write_text("{}")      # never shipped

    def kw(self, system="Windows"):
        return dict(home=self.home, env={}, which=lambda _n: None, system=system,
                    ableton_source=self.src)

    def status(self, system="Windows"):
        return ep.status([ep.ABLETON], **self.kw(system))[0]

    def library(self, system="Windows"):
        sub = "Documents" if system == "Windows" else "Music"
        lib = self.home / sub / "Ableton" / "User Library"
        lib.mkdir(parents=True, exist_ok=True)
        return lib

    def test_folders(self):
        self.assertEqual(ep.ableton_script_dir("/h", "Windows"),
                         Path("/h/Documents/Ableton/User Library/Remote Scripts/PolyKybd"))
        self.assertEqual(ep.ableton_script_dir("/h", "Darwin"),
                         Path("/h/Music/Ableton/User Library/Remote Scripts/PolyKybd"))
        self.assertIsNone(ep.ableton_script_dir("/h", "Linux"))

    def test_the_real_source_has_every_shipped_file(self):
        files = ep.shipped_files(ep.ABLETON)
        self.assertIsNotNone(files)
        self.assertEqual(sorted(files), sorted(FILES))

    def test_no_live_on_linux_or_without_a_user_library(self):
        st = self.status("Linux")
        self.assertEqual((st.state, st.target), (ep.STATE_NOT_PRESENT, None))
        self.assertEqual(self.status().state, ep.STATE_NOT_PRESENT)
        self.assertEqual(ep.install([ep.ABLETON], **self.kw())[0].ok, False)

    def test_install_copies_the_script_and_remove_deletes_it(self):
        lib = self.library()
        st = self.status()
        self.assertEqual(st.state, ep.STATE_NOT_INSTALLED)
        self.assertTrue(ep.default_selection(st))
        [r] = ep.install([ep.ABLETON], **self.kw())
        self.assertTrue(r.ok and r.changed, r)
        folder = lib / "Remote Scripts" / "PolyKybd"
        self.assertEqual(sorted(p.name for p in folder.iterdir()),
                         sorted(FILES + (ep.STAMP_NAME,)))
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)
        # Live compiles the script when it loads it.
        (folder / "__pycache__").mkdir()
        (folder / "__pycache__" / "core.cpython-311.pyc").write_bytes(b"\0")
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)
        [r] = ep.remove([ep.ABLETON], **self.kw())
        self.assertTrue(r.ok and r.changed, r)
        self.assertFalse(folder.exists())
        self.assertTrue((lib / "Remote Scripts").is_dir())   # Live's own folder stays

    def test_macos_install(self):
        lib = self.library("Darwin")
        ep.install([ep.ABLETON], **self.kw("Darwin"))
        self.assertTrue((lib / "Remote Scripts" / "PolyKybd" / "core.py").is_file())

    def test_a_users_settings_file_survives_refresh_and_remove(self):
        lib = self.library()
        folder = lib / "Remote Scripts" / "PolyKybd"
        ep.install([ep.ABLETON], **self.kw())
        (folder / "settings.json").write_text('{"port": 50200}')
        (self.src / "core.py").write_text("# core.py v2\n")
        self.assertEqual(self.status().state, ep.STATE_OUTDATED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.ABLETON])
        self.assertEqual((folder / "core.py").read_text(), "# core.py v2\n")
        ep.remove([ep.ABLETON], **self.kw())
        self.assertEqual([p.name for p in folder.iterdir()], ["settings.json"])

    def test_a_hand_copy_reads_manual(self):
        folder = self.library() / "Remote Scripts" / "PolyKybd"
        folder.mkdir(parents=True)
        (folder / "__init__.py").write_text("# mine\n")
        st = self.status()
        self.assertEqual(st.state, ep.STATE_MANUAL)
        self.assertFalse(ep.default_selection(st))


if __name__ == "__main__":
    unittest.main()
