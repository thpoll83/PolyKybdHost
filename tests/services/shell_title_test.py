"""Shell title integration (services/shell_title.py): the one marked line in
the user's shell startup files, and the shipped scripts it loads.

The startup files are the user's, so most tests compare BYTES: everything
outside the block must come back unchanged, and a remove after an install
must give back the original file."""
import codecs
import os
import pty
import re
import select
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from polyhost.services import shell_title as st


def _which(present):
    """A shutil.which stand-in that finds only ``present`` (name -> path)."""
    return lambda name: present.get(name)


class _Home(unittest.TestCase):
    """A temporary HOME with no shell found unless a test adds one."""

    def setUp(self):
        st.clear_probe_cache()
        self.addCleanup(st.clear_probe_cache)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.env = {"SHELL": "/bin/bash"}
        self.present = {"bash": "/usr/bin/bash"}

    def call(self, fn, shells=None, **kw):
        kw.setdefault("home", self.home)
        kw.setdefault("env", self.env)
        kw.setdefault("which", _which(self.present))
        kw.setdefault("system", "Linux")
        return fn(shells, **kw)

    def install(self, shells=None, **kw):
        return self.call(st.install, shells, **kw)

    def remove(self, shells=None, **kw):
        return self.call(st.remove, shells, **kw)

    def status(self, shells=None, **kw):
        return {s.shell: s for s in self.call(st.status, shells, **kw)}

    def backups(self, name):
        return sorted(p for p in self.home.iterdir() if p.name.startswith(name + ".polykybd-"))


class ShippedScriptsTest(unittest.TestCase):
    def test_every_script_exists_and_is_ascii(self):
        """Windows PowerShell 5.1 reads a BOM-less script in the ANSI code
        page, so the .ps1 must be ASCII; the others are kept so too."""
        for name in set(st.SCRIPT_NAMES.values()):
            data = (st.SCRIPT_DIR / name).read_bytes()
            self.assertTrue(data, name)
            data.decode("ascii")

    def test_scripts_are_packaged(self):
        root = Path(__file__).resolve().parents[2]
        setup = (root / "setup.py").read_text(encoding="utf-8")
        manifest = (root / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn('"res/shell/polykybd-title.*"', setup)
        self.assertIn("recursive-include polyhost/res/shell polykybd-title.*", manifest)

    def test_each_script_guards_a_second_source(self):
        for name, guard in (("polykybd-title.bash", "__poly_title_loaded"),
                            ("polykybd-title.zsh", "__poly_title_loaded"),
                            ("polykybd-title.ps1", "PolyKybdTitleLoaded")):
            self.assertIn(guard, (st.SCRIPT_DIR / name).read_text(encoding="ascii"))


class SourceLineTest(unittest.TestCase):
    def test_posix_line_round_trips_a_quote_and_a_space(self):
        path = "/home/o'neil/my apps/polykybd-title.bash"
        for shell in (st.BASH, st.ZSH):
            line = st.source_line(shell, path)
            self.assertTrue(line.startswith("if [ -r "))
            self.assertEqual(st._path_in_line(shell, line), path)

    def test_powershell_line_round_trips_a_quote(self):
        path = r"C:\Users\O'Neil\PolyKybdHost\polyhost\res\shell\polykybd-title.ps1"
        line = st.source_line(st.PWSH, path)
        self.assertIn("C:\\Users\\O''Neil", line)
        self.assertEqual(st._path_in_line(st.PWSH, line), path)

    def test_windows_bash_gets_a_forward_slash_path(self):
        self.assertNotIn("\\", st.script_path(st.BASH, system="Windows"))
        self.assertTrue(st.script_path(st.BASH, system="Windows").endswith("polykybd-title.bash"))


class InstallRemoveTest(_Home):
    def test_fresh_file_is_created_for_the_login_shell(self):
        [r] = self.install()
        self.assertTrue(r.ok and r.changed, r)
        self.assertIsNone(r.backup)
        text = (self.home / ".bashrc").read_text(encoding="utf-8")
        self.assertEqual(text, st.BEGIN_MARKER + "\n"
                         + st.source_line(st.BASH, st.script_path(st.BASH, "Linux")) + "\n"
                         + st.END_MARKER + "\n")
        self.assertEqual(self.status()[st.BASH].state, st.STATE_INSTALLED)

    def test_content_outside_the_block_keeps_its_bytes(self):
        # Latin-1 bytes that are not UTF-8, and no newline at the end.
        original = b"export A=1\n# caf\xe9\nalias ll='ls -l'"
        rc = self.home / ".bashrc"
        rc.write_bytes(original)
        [r] = self.install()
        self.assertTrue(r.changed)
        data = rc.read_bytes()
        self.assertTrue(data.startswith(original + b"\n" + st.BEGIN_MARKER.encode()), data)
        self.assertTrue(data.endswith(st.END_MARKER.encode() + b"\n"))
        self.assertEqual(r.backup.read_bytes(), original)

    def test_second_install_changes_nothing(self):
        rc = self.home / ".bashrc"
        rc.write_bytes(b"PS1='$ '\n")
        self.install()
        after_first = rc.read_bytes()
        backups = self.backups(".bashrc")
        [r] = self.install()
        self.assertTrue(r.ok)
        self.assertFalse(r.changed)
        self.assertIsNone(r.backup)
        self.assertEqual(rc.read_bytes(), after_first)
        self.assertEqual(self.backups(".bashrc"), backups)
        self.assertEqual(after_first.count(st.BEGIN_MARKER.encode()), 1)

    def test_remove_restores_the_original_bytes(self):
        original = b"export A=1\n\n# end\n"
        rc = self.home / ".bashrc"
        rc.write_bytes(original)
        self.install()
        [r] = self.remove()
        self.assertTrue(r.ok and r.changed, r)
        self.assertEqual(rc.read_bytes(), original)
        self.assertEqual(r.backup.read_bytes().count(st.BEGIN_MARKER.encode()), 1)
        [again] = self.remove([st.BASH])
        self.assertFalse(again.changed)
        self.assertEqual(rc.read_bytes(), original)

    def test_remove_keeps_lines_after_the_block(self):
        rc = self.home / ".bashrc"
        rc.write_bytes(b"a\n")
        self.install()
        rc.write_bytes(rc.read_bytes() + b"b\n")
        self.remove()
        self.assertEqual(rc.read_bytes(), b"a\nb\n")

    def test_crlf_file_stays_crlf(self):
        original = b"export A=1\r\nalias x=y\r\n"
        rc = self.home / ".bashrc"
        rc.write_bytes(original)
        self.install()
        data = rc.read_bytes()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertEqual(data.count(b"\r\n"), 5)
        self.remove()
        self.assertEqual(rc.read_bytes(), original)

    def test_stale_block_is_reported_and_replaced(self):
        old = "/old/checkout/polyhost/res/shell/polykybd-title.bash"
        rc = self.home / ".bashrc"
        before = b"x=1\n"
        rc.write_bytes(before + (st.BEGIN_MARKER + "\n" + st.source_line(st.BASH, old)
                                 + "\n" + st.END_MARKER + "\n").encode() + b"y=2\n")
        s = self.status()[st.BASH]
        self.assertEqual(s.state, st.STATE_STALE)
        self.assertEqual(s.detail, old)
        [r] = self.install()
        self.assertTrue(r.changed)
        self.assertEqual(r.message, st.MSG_UPDATED.format(path=rc))
        self.assertEqual(self.status()[st.BASH].state, st.STATE_INSTALLED)
        data = rc.read_bytes()
        self.assertNotIn(old.encode(), data)
        self.assertTrue(data.startswith(before) and data.endswith(b"y=2\n"))

    def test_two_blocks_become_one(self):
        rc = self.home / ".bashrc"
        block = (st.BEGIN_MARKER + "\n# hand copy\n" + st.END_MARKER + "\n").encode()
        rc.write_bytes(b"a\n" + block + b"b\n" + block)
        self.install()
        self.assertEqual(rc.read_bytes().count(st.BEGIN_MARKER.encode()), 1)
        self.remove()
        self.assertEqual(rc.read_bytes(), b"a\nb\n")

    def test_start_marker_without_end_is_refused(self):
        rc = self.home / ".bashrc"
        original = (st.BEGIN_MARKER + "\necho hi\n").encode()
        rc.write_bytes(original)
        [r] = self.install()
        self.assertFalse(r.ok)
        self.assertEqual(r.message, st.MSG_NO_END_MARKER.format(path=rc))
        self.assertEqual(rc.read_bytes(), original)
        self.assertEqual(self.backups(".bashrc"), [])

    def test_symlinked_rc_is_written_through_the_link(self):
        target = self.home / "dotfiles" / "bashrc"
        target.parent.mkdir()
        target.write_bytes(b"a\n")
        (self.home / ".bashrc").symlink_to(target)
        self.install()
        self.assertTrue((self.home / ".bashrc").is_symlink())
        self.assertIn(st.BEGIN_MARKER.encode(), target.read_bytes())

    def test_missing_shell_is_skipped(self):
        """zsh is not installed and has no ~/.zshrc: "all shells" leaves it
        out, and naming it reports that it is missing."""
        self.assertEqual(self.status()[st.ZSH].state, st.STATE_NOT_PRESENT)
        self.assertEqual([r.shell for r in self.install()], [st.BASH])
        self.assertFalse((self.home / ".zshrc").exists())
        [r] = self.install([st.ZSH])
        self.assertFalse(r.ok)
        self.assertEqual(r.message, st.MSG_NOT_PRESENT.format(shell=st.ZSH))
        self.assertFalse((self.home / ".zshrc").exists())

    def test_unused_zsh_gets_no_new_zshrc(self):
        """zsh installed, never used, login shell bash: no ~/.zshrc appears
        (it would also skip zsh's first-start setup)."""
        self.present["zsh"] = "/usr/bin/zsh"
        self.assertEqual([r.shell for r in self.install()], [st.BASH])
        self.assertFalse((self.home / ".zshrc").exists())
        self.env["SHELL"] = "/usr/bin/zsh"
        self.assertIn(st.ZSH, [r.shell for r in self.install()])
        self.assertTrue((self.home / ".zshrc").exists())

    def test_zdotdir_is_used_for_zsh(self):
        zdot = self.home / "zdot"
        zdot.mkdir()
        (zdot / ".zshrc").write_bytes(b"PS1='%% '\n")
        self.present["zsh"] = "/usr/bin/zsh"
        self.env["ZDOTDIR"] = str(zdot)
        self.install([st.ZSH])
        self.assertIn(st.BEGIN_MARKER.encode(), (zdot / ".zshrc").read_bytes())

    def test_wsl_launcher_is_not_a_bash(self):
        self.present["bash"] = r"C:\Windows\System32\bash.exe"
        self.assertEqual(self.status(system="Windows")[st.BASH].state, st.STATE_NOT_PRESENT)

    def test_backup_names_do_not_collide(self):
        rc = self.home / ".bashrc"
        rc.write_bytes(b"a\n")
        first = st._backup(rc, now=0)
        second = st._backup(rc, now=0)
        self.assertNotEqual(first, second)
        self.assertRegex(first.name, r"^\.bashrc\.polykybd-\d{8}-\d{6}\.bak$")
        self.assertRegex(second.name, r"^\.bashrc\.polykybd-\d{8}-\d{6}-1\.bak$")


class _FakeProc:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


class PowerShellTest(_Home):
    def setUp(self):
        super().setUp()
        self.present = {"pwsh": "/opt/pwsh", "powershell": "/opt/powershell"}
        self.profile = self.home / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        self.calls = []

    def answer(self, policy="RemoteSigned", profile=None):
        profile = profile or self.profile

        def run(argv, **kw):
            self.calls.append(argv)
            self.assertNotIn("shell", kw)
            self.assertIn("-NoProfile", argv)
            return _FakeProc(f"\ufeff{profile}\r\n{policy}\r\n".encode("utf-8"))
        return run

    def test_profile_path_and_new_file(self):
        """A missing profile and its folder are created; the Windows
        PowerShell 5.1 one as UTF-8 with a BOM."""
        res = self.install([st.POWERSHELL], run=self.answer())
        self.assertTrue(res[0].changed, res)
        data = self.profile.read_bytes()
        self.assertTrue(data.startswith(codecs.BOM_UTF8))
        self.assertIn(b"Test-Path -LiteralPath", data)
        self.assertEqual(self.status([st.POWERSHELL], run=self.answer())[st.POWERSHELL].state,
                         st.STATE_INSTALLED)

    def test_new_pwsh_profile_has_no_bom(self):
        self.install([st.PWSH], run=self.answer())
        self.assertTrue(self.profile.read_bytes().startswith(st.BEGIN_MARKER.encode()))

    def test_probe_is_cached(self):
        run = self.answer()
        self.status([st.PWSH], run=run)
        self.status([st.PWSH], run=run)
        self.assertEqual(len(self.calls), 1)

    def test_utf16_profile_keeps_its_encoding(self):
        self.profile.parent.mkdir(parents=True)
        original = codecs.BOM_UTF16_LE + "Set-Alias g git\r\n# Ünïcode\r\n".encode("utf-16-le")
        self.profile.write_bytes(original)
        self.install([st.PWSH], run=self.answer())
        data = self.profile.read_bytes()
        self.assertTrue(data.startswith(codecs.BOM_UTF16_LE))
        self.assertIn(st.BEGIN_MARKER, data[2:].decode("utf-16-le"))
        self.remove([st.PWSH], run=self.answer())
        self.assertEqual(self.profile.read_bytes(), original)

    def test_probe_timeout_is_reported_not_raised(self):
        def run(argv, **kw):
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        s = self.status([st.PWSH], run=run)[st.PWSH]
        self.assertEqual(s.state, st.STATE_UNKNOWN)
        self.assertIn("no answer", s.detail)
        [r] = self.install([st.PWSH], run=run)
        self.assertFalse(r.ok)
        self.assertTrue(r.message.startswith("pwsh did not report its profile path"))

    def test_probe_failure_is_not_cached(self):
        self.status([st.PWSH], run=lambda argv, **kw: _FakeProc(b"", b"boom", 1))
        s = self.status([st.PWSH], run=self.answer())[st.PWSH]
        self.assertEqual(s.state, st.STATE_NOT_INSTALLED)

    def test_probe_start_failure_and_garbage(self):
        def missing(argv, **kw):
            raise FileNotFoundError("no such file")
        self.assertEqual(self.status([st.PWSH], run=missing)[st.PWSH].state, st.STATE_UNKNOWN)
        st.clear_probe_cache()
        s = self.status([st.PWSH], run=lambda argv, **kw: _FakeProc(b"not a path\n"))[st.PWSH]
        self.assertEqual(s.state, st.STATE_UNKNOWN)

    def test_restricted_policy_blocks_install_but_not_remove(self):
        run = self.answer(policy="Restricted")
        s = self.status([st.POWERSHELL], run=run, system="Windows")[st.POWERSHELL]
        self.assertEqual((s.state, s.detail), (st.STATE_BLOCKED, "Restricted"))
        [r] = self.install([st.POWERSHELL], run=run, system="Windows")
        self.assertFalse(r.ok)
        self.assertEqual(r.message, st.MSG_POLICY.format(policy="Restricted"))
        self.assertFalse(self.profile.exists())
        # A block written while the policy allowed it can still be removed.
        st.clear_probe_cache()
        self.install([st.POWERSHELL], run=self.answer(), system="Windows")
        st.clear_probe_cache()
        [r] = self.remove([st.POWERSHELL], run=run, system="Windows")
        self.assertTrue(r.changed, r)

    def test_not_present_powershell_is_not_probed(self):
        self.present = {}
        s = self.status([st.PWSH, st.POWERSHELL], run=self.answer())
        self.assertEqual({k: v.state for k, v in s.items()},
                         {st.PWSH: st.STATE_NOT_PRESENT, st.POWERSHELL: st.STATE_NOT_PRESENT})
        self.assertEqual(self.calls, [])


class InfoRowsTest(_Home):
    def test_no_setup_rows_per_platform(self):
        self.present["fish"] = "/usr/bin/fish"
        linux = self.status()
        self.assertEqual(linux[st.FISH].state, st.STATE_NO_SETUP)
        self.assertNotIn(st.CMD, linux)
        self.assertIn(st.CMD, self.status(system="Windows", run=lambda a, **k: _FakeProc(b"", b"", 1)))
        self.assertIn(st.MACOS_TERMINAL, self.status(system="Darwin"))


# --- the installed line, run for real ----------------------------------------

def _run_in_pty(argv, env, inputs, settle=1.0, step=0.6):
    """Run an interactive shell on a pty, type ``inputs``, return all output."""
    master, slave = pty.openpty()
    proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env,
                            close_fds=True, start_new_session=True)
    os.close(slave)
    out = bytearray()

    def pump(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            ready, _w, _x = select.select([master], [], [], 0.05)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    return
                if not chunk:
                    return
                out.extend(chunk)
    try:
        pump(settle)
        for line in inputs:
            os.write(master, line)
            pump(step)
        proc.wait(timeout=10)
        pump(0.2)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        os.close(master)
    return bytes(out)


@unittest.skipUnless(shutil.which("bash"), "bash is not installed")
class BashOnAPtyTest(_Home):
    """The installed line, sourced by a real interactive bash. Ubuntu's prompt
    sets its own title; the command's title must appear when it runs, and the
    prompt's must come back."""

    def env_for(self):
        return {"HOME": str(self.home), "TERM": "xterm", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}

    def test_title_escape_after_install(self):
        rc = self.home / ".bashrc"
        # A trailing ";" in PROMPT_COMMAND and a DEBUG trap set before ours.
        rc.write_text("PS1='\\[\\e]0;base-title\\a\\]$ '\n"
                      "PROMPT_COMMAND='history -a;'\n"
                      "trap 'printf \"%s\\n\" \"$BASH_COMMAND\" >> \"$HOME/prev.log\"' DEBUG\n",
                      encoding="utf-8")
        [r] = self.install([st.BASH])
        self.assertTrue(r.changed, r)
        # Sourcing it a second time must change nothing.
        with open(rc, "a", encoding="utf-8") as fh:
            fh.write(f". {st.script_path(st.BASH)}\n")
        out = _run_in_pty(["bash", "-i"], self.env_for(),
                          [b"echo hi\n", b"exit\n"])
        self.assertIn(b"\x1b]2;echo hi\x07", out, out)
        self.assertGreater(out.count(b"\x1b]0;base-title\x07"), 1, out)
        self.assertEqual(out.count(b"\x1b]2;echo hi\x07"), 1, out)
        self.assertNotIn(b"syntax error", out)
        prev = (self.home / "prev.log").read_text(encoding="utf-8").splitlines()
        self.assertIn("echo hi", prev, "the earlier DEBUG trap no longer runs")

    def test_prompt_command_added_later_does_not_take_the_title(self):
        """A tool initialised after the line (direnv, a prompt theme) appends to
        PROMPT_COMMAND; on bash 4.4+ PS0 arms the trap, after the prompt."""
        ver = subprocess.run(["bash", "-c", "echo ${BASH_VERSINFO[0]} ${BASH_VERSINFO[1]}"],
                             capture_output=True, text=True, timeout=10).stdout.split()
        if tuple(int(v) for v in ver) < (4, 4):
            self.skipTest("bash before 4.4 has no PS0")
        rc = self.home / ".bashrc"
        rc.write_text("PS1='$ '\n", encoding="utf-8")
        self.install([st.BASH])
        with open(rc, "a", encoding="utf-8") as fh:
            fh.write("PROMPT_COMMAND+='; poly_late_hook=1'\n")
        out = _run_in_pty(["bash", "-i"], self.env_for(), [b"echo hi\n", b"\n", b"exit\n"])
        titles = re.findall(rb"\x1b\]2;(.*?)\x07", out)
        self.assertEqual(titles, [b"echo hi", b"exit"], out)

    def test_stale_line_starts_quietly(self):
        rc = self.home / ".bashrc"
        rc.write_text(st.BEGIN_MARKER + "\n"
                      + st.source_line(st.BASH, str(self.home / "gone" / "polykybd-title.bash"))
                      + "\n" + st.END_MARKER + "\n", encoding="utf-8")
        out = _run_in_pty(["bash", "-i"], self.env_for(), [b"echo ok\n", b"exit\n"])
        self.assertNotIn(b"No such file", out)
        self.assertNotIn(b"\x1b]2;", out)


@unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
class ZshOnAPtyTest(_Home):
    def test_title_escape_after_install(self):
        self.present["zsh"] = shutil.which("zsh")
        (self.home / ".zshrc").write_text("PS1='%% '\n", encoding="utf-8")
        self.install([st.ZSH])
        env = {"HOME": str(self.home), "ZDOTDIR": str(self.home), "TERM": "xterm",
               "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        out = _run_in_pty(["zsh", "-i"], env, [b"echo hi\n", b"exit\n"])
        self.assertIn(b"\x1b]2;echo hi\x07", out, out)


if __name__ == "__main__":
    unittest.main()
