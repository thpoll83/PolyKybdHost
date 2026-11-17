"""editor_plugins: VS Code, Cursor and Windsurf, installed through their
command line program, and JupyterLab, which gets the command to run.

The command line program is a fake ``run``; nothing starts a real editor.
"""
import io
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from polyhost.services import editor_plugins as ep
from polyhost.services import editor_targets as et

REPO = Path(__file__).resolve().parents[2]
EXT = et.VSCODE_EXTENSION_ID


def make_vsix(path, files, date=(2026, 1, 1, 0, 0, 0)):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(zipfile.ZipInfo(name, date), data)
    Path(path).write_bytes(buf.getvalue())


class FakeCli:
    """``code``: keeps the installed extensions, logs every call."""

    def __init__(self, installed=None, fail=None):
        self.installed = dict(installed or {})
        self.calls = []
        self.fail = fail

    def __call__(self, argv, timeout):
        self.calls.append(argv[1:])
        if self.fail:
            return 1, "", self.fail
        if argv[1] == "--list-extensions":
            return 0, "".join(f"{k}@{v}\n" for k, v in self.installed.items()), ""
        if argv[1] == "--install-extension":
            self.installed[EXT] = "1.0.0"
            return 0, "Extension installed.", ""
        if argv[1] == "--uninstall-extension":
            self.installed.pop(argv[2], None)
            return 0, "", ""
        raise AssertionError(argv)


class TestFindTheCli(unittest.TestCase):

    def test_path_first(self):
        found = et.vscode_cli("cursor", which=lambda n: "/usr/bin/" + n, home="/h", env={},
                              system="Linux")
        self.assertEqual(found, Path("/usr/bin/cursor"))
        self.assertEqual(et.vscode_cli("vscode", which=lambda n: "/b/" + n, home="/h", env={},
                                       system="Linux"), Path("/b/code"))

    def test_standard_folders_of_the_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp)
            none = lambda _n: None   # noqa: E731
            local = h / "AppData" / "Local"
            for rel in ("Programs/Microsoft VS Code/bin/code.cmd",
                        "Programs/Windsurf/bin/windsurf.cmd"):
                (local / rel).parent.mkdir(parents=True)
                (local / rel).write_text("")
            self.assertEqual(et.vscode_cli("vscode", none, h, {}, "Windows"),
                             local / "Programs/Microsoft VS Code/bin/code.cmd")
            self.assertEqual(et.vscode_cli("windsurf", none, h, {"LOCALAPPDATA": str(local)},
                                           "Windows"), local / "Programs/Windsurf/bin/windsurf.cmd")
            self.assertIsNone(et.vscode_cli("cursor", none, h, {}, "Windows"))
            mac = h / "Applications/Cursor.app/Contents/Resources/app/bin/cursor"
            mac.parent.mkdir(parents=True)
            mac.write_text("")
            self.assertEqual(et.vscode_cli("cursor", none, h, {}, "Darwin"), mac)
            # A test's home never finds /usr/share/code.
            self.assertIsNone(et.vscode_cli("vscode", none, h, {}, "Linux"))

    def test_parse_the_list(self):
        out = "ms-python.python@2026.1.0\nPolyKybd.polykybd-mode-reporter@1.0.0\n"
        self.assertEqual(et.parse_extension_list(out), "1.0.0")
        self.assertIsNone(et.parse_extension_list("polykybd.polykybd-mode-reporter-remote@1.0.0"))


class TestVsixDigest(unittest.TestCase):

    def test_zip_times_do_not_count_the_bytes_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, c = (Path(tmp) / n for n in ("a.vsix", "b.vsix", "c.vsix"))
            make_vsix(a, {"extension/package.json": "{}", "extension/out/x.js": "1"})
            make_vsix(b, {"extension/out/x.js": "1", "extension/package.json": "{}"},
                      date=(2026, 5, 5, 5, 5, 6))
            make_vsix(c, {"extension/package.json": "{}", "extension/out/x.js": "2"})
            self.assertNotEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(ep.vsix_digest(a), ep.vsix_digest(b))
            self.assertNotEqual(ep.vsix_digest(a), ep.vsix_digest(c))


class CliFixture(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.vsix = self.tmp / "polykybd-mode-reporter.vsix"
        make_vsix(self.vsix, {"extension/package.json": '{"version": "1.0.0"}'})
        self.state_file = self.tmp / "state.json"
        self.cli = FakeCli()
        self.which = lambda n: "/usr/bin/code" if n == "code" else None

    def kw(self, **over):
        kw = dict(home=self.home, env={}, which=self.which, system="Linux",
                  sources={e: self.vsix for e in ep.CLI_EDITORS}, state_file=self.state_file,
                  run=self.cli)
        kw.update(over)
        return kw

    def status(self):
        return ep.status([ep.VSCODE], **self.kw())[0]


class TestVsCode(CliFixture):

    def test_not_present_without_the_cli(self):
        st = ep.status([ep.VSCODE, ep.CURSOR], **self.kw())
        self.assertEqual([s.state for s in st], [ep.STATE_NOT_INSTALLED, ep.STATE_NOT_PRESENT])

    def test_install_status_update_remove(self):
        st = self.status()
        self.assertEqual((st.state, st.target), (ep.STATE_NOT_INSTALLED, Path("/usr/bin/code")))
        self.assertTrue(ep.default_selection(st))
        r = ep.install([ep.VSCODE], **self.kw())
        self.assertEqual(len(r), 1)
        self.assertTrue(r[0].ok and r[0].changed, r)
        self.assertIn(["--install-extension", str(self.vsix), "--force"], self.cli.calls)
        self.assertIn("code --install-extension polykybd-mode-reporter.vsix", r[0].message)
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)
        # An update of the app ships a rebuilt extension.
        make_vsix(self.vsix, {"extension/package.json": '{"version": "1.0.0"}',
                              "extension/out/extension.js": "rebuilt"})
        self.assertEqual(self.status().state, ep.STATE_OUTDATED)
        self.cli.calls.clear()
        self.assertEqual(ep.refresh_installed(**self.kw()), [ep.VSCODE])
        self.assertEqual(self.cli.calls[-1][0], "--install-extension")
        self.assertEqual(self.status().state, ep.STATE_INSTALLED)
        r = ep.remove([ep.VSCODE], **self.kw())
        self.assertTrue(r[0].ok and r[0].changed, r)
        self.assertEqual(self.cli.calls[-1], ["--uninstall-extension", EXT])
        self.assertEqual(self.status().state, ep.STATE_NOT_INSTALLED)
        self.assertIsNone(et.State(self.state_file).cli_digest(ep.VSCODE))

    def test_an_extension_from_the_marketplace_is_left_alone(self):
        self.cli.installed[EXT] = "1.2.0"
        st = self.status()
        self.assertEqual((st.state, st.detail), (ep.STATE_MANUAL, f"{EXT}@1.2.0"))
        for fn in (ep.install, ep.remove):
            r = fn([ep.VSCODE], **self.kw())
            self.assertFalse(r[0].ok, r)
        self.assertEqual(self.cli.calls, [["--list-extensions", "--show-versions"]] * 3)

    def test_a_marketplace_replacement_is_left_alone(self):
        r = ep.install([ep.VSCODE], **self.kw())
        self.assertTrue(r[0].ok and r[0].changed, r)
        self.assertEqual(et.State(self.state_file).cli_version(ep.VSCODE), "1.0.0")
        # The user installs 1.2.0 from the Marketplace over this app's copy.
        self.cli.installed[EXT] = "1.2.0"
        st = self.status()
        self.assertEqual((st.state, st.detail), (ep.STATE_MANUAL, f"{EXT}@1.2.0"))
        # An update of the app ships another .vsix: the refresh must not
        # overwrite the replacement, and Remove must not uninstall it.
        make_vsix(self.vsix, {"extension/package.json": '{"version": "1.0.0"}',
                              "extension/out/extension.js": "rebuilt"})
        self.cli.calls.clear()
        self.assertEqual(ep.refresh_installed(**self.kw()), [])
        self.assertFalse(ep.remove([ep.VSCODE], **self.kw())[0].ok)
        self.assertEqual([c[0] for c in self.cli.calls], ["--list-extensions"] * 2)
        self.assertEqual(self.cli.installed[EXT], "1.2.0")

    def test_a_state_file_that_cannot_be_written_is_reported(self):
        blocker = self.tmp / "blocker"
        blocker.write_text("")
        r = ep.install([ep.VSCODE], **self.kw(state_file=blocker / "state.json"))
        self.assertTrue(r[0].changed)
        self.assertFalse(r[0].ok)
        self.assertIn("could not be written", r[0].message)

    def test_a_failing_cli(self):
        r = ep.install([ep.VSCODE], **self.kw())
        self.assertTrue(r[0].ok)
        self.cli.fail = "boom"
        self.assertEqual(self.status().state, ep.STATE_NOT_PRESENT)
        st = ep.EditorStatus(ep.VSCODE, ep.STATE_NOT_INSTALLED, Path("/usr/bin/code"), "")
        r = ep.install([ep.VSCODE], statuses=[st], **self.kw())
        self.assertFalse(r[0].ok)
        self.assertIn("boom", r[0].message)

    def test_the_refresh_starts_no_cli_where_this_app_installed_nothing(self):
        self.assertEqual(ep.refresh_installed(**self.kw()), [])
        self.assertEqual(self.cli.calls, [])

    def test_the_shipped_vsix_files(self):
        for vsix, folder in ((ep.VSCODE_SOURCE, "vscode-extension"),
                             (ep.VSCODE_REMOTE_SOURCE, "vscode-extension/remote")):
            with zipfile.ZipFile(vsix) as zf:
                names = zf.namelist()
                pkg = zf.read("extension/package.json").decode("utf-8")
            self.assertIn("extension.vsixmanifest", names)
            shipped, source = json.loads(pkg), json.loads((REPO / folder / "package.json").read_text())
            self.assertEqual((shipped["name"], shipped["version"]), (source["name"], source["version"]))

    def test_the_shipped_vsix_has_the_current_readme(self):
        # vsce packs README.md as extension/readme.md: a README change without
        # a rebuild made built-plugins.yml fail (PR #962). The compiled
        # out/*.js are compared only by that CI job, which has Node and tsc.
        for vsix, folder in ((ep.VSCODE_SOURCE, "vscode-extension"),
                             (ep.VSCODE_REMOTE_SOURCE, "vscode-extension/remote")):
            with zipfile.ZipFile(vsix) as zf:
                readme = zf.read("extension/readme.md").decode("utf-8")
            source = (REPO / folder / "README.md").read_text(encoding="utf-8")
            # vsce rewrites a relative link target to a github.com URL.
            def text(md):
                return re.sub(r"\]\([^)]*\)", "]()", md)
            self.assertEqual(text(readme), text(source),
                             f"{vsix.name} is older than {folder}/README.md: run build.sh")


class TestJupyterLab(CliFixture):

    def make_source(self):
        src = self.tmp / "jupyterlab-extension"
        src.mkdir()
        (src / "pyproject.toml").write_text("")
        return src

    def test_the_command_not_an_install(self):
        src = self.make_source()
        kw = self.kw(sources={ep.JUPYTERLAB: src},
                     which=lambda n: "/usr/bin/jupyter" if n == "jupyter" else None)
        st = ep.status([ep.JUPYTERLAB], **kw)[0]
        self.assertEqual(st.state, ep.STATE_COMMAND)
        self.assertEqual(st.detail, f'python -m pip install "{src}"')
        self.assertFalse(ep.default_selection(st))
        r = ep.install([ep.JUPYTERLAB], **kw)
        self.assertEqual(len(r), 1)
        self.assertTrue(r[0].ok and not r[0].changed)
        self.assertIn(st.detail, r[0].message)
        r = ep.remove([ep.JUPYTERLAB], **kw)
        self.assertIn("pip uninstall polykybd_jupyterlab", r[0].message)
        self.assertEqual(ep.install(None, **kw), [])

    def test_found_by_jupyterlab_desktop_or_not_at_all(self):
        src = self.make_source()
        kw = self.kw(sources={ep.JUPYTERLAB: src}, which=lambda _n: None)
        self.assertEqual(ep.status([ep.JUPYTERLAB], **kw)[0].state, ep.STATE_NOT_PRESENT)
        (self.home / "Library" / "jupyterlab-desktop").mkdir(parents=True)
        kw["system"] = "Darwin"
        self.assertEqual(ep.status([ep.JUPYTERLAB], **kw)[0].state, ep.STATE_COMMAND)

    def test_no_source(self):
        kw = self.kw(sources={ep.JUPYTERLAB: self.tmp / "missing"})
        self.assertEqual(ep.status([ep.JUPYTERLAB], **kw)[0].state, ep.STATE_NO_SOURCE)

    def test_the_shipped_package_has_its_prebuilt_labextension(self):
        self.assertTrue((ep.JUPYTERLAB_SOURCE / "pyproject.toml").is_file())
        self.assertTrue((ep.JUPYTERLAB_SOURCE / "polykybd_jupyterlab" / "labextension"
                         / "package.json").is_file())


if __name__ == "__main__":
    unittest.main()
