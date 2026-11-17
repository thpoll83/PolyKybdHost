"""editor_plugins: Godot, Unity and Obsidian, installed per project or vault
folder, and the remembered folders (editor_targets.State).

Fake project folders in a temporary folder; nothing touches a real project.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from polyhost.services import editor_plugins as ep
from polyhost.services import editor_targets as et


class TestState(unittest.TestCase):

    def test_remembered_across_instances_and_a_broken_file_reads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "editor_plugins.json"
            s = et.State(path)
            self.assertTrue(s.add_project("godot", "/p/game"))
            s.add_project("godot", "/p/game")
            s.set_cli("vscode", "abc")
            again = et.State(path)
            self.assertEqual(again.projects("godot"), [str(Path("/p/game"))])
            self.assertEqual(again.cli_digest("vscode"), "abc")
            again.forget_project("godot", "/p/game")
            again.set_cli("vscode", None)
            self.assertEqual(et.State(path).data, {"projects": {"godot": []}, "cli": {}})
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(et.State(path).projects("godot"), [])

    def test_in_memory_for_a_test_home(self):
        s = et.State(None)
        s.add_project("unity", "/u")
        self.assertEqual(s.projects("unity"), [str(Path("/u"))])

    def test_project_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertFalse(et.is_project("godot", d))
            (d / "project.godot").write_text("")
            (d / "Packages").mkdir()
            (d / "Packages" / "manifest.json").write_text("{}")
            (d / ".obsidian").mkdir()
            for e in ("godot", "unity", "obsidian"):
                self.assertTrue(et.is_project(e, d), e)


class ProjectFixture(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.state_file = self.tmp / "state.json"
        src = self.tmp / "src"
        self.godot_src = src / "godot"
        self.write(self.godot_src, {"plugin.cfg": "cfg", "plugin.gd": "gd v1", "reporter_core.gd": "core"})
        self.unity_src = src / "unity"
        self.write(self.unity_src, {"package.json": '{"name": "org.polykybd.context-reporter"}',
                                    "package.json.meta": "m", "Editor.meta": "m",
                                    "Editor/ReporterCore.cs": "cs", "Editor/ReporterCore.cs.meta": "m",
                                    "Tests~/CoreTests.cs": "not copied", ".gitignore": "x"})
        self.obsidian_src = src / "obsidian"
        self.write(self.obsidian_src, {"main.js": "js v1", "manifest.json": "{}"})
        self.sources = {ep.GODOT: self.godot_src, ep.UNITY: self.unity_src,
                        ep.OBSIDIAN: self.obsidian_src}

    @staticmethod
    def write(root, files):
        for rel, text in files.items():
            p = Path(root) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    def kw(self, system="Linux"):
        return dict(home=self.home, env={}, which=lambda _n: None, system=system,
                    sources=self.sources, state_file=self.state_file)

    def status(self, editor, system="Linux"):
        return ep.status([editor], **self.kw(system))[0]

    def project(self, editor, name):
        d = self.tmp / name
        marker = d / et.PROJECT_MARKERS[editor]
        if editor == ep.OBSIDIAN:
            marker.mkdir(parents=True)
        else:
            self.write(d, {et.PROJECT_MARKERS[editor]: "{}"})
        return d


class TestGodot(ProjectFixture):

    def test_found_by_its_settings_folder_and_no_project_yet(self):
        self.assertEqual(self.status(ep.GODOT).state, ep.STATE_NOT_PRESENT)
        (self.home / ".config" / "godot").mkdir(parents=True)
        st = self.status(ep.GODOT)
        self.assertEqual((st.state, st.target), (ep.STATE_NO_PROJECT, None))
        self.assertFalse(ep.default_selection(st))
        (self.home / "AppData" / "Roaming" / "Godot").mkdir(parents=True)
        self.assertEqual(self.status(ep.GODOT, "Windows").state, ep.STATE_NO_PROJECT)
        r = ep.install([ep.GODOT], **self.kw())
        self.assertEqual(len(r), 1)
        self.assertFalse(r[0].ok)
        self.assertIn("No Godot project folder", r[0].message)

    def test_install_remembers_status_refresh_remove_forgets(self):
        game = self.project(ep.GODOT, "game")
        # No Godot settings folder needed when the folder is named.
        r = ep.install([ep.GODOT], projects={ep.GODOT: [str(game)]}, **self.kw())
        self.assertTrue(r[0].ok and r[0].changed, r)
        plugin = game / "addons" / "polykybd_reporter"
        self.assertEqual((plugin / "plugin.gd").read_text(), "gd v1")
        self.assertEqual(et.State(self.state_file).projects(ep.GODOT), [str(game)])
        st = self.status(ep.GODOT)
        self.assertEqual((st.state, st.detail), (ep.STATE_INSTALLED, str(game)))
        (self.godot_src / "plugin.gd").write_text("gd v2")
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.GODOT])
        self.assertEqual((plugin / "plugin.gd").read_text(), "gd v2")
        # Godot 4.4+ writes a .uid file beside each script.
        (plugin / "plugin.gd.uid").write_text("uid://x")
        r = ep.remove([ep.GODOT], **self.kw())
        self.assertTrue(r[0].ok and r[0].changed, r)
        self.assertFalse(plugin.exists())
        self.assertTrue((game / "project.godot").exists())
        self.assertEqual(et.State(self.state_file).projects(ep.GODOT), [])

    def test_a_folder_that_is_no_project_is_refused(self):
        other = self.tmp / "photos"
        other.mkdir()
        r = ep.install([ep.GODOT], projects={ep.GODOT: [str(other)]}, **self.kw())
        self.assertFalse(r[0].ok)
        self.assertIn("project.godot", r[0].message)
        self.assertFalse((other / "addons").exists())
        self.assertEqual(et.State(self.state_file).projects(ep.GODOT), [])

    def test_a_copy_of_the_user_is_left_alone(self):
        game = self.project(ep.GODOT, "game")
        self.write(game / "addons" / "polykybd_reporter", {"plugin.gd": "mine"})
        r = ep.install([ep.GODOT], projects={ep.GODOT: [str(game)]}, **self.kw())
        self.assertFalse(r[0].ok)
        self.assertEqual((game / "addons/polykybd_reporter/plugin.gd").read_text(), "mine")

    def test_only_the_named_project_is_removed(self):
        a, b = self.project(ep.GODOT, "a"), self.project(ep.GODOT, "b")
        ep.install([ep.GODOT], projects={ep.GODOT: [str(a), str(b)]}, **self.kw())
        self.assertEqual(self.status(ep.GODOT).detail, f"{a}, {b}")
        ep.remove([ep.GODOT], projects={ep.GODOT: [str(a)]}, **self.kw())
        self.assertFalse((a / "addons" / "polykybd_reporter").exists())
        self.assertTrue((b / "addons" / "polykybd_reporter").exists())
        self.assertEqual(et.State(self.state_file).projects(ep.GODOT), [str(b)])


class TestUnity(ProjectFixture):

    def test_embedded_package_with_its_meta_files(self):
        game = self.project(ep.UNITY, "game")
        r = ep.install([ep.UNITY], projects={ep.UNITY: [str(game)]}, **self.kw("Darwin"))
        self.assertTrue(r[0].ok, r)
        pkg = game / "Packages" / "org.polykybd.context-reporter"
        self.assertEqual(sorted(p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file()),
                         [".polykybd-host.json", "Editor.meta", "Editor/ReporterCore.cs",
                          "Editor/ReporterCore.cs.meta", "package.json", "package.json.meta"])
        self.assertEqual(self.status(ep.UNITY).state, ep.STATE_INSTALLED)
        ep.remove([ep.UNITY], **self.kw())
        self.assertFalse(pkg.exists())
        self.assertTrue((game / "Packages" / "manifest.json").exists())

    def test_a_package_added_by_git_url_is_left_alone(self):
        game = self.project(ep.UNITY, "game")
        (game / "Packages" / "manifest.json").write_text(json.dumps(
            {"dependencies": {et.UNITY_PACKAGE_NAME: "https://github.com/x.git?path=/unity-package"}}))
        r = ep.install([ep.UNITY], projects={ep.UNITY: [str(game)]}, **self.kw())
        self.assertFalse(r[0].ok)
        self.assertIn("manifest.json", r[0].message)
        self.assertFalse((game / "Packages" / et.UNITY_PACKAGE_NAME).exists())

    def test_found_by_unity_hub(self):
        self.assertEqual(self.status(ep.UNITY, "Windows").state, ep.STATE_NOT_PRESENT)
        (self.home / "AppData" / "Roaming" / "UnityHub").mkdir(parents=True)
        self.assertEqual(self.status(ep.UNITY, "Windows").state, ep.STATE_NO_PROJECT)


class TestObsidian(ProjectFixture):

    def test_the_settings_file_of_the_plugin_survives(self):
        vault = self.project(ep.OBSIDIAN, "Notes")
        ep.install([ep.OBSIDIAN], projects={ep.OBSIDIAN: [str(vault)]}, **self.kw())
        plugin = vault / ".obsidian" / "plugins" / "polykybd-mode-reporter"
        self.assertEqual((plugin / "main.js").read_text(), "js v1")
        # Obsidian saves the plugin's settings beside it.
        (plugin / "data.json").write_text('{"port": 50165}')
        self.assertEqual(self.status(ep.OBSIDIAN).state, ep.STATE_INSTALLED)
        ep.remove([ep.OBSIDIAN], **self.kw())
        self.assertEqual([p.name for p in plugin.iterdir()], ["data.json"])
        # Not a copy of the user: Install works again.
        r = ep.install([ep.OBSIDIAN], projects={ep.OBSIDIAN: [str(vault)]}, **self.kw())
        self.assertTrue(r[0].ok and r[0].changed, r)
        self.assertEqual((plugin / "data.json").read_text(), '{"port": 50165}')

    def test_a_vault_that_was_deleted_is_skipped(self):
        vault = self.project(ep.OBSIDIAN, "Notes")
        ep.install([ep.OBSIDIAN], projects={ep.OBSIDIAN: [str(vault)]}, **self.kw())
        shutil.rmtree(vault)
        (self.home / ".config" / "obsidian").mkdir(parents=True)
        self.assertEqual(self.status(ep.OBSIDIAN).state, ep.STATE_NO_PROJECT)

    def test_the_shipped_plugin_is_the_built_one(self):
        files = ep.new_shipped_files(ep.OBSIDIAN)
        self.assertEqual(sorted(files), ["main.js", "manifest.json"])
        repo = Path(__file__).resolve().parents[2]
        self.assertEqual(files["manifest.json"], (repo / "obsidian-plugin" / "manifest.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
