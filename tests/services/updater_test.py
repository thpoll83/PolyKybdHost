import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

from polyhost.services import updater


def _release_json(tag="v0.8.0", tarball_url="https://example.com/tarball/0.8.0"):
    return {
        "tag_name": tag,
        "tarball_url": tarball_url,
        "html_url": "https://example.com/release",
    }


def _make_response(status_code, payload=None, raise_for_status=False):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = payload or {}
    if raise_for_status:
        resp.raise_for_status.side_effect = requests.HTTPError("boom")
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestCheckLatest(unittest.TestCase):

    def test_returns_release_when_newer(self):
        with mock.patch.object(updater, "__version__", "0.7.2"), \
             mock.patch.object(updater.requests, "get",
                               return_value=_make_response(200, _release_json("v0.8.0"))):
            release = updater.check_latest()
        self.assertIsNotNone(release)
        self.assertEqual(release.version, "0.8.0")
        self.assertEqual(release.tarball_url, "https://example.com/tarball/0.8.0")

    def test_returns_none_when_equal(self):
        with mock.patch.object(updater, "__version__", "0.8.0"), \
             mock.patch.object(updater.requests, "get",
                               return_value=_make_response(200, _release_json("v0.8.0"))):
            self.assertIsNone(updater.check_latest())

    def test_returns_none_when_older(self):
        with mock.patch.object(updater, "__version__", "0.9.0"), \
             mock.patch.object(updater.requests, "get",
                               return_value=_make_response(200, _release_json("v0.8.0"))):
            self.assertIsNone(updater.check_latest())

    def test_strips_v_prefix(self):
        with mock.patch.object(updater, "__version__", "0.0.1"), \
             mock.patch.object(updater.requests, "get",
                               return_value=_make_response(200, _release_json("v1.2.3"))):
            release = updater.check_latest()
        self.assertEqual(release.version, "1.2.3")

    def test_handles_missing_v_prefix(self):
        with mock.patch.object(updater, "__version__", "0.0.1"), \
             mock.patch.object(updater.requests, "get",
                               return_value=_make_response(200, _release_json("1.2.3"))):
            release = updater.check_latest()
        self.assertEqual(release.version, "1.2.3")

    def test_returns_none_on_network_error(self):
        with mock.patch.object(updater.requests, "get",
                               side_effect=requests.ConnectionError("nope")):
            self.assertIsNone(updater.check_latest())

    def test_returns_none_on_rate_limit(self):
        with mock.patch.object(updater.requests, "get",
                               return_value=_make_response(403)):
            self.assertIsNone(updater.check_latest())

    def test_returns_none_on_invalid_version_tag(self):
        with mock.patch.object(updater, "__version__", "0.0.1"), \
             mock.patch.object(updater.requests, "get",
                               return_value=_make_response(200, _release_json("not-a-version"))):
            self.assertIsNone(updater.check_latest())

    def test_returns_none_on_malformed_json(self):
        resp = _make_response(200)
        resp.json.side_effect = ValueError("bad json")
        with mock.patch.object(updater.requests, "get", return_value=resp):
            self.assertIsNone(updater.check_latest())


def _build_tarball(path: Path, top_dir: str, files: dict):
    """Build a gzipped tarball at `path` containing `files` under `top_dir`."""
    with tarfile.open(path, "w:gz") as tar:
        for relname, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=f"{top_dir}/{relname}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


class TestSafeExtract(unittest.TestCase):

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            tar_path = Path(td) / "evil.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                data = b"pwn"
                info = tarfile.TarInfo(name="../../evil.txt")
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

            dest = Path(td) / "out"
            dest.mkdir()
            with tarfile.open(tar_path, "r:gz") as tar:
                with self.assertRaises(RuntimeError):
                    updater._safe_extract(tar, dest)

    def test_rejects_symlink_member(self):
        with tempfile.TemporaryDirectory() as td:
            tar_path = Path(td) / "link.tar.gz"
            with tarfile.open(tar_path, "w:gz") as tar:
                info = tarfile.TarInfo(name="link")
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                tar.addfile(info)

            dest = Path(td) / "out"
            dest.mkdir()
            with mock.patch("polyhost.services.updater.sys") as fake_sys:
                fake_sys.version_info = (3, 11, 0)
                with tarfile.open(tar_path, "r:gz") as tar:
                    with self.assertRaises(RuntimeError):
                        updater._safe_extract(tar, dest)

    def test_extracts_normal_tarball(self):
        with tempfile.TemporaryDirectory() as td:
            tar_path = Path(td) / "ok.tar.gz"
            _build_tarball(tar_path, "thpoll83-PolyKybdHost-abc",
                           {"polyhost/_version.py": "x = 1\n"})
            dest = Path(td) / "out"
            dest.mkdir()
            with tarfile.open(tar_path, "r:gz") as tar:
                updater._safe_extract(tar, dest)
            extracted = dest / "thpoll83-PolyKybdHost-abc" / "polyhost" / "_version.py"
            self.assertTrue(extracted.exists())


class TestDownloadAndExtract(unittest.TestCase):

    def test_returns_top_level_dir(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            archive = tmp / "release.tar.gz"
            _build_tarball(archive, "thpoll83-PolyKybdHost-deadbee",
                           {"polyhost/_version.py": "__version__ = '0.9.0'\n",
                            "README.rst": "hi\n"})

            chunks = []
            with open(archive, "rb") as fh:
                while True:
                    blob = fh.read(1024)
                    if not blob:
                        break
                    chunks.append(blob)

            ctx = mock.MagicMock()
            ctx.__enter__.return_value.iter_content.return_value = chunks
            ctx.__enter__.return_value.headers = {"Content-Length": str(archive.stat().st_size)}
            ctx.__enter__.return_value.raise_for_status.return_value = None

            workdir = tmp / "work"
            workdir.mkdir()
            with mock.patch.object(updater.requests, "get", return_value=ctx):
                top = updater.download_and_extract("https://example.com/x.tar.gz", workdir)

            self.assertTrue(top.is_dir())
            self.assertEqual(top.name, "thpoll83-PolyKybdHost-deadbee")
            self.assertTrue((top / "polyhost" / "_version.py").exists())


class TestApplyUpdate(unittest.TestCase):

    def test_copies_and_excludes(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            src = tmp / "src"
            (src / "polyhost").mkdir(parents=True)
            (src / "polyhost" / "_version.py").write_text("new\n")
            (src / "polyhost" / "newfile.py").write_text("hello\n")
            (src / ".git").mkdir()
            (src / ".git" / "config").write_text("[core]\n")
            (src / "__pycache__").mkdir()
            (src / "__pycache__" / "x.pyc").write_bytes(b"\x00")

            install = tmp / "install"
            install.mkdir()
            (install / "polyhost").mkdir()
            (install / "polyhost" / "_version.py").write_text("old\n")
            (install / "polyhost" / "stale.py").write_text("stale\n")

            with mock.patch.object(updater.subprocess, "run") as mock_run:
                mock_run.return_value = mock.Mock(returncode=0, stderr="")
                updater.apply_update(src, install)

            self.assertEqual((install / "polyhost" / "_version.py").read_text(), "new\n")
            self.assertTrue((install / "polyhost" / "newfile.py").exists())
            self.assertTrue((install / "polyhost" / "stale.py").exists(),
                            "copytree should not remove unrelated files")
            self.assertFalse((install / ".git").exists(),
                             ".git must be excluded")
            self.assertFalse((install / "__pycache__").exists(),
                             "__pycache__ must be excluded")
            mock_run.assert_called_once()
            self.assertEqual(mock_run.call_args.args[0][:4],
                             [sys.executable, "-m", "pip", "install"])

    def test_installs_requirements_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            src.mkdir()
            (src / "requirements.txt").write_text("requests\npackaging\n")
            install = Path(td) / "install"
            install.mkdir()

            with mock.patch.object(updater.subprocess, "run") as mock_run:
                mock_run.return_value = mock.Mock(returncode=0, stderr="")
                updater.apply_update(src, install)

            self.assertEqual(mock_run.call_count, 2)
            cmds = [c.args[0] for c in mock_run.call_args_list]
            self.assertIn("install", cmds[0])
            self.assertIn("-e", cmds[0])
            self.assertIn("-r", cmds[1])
            self.assertEqual(cmds[1][-1], str(install / "requirements.txt"))

    def test_pip_failure_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            src.mkdir()
            (src / "marker").write_text("x")
            install = Path(td) / "install"
            install.mkdir()
            with mock.patch.object(updater.subprocess, "run") as mock_run:
                mock_run.return_value = mock.Mock(returncode=1, stderr="boom", stdout="")
                updater.apply_update(src, install)
            self.assertTrue((install / "marker").exists())

    def test_requirements_pip_failure_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            src.mkdir()
            (src / "requirements.txt").write_text("requests\n")
            install = Path(td) / "install"
            install.mkdir()

            def fake_run(cmd, **kwargs):
                # First call (install -e .) succeeds; second (-r requirements.txt) fails.
                if "-r" in cmd:
                    return mock.Mock(returncode=1, stderr="resolve error", stdout="")
                return mock.Mock(returncode=0, stderr="", stdout="")

            with mock.patch.object(updater.subprocess, "run", side_effect=fake_run) as mock_run:
                with mock.patch.object(updater.log, "warning") as mock_warn:
                    updater.apply_update(src, install)

            self.assertEqual(mock_run.call_count, 2)
            warnings = " ".join(str(c) for c in mock_warn.call_args_list)
            self.assertIn("install -r requirements.txt", warnings)

    def test_pip_failure_falls_back_to_stdout_when_stderr_empty(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            src.mkdir()
            install = Path(td) / "install"
            install.mkdir()
            with mock.patch.object(updater.subprocess, "run") as mock_run, \
                 mock.patch.object(updater.log, "warning") as mock_warn:
                mock_run.return_value = mock.Mock(
                    returncode=1, stderr="", stdout="diagnostic on stdout")
                updater.apply_update(src, install)
            warnings = " ".join(str(c) for c in mock_warn.call_args_list)
            self.assertIn("diagnostic on stdout", warnings)


class TestVersionFromTag(unittest.TestCase):

    def test_plain_version(self):
        self.assertEqual(updater._version_from_tag("1.2.3"), "1.2.3")

    def test_v_prefix(self):
        self.assertEqual(updater._version_from_tag("v1.2.3"), "1.2.3")

    def test_firmware_prefix(self):
        # The firmware repo tags releases as PolyKybd-fw-vX.Y.Z.
        self.assertEqual(updater._version_from_tag("PolyKybd-fw-v0.8.3"), "0.8.3")

    def test_multi_digit_components(self):
        self.assertEqual(updater._version_from_tag("PolyKybd-fw-v0.8.10"), "0.8.10")

    def test_digit_in_prefix_is_skipped(self):
        # A stray digit in the prefix must not be mistaken for the version.
        self.assertEqual(updater._version_from_tag("PolyKybd2-fw-v0.8.3"), "0.8.3")

    def test_no_version_returns_empty(self):
        self.assertEqual(updater._version_from_tag("not-a-version"), "")


def _fw_release_json(tag="PolyKybd-fw-v0.8.3", with_bin=True, with_uf2=True):
    assets = []
    if with_bin:
        assets.append({"name": "handwired_polykybd_split72_default.bin",
                       "browser_download_url": "https://example.com/fw.bin"})
    if with_uf2:
        assets.append({"name": "handwired_polykybd_split72_default.uf2",
                       "browser_download_url": "https://example.com/fw.uf2"})
    return {
        "tag_name": tag,
        "assets": assets,
        "html_url": "https://example.com/fw-release",
        "published_at": "2026-06-05T09:12:22Z",
    }


class TestCheckFwLatest(unittest.TestCase):

    def setUp(self):
        # Isolate from the on-disk ETag cache so checks behave deterministically.
        for name, kw in (("_load_etag_cache", {"return_value": {}}),
                         ("_save_etag_cache", {})):
            patcher = mock.patch.object(updater, name, **kw)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def _resp(status_code, payload=None):
        resp = mock.Mock()
        resp.status_code = status_code
        resp.json.return_value = payload or {}
        resp.headers = {"ETag": '"deadbeef"'}
        return resp

    def test_prefixed_firmware_tag_is_parsed(self):
        # Regression: PolyKybd-fw-v* tags must parse rather than raise.
        with mock.patch.object(updater.requests, "get",
                               return_value=self._resp(200, _fw_release_json("PolyKybd-fw-v0.8.3"))):
            release = updater.check_fw_latest("0.8.1")
        self.assertIsNotNone(release)
        self.assertEqual(release.version, "0.8.3")
        self.assertEqual(release.tag, "PolyKybd-fw-v0.8.3")
        self.assertEqual(release.bin_url, "https://example.com/fw.bin")
        self.assertEqual(release.uf2_url, "https://example.com/fw.uf2")

    def test_up_to_date_returns_none(self):
        with mock.patch.object(updater.requests, "get",
                               return_value=self._resp(200, _fw_release_json("PolyKybd-fw-v0.8.1"))):
            self.assertIsNone(updater.check_fw_latest("0.8.1"))

    def test_newer_without_bin_returns_none(self):
        # A newer release that has no .bin asset cannot be flashed over HID.
        with mock.patch.object(updater.requests, "get",
                               return_value=self._resp(
                                   200, _fw_release_json("PolyKybd-fw-v0.9.0", with_bin=False))):
            self.assertIsNone(updater.check_fw_latest("0.8.1"))


if __name__ == "__main__":
    unittest.main()
