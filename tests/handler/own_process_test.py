"""Which focused windows are PolyHost's own.

PolyHost runs as `python -m polyhost`, so the window tracker names its windows
after the interpreter and the ESC mark used to be the Python logo. These pin
the command-line test that tells the two apart.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock

from polyhost.handler import own_process as op


class ArgvTest(unittest.TestCase):

    def test_every_launcher_we_ship_is_recognised(self):
        for argv in (
            ["python", "-m", "polyhost"],
            ["pythonw.exe", "-m", "polyhost", "--headless"],
            ["/usr/bin/python3", "-X", "utf8", "-m", "polyhost", "--dev", "2"],
            ["python3", "-u", "-mpolyhost"],
            ["python3", "-m", "polyhost.gui.fontpack_inspector_dialog"],
            ["python3", r"C:\src\PolyKybdHost\polyhost\__main__.py"],
        ):
            self.assertTrue(op.argv_is_polyhost(argv), argv)

    def test_other_python_programs_are_not(self):
        for argv in (
            ["python3"],
            ["python3", "-m", "http.server"],
            ["python3", "-m", "polyhostile"],
            ["python3", "-m", "debugpy", "--listen", "5678"],
            ["python3", "tool.py", "-m", "polyhost"],
            ["python3", "-c", "import polyhost"],
            ["python3", "-W", "-m", "x.py"],
            ["python3", "/other/__main__.py"],
            [],
        ):
            self.assertFalse(op.argv_is_polyhost(argv), argv)


class RuntimeNameTest(unittest.TestCase):

    def test_interpreter_names_on_each_platform(self):
        for name in ("python", "python3", "python3.11", "pythonw",
                     "Python", "pythonw.exe"):
            self.assertTrue(op.is_python_runtime(name), name)

    def test_other_apps(self):
        for name in ("", None, "code", "pycharm", "ipython", "python-foo"):
            self.assertFalse(op.is_python_runtime(name), name)


class ProcArgs2Test(unittest.TestCase):
    """macOS `KERN_PROCARGS2`: argc, exec path, NUL padding, argv, env."""

    @staticmethod
    def _buf(argv, exe=b"/usr/bin/python3"):
        body = exe + b"\0\0\0\0" + b"".join(a + b"\0" for a in argv)
        return len(argv).to_bytes(4, sys.byteorder) + body + b"HOME=/x\0"

    def test_argv_is_read_past_the_padding_and_stops_before_the_env(self):
        raw = self._buf([b"python3", b"-m", b"polyhost"])
        self.assertEqual(op.parse_procargs2(raw), ["python3", "-m", "polyhost"])

    def test_a_truncated_buffer_is_none(self):
        self.assertIsNone(op.parse_procargs2(b"\x01"))
        raw = self._buf([b"python3", b"-m", b"polyhost"])
        self.assertIsNone(op.parse_procargs2(raw[:-20]))


class OwnAppNameTest(unittest.TestCase):

    def test_this_process_is_ours(self):
        self.assertEqual(op.own_app_name("python3", os.getpid()), op.POLYHOST_APP)

    def test_a_non_python_app_is_never_inspected(self):
        with mock.patch.object(op, "process_argv") as argv:
            self.assertEqual(op.own_app_name("firefox", 1234), "firefox")
        argv.assert_not_called()

    def test_another_python_process_keeps_its_name(self):
        with mock.patch.object(op, "process_argv",
                               return_value=["python3", "script.py"]):
            self.assertEqual(op.own_app_name("python3", 1234), "python3")

    def test_a_polyhost_command_line_is_ours(self):
        with mock.patch.object(op, "process_argv",
                               return_value=["pythonw.exe", "-m", "polyhost"]):
            self.assertEqual(op.own_app_name("pythonw", 1234), op.POLYHOST_APP)

    def test_no_pid_or_an_unreadable_one_keeps_the_name(self):
        self.assertEqual(op.own_app_name("python3", None), "python3")
        with mock.patch.object(op, "process_argv", return_value=None):
            self.assertEqual(op.own_app_name("python3", 1234), "python3")

    def test_window_pid_survives_a_backend_without_getPID(self):
        self.assertIsNone(op.window_pid(object()))
        self.assertIsNone(op.window_pid(None))
        win = mock.Mock()
        win.getPID.return_value = 42
        self.assertEqual(op.window_pid(win), 42)


@unittest.skipUnless(sys.platform.startswith("linux"), "reads /proc")
class RealProcessTest(unittest.TestCase):
    """The real reader against real child processes, not a mocked argv."""

    def _child(self, *args, cwd=None):
        proc = subprocess.Popen(
            [sys.executable, *args], cwd=cwd,
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.stdin.close)
        return proc

    def test_a_child_started_as_polyhost_is_ours(self):
        # A stand-in `polyhost` package that just blocks on stdin: `-m` puts
        # the cwd first on sys.path, so it shadows the real one, and the child
        # carries exactly the command line autostart uses.
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        os.mkdir(os.path.join(tmp, "polyhost"))
        for name, body in (("__init__.py", ""),
                           ("__main__.py", "import sys\nsys.stdin.read()\n")):
            with open(os.path.join(tmp, "polyhost", name), "w",
                      encoding="utf-8") as fh:
                fh.write(body)
        # Popen returns after the exec, so the command line is already set.
        proc = self._child("-m", "polyhost", "--headless", cwd=tmp)
        self.assertTrue(op.is_polyhost_process(proc.pid))
        self.assertEqual(op.own_app_name("python3", proc.pid), op.POLYHOST_APP)

    def test_another_python_child_is_not_ours(self):
        proc = self._child("-c", "import sys; sys.stdin.read()")
        self.assertEqual(op.process_argv(proc.pid)[1], "-c")
        self.assertFalse(op.is_polyhost_process(proc.pid))

    def test_a_vanished_pid_is_not_ours(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        self.assertFalse(op.is_polyhost_process(proc.pid))


if __name__ == "__main__":
    unittest.main()
