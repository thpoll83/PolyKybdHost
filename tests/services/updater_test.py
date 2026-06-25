import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests
from packaging.version import Version

from polyhost.services import updater


def _release_json(tag="v0.8.0", tarball_url="https://example.com/tarball/0.8.0"):
    return {
        "tag_name": tag,
        "tarball_url": tarball_url,
        "html_url": "https://example.com/release",
    }


def _make_response(status_code, payload=None, headers=None):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = payload or {}
    # A real dict so the ETag-cache write (json.dumps) doesn't choke on a Mock.
    resp.headers = headers or {}
    resp.raise_for_status.return_value = None
    return resp


class TestCheckLatest(unittest.TestCase):

    def setUp(self):
        # Isolate from the on-disk ETag cache: deterministic, and never touches
        # the user's real cache file. Tests that exercise the 304 path override
        # ``self.mock_load.return_value``.
        load_p = mock.patch.object(updater, "_load_etag_cache", return_value={})
        save_p = mock.patch.object(updater, "_save_etag_cache")
        self.mock_load = load_p.start()
        save_p.start()
        self.addCleanup(load_p.stop)
        self.addCleanup(save_p.stop)

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

    def test_raises_on_network_error(self):
        # Network/API failures raise UpdateCheckError so callers can tell them
        # apart from "no newer version" (None).
        with mock.patch.object(updater.requests, "get",
                               side_effect=requests.ConnectionError("nope")):
            with self.assertRaises(updater.UpdateCheckError):
                updater.check_latest()

    def test_raises_on_rate_limit(self):
        # 403 now tries the github.com web fallback first; only when that's also
        # unreachable does the rate-limit error surface.
        with mock.patch.object(updater.requests, "get",
                               return_value=_make_response(403)), \
             mock.patch.object(updater.requests, "head",
                               side_effect=requests.RequestException("offline")):
            with self.assertRaises(updater.UpdateCheckError):
                updater.check_latest()

    def test_raises_on_invalid_version_tag(self):
        with mock.patch.object(updater, "__version__", "0.0.1"), \
             mock.patch.object(updater.requests, "get",
                               return_value=_make_response(200, _release_json("not-a-version"))):
            with self.assertRaises(updater.UpdateCheckError):
                updater.check_latest()

    def test_raises_on_malformed_json(self):
        resp = _make_response(200)
        resp.json.side_effect = ValueError("bad json")
        with mock.patch.object(updater.requests, "get", return_value=resp):
            with self.assertRaises(updater.UpdateCheckError):
                updater.check_latest()

    def test_returns_cached_release_on_304(self):
        # 304 Not Modified: re-evaluate the cached release against the current
        # version without a fresh download.
        self.mock_load.return_value = {"host": {
            "etag": '"abc"', "tag": "v1.2.3", "version": "1.2.3",
            "tarball_url": "https://example.com/tarball/1.2.3",
            "html_url": "https://example.com/release", "published_at": "",
        }}
        with mock.patch.object(updater, "__version__", "0.0.1"), \
             mock.patch.object(updater.requests, "get", return_value=_make_response(304)):
            release = updater.check_latest()
        self.assertIsNotNone(release)
        self.assertEqual(release.version, "1.2.3")
        self.assertEqual(release.tarball_url, "https://example.com/tarball/1.2.3")

    def test_returns_none_on_304_when_up_to_date(self):
        self.mock_load.return_value = {"host": {
            "etag": '"abc"', "tag": "v1.2.3", "version": "1.2.3",
            "tarball_url": "https://example.com/t", "html_url": "", "published_at": "",
        }}
        with mock.patch.object(updater, "__version__", "1.2.3"), \
             mock.patch.object(updater.requests, "get", return_value=_make_response(304)):
            self.assertIsNone(updater.check_latest())


def _redirect_response(location):
    resp = mock.Mock()
    resp.status_code = 302
    resp.headers = {"Location": location}
    return resp


class TestWebFallback(unittest.TestCase):
    """When the API is rate-limited (403), fall back to github.com (the web
    host), which is not subject to the API's 60/hour limit, so manual checks
    still work."""

    def setUp(self):
        load_p = mock.patch.object(updater, "_load_etag_cache", return_value={})
        save_p = mock.patch.object(updater, "_save_etag_cache")
        self.mock_load = load_p.start()
        save_p.start()
        self.addCleanup(load_p.stop)
        self.addCleanup(save_p.stop)

    def test_latest_tag_via_web_parses_redirect(self):
        with mock.patch.object(updater.requests, "head",
                               return_value=_redirect_response(
                                   "https://github.com/thpoll83/PolyKybdHost/releases/tag/v0.9.0")):
            self.assertEqual(updater._latest_tag_via_web(updater.HOST_REPO), "v0.9.0")

    def test_latest_tag_via_web_decodes_and_handles_no_tag(self):
        with mock.patch.object(updater.requests, "head",
                               return_value=_redirect_response(
                                   "https://github.com/x/y/releases/tag/PolyKybd-fw-v1.2.3%2Bbuild")):
            self.assertEqual(updater._latest_tag_via_web("x/y"), "PolyKybd-fw-v1.2.3+build")
        with mock.patch.object(updater.requests, "head",
                               return_value=_redirect_response("https://github.com/x/y/releases")):
            self.assertIsNone(updater._latest_tag_via_web("x/y"))

    def test_host_403_falls_back_to_web_and_builds_tarball(self):
        with mock.patch.object(updater, "__version__", "0.0.1"), \
             mock.patch.object(updater, "_current_version", return_value=Version("0.0.1")), \
             mock.patch.object(updater.requests, "get", return_value=_make_response(403)), \
             mock.patch.object(updater.requests, "head",
                               return_value=_redirect_response(
                                   "https://github.com/thpoll83/PolyKybdHost/releases/tag/v0.9.0")):
            rel = updater.check_latest()
        self.assertIsNotNone(rel)
        self.assertEqual(rel.version, "0.9.0")
        self.assertEqual(rel.tarball_url,
                         "https://github.com/thpoll83/PolyKybdHost/archive/refs/tags/v0.9.0.tar.gz")

    def test_host_403_web_says_up_to_date_returns_none(self):
        with mock.patch.object(updater, "_current_version", return_value=Version("9.9.9")), \
             mock.patch.object(updater.requests, "get", return_value=_make_response(403)), \
             mock.patch.object(updater.requests, "head",
                               return_value=_redirect_response(
                                   "https://github.com/thpoll83/PolyKybdHost/releases/tag/v0.9.0")):
            self.assertIsNone(updater.check_latest())

    def test_host_403_web_also_unreachable_raises(self):
        with mock.patch.object(updater.requests, "get", return_value=_make_response(403)), \
             mock.patch.object(updater.requests, "head",
                               side_effect=requests.RequestException("offline")):
            with self.assertRaises(updater.UpdateCheckError):
                updater.check_latest()

    def test_fw_403_falls_back_to_web_assets(self):
        html = ('<a href="/thpoll83/qmk_firmware/releases/download/PolyKybd-fw-v0.9.0/poly.bin">'
                '<a href="/thpoll83/qmk_firmware/releases/download/PolyKybd-fw-v0.9.0/poly.uf2">')
        asset_resp = _make_response(200)
        asset_resp.text = html
        with mock.patch.object(updater.requests, "get",
                               side_effect=[_make_response(403), asset_resp]), \
             mock.patch.object(updater.requests, "head",
                               return_value=_redirect_response(
                                   "https://github.com/thpoll83/qmk_firmware/releases/tag/PolyKybd-fw-v0.9.0")):
            fw = updater.check_fw_latest("0.8.0")
        self.assertIsNotNone(fw)
        self.assertEqual(fw.version, "0.9.0")
        self.assertTrue(fw.bin_url.endswith("/poly.bin"))
        self.assertTrue(fw.uf2_url.endswith("/poly.uf2"))


class TestLastCheckTime(unittest.TestCase):
    """The update-check throttle is persisted (in the ETag cache file) so it
    survives restarts — otherwise every relaunch fires a check and exhausts
    GitHub's 60-req/hour/IP limit."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cache = Path(self._tmp.name) / "update_etags.json"
        self._patch = mock.patch.object(updater, "_ETAG_CACHE", self._cache)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_defaults_to_zero_when_never_checked(self):
        self.assertEqual(updater.get_last_check_time(), 0.0)

    def test_round_trips(self):
        updater.set_last_check_time(1_700_000_000.0)
        self.assertEqual(updater.get_last_check_time(), 1_700_000_000.0)

    def test_does_not_clobber_etag_entries(self):
        # Persisting the timestamp must not wipe the host/fw ETag entries that
        # live in the same cache file (and vice-versa).
        updater._save_etag_cache({"host": {"etag": '"x"', "version": "1.0.0"}})
        updater.set_last_check_time(123.0)
        cache = updater._load_etag_cache()
        self.assertEqual(cache.get("checked_at"), 123.0)
        self.assertEqual(cache.get("host", {}).get("version"), "1.0.0")

    def test_corrupt_value_falls_back_to_zero(self):
        updater._save_etag_cache({"checked_at": "not-a-number"})
        self.assertEqual(updater.get_last_check_time(), 0.0)


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

    def test_preserves_prerelease_suffix(self):
        # The numeric run is anchored, but a trailing prerelease/build suffix is
        # kept so Version() orders it correctly (rc1 sorts before the final).
        self.assertEqual(updater._version_from_tag("v1.2.3rc1"), "1.2.3rc1")
        self.assertEqual(updater._version_from_tag("PolyKybd-fw-v1.0.0-beta.1"),
                         "1.0.0-beta.1")


def _fw_release_json(tag="PolyKybd-fw-v0.8.3", with_bin=True, with_uf2=True):
    assets = []
    if with_bin:
        assets.append({"name": "polykybd_split72_default.bin",
                       "browser_download_url": "https://example.com/fw.bin"})
    if with_uf2:
        assets.append({"name": "polykybd_split72_default.uf2",
                       "browser_download_url": "https://example.com/fw.uf2"})
    return {
        "tag_name": tag,
        "assets": assets,
        "html_url": "https://example.com/fw-release",
        "published_at": "2026-06-05T09:12:22Z",
    }


class TestCheckFwLatest(unittest.TestCase):

    def setUp(self):
        # Isolate from the on-disk ETag cache (see TestCheckLatest.setUp).
        load_p = mock.patch.object(updater, "_load_etag_cache", return_value={})
        save_p = mock.patch.object(updater, "_save_etag_cache")
        self.mock_load = load_p.start()
        save_p.start()
        self.addCleanup(load_p.stop)
        self.addCleanup(save_p.stop)

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

    def test_returns_cached_release_on_304(self):
        self.mock_load.return_value = {"fw": {
            "etag": '"abc"', "tag": "PolyKybd-fw-v0.9.0", "version": "0.9.0",
            "bin_url": "https://example.com/fw.bin",
            "uf2_url": "https://example.com/fw.uf2",
            "html_url": "https://example.com/fw-release", "published_at": "",
        }}
        with mock.patch.object(updater.requests, "get", return_value=self._resp(304)):
            release = updater.check_fw_latest("0.8.1")
        self.assertIsNotNone(release)
        self.assertEqual(release.version, "0.9.0")
        self.assertEqual(release.bin_url, "https://example.com/fw.bin")

    def test_raises_on_rate_limit(self):
        # 403 falls back to the github.com web path; raises only if that's down too.
        with mock.patch.object(updater.requests, "get", return_value=self._resp(403)), \
             mock.patch.object(updater.requests, "head",
                               side_effect=requests.RequestException("offline")):
            with self.assertRaises(updater.UpdateCheckError):
                updater.check_fw_latest("0.8.1")


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


class _FakePopen:
    """Minimal stand-in for subprocess.Popen as used by updater._run_pip."""

    def __init__(self, returncode=0, lines=()):
        self.stdout = iter(lines)
        self.returncode = returncode

    def wait(self):
        return self.returncode


def _popen_side_effect(*results):
    """Yield a _FakePopen per Popen call.

    Each entry in ``results`` is a ``(returncode, lines)`` tuple applied to
    successive calls, so a test can make the first pip invocation succeed and a
    later one fail.
    """
    it = iter(results)

    def _factory(cmd, **kwargs):
        returncode, lines = next(it)
        return _FakePopen(returncode, list(lines))

    return _factory


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

            with mock.patch.object(updater.subprocess, "Popen",
                                   side_effect=_popen_side_effect((0, []))) as mock_popen:
                locked = updater.apply_update(src, install)

            self.assertEqual((install / "polyhost" / "_version.py").read_text(), "new\n")
            self.assertTrue((install / "polyhost" / "newfile.py").exists())
            self.assertTrue((install / "polyhost" / "stale.py").exists(),
                            "copytree should not remove unrelated files")
            self.assertFalse((install / ".git").exists(),
                             ".git must be excluded")
            self.assertFalse((install / "__pycache__").exists(),
                             "__pycache__ must be excluded")
            self.assertEqual(locked, [], "no locked files expected on non-Windows")
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args.args[0]
            self.assertEqual(cmd[:4], [sys.executable, "-m", "pip", "install"])
            self.assertIn("-e", cmd)

    def test_installs_requirements_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            src.mkdir()
            (src / "requirements.txt").write_text("requests\npackaging\n")
            install = Path(td) / "install"
            install.mkdir()

            with mock.patch.object(updater.subprocess, "Popen",
                                   side_effect=_popen_side_effect((0, []), (0, []))) as mock_popen:
                updater.apply_update(src, install)

            self.assertEqual(mock_popen.call_count, 2)
            cmds = [c.args[0] for c in mock_popen.call_args_list]
            self.assertIn("-e", cmds[0])
            self.assertIn("-r", cmds[1])
            self.assertEqual(cmds[1][-1], str(install / "requirements.txt"))

    def test_pip_failure_raises(self):
        # _run_pip now raises on a non-zero exit, and apply_update lets it
        # propagate. The captured pip output is surfaced in the message.
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            src.mkdir()
            (src / "marker").write_text("x")
            install = Path(td) / "install"
            install.mkdir()
            with mock.patch.object(updater.subprocess, "Popen",
                                   side_effect=_popen_side_effect((1, ["boom"]))):
                with self.assertRaises(RuntimeError) as ctx:
                    updater.apply_update(src, install)
            self.assertIn("boom", str(ctx.exception))
            # Files are copied before the (failing) pip step runs.
            self.assertTrue((install / "marker").exists())

    def test_requirements_failure_raises(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            src.mkdir()
            (src / "requirements.txt").write_text("requests\n")
            install = Path(td) / "install"
            install.mkdir()
            # First call (install -e .) succeeds; second (-r requirements) fails.
            with mock.patch.object(updater.subprocess, "Popen",
                                   side_effect=_popen_side_effect((0, []), (1, ["resolve error"]))):
                with self.assertRaises(RuntimeError) as ctx:
                    updater.apply_update(src, install)
            self.assertIn("resolve error", str(ctx.exception))


class _Recorder:
    """Records callback invocations as ``(name, args)`` tuples.

    Replaces the old pyqtSignal-spy pattern: the threaded updater classes now
    take plain callables, so a test passes recorder methods and asserts on the
    captured sequence. ``names`` preserves emission order — the contract the Qt
    queued-signal delivery used to provide.
    """

    def __init__(self):
        self.calls = []

    def make(self, name):
        return lambda *args: self.calls.append((name, args))

    @property
    def names(self):
        return [name for name, _ in self.calls]

    def args_for(self, name):
        return [args for n, args in self.calls if n == name]


class TestUpdateChecker(unittest.TestCase):
    """The threaded checker maps check_latest/check_fw_latest results to callbacks.

    Each test drives ``run()`` synchronously (no thread start) so the assertions
    are race-free; the thread body is identical either way.
    """

    def _run(self, rec, current_fw_version=None):
        checker = updater.UpdateChecker(
            current_fw_version=current_fw_version,
            on_update_available=rec.make("update_available"),
            on_fw_up_available=rec.make("fw_up_available"),
            on_host_no_update=rec.make("host_no_update"),
            on_fw_no_update=rec.make("fw_no_update"),
            on_error=rec.make("error"),
        )
        self.assertTrue(checker.daemon)
        checker.run()

    def test_host_update_available(self):
        rec = _Recorder()
        rel = updater.ReleaseInfo("v1.0.0", "1.0.0", "url", "html", "")
        with mock.patch.object(updater, "check_latest", return_value=rel):
            self._run(rec)
        self.assertEqual(rec.names, ["update_available"])
        self.assertEqual(rec.args_for("update_available"), [(rel,)])

    def test_host_no_update(self):
        rec = _Recorder()
        with mock.patch.object(updater, "check_latest", return_value=None):
            self._run(rec)
        self.assertEqual(rec.names, ["host_no_update"])

    def test_host_error_then_no_update(self):
        # On failure the error callback fires first, then host_no_update — the
        # ordering callers rely on to distinguish "error" from "no newer version".
        rec = _Recorder()
        with mock.patch.object(updater, "check_latest",
                               side_effect=updater.UpdateCheckError("boom")):
            self._run(rec)
        self.assertEqual(rec.names, ["error", "host_no_update"])
        self.assertEqual(rec.args_for("error"), [("boom",)])

    def test_firmware_checked_only_when_version_given(self):
        rec = _Recorder()
        with mock.patch.object(updater, "check_latest", return_value=None), \
             mock.patch.object(updater, "check_fw_latest") as mock_fw:
            self._run(rec)  # no current_fw_version
        mock_fw.assert_not_called()
        self.assertEqual(rec.names, ["host_no_update"])

    def test_firmware_update_available(self):
        rec = _Recorder()
        fw = updater.FwUpReleaseInfo("PolyKybd-fw-v0.9.0", "0.9.0",
                                     "bin", "uf2", "html", "")
        with mock.patch.object(updater, "check_latest", return_value=None), \
             mock.patch.object(updater, "check_fw_latest", return_value=fw):
            self._run(rec, current_fw_version="0.8.0")
        self.assertEqual(rec.names, ["host_no_update", "fw_up_available"])
        self.assertEqual(rec.args_for("fw_up_available"), [(fw,)])

    def test_firmware_no_update(self):
        rec = _Recorder()
        with mock.patch.object(updater, "check_latest", return_value=None), \
             mock.patch.object(updater, "check_fw_latest", return_value=None):
            self._run(rec, current_fw_version="0.8.0")
        self.assertEqual(rec.names, ["host_no_update", "fw_no_update"])

    def test_none_callbacks_are_skipped(self):
        # A checker with no callbacks wired up must not raise.
        with mock.patch.object(updater, "check_latest", return_value=None):
            updater.UpdateChecker().run()


class TestUpdateInstaller(unittest.TestCase):

    def _make(self, release, rec):
        inst = updater.UpdateInstaller(
            release,
            on_progress=rec.make("progress"),
            on_finished_ok=rec.make("finished_ok"),
            on_relay_needed=rec.make("relay_needed"),
            on_failed=rec.make("failed"),
        )
        # NON-daemon by design: apply_update() rewrites the install tree + runs
        # pip; the process must not exit and kill it mid-install.
        self.assertFalse(inst.daemon)
        return inst

    def test_finished_ok_when_no_locked_files(self):
        rec = _Recorder()
        rel = updater.ReleaseInfo("v1.0.0", "1.0.0", "url", "html", "")
        with mock.patch.object(updater, "get_install_root", return_value=Path("/install")), \
             mock.patch.object(updater, "download_and_extract", return_value=Path("/extracted")), \
             mock.patch.object(updater, "apply_update", return_value=[]), \
             mock.patch.object(updater.shutil, "rmtree"), \
             mock.patch.object(updater.tempfile, "mkdtemp", return_value="/tmp/x"):
            self._make(rel, rec).run()
        self.assertIn("finished_ok", rec.names)
        self.assertNotIn("relay_needed", rec.names)
        self.assertNotIn("failed", rec.names)

    def test_relay_needed_when_locked_files(self):
        rec = _Recorder()
        rel = updater.ReleaseInfo("v1.0.0", "1.0.0", "url", "html", "")
        with mock.patch.object(updater, "get_install_root", return_value=Path("/install")), \
             mock.patch.object(updater, "download_and_extract", return_value=Path("/extracted")), \
             mock.patch.object(updater, "apply_update", return_value=[("a", "b")]), \
             mock.patch.object(updater, "_write_relay_script", return_value=Path("/tmp/x/relay.py")), \
             mock.patch.object(updater.tempfile, "mkdtemp", return_value="/tmp/x"):
            self._make(rel, rec).run()
        self.assertIn("relay_needed", rec.names)
        self.assertNotIn("finished_ok", rec.names)
        self.assertEqual(rec.args_for("relay_needed"), [("/tmp/x/relay.py",)])

    def test_failed_when_install_dir_not_writable(self):
        rec = _Recorder()
        rel = updater.ReleaseInfo("v1.0.0", "1.0.0", "url", "html", "")
        with mock.patch.object(updater, "get_install_root",
                               side_effect=updater.NotWritableError("/install")):
            self._make(rel, rec).run()
        self.assertEqual(rec.names, ["failed"])
        self.assertIn("/install", rec.args_for("failed")[0][0])

    def test_failed_on_download_error(self):
        rec = _Recorder()
        rel = updater.ReleaseInfo("v1.0.0", "1.0.0", "url", "html", "")
        with mock.patch.object(updater, "get_install_root", return_value=Path("/install")), \
             mock.patch.object(updater, "download_and_extract",
                               side_effect=RuntimeError("net down")), \
             mock.patch.object(updater.shutil, "rmtree"), \
             mock.patch.object(updater.tempfile, "mkdtemp", return_value="/tmp/x"):
            self._make(rel, rec).run()
        self.assertIn("failed", rec.names)
        self.assertEqual(rec.args_for("failed"), [("net down",)])


class _NamedFile:
    """A real file handle with a writable ``name`` (the downloader reads tmp.name).

    ``tempfile.NamedTemporaryFile`` yields an object whose ``.name`` is the path;
    a plain ``open()`` handle's ``.name`` is read-only, so this thin wrapper
    forwards writes to the underlying file while exposing a settable name.
    """

    def __init__(self, fh, name):
        self._fh = fh
        self.name = name

    def write(self, data):
        return self._fh.write(data)


class TestFwUpDownloader(unittest.TestCase):

    @staticmethod
    def _stream_response(chunks, total):
        ctx = mock.MagicMock()
        resp = ctx.__enter__.return_value
        resp.iter_content.return_value = chunks
        resp.headers = {"Content-Length": str(total)} if total else {}
        resp.raise_for_status.return_value = None
        return ctx

    def test_finished_ok_writes_bin(self):
        rec = _Recorder()
        rel = updater.FwUpReleaseInfo("PolyKybd-fw-v0.9.0", "0.9.0",
                                      "https://example.com/fw.bin", "", "html", "")
        dl = updater.FwUpDownloader(
            rel,
            on_progress=rec.make("progress"),
            on_finished=rec.make("finished"),
        )
        self.assertTrue(dl.daemon)
        with tempfile.TemporaryDirectory() as td:
            ctx = self._stream_response([b"abc", b"def"], total=6)
            bin_path = Path(td) / "fw.bin"
            raw = open(bin_path, "wb")
            fh = _NamedFile(raw, str(bin_path))
            with mock.patch.object(updater.requests, "get", return_value=ctx), \
                 mock.patch.object(updater.tempfile, "NamedTemporaryFile") as mock_ntf:
                mock_ntf.return_value.__enter__.return_value = fh
                try:
                    dl.run()
                finally:
                    raw.close()
            written = bin_path.read_bytes()
        self.assertEqual(rec.args_for("finished"), [(True, "", str(bin_path))])
        self.assertEqual(written, b"abcdef")
        # progress reported at least once (Connecting + per-chunk).
        self.assertGreaterEqual(len(rec.args_for("progress")), 1)

    def test_finished_failure_unlinks_partial(self):
        rec = _Recorder()
        rel = updater.FwUpReleaseInfo("PolyKybd-fw-v0.9.0", "0.9.0",
                                      "https://example.com/fw.bin", "", "html", "")
        dl = updater.FwUpDownloader(
            rel,
            on_progress=rec.make("progress"),
            on_finished=rec.make("finished"),
        )
        with tempfile.TemporaryDirectory() as td:
            bin_path = Path(td) / "fw.bin"
            raw = open(bin_path, "wb")
            fh = _NamedFile(raw, str(bin_path))
            with mock.patch.object(updater.requests, "get",
                                   side_effect=requests.ConnectionError("nope")), \
                 mock.patch.object(updater.tempfile, "NamedTemporaryFile") as mock_ntf:
                mock_ntf.return_value.__enter__.return_value = fh
                try:
                    dl.run()
                finally:
                    raw.close()
            ok, err, path = rec.args_for("finished")[0]
            self.assertFalse(ok)
            self.assertEqual(path, "")
            self.assertIn("nope", err)
            self.assertFalse(bin_path.exists(), "partial download must be unlinked")


if __name__ == "__main__":
    unittest.main()
