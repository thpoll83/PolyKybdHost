"""Shell title integration (services/shell_title.py): the one marked line in
the user's shell startup files, and the shipped scripts it loads.

The startup files are the user's, so most tests compare BYTES: everything
outside the block must come back unchanged, and a remove after an install
must give back the original file."""
import codecs
import contextlib
import os
import re
import select
import shutil
import subprocess
import tempfile
import time
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.services import shell_title as st

try:   # POSIX only: Windows (Git Bash included) has no pty module
    import pty
except ImportError:  # pragma: no cover - Windows
    pty = None


def _which(present):
    """A shutil.which stand-in that finds only ``present`` (name -> path)."""
    return lambda name: present.get(name)


def _no_process(argv, **kw):
    """The default `run` in these tests: no real process starts unless a
    test asks for one, so the zsh probe falls back to the environment."""
    raise OSError("no process in this test")


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
        kw.setdefault("run", _no_process)
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

    def test_codex_line_still_names_the_script(self):
        path = "/home/o'neil/my apps/polykybd-title.bash"
        for shell in (st.BASH, st.ZSH, st.PWSH):
            line = st.source_line(shell, path, codex=True)
            self.assertNotEqual(line, st.source_line(shell, path))
            self.assertEqual(st._path_in_line(shell, line), path)

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

    def test_codex_option_is_reported_and_toggled(self):
        rc = self.home / ".bashrc"
        [r] = self.install(codex=True)
        self.assertTrue(r.changed)
        self.assertIn("__poly_title_codex=1", rc.read_text(encoding="utf-8"))
        bash = self.status()[st.BASH]
        self.assertEqual((bash.state, bash.codex), (st.STATE_INSTALLED, True))
        # Installing with no choice keeps the option.
        [r] = self.install()
        self.assertFalse(r.changed, r)
        self.assertTrue(self.status()[st.BASH].codex)
        # Turning it off rewrites the one line and says so.
        [r] = self.install(codex=False)
        self.assertTrue(r.changed)
        self.assertEqual(r.message, st.MSG_CODEX_OFF.format(path=rc))
        self.assertEqual(rc.read_text(encoding="utf-8").count(st.BEGIN_MARKER), 1)
        bash = self.status()[st.BASH]
        self.assertEqual((bash.state, bash.codex), (st.STATE_INSTALLED, False))
        [r] = self.install(codex=True)
        self.assertEqual(r.message, st.MSG_CODEX_ON.format(path=rc))

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

    def test_zsh_reports_its_startup_dir(self):
        """A ZDOTDIR set in ~/.zshenv only is what `zsh -c` reports."""
        zdot = self.home / "zd"
        self.present["zsh"] = "/opt/zsh"
        seen = []

        def run(argv, **kw):
            seen.append((argv, kw))
            return _FakeProc(f"{zdot}\n".encode())
        s = self.status([st.ZSH], run=run)[st.ZSH]
        self.assertEqual(s.rc_path, zdot / ".zshrc")
        argv, kw = seen[0]
        self.assertEqual(argv[:2], ["/opt/zsh", "-c"])
        self.assertNotIn("shell", kw)
        self.assertEqual(kw["env"]["HOME"], str(self.home))
        self.assertIn("timeout", kw)

    def test_zsh_probe_failure_falls_back(self):
        self.present["zsh"] = "/opt/zsh"
        self.env["ZDOTDIR"] = str(self.home / "fromenv")

        def timeout(argv, **kw):
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))
        for run in (timeout, lambda argv, **kw: _FakeProc(b"not a path\n"),
                    lambda argv, **kw: _FakeProc(b"/x\n", returncode=1)):
            s = self.status([st.ZSH], run=run)[st.ZSH]
            self.assertEqual(s.rc_path, self.home / "fromenv" / ".zshrc")

    @unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
    def test_real_zsh_reads_zdotdir_from_zshenv(self):
        self.present["zsh"] = shutil.which("zsh")
        (self.home / ".zshenv").write_text('ZDOTDIR="$HOME/zd"\n', encoding="utf-8")
        env = {"SHELL": "/bin/bash", "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        s = self.status([st.ZSH], run=subprocess.run, env=env)[st.ZSH]
        self.assertEqual(s.rc_path, self.home / "zd" / ".zshrc")

    def test_wsl_launcher_is_not_a_bash(self):
        self.present["bash"] = r"C:\Windows\System32\bash.exe"
        self.assertEqual(self.status(system="Windows")[st.BASH].state, st.STATE_NOT_PRESENT)

    def test_non_ascii_install_path_reads_as_installed(self):
        """The block is compared in the file's encoding: a UTF-8 file with
        an install under /home/rené/ is installed, not stale."""
        scripts = self.home / "rené" / "shell"
        scripts.mkdir(parents=True)
        for name in set(st.SCRIPT_NAMES.values()):
            shutil.copy(st.SCRIPT_DIR / name, scripts / name)
        with mock.patch.object(st, "SCRIPT_DIR", scripts), \
                mock.patch.object(st.locale, "getpreferredencoding", return_value="UTF-8"):
            [r] = self.install()
            self.assertTrue(r.changed, r)
            self.assertIn("rené".encode("utf-8"), (self.home / ".bashrc").read_bytes())
            self.assertEqual(self.status()[st.BASH].state, st.STATE_INSTALLED)
            [again] = self.install()
            self.assertFalse(again.changed)

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

    def test_a_changed_policy_is_seen_on_the_next_status(self):
        """After Set-ExecutionPolicy the dialog's next refresh must allow the
        install; only an allowing answer is cached."""
        self.status([st.POWERSHELL], run=self.answer(policy="Restricted"), system="Windows")
        s = self.status([st.POWERSHELL], run=self.answer(policy="RemoteSigned"),
                        system="Windows")[st.POWERSHELL]
        self.assertEqual(s.state, st.STATE_NOT_INSTALLED)
        self.assertEqual(len(self.calls), 2)

    def test_not_present_powershell_is_not_probed(self):
        self.present = {}
        s = self.status([st.PWSH, st.POWERSHELL], run=self.answer())
        self.assertEqual({k: v.state for k, v in s.items()},
                         {st.PWSH: st.STATE_NOT_PRESENT, st.POWERSHELL: st.STATE_NOT_PRESENT})
        self.assertEqual(self.calls, [])


class InfoRowsTest(_Home):
    def test_no_setup_rows_per_platform(self):
        self.present.update(fish="/usr/bin/fish", nu="/usr/bin/nu", xonsh="/usr/bin/xonsh")
        linux = self.status()
        # fish is a row of its own (its file is only for the Codex option).
        self.assertEqual(linux[st.FISH].state, st.STATE_NOT_INSTALLED)
        self.assertEqual(linux[st.NUSHELL].state, st.STATE_NO_SETUP)
        self.assertEqual(linux[st.XONSH].state, st.STATE_NO_SETUP)
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


@unittest.skipUnless(pty is not None and os.name == "posix" and shutil.which("bash"),
                     "needs bash and a pty (POSIX)")
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
        # After each command the prompt writes the neutral title once.
        self.assertEqual(titles[0], b"echo hi", out)
        self.assertEqual(titles[-1], b"exit", out)
        self.assertNotIn(b"poly_late_hook", b"".join(titles), out)

    def test_set_u_shell_gets_no_unbound_variable_error(self):
        rc = self.home / ".bashrc"
        rc.write_text("set -u\nPS1='$ '\n", encoding="utf-8")
        self.install([st.BASH])
        out = _run_in_pty(["bash", "-i"], self.env_for(), [b"echo hi\n", b"exit\n"])
        self.assertNotIn(b"unbound variable", out, out)
        self.assertIn(b"\x1b]2;echo hi\x07", out, out)

    def _fake_codex(self):
        """A `codex` on PATH that prints its arguments, one per line."""
        bindir = self.home / "bin"
        bindir.mkdir()
        exe = bindir / "codex"
        exe.write_text('#!/bin/sh\nfor a in "$@"; do printf "ARG<%s>\\n" "$a"; done\n',
                       encoding="utf-8")
        exe.chmod(0o755)
        env = self.env_for()
        env["PATH"] = f"{bindir}:{env['PATH']}"
        return env

    def test_codex_wrapper_passes_the_title_items(self):
        (self.home / ".bashrc").write_text("PS1='$ '\n", encoding="utf-8")
        self.install([st.BASH], codex=True)
        out = _run_in_pty(["bash", "-i"], self._fake_codex(),
                          [b"codex exec 'a b'\n", b"exit\n"])
        self.assertIn(b"ARG<-c>", out, out)
        self.assertIn(b"ARG<tui.terminal_title=['app-name','activity','thread-name',"
                      b"'project-name']>", out, out)
        self.assertIn(b"ARG<a b>", out, out)

    def test_codex_wrapper_keeps_a_title_from_codex_config(self):
        (self.home / ".bashrc").write_text("PS1='$ '\n", encoding="utf-8")
        (self.home / ".codex").mkdir()
        (self.home / ".codex" / "config.toml").write_text(
            '[tui]\nterminal_title = ["spinner", "project-name"]\n', encoding="utf-8")
        self.install([st.BASH], codex=True)
        out = _run_in_pty(["bash", "-i"], self._fake_codex(), [b"codex exec\n", b"exit\n"])
        self.assertIn(b"ARG<exec>", out, out)
        self.assertNotIn(b"ARG<-c>", out, out)

    def test_codex_wrapper_keeps_an_alias_of_your_own(self):
        (self.home / ".bashrc").write_text("PS1='$ '\nalias codex='echo MINE'\n",
                                           encoding="utf-8")
        self.install([st.BASH], codex=True)
        out = _run_in_pty(["bash", "-i"], self._fake_codex(), [b"codex\n", b"exit\n"])
        self.assertIn(b"MINE", out, out)
        self.assertNotIn(b"ARG<-c>", out, out)

    def test_no_wrapper_without_the_option(self):
        (self.home / ".bashrc").write_text("PS1='$ '\n", encoding="utf-8")
        self.install([st.BASH])
        out = _run_in_pty(["bash", "-i"], self._fake_codex(), [b"codex exec\n", b"exit\n"])
        self.assertIn(b"ARG<exec>", out, out)
        self.assertNotIn(b"ARG<-c>", out, out)

    def test_prompt_writes_a_neutral_title_after_a_command(self):
        """A prompt that sets no title of its own: the command's title must not
        stay (with its overlay) at the next prompt."""
        (self.home / ".bashrc").write_text("PS1='$ '\n", encoding="utf-8")
        self.install([st.BASH])
        env = dict(self.env_for(), USER="me")
        out = _run_in_pty(["bash", "-i"], env, [b"cd ~\n", b"echo hi\n", b"exit\n"])
        titles = re.findall(rb"\x1b\]2;(.*?)\x07", out)
        i = titles.index(b"echo hi")
        self.assertRegex(titles[i + 1], rb"^me@[^:]+: ~$", titles)
        # No title at the first prompt, before any command ran.
        self.assertEqual(titles[0], b"cd ~", titles)

    def test_a_prompt_title_still_takes_priority(self):
        """Ubuntu's PS1 sets the title itself; it is printed after the reset."""
        (self.home / ".bashrc").write_text("PS1='\\[\\e]0;base-title\\a\\]$ '\n",
                                           encoding="utf-8")
        self.install([st.BASH])
        out = _run_in_pty(["bash", "-i"], self.env_for(), [b"echo hi\n", b"exit\n"])
        after = out[out.index(b"\x1b]2;echo hi\x07"):]
        reset = after.find(b": ", after.find(b"\x1b]2;", 1))
        self.assertGreater(after.rfind(b"\x1b]0;base-title\x07"), reset, out)

    def test_stale_line_starts_quietly(self):
        rc = self.home / ".bashrc"
        rc.write_text(st.BEGIN_MARKER + "\n"
                      + st.source_line(st.BASH, str(self.home / "gone" / "polykybd-title.bash"))
                      + "\n" + st.END_MARKER + "\n", encoding="utf-8")
        out = _run_in_pty(["bash", "-i"], self.env_for(), [b"echo ok\n", b"exit\n"])
        self.assertNotIn(b"No such file", out)
        self.assertNotIn(b"\x1b]2;", out)


@unittest.skipUnless(pty is not None and os.name == "posix" and shutil.which("zsh"),
                     "needs zsh and a pty (POSIX)")
class ZshOnAPtyTest(_Home):
    def test_title_escape_after_install(self):
        self.present["zsh"] = shutil.which("zsh")
        (self.home / ".zshrc").write_text("PS1='%% '\n", encoding="utf-8")
        self.install([st.ZSH])
        env = {"HOME": str(self.home), "ZDOTDIR": str(self.home), "TERM": "xterm",
               "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        out = _run_in_pty(["zsh", "-i"], env, [b"echo hi\n", b"exit\n"])
        self.assertIn(b"\x1b]2;echo hi\x07", out, out)

    def test_prompt_writes_a_neutral_title_after_a_command(self):
        self.present["zsh"] = shutil.which("zsh")
        (self.home / ".zshrc").write_text("PS1='%% '\n", encoding="utf-8")
        self.install([st.ZSH])
        env = {"HOME": str(self.home), "ZDOTDIR": str(self.home), "TERM": "xterm",
               "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        out = _run_in_pty(["zsh", "-i"], env, [b"cd ~\n", b"echo hi\n", b"exit\n"])
        titles = re.findall(rb"\x1b\]2;(.*?)\x07", out)
        i = titles.index(b"echo hi")
        self.assertRegex(titles[i + 1], rb"@[^:]+: ~$", titles)

    def test_a_theme_precmd_title_is_written_after_the_reset(self):
        self.present["zsh"] = shutil.which("zsh")
        (self.home / ".zshrc").write_text("PS1='%% '\n", encoding="utf-8")
        self.install([st.ZSH])
        with open(self.home / ".zshrc", "a", encoding="utf-8") as fh:
            fh.write("theme_title() { print -n $'\\e]2;THEME\\a' }\n"
                     "precmd_functions+=(theme_title)\n")
        env = {"HOME": str(self.home), "ZDOTDIR": str(self.home), "TERM": "xterm",
               "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        out = _run_in_pty(["zsh", "-i"], env, [b"echo hi\n", b"exit\n"])
        titles = re.findall(rb"\x1b\]2;(.*?)\x07", out)
        i = titles.index(b"echo hi")
        self.assertEqual(titles[i + 2], b"THEME", titles)

    def test_codex_wrapper_passes_the_title_items(self):
        self.present["zsh"] = shutil.which("zsh")
        (self.home / ".zshrc").write_text("PS1='%% '\n", encoding="utf-8")
        self.install([st.ZSH], codex=True)
        bindir = self.home / "bin"
        bindir.mkdir()
        (bindir / "codex").write_text('#!/bin/sh\nfor a in "$@"; do printf "ARG<%s>\\n" "$a"; done\n',
                                      encoding="utf-8")
        (bindir / "codex").chmod(0o755)
        env = {"HOME": str(self.home), "ZDOTDIR": str(self.home), "TERM": "xterm",
               "PATH": f"{bindir}:" + os.environ.get("PATH", "/usr/bin:/bin")}
        out = _run_in_pty(["zsh", "-i"], env, [b"codex exec\n", b"exit\n"])
        self.assertIn(b"ARG<tui.terminal_title=['app-name','activity','thread-name',"
                      b"'project-name']>", out, out)
        self.assertIn(b"ARG<exec>", out, out)


class FishFileTest(_Home):
    def test_line_round_trips_a_quote_and_a_backslash(self):
        path = "/home/o'neil/my\\apps/polykybd-title.fish"
        for codex in (False, True):
            line = st.source_line(st.FISH, path, codex)
            self.assertTrue(line.startswith("if test -r '"), line)
            self.assertEqual(st._path_in_line(st.FISH, line), path)

    def test_install_goes_to_conf_d_and_only_with_codex_by_default(self):
        self.present["fish"] = "/usr/bin/fish"
        rc = self.home / ".config" / "fish" / "conf.d" / "polykybd.fish"
        self.assertNotIn(st.FISH, [r.shell for r in self.install()])
        self.assertFalse(rc.exists())
        results = {r.shell: r for r in self.install(codex=True)}
        self.assertTrue(results[st.FISH].changed, results)
        self.assertIn("set -g __poly_title_codex 1", rc.read_text(encoding="utf-8"))
        fish = self.status()[st.FISH]
        self.assertEqual((fish.state, fish.codex), (st.STATE_INSTALLED, True))

    def test_xdg_config_home_is_used(self):
        self.present["fish"] = "/usr/bin/fish"
        self.env["XDG_CONFIG_HOME"] = str(self.home / "cfg")
        self.install([st.FISH], codex=True)
        self.assertTrue((self.home / "cfg" / "fish" / "conf.d" / "polykybd.fish").is_file())


@unittest.skipUnless(pty is not None and os.name == "posix" and shutil.which("fish"),
                     "needs fish and a pty (POSIX)")
class FishOnAPtyTest(_Home):
    """fish needs a controlling terminal, which _run_in_pty does not give."""

    @staticmethod
    def _run(env, inputs, settle=2.0, step=1.0):
        pid, fd = pty.fork()
        if pid == 0:    # pragma: no cover - the child
            os.execvpe("fish", ["fish", "-i"], env)
        out = b""

        def pump(t):
            nonlocal out
            end = time.monotonic() + t
            while time.monotonic() < end:
                if select.select([fd], [], [], 0.1)[0]:
                    try:
                        out += os.read(fd, 65536)
                    except OSError:
                        return
        try:
            pump(settle)
            for data in inputs:
                os.write(fd, data)
                pump(step)
        finally:
            # The shell may have exited already (fish ends on EOF); only the
            # reaping below matters then.
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, 9)
            os.waitpid(pid, 0)
            os.close(fd)
        return out

    def _env(self, bindir):
        return {"HOME": str(self.home), "TERM": "xterm",
                "PATH": f"{bindir}:" + os.environ.get("PATH", "/usr/bin:/bin")}

    def _fake_codex(self):
        bindir = self.home / "bin"
        bindir.mkdir()
        (bindir / "codex").write_text('#!/bin/sh\nfor a in "$@"; do printf "ARG<%s>\\n" "$a"; done\n',
                                      encoding="utf-8")
        (bindir / "codex").chmod(0o755)
        return bindir

    def test_codex_wrapper_passes_the_title_items(self):
        self.present["fish"] = shutil.which("fish")
        self.install([st.FISH], codex=True)
        out = self._run(self._env(self._fake_codex()), [b"codex exec 'a b'\r"])
        self.assertIn(b"ARG<tui.terminal_title=['app-name','activity','thread-name',"
                      b"'project-name']>", out, out)
        self.assertIn(b"ARG<a b>", out, out)

    def test_codex_wrapper_keeps_a_title_from_codex_config(self):
        self.present["fish"] = shutil.which("fish")
        (self.home / ".codex").mkdir()
        (self.home / ".codex" / "config.toml").write_text(
            '[tui]\nterminal_title = ["spinner"]\n', encoding="utf-8")
        self.install([st.FISH], codex=True)
        out = self._run(self._env(self._fake_codex()), [b"codex exec\r"])
        self.assertIn(b"ARG<exec>", out, out)
        self.assertNotIn(b"ARG<-c>", out, out)

    def test_no_wrapper_without_the_option(self):
        self.present["fish"] = shutil.which("fish")
        self.install([st.FISH], codex=False)
        out = self._run(self._env(self._fake_codex()), [b"codex exec\r"])
        self.assertIn(b"ARG<exec>", out, out)
        self.assertNotIn(b"ARG<-c>", out, out)


if __name__ == "__main__":
    unittest.main()
