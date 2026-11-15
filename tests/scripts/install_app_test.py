"""scripts/install_app.py: the app installer's download, extraction and checks.

The installer copies the updater's build-only rule (it runs before polyhost's
dependencies exist), so these tests hold the two copies to the same answers.
"""
import importlib.util
import io
import re
import tarfile
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.services import updater
from tests.services.updater_build_only_test import SAMPLE_FILES, kept_by_rule

REPO = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location("install_app", REPO / "scripts/install_app.py")
install_app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(install_app)


def _tarball(path: Path, top: str, names, extra=()):
    with tarfile.open(path, "w:gz") as tar:
        for rel in names:
            info = tarfile.TarInfo(name=f"{top}/{rel}")
            info.size = 2
            tar.addfile(info, io.BytesIO(b"x\n"))
        for info in extra:
            tar.addfile(info, io.BytesIO(b"x\n") if info.isfile() else None)


class TestBuildOnlyRuleCopy(unittest.TestCase):

    def test_constants_match_the_updater(self):
        self.assertEqual(install_app.BUILD_ONLY_DIRS, updater.BUILD_ONLY_DIRS)
        self.assertEqual(install_app.KEPT_IN_BUILD_ONLY.pattern,
                         updater.KEPT_IN_BUILD_ONLY.pattern)

    def test_same_answer_for_every_sample_path_and_folder(self):
        paths = set(SAMPLE_FILES)
        for rel in SAMPLE_FILES:
            parts = rel.split("/")
            paths.update("/".join(parts[:i]) for i in range(1, len(parts)))
        for rel in sorted(paths):
            for is_dir in (False, True):
                self.assertEqual(install_app.is_build_only(rel, is_dir),
                                 updater.is_build_only(rel, is_dir), (rel, is_dir))


class TestExtract(unittest.TestCase):

    def test_keeps_what_the_updater_keeps(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "r.tar.gz"
            _tarball(archive, "PolyKybdHost-1.0.0", SAMPLE_FILES)
            dest = Path(td) / "out"
            dest.mkdir()
            top = install_app.extract(archive, dest)
            got = {p.relative_to(top).as_posix() for p in top.rglob("*") if p.is_file()}
        self.assertEqual(top.name, "PolyKybdHost-1.0.0")
        self.assertEqual(got, kept_by_rule(SAMPLE_FILES))

    def test_refuses_a_member_outside_the_folder(self):
        evil = tarfile.TarInfo(name="../evil.txt")
        evil.size = 2
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "r.tar.gz"
            _tarball(archive, "top", ["README.md"], extra=[evil])
            dest = Path(td) / "out"
            dest.mkdir()
            with self.assertRaises(Exception):
                install_app.extract(archive, dest)
            self.assertFalse((Path(td) / "evil.txt").exists())

    def test_refuses_more_than_one_top_folder(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "r.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                for name in ("a/x.txt", "b/y.txt"):
                    info = tarfile.TarInfo(name=name)
                    info.size = 2
                    tar.addfile(info, io.BytesIO(b"x\n"))
            dest = Path(td) / "out"
            dest.mkdir()
            with self.assertRaises(RuntimeError):
                install_app.extract(archive, dest)


class TestRefs(unittest.TestCase):

    def _redirect_to(self, url):
        resp = mock.MagicMock()
        resp.__enter__.return_value.geturl.return_value = url
        return mock.patch.object(install_app, "_open", return_value=resp)

    def test_latest_tag_from_the_redirect(self):
        with self._redirect_to("https://github.com/o/r/releases/tag/v1.24.0"):
            self.assertEqual(install_app.latest_tag("o/r"), "v1.24.0")

    def test_no_release_stops(self):
        with self._redirect_to("https://github.com/o/r/releases"):
            with self.assertRaises(SystemExit):
                install_app.latest_tag("o/r")

    def test_tarball_url(self):
        self.assertEqual(install_app.tarball_url("o/r", "v1.2.3"),
                         "https://github.com/o/r/archive/v1.2.3.tar.gz")


class TestMain(unittest.TestCase):

    def test_refuses_a_developer_checkout(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / ".git").mkdir()
            with mock.patch.object(install_app, "download") as download:
                with self.assertRaises(SystemExit):
                    install_app.main(["--target", td, "--ref", "v1.0.0", "--no-launch"])
            download.assert_not_called()


class TestShellWrappers(unittest.TestCase):
    """install-app.sh and install-app.ps1 pin the same uv build."""

    def _read(self, name):
        return (REPO / "scripts" / name).read_text(encoding="utf-8")

    def test_same_uv_and_python_version(self):
        sh, ps1 = self._read("install-app.sh"), self._read("install-app.ps1")
        uv_sh = re.search(r'^UV_VERSION="([^"]+)"', sh, re.M).group(1)
        uv_ps1 = re.search(r'^\$UvVersion = "([^"]+)"', ps1, re.M).group(1)
        py_sh = re.search(r'^PYTHON_VERSION="([^"]+)"', sh, re.M).group(1)
        py_ps1 = re.search(r'^\$PythonVersion = "([^"]+)"', ps1, re.M).group(1)
        self.assertEqual(uv_sh, uv_ps1)
        self.assertEqual(py_sh, py_ps1)
        # The checksum comments name the installer of the pinned version.
        self.assertIn(f"astral.sh/uv/{uv_sh}/install.sh", sh)
        self.assertIn(f"astral.sh/uv/{uv_ps1}/install.sh", ps1)

    def test_every_asset_has_a_sha256(self):
        sh, ps1 = self._read("install-app.sh"), self._read("install-app.ps1")
        sh_pairs = re.findall(r'UV_ASSET="([^"]+)"\s+UV_SHA256="([0-9a-f]{64})"', sh)
        ps1_pairs = re.findall(r'"(uv-[^"]+\.zip)"\s*=\s*"([0-9a-f]{64})"', ps1)
        self.assertEqual(len(sh_pairs), 4)
        self.assertEqual(len(ps1_pairs), 2)


if __name__ == "__main__":
    unittest.main()
