"""services/gnome_extension.py on a temporary data folder, with a fake gsettings,
gdbus and download: no GNOME and no network."""
import hashlib
import subprocess
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from polyhost.services import gnome_extension as ge

# The pinned files' content is not in this repository; the tests pin their own
# bytes by patching EXTENSION_FILES.
FILES = {"extension.js": b"export default class X { enable() {} disable() {} }\n",
         "metadata.json": b'{"uuid": "window-reporter@polykybd.org"}\n'}
PINS = {name: hashlib.sha256(data).hexdigest() for name, data in FILES.items()}


class FakeGnome:
    """gsettings and gdbus, keyed on the command line."""

    def __init__(self, enabled=None, disabled=None, user_off=False, writable=True,
                 active=False, gsettings=True, gdbus=True):
        self.values = {ge.KEY_ENABLED: ge.format_strv(enabled or []),
                       ge.KEY_DISABLED: ge.format_strv(disabled or []) if disabled
                       else "@as []",
                       ge.KEY_USER_OFF: "true" if user_off else "false"}
        self.writable = writable
        self.active = active
        self.gsettings = gsettings
        self.gdbus = gdbus
        self.calls = []

    def __call__(self, cmd, **_kw):
        self.calls.append(cmd)
        if cmd[0] == "gsettings":
            if not self.gsettings:
                raise FileNotFoundError("gsettings")
            verb, schema, key = cmd[1:4]
            assert schema == ge.SCHEMA
            if verb == "get":
                return subprocess.CompletedProcess(cmd, 0, self.values[key] + "\n", "")
            if verb == "set":
                self.values[key] = cmd[4]
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if verb == "writable":
                return subprocess.CompletedProcess(cmd, 0, "true\n" if self.writable
                                                   else "false\n", "")
        if cmd[0] == "gdbus":
            if not self.gdbus:
                raise FileNotFoundError("gdbus")
            return subprocess.CompletedProcess(cmd, 0 if self.active else 1, "", "")
        raise AssertionError(cmd)

    def enabled(self):
        return ge.parse_strv(self.values[ge.KEY_ENABLED])


class GnomeExtensionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.env = {"XDG_DATA_HOME": self._tmp.name, "XDG_SESSION_TYPE": "wayland"}
        self.folder = Path(self._tmp.name) / "gnome-shell" / "extensions" / ge.UUID
        patcher = mock.patch.object(ge, "EXTENSION_FILES", PINS)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.fetched = []

    def fetch(self, url):
        self.fetched.append(url)
        return FILES[url.rsplit("/", 1)[1]]

    def test_is_gnome(self):
        for desktop in ("GNOME", "ubuntu:GNOME", "GNOME-Classic:GNOME"):
            self.assertTrue(ge.is_gnome({"XDG_CURRENT_DESKTOP": desktop}, "linux"), desktop)
        for desktop in ("KDE", "XFCE", "", "Unity"):
            self.assertFalse(ge.is_gnome({"XDG_CURRENT_DESKTOP": desktop}, "linux"), desktop)
        self.assertFalse(ge.is_gnome({"XDG_CURRENT_DESKTOP": "GNOME"}, "darwin"))

    def test_strv_round_trip(self):
        for values in ([], ["a@b.org"], ["it's", "back\\slash", "ding@rastersoft.com"]):
            self.assertEqual(ge.parse_strv(ge.format_strv(values)), values)
        self.assertEqual(ge.parse_strv("@as []"), [])
        with self.assertRaises(ValueError):
            ge.parse_strv("['a', 3]")

    def test_urls_use_the_pinned_commit(self):
        self.assertEqual(ge.file_url("metadata.json"),
                         "https://raw.githubusercontent.com/thpoll83/gnome-wayland-winreader/"
                         f"{ge.EXTENSION_COMMIT}/metadata.json")
        self.assertRegex(ge.EXTENSION_COMMIT, r"^[0-9a-f]{40}$")

    def test_status_of_a_missing_extension_with_user_extensions_off(self):
        # The 2026-11-25 machine: no folder, user extensions switched off.
        gnome = FakeGnome(enabled=["ding@rastersoft.com"], user_off=True)
        st = ge.status(env=self.env, run=gnome)
        self.assertEqual((st.files, st.enabled, st.user_off, st.user_off_writable, st.active),
                         ("missing", False, True, True, False))
        self.assertEqual(st.folder, self.folder)
        self.assertTrue(st.wayland)

    def test_install_writes_the_pinned_files_and_enables(self):
        gnome = FakeGnome(enabled=["ding@rastersoft.com"], disabled=[ge.UUID])
        results = ge.install(env=self.env, run=gnome, fetch=self.fetch)
        self.assertEqual([(r.message, r.changed) for r in results], [(ge.MSG_INSTALLED, True)])
        for name, data in FILES.items():
            self.assertEqual((self.folder / name).read_bytes(), data)
        self.assertEqual(gnome.enabled(), ["ding@rastersoft.com", ge.UUID])
        self.assertEqual(ge.parse_strv(gnome.values[ge.KEY_DISABLED]), [])
        # User extensions are a separate choice: not touched.
        self.assertEqual(gnome.values[ge.KEY_USER_OFF], "false")
        self.assertEqual(ge.status(env=self.env, run=gnome).files, "current")

    def test_install_refuses_a_file_that_does_not_match_the_pin(self):
        gnome = FakeGnome()

        def tampered(url):
            data = self.fetch(url)
            return data + b"// changed\n" if url.endswith("extension.js") else data
        results = ge.install(env=self.env, run=gnome, fetch=tampered)
        self.assertEqual(results[0].message, ge.MSG_FAILED)
        self.assertIn("SHA-256", results[0].detail)
        # Neither file is written, and GNOME's settings are unchanged.
        self.assertFalse(self.folder.exists())
        self.assertEqual(gnome.enabled(), [])

    def test_install_refuses_an_oversized_answer(self):
        results = ge.install(env=self.env, run=FakeGnome(),
                             fetch=lambda url: b"x" * (ge.MAX_FILE_BYTES + 1))
        self.assertEqual(results[0].message, ge.MSG_FAILED)
        self.assertFalse(self.folder.exists())

    def test_install_again_downloads_nothing(self):
        gnome = FakeGnome()
        ge.install(env=self.env, run=gnome, fetch=self.fetch)
        self.fetched.clear()
        results = ge.install(env=self.env, run=gnome, fetch=self.fetch)
        self.assertEqual([(r.message, r.changed) for r in results],
                         [(ge.MSG_UP_TO_DATE, False)])
        self.assertEqual(self.fetched, [])
        self.assertEqual(gnome.enabled(), [ge.UUID])

    def test_install_replaces_another_version(self):
        self.folder.mkdir(parents=True)
        (self.folder / "extension.js").write_text("old")
        (self.folder / "metadata.json").write_bytes(FILES["metadata.json"])
        gnome = FakeGnome()
        self.assertEqual(ge.status(env=self.env, run=gnome).files, "other")
        results = ge.install(env=self.env, run=gnome, fetch=self.fetch)
        self.assertEqual(results[0].message, ge.MSG_UPDATED)
        self.assertEqual((self.folder / "extension.js").read_bytes(), FILES["extension.js"])

    def test_user_extensions_only_when_asked(self):
        gnome = FakeGnome(user_off=True)
        results = ge.install(extension=False, user_extensions=True, env=self.env, run=gnome,
                             fetch=self.fetch)
        self.assertEqual([r.message for r in results], [ge.MSG_USER_ON])
        self.assertEqual(gnome.values[ge.KEY_USER_OFF], "false")
        self.assertEqual(self.fetched, [])

    def test_remove_deletes_only_its_files_and_the_uuid(self):
        gnome = FakeGnome(enabled=["ding@rastersoft.com"], user_off=False)
        ge.install(env=self.env, run=gnome, fetch=self.fetch)
        (self.folder / "notes.txt").write_text("the user's file")
        results = ge.remove(env=self.env, run=gnome)
        self.assertEqual(results[0].message, ge.MSG_REMOVED)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["notes.txt"])
        self.assertEqual(gnome.enabled(), ["ding@rastersoft.com"])
        (self.folder / "notes.txt").unlink()
        self.assertEqual(ge.remove(env=self.env, run=gnome)[0].message, ge.MSG_NOT_INSTALLED)
        self.assertFalse(self.folder.exists())

    def test_remove_leaves_user_extensions_on(self):
        gnome = FakeGnome()
        ge.install(env=self.env, run=gnome, fetch=self.fetch)
        ge.remove(env=self.env, run=gnome)
        self.assertEqual(gnome.values[ge.KEY_USER_OFF], "false")
        self.assertFalse(any(c[:2] == ["gsettings", "set"] and c[3] == ge.KEY_USER_OFF
                             for c in gnome.calls))

    def test_status_without_gsettings_or_gdbus(self):
        st = ge.status(env=self.env, run=FakeGnome(gsettings=False, gdbus=False))
        self.assertEqual((st.files, st.enabled, st.user_off, st.active),
                         ("missing", None, None, None))
        self.assertIn("gsettings", st.error)


if __name__ == "__main__":
    unittest.main()
