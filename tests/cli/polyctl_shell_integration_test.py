"""`polyctl shell-integration` edits the user's shell startup files and must
never try to reach the host (it needs neither the daemon nor the keyboard)."""
import io
import os
import shutil
import tempfile
import unittest
import unittest.mock as mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from polyhost.cli import polyctl
from polyhost.services import shell_title


class PolyctlShellIntegrationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)

    def run_main(self, *argv, env=None):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(polyctl, "connect",
                               side_effect=AssertionError("must not connect")), \
                mock.patch.dict(os.environ, env or {}), \
                redirect_stdout(out), redirect_stderr(err):
            code = polyctl.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_status_lists_each_shell_without_a_host(self):
        statuses = [shell_title.ShellStatus("bash", "installed", Path("/h/.bashrc"), ""),
                    shell_title.ShellStatus("pwsh", "unknown", None, "no answer within 20 s")]
        with mock.patch.object(shell_title, "status", return_value=statuses) as status:
            code, out, _ = self.run_main("shell-integration", "status")
        self.assertEqual(code, 0)
        status.assert_called_once_with(None)
        self.assertIn("bash", out)
        self.assertIn("/h/.bashrc", out)
        self.assertIn("no answer within 20 s", out)

    def test_shell_filter_is_passed_through(self):
        with mock.patch.object(shell_title, "remove", return_value=[]) as remove:
            code, out, _ = self.run_main("shell-integration", "remove",
                                         "--shell", "zsh", "--shell", "pwsh")
        self.assertEqual(code, 0)
        remove.assert_called_once_with(["zsh", "pwsh"])
        self.assertIn("nothing to do", out)

    def test_failure_sets_the_exit_code(self):
        res = [shell_title.Result("pwsh", False, False, "pwsh did not report its profile path: x", None)]
        with mock.patch.object(shell_title, "install", return_value=res):
            code, out, _ = self.run_main("shell-integration", "install", "--shell", "pwsh")
        self.assertEqual(code, 1)
        self.assertIn("pwsh: pwsh did not report", out)

    def test_codex_choice_is_passed_through(self):
        for argv, want in ((["--codex"], True), (["--no-codex"], False), ([], None)):
            with mock.patch.object(shell_title, "install", return_value=[]) as install:
                self.run_main("shell-integration", "install", "--shell", "bash", *argv)
            install.assert_called_once_with(["bash"], codex=want)

    def test_unknown_shell_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.run_main("shell-integration", "install", "--shell", "tcsh")

    @unittest.skipUnless(shutil.which("bash") and os.name == "posix", "needs bash on POSIX")
    def test_real_install_and_remove_in_a_temp_home(self):
        """The real entry point, end to end, in a temporary HOME."""
        env = {"HOME": str(self.home), "SHELL": "/bin/bash"}
        rc = self.home / ".bashrc"
        rc.write_bytes(b"PS1='$ '\n")
        code, out, _ = self.run_main("shell-integration", "install", "--shell", "bash", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn("Added the line", out)
        self.assertIn("backup:", out)
        self.assertIn(shell_title.BEGIN_MARKER.encode(), rc.read_bytes())
        code, out, _ = self.run_main("shell-integration", "status", "--shell", "bash", env=env)
        self.assertIn("installed", out)
        self.assertNotIn("not installed", out)
        code, out, _ = self.run_main("shell-integration", "remove", "--shell", "bash", env=env)
        self.assertEqual(code, 0)
        self.assertEqual(rc.read_bytes(), b"PS1='$ '\n")


if __name__ == "__main__":
    unittest.main()
