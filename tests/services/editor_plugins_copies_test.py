"""editor_plugins: the copy per version or profile of Blender, Maya and QGIS,
and the .bwextension in Bitwig Studio's Extensions folder.

Works in a temporary home with fake program folders and fake plugin sources,
so nothing touches a real program.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from polyhost.services import editor_plugins as ep
from polyhost.services import editor_targets as et

REPO = Path(__file__).resolve().parents[2]


class TestWhere(unittest.TestCase):
    """The folders each program loads the plugin from, per OS."""

    def test_blender_bases(self):
        self.assertEqual(et.blender_config_bases("/h", {}, "Linux")[0][1], Path("/h/.config/blender"))
        self.assertEqual(et.blender_config_bases("/h", {"XDG_CONFIG_HOME": "/c"}, "Linux")[0][1],
                         Path("/c/blender"))
        self.assertEqual(et.blender_config_bases("/h", {"APPDATA": "/a"}, "Windows"),
                         [("", Path("/a/Blender Foundation/Blender"))])
        self.assertEqual(et.blender_config_bases("/h", {}, "Darwin"),
                         [("", Path("/h/Library/Application Support/Blender"))])

    def test_blender_folder_by_version(self):
        self.assertEqual(et.blender_addon_dir("/b/4.2", (4, 2)),
                         Path("/b/4.2/extensions/user_default/polykybd_context_reporter"))
        self.assertEqual(et.blender_addon_dir("/b/4.1", (4, 1)),
                         Path("/b/4.1/scripts/addons/polykybd_context_reporter"))

    def test_maya_app_dir(self):
        self.assertEqual(et.maya_app_dir("/h", {}, "Linux"), Path("/h/maya"))
        self.assertEqual(et.maya_app_dir("/h", {}, "Windows"), Path("/h/Documents/maya"))
        self.assertEqual(et.maya_app_dir("/h", {}, "Darwin"),
                         Path("/h/Library/Preferences/Autodesk/maya"))
        self.assertEqual(et.maya_app_dir("/h", {"MAYA_APP_DIR": "/m"}, "Linux"), Path("/m"))

    def test_qgis_profiles(self):
        self.assertEqual(et.qgis_profiles_dirs("/h", {}, "Linux")[0][1],
                         Path("/h/.local/share/QGIS/QGIS3/profiles"))
        self.assertEqual(et.qgis_profiles_dirs("/h", {"APPDATA": "/a"}, "Windows"),
                         [("", Path("/a/QGIS/QGIS3/profiles"))])
        self.assertEqual(et.qgis_profiles_dirs("/h", {}, "Darwin"),
                         [("", Path("/h/Library/Application Support/QGIS/QGIS3/profiles"))])

    def test_bitwig_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            self.assertIsNone(et.bitwig_extensions_dir(h, {}, "Linux"))
            (h / "Bitwig Studio").mkdir()
            self.assertEqual(et.bitwig_extensions_dir(h, {}, "Linux"),
                             h / "Bitwig Studio" / "Extensions")
            self.assertIsNone(et.bitwig_extensions_dir(h, {}, "Windows"))
            (h / "Documents" / "Bitwig Studio").mkdir(parents=True)
            self.assertEqual(et.bitwig_extensions_dir(h, {}, "Darwin"),
                             h / "Documents" / "Bitwig Studio" / "Extensions")


class Fixture(unittest.TestCase):
    """A fake home and fake plugin sources."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        src = self.tmp / "src"
        self.blender_src = src / "blender"
        self.write(self.blender_src, {"__init__.py": "v1", "core.py": "core",
                                      "blender_manifest.toml": 'version = "1.0.0"'})
        (self.blender_src / "__pycache__").mkdir()
        (self.blender_src / "__pycache__" / "core.cpython-311.pyc").write_bytes(b"x")
        self.maya_src = src / "maya"
        self.write(self.maya_src, {"plug-ins/polykybd_mode_reporter.py": "plugin v1",
                                   "polykybd.mod": "+ PolyKybdModeReporter 1.0.0 PATH_TO_THIS_FOLDER\n",
                                   "README.md": "not copied"})
        self.qgis_src = src / "qgis"
        self.write(self.qgis_src, {"__init__.py": "i", "plugin.py": "p", "core.py": "c",
                                   "metadata.txt": "version=1.0.0"})
        self.bitwig_src = src / "PolyKybdContextReporter.bwextension"
        self.bitwig_src.write_bytes(b"jar v1")
        self.sources = {ep.BLENDER: self.blender_src, ep.MAYA: self.maya_src,
                        ep.QGIS: self.qgis_src, ep.BITWIG: self.bitwig_src}

    @staticmethod
    def write(root, files):
        for rel, text in files.items():
            p = Path(root) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    def kw(self, system="Linux", env=None):
        return dict(home=self.home, env=env or {}, which=lambda _n: None, system=system,
                    sources=self.sources, state_file=self.tmp / "state.json")

    def status(self, editor, **kw):
        return ep.status([editor], **self.kw(**kw))[0]


class TestBlender(Fixture):

    def make_versions(self, *versions, base=None):
        base = base or self.home / ".config" / "blender"
        for v in versions:
            (base / v / "config").mkdir(parents=True)
        return base

    def test_not_present_until_blender_ran(self):
        self.assertEqual(self.status(ep.BLENDER).state, ep.STATE_NOT_PRESENT)
        self.make_versions("3.5")       # older than the add-on supports
        self.assertEqual(self.status(ep.BLENDER).state, ep.STATE_NOT_PRESENT)

    def test_install_one_copy_per_version_in_the_right_place(self):
        base = self.make_versions("3.5", "4.1", "4.2", "5.2")
        (base / "userpref.blend").write_bytes(b"")   # a file, not a version
        st = self.status(ep.BLENDER)
        self.assertEqual(st.state, ep.STATE_NOT_INSTALLED)
        self.assertEqual(st.target, base)
        self.assertEqual(st.detail, "4.1, 4.2, 5.2")
        self.assertTrue(ep.default_selection(st))
        results = ep.install([ep.BLENDER], **self.kw())
        self.assertEqual(len(results), 3, results)
        self.assertTrue(all(r.ok and r.changed for r in results), results)
        legacy = base / "4.1" / "scripts" / "addons" / "polykybd_context_reporter"
        ext = base / "5.2" / "extensions" / "user_default" / "polykybd_context_reporter"
        self.assertEqual((legacy / "__init__.py").read_text(), "v1")
        self.assertEqual((ext / "blender_manifest.toml").read_text(), 'version = "1.0.0"')
        self.assertFalse((ext / "__pycache__").exists())
        self.assertFalse((base / "3.5" / "scripts").exists())
        self.assertEqual(self.status(ep.BLENDER).state, ep.STATE_INSTALLED)

    def test_windows_and_macos_folders(self):
        appdata = self.home / "AppData" / "Roaming"
        base = self.make_versions("4.2", base=appdata / "Blender Foundation" / "Blender")
        ep.install([ep.BLENDER], **self.kw(system="Windows"))
        self.assertTrue((base / "4.2/extensions/user_default/polykybd_context_reporter/core.py").is_file())
        base = self.make_versions("4.4", base=self.home / "Library/Application Support/Blender")
        st = self.status(ep.BLENDER, system="Darwin")
        self.assertEqual((st.state, st.target, st.detail), (ep.STATE_NOT_INSTALLED, base, "4.4"))

    def test_user_resources_variable(self):
        custom = self.home / "portable"
        custom.mkdir()
        env = {"BLENDER_USER_RESOURCES": str(custom)}
        ep.install([ep.BLENDER], **self.kw(env=env))
        self.assertTrue((custom / "extensions/user_default/polykybd_context_reporter/__init__.py").is_file())

    def test_a_hand_installed_copy_is_left_alone(self):
        base = self.make_versions("4.2", "4.5")
        # Installed by hand as a legacy add-on in 4.2: Blender would load both.
        self.write(base / "4.2/scripts/addons/polykybd_context_reporter", {"__init__.py": "mine"})
        # Installed from disk in 4.5, no stamp.
        self.write(base / "4.5/extensions/user_default/polykybd_context_reporter",
                   {"__init__.py": "mine"})
        st = self.status(ep.BLENDER)
        self.assertEqual(st.state, ep.STATE_MANUAL)
        results = ep.install([ep.BLENDER], **self.kw())
        self.assertTrue(all(not r.ok and not r.changed for r in results), results)
        self.assertEqual((base / "4.5/extensions/user_default/polykybd_context_reporter/__init__.py")
                         .read_text(), "mine")
        self.assertFalse((base / "4.2/extensions").exists())
        ep.remove([ep.BLENDER], **self.kw())
        self.assertTrue((base / "4.2/scripts/addons/polykybd_context_reporter/__init__.py").exists())

    def test_update_refresh_and_hand_changes(self):
        base = self.make_versions("4.2", "4.5")
        ep.install([ep.BLENDER], **self.kw())
        copy42 = base / "4.2/extensions/user_default/polykybd_context_reporter"
        copy45 = base / "4.5/extensions/user_default/polykybd_context_reporter"
        (copy45 / "core.py").write_text("changed by hand")
        self.assertEqual(self.status(ep.BLENDER).state, ep.STATE_MODIFIED)
        # An update of the app: the shipped files change.
        (self.blender_src / "core.py").write_text("core v2")
        self.assertEqual(self.status(ep.BLENDER).state, ep.STATE_OUTDATED)
        refreshed = ep.refresh_installed(**{k: v for k, v in self.kw().items()})
        self.assertIn(ep.BLENDER, refreshed)
        self.assertEqual((copy42 / "core.py").read_text(), "core v2")
        self.assertEqual((copy45 / "core.py").read_text(), "changed by hand")
        results = ep.remove([ep.BLENDER], **self.kw())
        self.assertEqual(sorted(r.ok for r in results), [False, True], results)
        self.assertFalse(copy42.exists())
        self.assertTrue((copy45 / "core.py").exists())

    def test_the_refresh_does_not_install_into_a_new_version(self):
        base = self.make_versions("4.2")
        ep.install([ep.BLENDER], **self.kw())
        self.make_versions("4.5")       # a Blender installed since
        (self.blender_src / "core.py").write_text("core v2")
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.BLENDER])
        self.assertEqual((base / "4.2/extensions/user_default/polykybd_context_reporter/core.py")
                         .read_text(), "core v2")
        self.assertFalse((base / "4.5" / "extensions").exists())

    def test_remove_deletes_the_bytecode_too(self):
        base = self.make_versions("4.2")
        ep.install([ep.BLENDER], **self.kw())
        copy = base / "4.2/extensions/user_default/polykybd_context_reporter"
        (copy / "__pycache__").mkdir()
        (copy / "__pycache__" / "core.cpython-311.pyc").write_bytes(b"x")
        results = ep.remove(None, **self.kw())
        self.assertTrue(any(r.editor == ep.BLENDER and r.changed for r in results), results)
        self.assertFalse(copy.exists())

    def test_no_source(self):
        self.make_versions("4.2")
        kw = self.kw()
        kw["sources"] = {ep.BLENDER: self.tmp / "missing"}
        st = ep.status([ep.BLENDER], **kw)[0]
        self.assertEqual(st.state, ep.STATE_NO_SOURCE)
        self.assertFalse(ep.install([ep.BLENDER], **kw)[0].ok)

    def test_the_shipped_add_on_is_complete(self):
        files = ep.new_shipped_files(ep.BLENDER)
        self.assertEqual(sorted(files), ["__init__.py", "blender_manifest.toml", "core.py"])


class TestMaya(Fixture):

    def test_module_per_version_with_its_module_file(self):
        app = self.home / "maya"
        for v in ("2020", "2025", "2026", "scripts"):
            (app / v).mkdir(parents=True)
        st = self.status(ep.MAYA)
        self.assertEqual((st.state, st.target, st.detail),
                         (ep.STATE_NOT_INSTALLED, app, "2025, 2026"))
        results = ep.install([ep.MAYA], **self.kw())
        self.assertEqual(len(results), 2, results)
        folder = app / "2026" / "modules" / "polykybd"
        self.assertEqual((folder / "plug-ins/polykybd_mode_reporter.py").read_text(), "plugin v1")
        # Relative to the .mod file: no home path (it can have a space).
        self.assertEqual((folder.parent / "polykybd.mod").read_text(),
                         "+ PolyKybdModeReporter 1.0.0 ./polykybd\n")
        self.assertFalse((folder / "README.md").exists())
        self.assertFalse((app / "2020" / "modules").exists())
        self.assertEqual(self.status(ep.MAYA).state, ep.STATE_INSTALLED)
        ep.remove([ep.MAYA], **self.kw())
        self.assertFalse((folder.parent / "polykybd.mod").exists())
        self.assertFalse(folder.exists())

    def test_windows_documents_folder(self):
        app = self.home / "Documents" / "maya"
        (app / "2025").mkdir(parents=True)
        ep.install([ep.MAYA], **self.kw(system="Windows"))
        self.assertTrue((app / "2025/modules/polykybd.mod").is_file())

    def test_a_module_file_of_the_readme_install_is_left_alone(self):
        app = self.home / "Library/Preferences/Autodesk/maya"
        (app / "2025").mkdir(parents=True)
        self.write(app / "modules", {"polykybd.mod": "+ PolyKybdModeReporter 1.0.0 /x\n"})
        st = self.status(ep.MAYA, system="Darwin")
        self.assertEqual(st.state, ep.STATE_MANUAL)
        self.assertEqual(st.detail, str(app / "modules" / "polykybd.mod"))
        self.assertFalse(ep.install([ep.MAYA], **self.kw(system="Darwin"))[0].ok)
        self.assertFalse((app / "2025" / "modules").exists())


class TestQgis(Fixture):

    def test_one_copy_per_profile_and_a_zip_install_is_kept(self):
        profiles = self.home / ".local/share/QGIS/QGIS3/profiles"
        (profiles / "default").mkdir(parents=True)
        # Installed from the zip in the plugin manager: no stamp.
        self.write(profiles / "work/python/plugins/polykybd_context_reporter",
                   {"__init__.py": "zip"})
        st = self.status(ep.QGIS)
        self.assertEqual(st.state, ep.STATE_NOT_INSTALLED)
        self.assertEqual(st.detail, "default, work")
        results = ep.install([ep.QGIS], **self.kw())
        self.assertEqual([r.ok for r in results], [True, False], results)
        self.assertTrue((profiles / "default/python/plugins/polykybd_context_reporter/metadata.txt")
                        .is_file())
        self.assertEqual((profiles / "work/python/plugins/polykybd_context_reporter/__init__.py")
                         .read_text(), "zip")
        self.assertEqual(self.status(ep.QGIS).state, ep.STATE_MANUAL)
        ep.remove([ep.QGIS], **self.kw())
        self.assertFalse((profiles / "default/python/plugins/polykybd_context_reporter").exists())
        self.assertTrue((profiles / "work/python/plugins/polykybd_context_reporter").exists())

    def test_windows_profiles(self):
        profiles = self.home / "AppData/Roaming/QGIS/QGIS3/profiles"
        (profiles / "default").mkdir(parents=True)
        self.assertEqual(self.status(ep.QGIS, system="Windows").state, ep.STATE_NOT_INSTALLED)


class TestBitwig(Fixture):

    def test_the_file_in_the_shared_extensions_folder(self):
        ext = self.home / "Bitwig Studio" / "Extensions"
        self.write(ext, {"Other.bwextension": "someone else's"})
        st = self.status(ep.BITWIG)
        self.assertEqual((st.state, st.target), (ep.STATE_NOT_INSTALLED, ext))
        r = ep.install([ep.BITWIG], **self.kw())[0]
        self.assertTrue(r.ok and r.changed, r)
        self.assertEqual((ext / "PolyKybdContextReporter.bwextension").read_bytes(), b"jar v1")
        self.assertTrue((ext / ep.BITWIG_STAMP_NAME).is_file())
        self.assertEqual(self.status(ep.BITWIG).state, ep.STATE_INSTALLED)
        self.bitwig_src.write_bytes(b"jar v2")
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.BITWIG])
        self.assertEqual((ext / "PolyKybdContextReporter.bwextension").read_bytes(), b"jar v2")
        ep.remove([ep.BITWIG], **self.kw())
        self.assertEqual(sorted(p.name for p in ext.iterdir()), ["Other.bwextension"])

    def test_remove_keeps_the_extensions_folder(self):
        ext = self.home / "Bitwig Studio" / "Extensions"
        ext.mkdir(parents=True)
        ep.install([ep.BITWIG], **self.kw())
        ep.remove([ep.BITWIG], **self.kw())
        self.assertTrue(ext.is_dir())
        self.assertEqual(list(ext.iterdir()), [])

    def test_a_dragged_in_copy_is_left_alone(self):
        ext = self.home / "Documents" / "Bitwig Studio" / "Extensions"
        self.write(ext, {"PolyKybdContextReporter.bwextension": "dragged"})
        st = self.status(ep.BITWIG, system="Windows")
        self.assertEqual(st.state, ep.STATE_MANUAL)
        self.assertFalse(ep.install([ep.BITWIG], **self.kw(system="Windows"))[0].ok)
        self.assertEqual((ext / "PolyKybdContextReporter.bwextension").read_text(), "dragged")

    def test_the_shipped_extension_is_there(self):
        self.assertEqual(list(ep.new_shipped_files(ep.BITWIG)), ["PolyKybdContextReporter.bwextension"])


if __name__ == "__main__":
    unittest.main()
