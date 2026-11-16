"""editor_plugins: unpacking the JetBrains plugin zip into each IDE's plugins folder.

Works in a temporary home with fake IDE folders and a fake plugin zip, so
nothing touches a real IDE.
"""
import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from polyhost.services import editor_plugins as ep

REPO = Path(__file__).resolve().parents[2]
TOP = ep.JETBRAINS_PLUGIN_NAME


def make_zip(path, files):
    """A plugin zip like `gradle buildPlugin` writes: one top folder."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{TOP}/", b"")
        zf.writestr(f"{TOP}/lib/", b"")
        for rel, data in files.items():
            zf.writestr(f"{TOP}/{rel}", data)
    Path(path).write_bytes(buf.getvalue())


class TestJetBrainsWhere(unittest.TestCase):
    """The folders of JetBrains, "Directories used by the IDE" (configuration
    and plugins directory), and IntelliJ's PathManager.platformPath()."""

    def test_plugins_folder_per_os(self):
        self.assertEqual(ep.jetbrains_plugins_dir("PyCharm2025.2", home="/h", env={"APPDATA": "/a"},
                                                  system="Windows"),
                         Path("/a/JetBrains/PyCharm2025.2/plugins"))
        self.assertEqual(ep.jetbrains_plugins_dir("PyCharm2025.2", home="/h", env={}, system="Windows"),
                         Path("/h/AppData/Roaming/JetBrains/PyCharm2025.2/plugins"))
        self.assertEqual(ep.jetbrains_plugins_dir("PyCharm2025.2", home="/h", env={}, system="Darwin"),
                         Path("/h/Library/Application Support/JetBrains/PyCharm2025.2/plugins"))
        self.assertEqual(ep.jetbrains_plugins_dir("PyCharm2025.2", home="/h", env={}, system="Linux"),
                         Path("/h/.local/share/JetBrains/PyCharm2025.2"))
        self.assertEqual(ep.jetbrains_plugins_dir("PyCharm2025.2", home="/h",
                                                  env={"XDG_DATA_HOME": "/d"}, system="Linux"),
                         Path("/d/JetBrains/PyCharm2025.2"))

    def test_config_folder_per_os(self):
        self.assertEqual(ep.jetbrains_config_base(home="/h", env={}, system="Linux"),
                         Path("/h/.config/JetBrains"))
        self.assertEqual(ep.jetbrains_config_base(home="/h", env={"XDG_CONFIG_HOME": "/c"},
                                                  system="Linux"), Path("/c/JetBrains"))
        self.assertEqual(ep.jetbrains_config_base(home="/h", env={}, system="Darwin"),
                         Path("/h/Library/Application Support/JetBrains"))

    def test_build_from_the_folder_name(self):
        self.assertEqual(ep.jetbrains_build("IntelliJIdea2024.2"), 242)
        self.assertEqual(ep.jetbrains_build("PyCharmCE2025.1"), 251)
        self.assertEqual(ep.jetbrains_build("RustRover2026.3"), 263)
        for name in ("Toolbox", "consentOptions", "PyCharm2025", "JetBrainsGateway2025.2",
                     "JetBrainsClient2025.2", "polykybd-backup-20261116-120000"):
            self.assertIsNone(ep.jetbrains_build(name), name)


class JetBrainsFixture(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.zip = self.tmp / "polykybd-context-reporter.zip"
        make_zip(self.zip, {"lib/polykybd-context-reporter-1.0.0.jar": b"jar v1"})

    def kw(self, system="Linux"):
        return dict(home=self.home, env={}, which=lambda _n: None, system=system,
                    jetbrains_source=self.zip)

    def status(self, system="Linux"):
        return ep.status([ep.JETBRAINS], **self.kw(system))[0]

    def ide(self, selector, system="Linux"):
        """An IDE that has run: its configuration folder exists."""
        (ep.jetbrains_config_base(self.home, {}, system) / selector).mkdir(parents=True)
        return ep.jetbrains_plugins_dir(selector, self.home, {}, system) / TOP


class TestJetBrains(JetBrainsFixture):

    def test_not_present_without_an_ide(self):
        self.assertEqual(self.status().state, ep.STATE_NOT_PRESENT)

    def test_an_ide_older_than_2024_2_does_not_count(self):
        self.ide("IntelliJIdea2024.1")
        self.ide("JetBrainsGateway2025.2")
        self.assertEqual(self.status().state, ep.STATE_NOT_PRESENT)

    def test_no_source_without_the_built_zip(self):
        self.ide("PyCharm2025.2")
        kw = self.kw()
        kw["jetbrains_source"] = self.tmp / "missing.zip"
        st = ep.status([ep.JETBRAINS], **kw)[0]
        self.assertEqual(st.state, ep.STATE_NO_SOURCE)
        self.assertEqual(st.detail, str(self.tmp / "missing.zip"))
        [r] = ep.install([ep.JETBRAINS], **kw)
        self.assertFalse(r.ok)
        self.assertIn("missing.zip", r.message)

    def test_a_zip_with_an_entry_outside_its_folder_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{TOP}/lib/a.jar", b"x")
            zf.writestr(f"{TOP}/../evil.jar", b"x")
        self.zip.write_bytes(buf.getvalue())
        self.assertIsNone(ep.shipped_files(ep.JETBRAINS, self.zip))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr(f"{TOP}/..\\evil.jar", b"x")     # a Windows separator
        self.zip.write_bytes(buf.getvalue())
        self.assertIsNone(ep.shipped_files(ep.JETBRAINS, self.zip))
        self.zip.write_bytes(b"not a zip")
        self.assertIsNone(ep.shipped_files(ep.JETBRAINS, self.zip))

    def test_install_unpacks_into_every_ide_and_remove_deletes_it(self):
        for system in ("Linux", "Windows", "Darwin"):
            with self.subTest(system=system):
                shutil.rmtree(self.home)
                self.home.mkdir()
                idea = self.ide("IntelliJIdea2025.2", system)
                pycharm = self.ide("PyCharmCE2024.2", system)
                old = self.ide("WebStorm2023.3", system)
                st = self.status(system)
                self.assertEqual(st.state, ep.STATE_NOT_INSTALLED)
                self.assertEqual(st.detail, "IntelliJIdea2025.2, PyCharmCE2024.2")
                self.assertTrue(ep.default_selection(st))
                results = ep.install([ep.JETBRAINS], **self.kw(system))
                self.assertEqual(len(results), 2, results)
                self.assertTrue(all(r.ok and r.changed for r in results), results)
                for folder in (idea, pycharm):
                    self.assertEqual((folder / "lib/polykybd-context-reporter-1.0.0.jar").read_bytes(),
                                     b"jar v1")
                    self.assertEqual(ep.read_stamp(folder),
                                     {"lib/polykybd-context-reporter-1.0.0.jar": ep._sha(b"jar v1")})
                self.assertFalse(old.exists())
                self.assertEqual(self.status(system).state, ep.STATE_INSTALLED)
                results = ep.remove([ep.JETBRAINS], **self.kw(system))
                self.assertEqual(len(results), 2, results)
                self.assertTrue(all(r.ok and r.changed for r in results), results)
                self.assertFalse(idea.exists() or pycharm.exists())
                self.assertEqual(self.status(system).state, ep.STATE_NOT_INSTALLED)

    def test_other_plugins_in_the_folder_stay(self):
        folder = self.ide("GoLand2025.1")
        other = folder.parent / "some-other-plugin" / "lib" / "x.jar"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"theirs")
        ep.install([ep.JETBRAINS], **self.kw())
        ep.remove([ep.JETBRAINS], **self.kw())
        self.assertEqual(other.read_bytes(), b"theirs")
        self.assertTrue(folder.parent.is_dir())

    def test_an_ide_found_only_by_its_plugins_folder(self):
        # On Linux the plugins folder is apart from the configuration folder.
        (self.home / ".local/share/JetBrains/CLion2025.2").mkdir(parents=True)
        self.assertEqual(self.status().state, ep.STATE_NOT_INSTALLED)

    def test_a_new_plugin_version_replaces_the_old_jar_and_refresh_does_it(self):
        folder = self.ide("Rider2025.2")
        ep.install([ep.JETBRAINS], **self.kw())
        make_zip(self.zip, {"lib/polykybd-context-reporter-1.1.0.jar": b"jar v2"})
        self.assertEqual(self.status().state, ep.STATE_OUTDATED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.JETBRAINS])
        self.assertEqual(sorted(p.name for p in (folder / "lib").iterdir()),
                         ["polykybd-context-reporter-1.1.0.jar"])
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [])

    def test_refresh_updates_only_this_apps_older_copies(self):
        a = self.ide("PhpStorm2025.2")
        ep.install([ep.JETBRAINS], **self.kw())
        b = self.ide("RubyMine2025.2")           # started after the install
        make_zip(self.zip, {"lib/polykybd-context-reporter-1.0.0.jar": b"jar v2"})
        self.assertEqual(self.status().state, ep.STATE_OUTDATED)
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.JETBRAINS])
        self.assertEqual((a / "lib/polykybd-context-reporter-1.0.0.jar").read_bytes(), b"jar v2")
        self.assertFalse(b.exists())
        self.assertEqual(self.status().state, ep.STATE_NOT_INSTALLED)

    def test_a_copy_changed_by_hand_is_left_alone(self):
        a = self.ide("DataGrip2025.2")
        b = self.ide("GoLand2025.2")
        ep.install([ep.JETBRAINS], **self.kw())
        (a / "lib/polykybd-context-reporter-1.0.0.jar").write_bytes(b"edited")
        self.assertEqual(self.status().state, ep.STATE_MODIFIED)
        results = ep.remove([ep.JETBRAINS], **self.kw())
        by_path = {r.ok: r for r in results}
        self.assertEqual(len(results), 2)
        self.assertFalse(by_path[False].ok)
        self.assertEqual((a / "lib/polykybd-context-reporter-1.0.0.jar").read_bytes(), b"edited")
        self.assertFalse(b.exists())

    def test_remove_all_finds_a_copy_while_another_ide_has_none(self):
        a = self.ide("WebStorm2025.2")
        ep.install([ep.JETBRAINS], **self.kw())
        self.ide("GoLand2025.2")
        self.assertEqual(self.status().state, ep.STATE_NOT_INSTALLED)
        results = ep.remove(None, **self.kw())
        self.assertEqual([r.editor for r in results if r.changed], [ep.JETBRAINS])
        self.assertFalse(a.exists())

    def test_a_plugin_installed_from_disk_reads_manual_and_install_sets_it_aside(self):
        folder = self.ide("IntelliJIdea2025.2")
        (folder / "lib").mkdir(parents=True)
        (folder / "lib" / "polykybd-context-reporter-0.9.0.jar").write_bytes(b"by hand")
        st = self.status()
        self.assertEqual(st.state, ep.STATE_MANUAL)
        self.assertEqual(st.detail, str(folder))
        [r] = ep.install([ep.JETBRAINS], **self.kw())
        self.assertTrue(r.ok and r.changed, r.message)
        self.assertIsNotNone(r.backup)
        self.assertEqual((Path(r.backup) / "lib" / "polykybd-context-reporter-0.9.0.jar").read_bytes(),
                         b"by hand")
        # The copy set aside is outside the plugins folder, so the IDE does not load it.
        self.assertNotEqual(Path(r.backup).parent, folder.parent)
        self.assertEqual(sorted(p.name for p in (folder / "lib").iterdir()),
                         ["polykybd-context-reporter-1.0.0.jar"])
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)


class TestShippedJetBrainsPlugin(unittest.TestCase):

    def test_the_shipped_zip_holds_the_plugin_jar_with_its_descriptor(self):
        files = ep.shipped_files(ep.JETBRAINS)
        self.assertIsNotNone(files, ep.JETBRAINS_SOURCE)
        [jar] = files
        self.assertRegex(jar, r"^lib/polykybd-context-reporter-[\d.]+\.jar$")
        with zipfile.ZipFile(io.BytesIO(files[jar])) as zf:
            xml = zf.read("META-INF/plugin.xml").decode("utf-8")
        self.assertIn("<id>org.polykybd.context-reporter</id>", xml)
        self.assertIn(f'since-build="{ep.JETBRAINS_MIN_BUILD}"', xml)

    def test_the_shipped_zip_is_built_from_this_version_of_the_plugin(self):
        gradle = (REPO / "jetbrains-plugin" / "build.gradle.kts").read_text(encoding="utf-8")
        version = next(line.split('"')[1] for line in gradle.splitlines()
                       if line.startswith("version = "))
        self.assertIn(f"lib/polykybd-context-reporter-{version}.jar", ep.shipped_files(ep.JETBRAINS))
        self.assertIn(f'sinceBuild = "{ep.JETBRAINS_MIN_BUILD}"', gradle)


if __name__ == "__main__":
    unittest.main()
