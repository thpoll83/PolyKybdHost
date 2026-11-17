"""`polyctl editor-plugins` copies the editor mode plugins and must never try
to reach the host (it needs neither the daemon nor the keyboard)."""
import io
import os
import tempfile
import unittest
import unittest.mock as mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from polyhost.cli import polyctl
from polyhost.services import editor_plugins


class PolyctlEditorPluginsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(polyctl, "connect",
                               side_effect=AssertionError("must not connect")), \
                redirect_stdout(out), redirect_stderr(err):
            code = polyctl.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_status_lists_each_editor_without_a_host(self):
        statuses = [editor_plugins.EditorStatus("vim", "installed", Path("/h/.vim/x"), ""),
                    editor_plugins.EditorStatus("emacs", "manual", Path("/h/.emacs"), "/h/.emacs")]
        with mock.patch.object(editor_plugins, "status", return_value=statuses) as status:
            code, out, _ = self.run_main("editor-plugins", "status")
        self.assertEqual(code, 0)
        status.assert_called_once_with(None)
        self.assertIn("/h/.vim/x", out)
        self.assertIn("loaded from somewhere else", out)

    def test_install_and_remove_in_a_real_home(self):
        env = {"HOME": str(self.home), "XDG_DATA_HOME": "", "XDG_CONFIG_HOME": ""}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(editor_plugins.shutil, "which",
                                  side_effect=lambda n: "/usr/bin/vim" if n == "vim" else None):
            code, out, _ = self.run_main("editor-plugins", "install", "--editor", "vim")
            self.assertEqual(code, 0, out)
            self.assertTrue((self.home / ".vim/pack/polykybd/start/polykybd/plugin/polykybd.vim").is_file())
            self.assertIn("Restart the editor", out)
            code, out, _ = self.run_main("editor-plugins", "remove", "--editor", "vim")
            self.assertEqual(code, 0, out)
            self.assertFalse((self.home / ".vim/pack/polykybd").exists())

    def test_a_failed_install_exits_1(self):
        results = [editor_plugins.Result("vim", False, False, "nope", None)]
        with mock.patch.object(editor_plugins, "install", return_value=results):
            code, out, _ = self.run_main("editor-plugins", "install")
        self.assertEqual(code, 1)
        self.assertIn("vim: nope", out)

    def test_project_folders_reach_the_service(self):
        with mock.patch.object(editor_plugins, "install", return_value=[]) as inst:
            code, out, _ = self.run_main("editor-plugins", "install", "--editor", "godot",
                                         "--editor", "vim", "--project", "game")
        self.assertEqual(code, 0, out)
        inst.assert_called_once_with(["godot", "vim"],
                                     projects={"godot": [os.path.abspath("game")]})
        with mock.patch.object(editor_plugins, "remove", return_value=[]) as rem:
            self.run_main("editor-plugins", "remove", "--editor", "obsidian", "--project", "/v")
        rem.assert_called_once_with(["obsidian"], projects={"obsidian": [os.path.abspath("/v")]})

    def test_project_needs_a_per_project_editor(self):
        with mock.patch.object(editor_plugins, "install") as inst:
            code, _out, err = self.run_main("editor-plugins", "install", "--editor", "vim",
                                            "--project", "x")
        self.assertEqual(code, 2)
        self.assertIn("--project needs", err)
        inst.assert_not_called()

    def test_every_editor_is_a_choice_and_every_state_has_a_text(self):
        for editor in editor_plugins.EDITORS:
            with mock.patch.object(editor_plugins, "status", return_value=[]):
                code, _out, err = self.run_main("editor-plugins", "status", "--editor", editor)
            self.assertEqual(code, 0, err)
        states = [v for k, v in vars(editor_plugins).items() if k.startswith("STATE_")]
        for state in states:
            self.assertIn(state, polyctl._EDITOR_STATE_TEXT)

    def test_the_jupyterlab_command_is_printed(self):
        st = [editor_plugins.EditorStatus("jupyterlab", "command", None,
                                          'python -m pip install "/x/jupyterlab-extension"')]
        with mock.patch.object(editor_plugins, "status", return_value=st):
            _code, out, _ = self.run_main("editor-plugins", "status")
        self.assertIn('python -m pip install "/x/jupyterlab-extension"', out)


if __name__ == "__main__":
    unittest.main()
