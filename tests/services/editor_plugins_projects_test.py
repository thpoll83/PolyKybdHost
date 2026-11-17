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
            s.set_cli("vscode", "abc", "1.0.0")
            again = et.State(path)
            self.assertEqual(again.projects("godot"), [str(Path("/p/game"))])
            self.assertEqual((again.cli_digest("vscode"), again.cli_version("vscode")),
                             ("abc", "1.0.0"))
            again.forget_project("godot", "/p/game")
            again.set_cli("vscode", None)
            self.assertEqual(et.State(path).data, {"projects": {"godot": []}, "cli": {}})
            path.write_text("{not json", encoding="utf-8")
            self.assertEqual(et.State(path).projects("godot"), [])

    def test_a_failed_write_keeps_the_file_and_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "editor_plugins.json"
            s = et.State(path)
            s.add_project("godot", "/p/game")
            before = path.read_bytes()

            def bad(data):
                data["cli"]["vscode"] = object()      # not JSON
            self.assertFalse(s.update(bad))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["editor_plugins.json", "editor_plugins.json.lock"])

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


class TestCraftedStamps(ProjectFixture):
    """A downloaded project can hold a stamp of its own: no entry of it may
    make Install, Remove or the refresh touch a file outside the plugin
    folder."""

    def godot_copy(self):
        game = self.project(ep.GODOT, "game")
        ep.install([ep.GODOT], projects={ep.GODOT: [str(game)]}, **self.kw())
        return game, game / "addons" / "polykybd_reporter"

    def craft(self, plugin, entries):
        stamp = json.loads((plugin / ep.STAMP_NAME).read_text())
        stamp["files"].update(entries)
        (plugin / ep.STAMP_NAME).write_text(json.dumps(stamp))

    def assert_untouched(self, plugin, *outside):
        self.assertEqual(self.status(ep.GODOT).state, ep.STATE_MANUAL)
        (self.godot_src / "plugin.gd").write_text("gd v2")     # an update
        for r in (ep.install([ep.GODOT], **self.kw())
                  + ep.remove([ep.GODOT], **self.kw())):
            self.assertFalse(r.changed, r)
        self.assertEqual(ep.refresh_installed(**self.kw()), [])
        self.assertEqual((plugin / "plugin.gd").read_text(), "gd v1")
        for path in outside:
            self.assertTrue(path.exists(), path)

    def test_a_parent_folder_entry(self):
        game, plugin = self.godot_copy()
        # A missing file first makes the copy read "outdated" without the
        # check, and the update would then delete the second entry.
        self.craft(plugin, {"gone.gd": "0" * 64, "../../project.godot": "0" * 64})
        self.assert_untouched(plugin, game / "project.godot")

    def test_an_absolute_entry(self):
        game, plugin = self.godot_copy()
        victim = self.tmp / "victim.txt"
        victim.write_text("keep")
        self.craft(plugin, {str(victim): "0" * 64})
        self.assert_untouched(plugin, victim)

    def test_backslash_and_drive_entries(self):
        for bad in ("..\\..\\project.godot", "C:/x", "a//b", "./a"):
            self.assertFalse(ep.stamp_path_ok(self.tmp, bad), bad)
        self.assertTrue(ep.stamp_path_ok(self.tmp, "a/b.gd"))

    def test_a_link_out_of_the_folder(self):
        game, plugin = self.godot_copy()
        victim = self.tmp / "victim.txt"
        victim.write_text("keep")
        (plugin / "link.gd").symlink_to(victim)
        self.craft(plugin, {"link.gd": "0" * 64})
        self.assert_untouched(plugin, victim)

    def test_a_linked_addons_folder(self):
        game = self.project(ep.GODOT, "game")
        elsewhere = self.tmp / "elsewhere"
        (elsewhere / "polykybd_reporter").mkdir(parents=True)
        (game / "addons").symlink_to(elsewhere)
        st = ep.status([ep.GODOT], **self.kw())[0]
        r = ep.install([ep.GODOT], projects={ep.GODOT: [str(game)]}, **self.kw())
        self.assertFalse(r[0].ok, r)
        self.assertEqual(list((elsewhere / "polykybd_reporter").iterdir()), [])
        self.assertIn(st.state, (ep.STATE_NO_PROJECT, ep.STATE_NOT_PRESENT))

    def test_the_sidecars_of_houdini_and_maya_are_the_only_exceptions(self):
        houdini = self.tmp / "prefs" / "packages" / "polykybd"
        maya = self.tmp / "maya" / "2025" / "modules" / "polykybd"
        other = self.tmp / "game" / "addons" / "polykybd"
        self.assertTrue(ep.stamp_path_ok(houdini, "../polykybd.json"))
        self.assertTrue(ep.stamp_path_ok(maya, "../polykybd.mod"))
        self.assertFalse(ep.stamp_path_ok(houdini, "../polykybd.mod"))
        self.assertFalse(ep.stamp_path_ok(other, "../polykybd.json"))

    def test_an_existing_editor_vim_is_protected_too(self):
        home = self.home
        victim = home / ".vimrc"
        victim.write_text("keep")
        kw = dict(home=home, env={}, which=lambda n: "/usr/bin/vim" if n == "vim" else None,
                  system="Linux")
        ep.install([ep.VIM], **kw)
        plugin = home / ".vim/pack/polykybd/start/polykybd"
        stamp = json.loads((plugin / ep.STAMP_NAME).read_text())
        stamp["files"]["../../../../../.vimrc"] = "0" * 64
        (plugin / ep.STAMP_NAME).write_text(json.dumps(stamp))
        self.assertEqual(ep.status([ep.VIM], **kw)[0].state, ep.STATE_MANUAL)
        ep.remove([ep.VIM], **kw)
        ep.refresh_installed(**kw)
        self.assertEqual(victim.read_text(), "keep")
        self.assertTrue((plugin / "plugin" / "polykybd.vim").exists())


    def test_an_explicit_vim_install_moves_only_the_manual_folder_aside(self):
        home = self.home
        x = home / ".vim" / "pack" / "polykybd" / "x"       # ../../x from the copy
        x.parent.mkdir(parents=True)
        x.write_text("keep")
        victim = home / ".vimrc"
        victim.write_text("keep")
        kw = dict(home=home, env={}, which=lambda n: "/usr/bin/vim" if n == "vim" else None,
                  system="Linux")
        ep.install([ep.VIM], **kw)
        plugin = home / ".vim/pack/polykybd/start/polykybd"
        stamp = json.loads((plugin / ep.STAMP_NAME).read_text())
        stamp["files"].update({"../../x": "0" * 64, str(victim): "0" * 64})
        crafted = json.dumps(stamp)
        (plugin / ep.STAMP_NAME).write_text(crafted)
        pack = home / ".vim" / "pack" / "polykybd"

        def outside():
            return {p: p.read_bytes() for p in home.rglob("*")
                    if p.is_file() and pack not in p.parents}
        before = outside()
        st = ep.status([ep.VIM], **kw)[0]
        self.assertEqual((st.state, st.detail), (ep.STATE_MANUAL, str(plugin)))
        r = ep.install([ep.VIM], **kw)
        self.assertTrue(r[0].ok and r[0].changed, r)
        # The whole folder was moved beside start/, with its crafted stamp...
        self.assertEqual(r[0].backup.parent, pack)
        self.assertEqual((r[0].backup / ep.STAMP_NAME).read_text(), crafted)
        # ...no stamp path was followed, and the new copy is this app's.
        self.assertEqual(x.read_text(), "keep")
        self.assertEqual(outside(), before)
        self.assertEqual(sorted(p.name for p in pack.iterdir()),
                         sorted(["start", "x", r[0].backup.name]))
        self.assertEqual(ep.status([ep.VIM], **kw)[0].state, ep.STATE_INSTALLED)


class TestStateNotSaved(ProjectFixture):

    def test_a_project_that_cannot_be_remembered_is_reported(self):
        game = self.project(ep.GODOT, "game")
        blocker = self.tmp / "blocker"
        blocker.write_text("")
        kw = self.kw()
        kw["state_file"] = blocker / "state.json"
        r = ep.install([ep.GODOT], projects={ep.GODOT: [str(game)]}, **kw)
        self.assertFalse(r[0].ok)
        self.assertTrue(r[0].changed)
        self.assertIn("could not be written", r[0].message)

    def test_an_installed_plugin_whose_folder_cannot_be_remembered(self):
        game = self.project(ep.GODOT, "game")
        r = ep.install([ep.GODOT], projects={ep.GODOT: [str(game)]}, **self.kw())
        self.assertTrue(r[0].ok and r[0].changed, r)
        blocker = self.tmp / "blocker"
        blocker.write_text("")
        kw = self.kw()
        kw["state_file"] = blocker / "state.json"
        r = ep.install([ep.GODOT], projects={ep.GODOT: [str(game)]}, **kw)
        self.assertEqual((r[0].ok, r[0].changed), (False, False), r)
        self.assertNotIn("The change was made", r[0].message)
        self.assertIn("does not remember this folder", r[0].message)


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
