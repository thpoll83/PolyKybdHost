"""Tests for the WinCompose installer resolution (Qt-free, no network).

Only the pure decision logic is covered — asset picking, the "no release / no
installer" outcome that makes the tray fall back to the browser, and that a
non-Windows launch is refused rather than attempted.
"""
import unittest
from unittest import mock

from polyhost.services import wincompose_install as wc


BASE = "https://github.com/thpoll83/wincompose/releases/download/v0.9.16"


class PickInstallerAssetTest(unittest.TestCase):
    def test_picks_the_setup_exe(self):
        urls = [f"{BASE}/WinCompose-0.9.16.zip",
                f"{BASE}/WinCompose-Setup-0.9.16.exe",
                f"{BASE}/SHA256SUMS"]
        self.assertEqual(wc.pick_installer_asset(urls), f"{BASE}/WinCompose-Setup-0.9.16.exe")

    def test_setup_match_is_case_insensitive(self):
        urls = [f"{BASE}/wincompose-setup-0.9.16.exe"]
        self.assertEqual(wc.pick_installer_asset(urls), urls[0])

    def test_never_picks_the_portable_zip(self):
        """The portable .zip needs no installing — offering it would be wrong."""
        self.assertIsNone(wc.pick_installer_asset([f"{BASE}/WinCompose-0.9.16.zip"]))

    def test_falls_back_to_any_exe_when_none_says_setup(self):
        """A renamed installer should still work rather than silently vanish."""
        urls = [f"{BASE}/SHA256SUMS", f"{BASE}/WinCompose-Installer.exe"]
        self.assertEqual(wc.pick_installer_asset(urls), f"{BASE}/WinCompose-Installer.exe")

    def test_no_assets_at_all(self):
        self.assertIsNone(wc.pick_installer_asset([]))


class FindInstallerTest(unittest.TestCase):
    def test_no_release_returns_none(self):
        """Before the first release exists the tray must fall back to the browser,
        not report an error."""
        with mock.patch.object(wc, "_latest_tag_via_web", return_value=None):
            self.assertIsNone(wc.find_installer())

    def test_release_without_installer_asset_returns_none(self):
        with mock.patch.object(wc, "_latest_tag_via_web", return_value="v0.9.16"), \
             mock.patch.object(wc, "release_asset_urls", return_value=[f"{BASE}/notes.txt"]):
            self.assertIsNone(wc.find_installer())

    def test_resolves_tag_url_and_filename(self):
        with mock.patch.object(wc, "_latest_tag_via_web", return_value="v0.9.16"), \
             mock.patch.object(wc, "release_asset_urls",
                               return_value=[f"{BASE}/WinCompose-Setup-0.9.16.exe"]):
            info = wc.find_installer()
        self.assertEqual(info.tag, "v0.9.16")
        self.assertEqual(info.filename, "WinCompose-Setup-0.9.16.exe")
        self.assertTrue(info.url.endswith("WinCompose-Setup-0.9.16.exe"))


class LaunchInstallerTest(unittest.TestCase):
    def test_refuses_off_windows(self):
        with mock.patch.object(wc.sys, "platform", "linux"):
            ok, err = wc.launch_installer("/tmp/setup.exe")
        self.assertFalse(ok)
        self.assertIn("Windows", err)


class ParseAssetUrlsTest(unittest.TestCase):
    def test_extracts_download_links_from_the_expanded_assets_fragment(self):
        from polyhost.services.updater import parse_asset_urls
        html = ('<li><a href="/thpoll83/wincompose/releases/download/v1/A-Setup.exe">a</a></li>'
                '<li><a href="/thpoll83/wincompose/releases/tag/v1">not an asset</a></li>')
        self.assertEqual(
            parse_asset_urls(html),
            ["https://github.com/thpoll83/wincompose/releases/download/v1/A-Setup.exe"])


if __name__ == "__main__":
    unittest.main()
