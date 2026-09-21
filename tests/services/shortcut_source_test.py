"""Picking a shortcut backend, and what happens on a platform that has none.

The backends themselves cannot be exercised here — there is no accessibility bus
in this container and no Windows at all — so what is pinned is the SURROUNDING
contract: which platform gets which backend, that an unusable one is refused
rather than returned, and that nothing raises out of any of it.

⚠️ That last one matters more than it looks. `harvest()` runs on a background
thread for a cosmetic feature, and an escape there reaches
`threading.excepthook`, which this app routes into crash_log.txt — so a dead
accessibility bridge would put a spurious crash in every later problem report.
"""

import builtins
import sys
import unittest
from unittest.mock import Mock, patch

from polyhost.services import shortcut_source as ss


class BackendChoiceTest(unittest.TestCase):

    def test_each_platform_gets_its_own_backend(self):
        for platform, expected in (("linux", "atspi"), ("win32", "uia"),
                                   ("freebsd13", "atspi")):
            with patch.object(ss.sys, "platform", platform):
                self.assertEqual(ss.backend_name(), expected)

    def test_macOS_now_HAS_a_backend(self):
        """⚠️ INVERTED. This used to assert the opposite -- `backend_name() == ""`
        and a `pick()` of None -- and the docstring explaining why ("a third
        unrelated interface, needing pyobjc plus a consent prompt neither other
        platform has") was a correct description of the COST, not of an
        impossibility. The AX backend landed, so the cost is paid and the
        assertion flips.

        `pick()` is deliberately NOT asserted here: it answers None on this
        machine because pyobjc is absent, and it would answer a module on a Mac
        with the permission granted. Asserting either would pin the environment
        rather than the wiring. `_backend_module` is the wiring, and the macOS
        test file pins it for all three platforms at once."""
        with patch.object(ss.sys, "platform", "darwin"):
            self.assertEqual(ss.backend_name(), "macos")

    def test_an_UNAVAILABLE_backend_is_refused_rather_than_returned(self):
        """⚠️ The import succeeds on a machine with no accessibility bus at all,
        so the availability probe is part of the pick — otherwise "the bridge is
        not running" and "this app exposes nothing" would be indistinguishable,
        which is exactly the distinction the log line has to draw."""
        fake = type("B", (), {"available": staticmethod(lambda: False)})()
        with patch.dict("sys.modules",
                        {"polyhost.services.shortcut_source.atspi": fake}), \
             patch.object(ss.sys, "platform", "linux"):
            self.assertIsNone(ss.pick())

    def test_an_import_that_raises_is_no_backend_not_a_crash(self):
        with patch.object(ss.sys, "platform", "linux"), \
             patch("builtins.__import__", side_effect=ImportError("no gi")):
            self.assertIsNone(ss.pick())


class UnavailableReasonTest(unittest.TestCase):
    """Three causes that need OPPOSITE fixes, told apart rather than flattened."""

    def test_macOS_names_ITS_OWN_cause_rather_than_the_platform(self):
        """⚠️ INVERTED with the one above, and this is the half that matters.

        It used to require the word "platform" in the reason, because the only
        true thing to say about macOS was that it had no backend. Now the reason
        has to name a cause the user can ACT on -- a missing pyobjc or an
        ungranted permission -- and "this platform has no accessibility backend"
        would be the flat sentence the whole `unavailable_reason` API exists to
        replace. So the test is the opposite: the word must be ABSENT."""
        with patch.object(ss.sys, "platform", "darwin"):
            reason = ss.unavailable_reason()
        self.assertIsNotNone(reason)
        self.assertNotIn("this platform has no accessibility backend", reason)

    def test_a_VENV_whose_VERSION_differs_is_told_to_be_REBUILT(self):
        # ⚠️ Reaching this at all means `_import_gi`'s rescue already failed, and
        # it can only fail one way: the distro's compiled `_gi` is built for a
        # different Python minor version. So the old advice -- "set
        # include-system-site-packages" -- would NOT have helped, and saying it
        # would send the reader down a path that cannot work.
        from polyhost.services.shortcut_source import atspi
        with patch.object(atspi, "_import_gi", side_effect=ImportError("No module named 'gi'")), \
             patch("glob.glob", return_value=["/usr/lib/python3/dist-packages/gi/_gi.cpython-312-x.so"]), \
             patch.object(sys, "prefix", "/home/u/.venv"), \
             patch.object(sys, "base_prefix", "/usr"):
            reason = atspi.unavailable_reason()
        self.assertIn("virtualenv", reason)
        self.assertIn("recreate it", reason)
        self.assertNotIn("include-system-site-packages", reason)

    def test_the_message_NAMES_BOTH_VERSIONS(self):
        # "a different Python" is not actionable; "built for 3.12, this is 3.11"
        # is. The version is already in the filename -- read it rather than
        # leaving the reader to find it.
        from polyhost.services.shortcut_source import atspi
        with patch.object(atspi, "_import_gi", side_effect=ImportError("boom")), \
             patch("glob.glob", return_value=["/usr/lib/python3/dist-packages/gi/_gi.cpython-312-x.so"]), \
             patch("sysconfig.get_config_var", return_value=".cpython-311-x.so"), \
             patch.object(sys, "prefix", "/usr"), \
             patch.object(sys, "base_prefix", "/usr"):
            reason = atspi.unavailable_reason()
        self.assertIn("3.12", reason)
        self.assertIn("3.11", reason)
        self.assertNotIn("not installed", reason)

    def test_PyGObject_genuinely_absent_IS_called_missing(self):
        from polyhost.services.shortcut_source import atspi
        with patch.object(atspi, "_import_gi", side_effect=ImportError("boom")), \
             patch("glob.glob", return_value=[]):
            self.assertIn("not installed", atspi.unavailable_reason())

    def test_a_WORKING_backend_gives_no_reason_at_all(self):
        # ⚠️ Patch the ATTRIBUTE on the package, not `sys.modules`: the function
        # does `from polyhost.services.shortcut_source import atspi`, and once
        # the submodule has been imported once that resolves to the package
        # attribute, so a sys.modules patch silently hands back the real module.
        backend = Mock(unavailable_reason=lambda: None)
        with patch.object(ss, "backend_name", return_value="atspi"), \
             patch.object(ss, "atspi", backend, create=True):
            self.assertIsNone(ss.unavailable_reason())

    def test_a_backend_WITHOUT_the_reason_api_still_answers(self):
        # The uia backend predates it; reporting it as working would be worse
        # than a vague sentence.
        backend = Mock(spec=["available"])
        backend.available.return_value = False
        with patch.object(ss, "backend_name", return_value="uia"), \
             patch.object(ss, "uia", backend, create=True):
            self.assertIn("unusable", ss.unavailable_reason())


class SystemSiteRescueTest(unittest.TestCase):
    """A venv is the standard way to run this app, and PyGObject cannot go in one."""

    def setUp(self):
        from polyhost.services.shortcut_source import atspi
        self.atspi = atspi

    def test_the_dir_is_taken_only_when_its_gi_MATCHES_this_interpreter(self):
        # ⚠️ The whole safety argument. `gi` is a COMPILED extension built for
        # one Python minor version; importing 3.12's `_gi.cpython-312-*.so` into
        # 3.11 fails with a circular-import error naming neither cause.
        with patch("sysconfig.get_config_var", return_value=".cpython-312-x86_64-linux-gnu.so"), \
             patch("os.path.exists", lambda p: p.endswith(
                 "/gi/_gi.cpython-312-x86_64-linux-gnu.so")):
            self.assertEqual(self.atspi._system_site_dir(),
                             "/usr/lib/python3/dist-packages")

    def test_a_MISMATCHED_gi_is_refused_rather_than_imported(self):
        with patch("sysconfig.get_config_var", return_value=".cpython-311-x86_64-linux-gnu.so"), \
             patch("os.path.exists", lambda p: p.endswith(
                 "/gi/_gi.cpython-312-x86_64-linux-gnu.so")):
            self.assertIsNone(self.atspi._system_site_dir())

    def test_the_rescue_leaves_sys_path_CLEAN(self):
        # Leaving the distro's dist-packages on the path would shadow the venv's
        # own packages for the rest of the process.
        #
        # ⚠️ The directory has to be one that is NOT already on `sys.path`, and
        # the obvious choice is not: this container really does carry
        # /usr/lib/python3/dist-packages, so the first version of this test
        # compared a path against itself and PASSED with the removal deleted.
        # Caught by the mutation sweep, not by the test.
        marker = "/nonexistent/rescue-marker-dist-packages"
        self.assertNotIn(marker, sys.path, "the fixture must be able to fail")
        before = list(sys.path)
        fake = Mock()
        real_import = builtins.__import__

        def only_gi_needs_the_path(name, *a, **k):
            if name == "gi" and marker not in sys.path:
                raise ImportError("No module named 'gi'")
            if name == "gi":
                return fake
            return real_import(name, *a, **k)

        with patch.object(self.atspi, "_system_site_dir", return_value=marker), \
             patch.object(builtins, "__import__", only_gi_needs_the_path):
            self.assertIs(self.atspi._import_gi(), fake)
        self.assertNotIn(marker, sys.path)
        self.assertEqual(sys.path, before)

    def test_with_NO_matching_dir_the_original_ImportError_survives(self):
        # The caller turns it into the reason, so swallowing it would lose the
        # message entirely.
        real_import = builtins.__import__

        def no_gi(name, *a, **k):
            if name == "gi":
                raise ImportError("No module named 'gi'")
            return real_import(name, *a, **k)

        with patch.object(self.atspi, "_system_site_dir", return_value=None), \
             patch.object(builtins, "__import__", no_gi):
            with self.assertRaises(ImportError):
                self.atspi._import_gi()


class BusProbeTest(unittest.TestCase):
    """`Atspi.get_desktop()` ABORTS the process when the bus is down."""

    def setUp(self):
        from polyhost.services.shortcut_source import atspi
        self.atspi = atspi
        self.atspi._BUS_OK = None

    def tearDown(self):
        self.atspi._BUS_OK = None

    def test_a_failed_init_is_asked_ONCE_and_remembered(self):
        # ⚠️ `Atspi.init()` is not idempotent as a probe: the first call returns
        # 2 when the bus is unreachable, and a SECOND returns 1 ("already
        # initialised") even though it failed. Re-probing therefore reports
        # success and the next get_desktop() kills the process with SIGTRAP --
        # measured, one call after the one that answered correctly.
        fake = Mock()
        fake.init.side_effect = [2, 1, 1, 1]
        self.assertFalse(self.atspi._bus_ok(fake))
        for _ in range(3):
            self.assertFalse(self.atspi._bus_ok(fake))
        self.assertEqual(fake.init.call_count, 1)

    def test_get_desktop_is_NEVER_reached_when_the_bus_is_down(self):
        # ⚠️ The crash guard, and the reason the whole probe was rewritten.
        # `Atspi.get_desktop()` does not raise when the bus is unreachable -- it
        # g_error()s, which calls abort(). SIGTRAP, exit 133, no Python
        # exception. It runs on the fetcher's background thread inside the tray
        # app, so reaching it takes the whole application down for a cosmetic
        # feature. Measured 2026-09-18 in a venv with no system site-packages.
        fake = Mock()
        fake.init.return_value = 2
        fake.get_desktop.side_effect = AssertionError(
            "get_desktop() would have ABORTED the process here")
        with patch.object(self.atspi, "_import_gi", return_value=Mock()), \
             patch.object(self.atspi, "_atspi", return_value=fake):
            reason = self.atspi.unavailable_reason()
        self.assertIn("accessibility bus is not running", reason)
        fake.get_desktop.assert_not_called()

    def test_a_working_bus_reads_as_ok(self):
        fake = Mock()
        fake.init.return_value = 0
        self.assertTrue(self.atspi._bus_ok(fake))

    def test_ALREADY_INITIALISED_is_success_not_failure(self):
        fake = Mock()
        fake.init.return_value = 1
        self.assertTrue(self.atspi._bus_ok(fake))


class HarvestTest(unittest.TestCase):

    def test_no_backend_harvests_nothing(self):
        with patch.object(ss, "pick", return_value=None):
            self.assertEqual(ss.harvest("mousepad"), [])

    def test_a_backend_that_RAISES_harvests_nothing(self):
        boom = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app, reason=None, pid=None: (_ for _ in ()).throw(OSError("bus gone")))})()
        with patch.object(ss, "pick", return_value=boom):
            self.assertEqual(ss.harvest("mousepad"), [])

    def test_a_backend_that_RAISES_past_its_guard_SAYS_so_and_asks_to_retry(self):
        """⚠️ Not "the app exposes no accelerators". Every backend promises not
        to raise, so reaching this handler is itself the finding — and it says
        nothing about the app, so the empty answer must not be cached."""
        boom = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app, reason=None, pid=None: (_ for _ in ()).throw(OSError("bus gone")))})()
        reason = {}
        with patch.object(ss, "pick", return_value=boom):
            self.assertEqual(ss.harvest("mousepad", reason=reason), [])
        self.assertIn("past its own guard", reason["why"])
        self.assertIn("bus gone", reason["why"])
        self.assertTrue(reason["retry"])

    def test_a_working_backend_is_passed_the_app_name(self):
        seen = []
        ok = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app, reason=None, pid=None: seen.append(app) or ["shortcut"])})()
        with patch.object(ss, "pick", return_value=ok):
            self.assertEqual(ss.harvest("mousepad"), ["shortcut"])
        self.assertEqual(seen, ["mousepad"])

    def test_the_reason_dict_reaches_the_backend(self):
        """⚠️ The whole point, and a `lambda app:` fake hides it — the real
        backends now take `reason`, so a fake that does not is a TypeError
        swallowed by the guard above and every harvest silently returns []."""
        seen = []
        ok = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app, reason=None, pid=None: seen.append(reason) or [])})()
        mine = {}
        with patch.object(ss, "pick", return_value=ok):
            ss.harvest("mousepad", reason=mine)
        self.assertIs(seen[0], mine)

    def test_the_PID_reaches_the_backend(self):
        """⚠️ On macOS this is the difference between harvesting the app the
        caller named and harvesting whatever NSWorkspace last called frontmost —
        a value frozen on the fetcher's worker thread, measured in the field as
        every app but one refusing with a focus race that had not happened."""
        seen = {}
        ok = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app, reason=None, pid=None: seen.update(pid=pid) or [])})()
        with patch.object(ss, "pick", return_value=ok):
            ss.harvest("mousepad", pid=4242)
        self.assertEqual(seen["pid"], 4242)

    def test_NO_pid_is_passed_as_None(self):
        """The probe and the forwarded paths have none; the backend then falls
        back to frontmost, which is correct off the worker thread."""
        seen = {}
        ok = type("B", (), {"shortcuts_for_app": staticmethod(
            lambda app, reason=None, pid=None: seen.update(pid=pid) or [])})()
        with patch.object(ss, "pick", return_value=ok):
            ss.harvest("mousepad")
        self.assertIsNone(seen["pid"])

    def test_ALL_THREE_backends_accept_the_reason_parameter(self):
        """One signature, so `harvest()` needs no branch — and a backend that
        lost the parameter would be a TypeError the guard turns into a silent
        empty harvest on that platform only, which nothing else here would
        catch."""
        import inspect
        from polyhost.services.shortcut_source import atspi, macos, uia
        for mod in (atspi, macos, uia):
            params = inspect.signature(mod.shortcuts_for_app).parameters
            self.assertIn("reason", params, mod.__name__)
            self.assertIn("pid", params, mod.__name__)

    def test_this_container_really_has_none(self):
        """Not a tautology: it is the state every other test here assumes, and
        it is what makes the Phase-2 path unexercisable offline. If this ever
        starts failing, the harvest CAN be tested end to end and should be."""
        self.assertIsNone(ss.pick())


class ProbeParityTest(unittest.TestCase):
    """The probe is a CLI over this package, not a second implementation."""

    def test_the_accelerator_formats_agree_on_one_chord(self):
        """Both backends fold L/R modifiers onto one nibble, so the same chord
        has to arrive identically however it was spelled."""
        gtk = ss.parse_accel("<Control><Shift>s")
        win = ss.parse_win_accel("Ctrl+Shift+S")
        self.assertEqual((gtk.mods, gtk.hid), (win.mods, win.hid))

    def test_a_localized_windows_string_still_parses(self):
        de = ss.parse_win_accel("Strg+Umschalt+S")
        self.assertEqual((de.mods, de.hid), (0x03, 0x16))

    def test_an_unknown_modifier_is_REFUSED_not_read_as_a_key(self):
        """Reporting 'Wibble+S' as the single key "Wibble+S" would be worse than
        reporting nothing."""
        self.assertIsNone(ss.parse_win_accel("Wibble+S"))

    def test_the_system_menu_chord_is_NOT_an_app_shortcut(self):
        """`Alt+Space 'System'` is the window manager's, on every window.

        Field daemon_log.txt (2026-09-14): Calculator and Photos each reported it
        as their ONLY harvested shortcut, so the diagnostic claimed "1
        shortcut(s) harvested" for two apps that expose none.
        """
        accel = ss.parse_win_accel("Alt+Space")
        self.assertTrue(ss.is_window_manager_chord(accel.mods, accel.keysym))

    def test_close_window_is_the_same_case(self):
        accel = ss.parse_win_accel("Alt+F4")
        self.assertTrue(ss.is_window_manager_chord(accel.mods, accel.keysym))

    def test_an_ordinary_chord_on_the_same_KEY_survives(self):
        """The rule is the whole chord, not the key: Ctrl+Space is a real
        binding in plenty of apps and must not be swept up with Alt+Space."""
        for text in ("Ctrl+Space", "Shift+Space", "Ctrl+Alt+Space", "Ctrl+F4"):
            accel = ss.parse_win_accel(text)
            self.assertFalse(ss.is_window_manager_chord(accel.mods, accel.keysym),
                             f"{text} was dropped as a window-manager chord")

    def test_the_rule_keys_on_the_CHORD_and_never_on_the_LABEL(self):
        """"System" is localized -- German reports "Systemmenü" -- so a label
        test would drop these on an English desktop and nowhere else. The
        signature takes no label at all, which is what pins that."""
        import inspect
        params = inspect.signature(ss.is_window_manager_chord).parameters
        self.assertEqual(list(params), ["mods", "keysym"])
        de = ss.parse_win_accel("Alt+Leertaste")   # unknown key token, still Alt
        self.assertTrue(de is None or de.mods == ss.MOD_ALT)


if __name__ == "__main__":
    unittest.main()
