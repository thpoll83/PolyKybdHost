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


if __name__ == "__main__":
    unittest.main()
