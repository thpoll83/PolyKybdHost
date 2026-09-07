"""os_theme — what the desktop says, and what the app does with it.

The per-platform readers are mocked (this container is one desktop, and the
Windows path needs `winreg`), so what these pin is the shape the callers depend
on: **never raise**, `None` when the desktop does not answer, and a `resolve`
rule where an explicit setting wins, "auto" follows the desktop, and anything
unresolvable falls back to dark — the app's historical look, so a failed
detection changes nothing rather than flipping somebody's tray.
"""
import subprocess
import unittest
import unittest.mock as mock

from polyhost.services import os_theme
from polyhost.services.os_theme import THEME_AUTO, THEME_DARK, THEME_LIGHT


class TestResolve(unittest.TestCase):
    def test_an_explicit_setting_beats_the_desktop(self):
        self.assertEqual(os_theme.resolve_theme(THEME_LIGHT, THEME_DARK), THEME_LIGHT)
        self.assertEqual(os_theme.resolve_theme(THEME_DARK, THEME_LIGHT), THEME_DARK)

    def test_auto_follows_the_desktop(self):
        self.assertEqual(os_theme.resolve_theme(THEME_AUTO, THEME_LIGHT), THEME_LIGHT)
        self.assertEqual(os_theme.resolve_theme(THEME_AUTO, THEME_DARK), THEME_DARK)

    def test_a_desktop_that_does_not_answer_falls_back_to_dark(self):
        self.assertEqual(os_theme.resolve_theme(THEME_AUTO, None), os_theme.FALLBACK)
        self.assertEqual(os_theme.FALLBACK, THEME_DARK)

    def test_an_unset_or_nonsense_setting_is_auto(self):
        for value in (None, "", "  ", "Auto", "AUTO", "sepia", 7):
            self.assertEqual(os_theme.resolve_theme(value, THEME_LIGHT), THEME_LIGHT,
                             repr(value))

    def test_case_and_padding_do_not_pin_the_theme_wrong(self):
        self.assertEqual(os_theme.resolve_theme(" Light ", THEME_DARK), THEME_LIGHT)


class TestDetectionShape(unittest.TestCase):
    def setUp(self):
        os_theme.forget_detected()

    def tearDown(self):
        os_theme.forget_detected()

    def test_a_platform_reader_that_raises_is_not_an_error(self):
        with mock.patch.object(os_theme, "_detect_linux", side_effect=RuntimeError("boom")), \
             mock.patch.object(os_theme.sys, "platform", "linux"):
            self.assertIsNone(os_theme.detect_os_theme(use_cache=False))

    def test_the_answer_is_cached_between_calls(self):
        with mock.patch.object(os_theme, "_detect_linux",
                               return_value=THEME_LIGHT) as reader, \
             mock.patch.object(os_theme.sys, "platform", "linux"):
            self.assertEqual(os_theme.detect_os_theme(), THEME_LIGHT)
            self.assertEqual(os_theme.detect_os_theme(), THEME_LIGHT)
            self.assertEqual(reader.call_count, 1)
            os_theme.forget_detected()
            self.assertEqual(os_theme.detect_os_theme(), THEME_LIGHT)
            self.assertEqual(reader.call_count, 2)

    def test_use_cache_false_always_asks_again(self):
        with mock.patch.object(os_theme, "_detect_linux",
                               return_value=THEME_DARK) as reader, \
             mock.patch.object(os_theme.sys, "platform", "linux"):
            os_theme.detect_os_theme(use_cache=False)
            os_theme.detect_os_theme(use_cache=False)
            self.assertEqual(reader.call_count, 2)


class TestCommandRunner(unittest.TestCase):
    """`_run` is what makes the mac/Linux readers unable to raise."""

    def test_a_missing_command_is_none(self):
        with mock.patch.object(os_theme.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(os_theme._run(["nope"]))

    def test_a_timeout_is_none(self):
        err = subprocess.TimeoutExpired(cmd="x", timeout=2)
        with mock.patch.object(os_theme.subprocess, "run", side_effect=err):
            self.assertIsNone(os_theme._run(["slow"]))

    def test_a_nonzero_exit_is_none(self):
        done = subprocess.CompletedProcess(args=[], returncode=1, stdout="dark", stderr="")
        with mock.patch.object(os_theme.subprocess, "run", return_value=done):
            self.assertIsNone(os_theme._run(["failing"]))


class TestMacos(unittest.TestCase):
    def test_the_key_being_absent_means_light(self):
        # `defaults read -g AppleInterfaceStyle` FAILS in light mode — the key
        # only exists while dark mode is on, so a None here is an answer.
        with mock.patch.object(os_theme, "_run", return_value=None):
            self.assertEqual(os_theme._detect_macos(), THEME_LIGHT)

    def test_dark_is_dark(self):
        with mock.patch.object(os_theme, "_run", return_value="Dark"):
            self.assertEqual(os_theme._detect_macos(), THEME_DARK)


class TestLinux(unittest.TestCase):
    def test_the_colour_scheme_preference_wins(self):
        with mock.patch.object(os_theme, "_run", return_value="'prefer-dark'"):
            self.assertEqual(os_theme._detect_linux(), THEME_DARK)
        with mock.patch.object(os_theme, "_run", return_value="'prefer-light'"):
            self.assertEqual(os_theme._detect_linux(), THEME_LIGHT)

    def test_default_falls_through_to_the_theme_name(self):
        answers = {"color-scheme": "'default'", "gtk-theme": "'Adwaita-dark'"}

        def fake(argv):
            return answers[argv[-1]]

        with mock.patch.object(os_theme, "_run", side_effect=fake):
            self.assertEqual(os_theme._detect_linux(), THEME_DARK)
        answers["gtk-theme"] = "'Adwaita'"
        with mock.patch.object(os_theme, "_run", side_effect=fake):
            self.assertEqual(os_theme._detect_linux(), THEME_LIGHT)

    def test_no_gsettings_at_all_is_unknown(self):
        with mock.patch.object(os_theme, "_run", return_value=None):
            self.assertIsNone(os_theme._detect_linux())


class TestWindows(unittest.TestCase):
    """AppsUseLightTheme is 1 for light, 0 for dark — the inversion is the whole
    reading, and getting it backwards is a silent flip of everyone's tray."""

    def _with_registry(self, value):
        winreg = mock.MagicMock()
        winreg.QueryValueEx.return_value = (value, 4)
        return mock.patch.dict("sys.modules", {"winreg": winreg})

    def test_one_is_light_and_zero_is_dark(self):
        with self._with_registry(1):
            self.assertEqual(os_theme._detect_windows(), THEME_LIGHT)
        with self._with_registry(0):
            self.assertEqual(os_theme._detect_windows(), THEME_DARK)

    def test_a_missing_value_is_unknown_not_a_crash(self):
        winreg = mock.MagicMock()
        winreg.QueryValueEx.side_effect = OSError("no such value")
        with mock.patch.dict("sys.modules", {"winreg": winreg}):
            self.assertIsNone(os_theme._detect_windows())

    def test_no_winreg_module_is_unknown(self):
        with mock.patch.dict("sys.modules", {"winreg": None}):
            self.assertIsNone(os_theme._detect_windows())


if __name__ == "__main__":
    unittest.main()
