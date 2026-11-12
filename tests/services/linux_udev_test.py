import os
import shlex
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.services import linux_udev


SHIPPED = (
    "# PolyKybd raw-HID access\n"
    'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2021", ATTRS{idProduct}=="2007", MODE="0666"\n'
    "\n"
    "# Bulk pipe\n"
    'SUBSYSTEM=="tty", ATTRS{idVendor}=="2021", ATTRS{idProduct}=="2007", MODE="0666", ENV{ID_MM_DEVICE_IGNORE}="1"\n'
)


class ImportsWithoutGetuidTest(unittest.TestCase):
    def test_module_imports_where_os_has_no_getuid(self):
        """host.py imports the module on every platform; Windows has no
        os.getuid, and a default argument evaluated at import broke the
        Windows tray (#411)."""
        code = ("import os, sys; os.__dict__.pop('getuid', None); "
                "import polyhost.services.linux_udev as m; "
                "print(m.is_linux.__name__)")
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              cwd=str(Path(__file__).resolve().parents[2]), timeout=60,
                              env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "is_linux")


class RuleLinesTest(unittest.TestCase):
    def test_drops_comments_and_blank_lines(self):
        self.assertEqual(linux_udev.rule_lines(SHIPPED), [
            'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2021", ATTRS{idProduct}=="2007", MODE="0666"',
            'SUBSYSTEM=="tty", ATTRS{idVendor}=="2021", ATTRS{idProduct}=="2007", MODE="0666", ENV{ID_MM_DEVICE_IGNORE}="1"',
        ])

    def test_shipped_file_has_hidraw_and_tty_lines(self):
        """The fast link needs the tty lines; a shipped file without them would
        make the tray's offer install a rule that does not help."""
        lines = linux_udev.rule_lines(linux_udev.RULES_SRC.read_text(encoding="utf-8"))
        self.assertTrue(any(line.startswith('SUBSYSTEM=="hidraw"') for line in lines))
        self.assertTrue(any(line.startswith('SUBSYSTEM=="tty"') for line in lines))


class RuleStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name, "src.rules")
        self.dst = Path(self.tmp.name, "dst.rules")
        self.src.write_text(SHIPPED, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_when_nothing_installed(self):
        self.assertEqual(linux_udev.rule_status(self.src, self.dst), linux_udev.STATUS_MISSING)

    def test_ok_when_installed_copy_matches(self):
        self.dst.write_text(SHIPPED, encoding="utf-8")
        self.assertEqual(linux_udev.rule_status(self.src, self.dst), linux_udev.STATUS_OK)

    def test_ok_ignores_comments_order_and_extra_lines(self):
        lines = linux_udev.rule_lines(SHIPPED)
        self.dst.write_text("# installed by hand\n" + lines[1] + "\n" + lines[0] + "\n"
                            'SUBSYSTEM=="usb", MODE="0666"\n', encoding="utf-8")
        self.assertEqual(linux_udev.rule_status(self.src, self.dst), linux_udev.STATUS_OK)

    def test_stale_when_the_tty_lines_are_missing(self):
        """An install from before the fast link has only the hidraw lines."""
        self.dst.write_text(linux_udev.rule_lines(SHIPPED)[0] + "\n", encoding="utf-8")
        self.assertEqual(linux_udev.rule_status(self.src, self.dst), linux_udev.STATUS_STALE)

    def test_stale_when_installed_file_is_empty(self):
        self.dst.write_text("", encoding="utf-8")
        self.assertEqual(linux_udev.rule_status(self.src, self.dst), linux_udev.STATUS_STALE)


class CheckRuleFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name, "src.rules")

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, text, mode=0o644):
        self.src.write_text(text, encoding="utf-8")
        self.src.chmod(mode)

    def test_shipped_file_passes(self):
        self.assertEqual(linux_udev.check_rule_file(linux_udev.RULES_SRC), "")

    def test_sample_passes(self):
        self._write(SHIPPED)
        self.assertEqual(linux_udev.check_rule_file(self.src), "")

    def test_run_line_is_refused(self):
        """A RUN entry would make root execute a program at every plug."""
        self._write(SHIPPED + 'SUBSYSTEM=="usb", RUN+="/tmp/evil.sh"\n')
        self.assertIn("unexpected rule entry", linux_udev.check_rule_file(self.src))

    def test_owner_and_program_are_refused(self):
        for entry in ('OWNER="root"', 'PROGRAM="/bin/sh"', 'IMPORT{program}="x"', 'GROUP="disk"'):
            self._write('SUBSYSTEM=="hidraw", ' + entry + "\n")
            self.assertIn("unexpected rule entry", linux_udev.check_rule_file(self.src), entry)

    def test_malformed_line_is_refused(self):
        self._write('SUBSYSTEM=="hidraw" MODE="0666"\n')
        self.assertIn("unexpected rule entry", linux_udev.check_rule_file(self.src))

    def test_world_writable_file_is_refused(self):
        self._write(SHIPPED, mode=0o666)
        self.assertIn("writable by everyone", linux_udev.check_rule_file(self.src))

    def test_group_writable_file_passes(self):
        """A checkout under a user-private group (umask 002) is 0664."""
        self._write(SHIPPED, mode=0o664)
        self.assertEqual(linux_udev.check_rule_file(self.src), "")

    def test_file_owned_by_another_user_is_refused(self):
        self._write(SHIPPED)
        real = linux_udev.os.stat(self.src)
        other = mock.Mock(st_mode=real.st_mode, st_uid=real.st_uid + 1)
        self.assertIn("owned by another user",
                      linux_udev.check_rule_file(self.src, _stat=lambda p: other))

    def test_missing_file(self):
        self.assertIn("cannot read", linux_udev.check_rule_file(self.src))


class InstallCommandTest(unittest.TestCase):
    def test_paths_are_arguments_not_shell_text(self):
        argv = linux_udev.install_command("/a b/src.rules", "/etc/udev/rules.d/x.rules", "/usr/bin/pkexec")
        self.assertEqual(argv[:3], ["/usr/bin/pkexec", "sh", "-c"])
        self.assertNotIn("/a b/src.rules", argv[3])
        self.assertEqual(argv[-2:], ["/a b/src.rules", "/etc/udev/rules.d/x.rules"])
        self.assertIn('install -m 0644 -- "$1" "$2"', argv[3])
        self.assertIn("udevadm control --reload-rules", argv[3])
        self.assertIn("udevadm trigger", argv[3])


class ManualCommandsTest(unittest.TestCase):
    def test_paths_are_shell_quoted(self):
        """An apostrophe or a space in the checkout path must not break the
        command the failure dialog offers to copy."""
        cmds = linux_udev.manual_commands("/home/o'brien/Poly Host/99-hid.rules",
                                          "/etc/udev/rules.d/99-hid.rules")
        first, second = cmds.split("\n")
        self.assertEqual(shlex.split(first), [
            "sudo", "install", "-m", "0644",
            "/home/o'brien/Poly Host/99-hid.rules", "/etc/udev/rules.d/99-hid.rules"])
        self.assertEqual(second, "sudo udevadm control --reload-rules && sudo udevadm trigger")


def _proc(code, stderr="", stdout=""):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


class InstallRulesTest(unittest.TestCase):
    def setUp(self):
        for name, value in (("is_linux", True), ("check_rule_file", "")):
            patcher = mock.patch.object(linux_udev, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_not_linux(self):
        with mock.patch.object(linux_udev, "is_linux", return_value=False):
            ok, err = linux_udev.install_rules(run=mock.Mock(), which=lambda name: "/usr/bin/pkexec")
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_NOT_LINUX)

    def test_no_pkexec(self):
        run = mock.Mock()
        ok, err = linux_udev.install_rules(run=run, which=lambda name: None)
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_NO_PKEXEC)
        run.assert_not_called()

    def test_unsafe_file_is_refused_before_pkexec(self):
        run = mock.Mock()
        with mock.patch.object(linux_udev, "check_rule_file", return_value="unexpected rule entry: RUN+=\"x\""):
            ok, err = linux_udev.install_rules("/s", "/d", run=run, which=lambda name: "/usr/bin/pkexec")
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_UNSAFE_FILE.format(reason='unexpected rule entry: RUN+="x"'))
        run.assert_not_called()

    def test_success(self):
        run = mock.Mock(return_value=_proc(0))
        ok, err = linux_udev.install_rules("/s", "/d", run=run, which=lambda name: "/usr/bin/pkexec")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        argv = run.call_args.args[0]
        self.assertEqual(argv[0], "/usr/bin/pkexec")
        self.assertEqual(argv[-2:], ["/s", "/d"])
        self.assertEqual(run.call_args.kwargs["timeout"], linux_udev.PROMPT_TIMEOUT_S)

    def test_dismissed_prompt(self):
        run = mock.Mock(return_value=_proc(linux_udev.PKEXEC_DISMISSED))
        ok, err = linux_udev.install_rules(run=run, which=lambda name: "/usr/bin/pkexec")
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_DISMISSED)

    def test_not_authorised(self):
        run = mock.Mock(return_value=_proc(linux_udev.PKEXEC_NOT_AUTHORISED))
        ok, err = linux_udev.install_rules(run=run, which=lambda name: "/usr/bin/pkexec")
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_NOT_AUTHORISED)

    def test_command_failure_carries_code_and_output(self):
        run = mock.Mock(return_value=_proc(1, stderr="install: cannot create regular file\n"))
        ok, err = linux_udev.install_rules(run=run, which=lambda name: "/usr/bin/pkexec")
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_FAILED.format(
            code=1, output="install: cannot create regular file"))

    def test_timeout(self):
        run = mock.Mock(side_effect=subprocess.TimeoutExpired(cmd="pkexec", timeout=1))
        ok, err = linux_udev.install_rules(run=run, which=lambda name: "/usr/bin/pkexec")
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_TIMEOUT)

    def test_not_started(self):
        run = mock.Mock(side_effect=OSError("boom"))
        ok, err = linux_udev.install_rules(run=run, which=lambda name: "/usr/bin/pkexec")
        self.assertFalse(ok)
        self.assertEqual(err, linux_udev.MSG_NOT_STARTED.format(error="boom"))


if __name__ == "__main__":
    unittest.main()
