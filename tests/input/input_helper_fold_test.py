"""The shared base class's compatible-layout fallback, and the three maps.

This is the path Windows and GNOME take: neither overrides `set_language`, so
both cycle the OS with keystrokes and both depend on the fallback added here.
KDE and macOS have real selectors and override it entirely — they read the
same `self.comp`, from their own code."""

import unittest

from polyhost.input.input_helper import InputHelper
from polyhost.lang.lang_compat import LangComp


class FakeCycler(InputHelper):
    """An OS whose layout list is fixed and whose Win/Super+Space works.

    `get_current_language` advances one step per call, which is what the real
    helper observes after each keypress — so `presses` counts how much the
    user would actually see the language indicator flicker."""

    def __init__(self, platform, installed, current=None):
        super().__init__(platform)
        self.installed = list(installed)
        self.cur = current or self.installed[0]
        self.reads = 0

    def get_languages(self):
        return self.installed

    def get_current_language(self):
        self.reads += 1
        if self.reads > 1:      # the first read is the state before any press
            i = self.installed.index(self.cur)
            self.cur = self.installed[(i + 1) % len(self.installed)]
        return True, self.cur


class DirectMatchTest(unittest.TestCase):
    """What already worked, and must keep working: folding within a language."""

    def test_the_exact_culture_is_found(self):
        ok, got = FakeCycler("windows", ["en-US", "de-DE"]).set_language("de", "DE")
        self.assertTrue(ok)
        self.assertEqual(got, "de-DE")

    def test_a_region_the_os_lacks_still_lands_on_its_language(self):
        # de-AT on a box with only de-DE. This is the two-character fallback
        # that has always been there, and is most likely what people remember
        # as "the compat file working on Windows" — it is not the file.
        ok, got = FakeCycler("windows", ["en-US", "de-DE"]).set_language("de", "AT")
        self.assertTrue(ok)
        self.assertEqual(got, "de-DE")


class CompatibleLayoutFallbackTest(unittest.TestCase):
    """What did not work: a language no OS ships a keyboard for."""

    def test_tahitian_folds_onto_french(self):
        h = FakeCycler("windows", ["en-US", "fr-FR"])
        ok, got = h.set_language("ty", "PF")
        self.assertTrue(ok, got)
        self.assertEqual(got, "fr-FR")

    def test_quechua_folds_onto_the_latin_american_layout(self):
        h = FakeCycler("windows", ["en-US", "es-MX"])
        ok, got = h.set_language("qu", "PE")
        self.assertTrue(ok, got)
        self.assertEqual(got, "es-MX")

    def test_basque_folds_onto_spanish(self):
        h = FakeCycler("windows", ["en-US", "es-ES"])
        ok, got = h.set_language("eu", "ES")
        self.assertTrue(ok, got)
        self.assertEqual(got, "es-ES")

    def test_northern_sami_takes_norwegian_before_the_danish_fold(self):
        h = FakeCycler("windows", ["en-US", "da-DK", "nb-NO"])
        ok, got = h.set_language("se", "NO")
        self.assertTrue(ok, got)
        self.assertEqual(got, "nb-NO")

    def test_gnome_gets_the_same_fallback(self):
        # GNOME does not override set_language either, and its helper used to
        # build a LangComp it never read.
        h = FakeCycler("linux", ["en-US", "fr-FR"])
        ok, got = h.set_language("ty", "PF")
        self.assertTrue(ok, got)
        self.assertEqual(got, "fr-FR")

    def test_a_fold_the_os_does_not_have_costs_no_keypresses(self):
        """Each attempt cycles the OS with real Win/Super+Space presses, which
        the user sees as the language indicator flickering. An alternative the
        machine does not have must not buy a round of them —
        `_set_language_direct` refuses before it touches the controller."""
        h = FakeCycler("windows", ["en-US"])
        ok, msg = h.set_language("qu", "PE")        # folds onto es-MX
        self.assertFalse(ok)
        self.assertIn("qu-PE", msg)
        self.assertEqual(h.reads, 0, "pressed keys for a layout that is absent")

    def test_a_helper_with_no_map_keeps_the_old_behaviour(self):
        h = FakeCycler(None, ["en-US"])
        self.assertIsNone(h.comp)
        ok, msg = h.set_language("ty", "PF")
        self.assertFalse(ok)
        self.assertIn("No compatible language", msg)

    def test_the_failure_names_what_was_asked_for_not_the_last_fold_tried(self):
        h = FakeCycler("windows", ["ja-JP"])
        ok, msg = h.set_language("ty", "PF")
        self.assertFalse(ok)
        self.assertIn("ty-PF", msg)


class HelperWiringTest(unittest.TestCase):
    """Which map each real helper loads.

    ⚠️ **Not checkable from the DATA**: the macOS and Windows maps currently
    hold identical values, so a helper wired to the wrong one behaves exactly
    the same today and diverges the first time the files differ. `LangComp`
    records its platform so this can be asserted at all."""

    def test_each_helper_loads_its_own_platforms_map(self):
        from polyhost.input.win_helper import WindowsInputHelper
        from polyhost.input.macos_helper import MacOSInputHelper
        from polyhost.input.linux_kde_helper import LinuxPlasmaHelper
        from polyhost.input.linux_gnome_helper import LinuxGnomeInputHelper
        for helper, platform in ((WindowsInputHelper(), "windows"),
                                 (MacOSInputHelper(), "macos"),
                                 (LinuxPlasmaHelper(), "linux"),
                                 (LinuxGnomeInputHelper(), "linux")):
            with self.subTest(helper=type(helper).__name__):
                self.assertIsNotNone(helper.comp, "no compatibility map loaded")
                self.assertEqual(helper.comp.platform, platform)

    def test_every_helper_has_a_logger(self):
        """`LinuxPlasmaHelper` did not call `super().__init__()` at all, so
        `self.log` was missing and each of its `except` paths raised
        AttributeError instead of logging — the same defect fixed for
        `MacOSInputHelper` in 9d74546."""
        from polyhost.input.win_helper import WindowsInputHelper
        from polyhost.input.macos_helper import MacOSInputHelper
        from polyhost.input.linux_kde_helper import LinuxPlasmaHelper
        from polyhost.input.linux_gnome_helper import LinuxGnomeInputHelper
        for helper in (WindowsInputHelper(), MacOSInputHelper(),
                       LinuxPlasmaHelper(), LinuxGnomeInputHelper()):
            with self.subTest(helper=type(helper).__name__):
                self.assertTrue(hasattr(helper, "log"))


class NativeWindowsPathTest(unittest.TestCase):
    """`WindowsInputHelper` OVERRIDES `set_language` when
    `dev_win_native_set_language` is on, so the inherited fallback is not
    reached unless the native path hands back to it.

    ⚠️ The first case below is not an edge case: a fold language has no LCID
    *by construction*. `locale.windows_locale` lists Windows cultures, and
    Tahitian, Filipino and Quechua are not among them — so a hard return there
    switched folds off for exactly the ~60 layouts that need them."""

    def _helper(self, installed, native):
        from polyhost.input.win_helper import WindowsInputHelper

        class Fake(WindowsInputHelper):
            def __init__(s):
                super().__init__({"dev_win_native_set_language": native})
                s.i = list(installed)
                s.c = s.i[0]
                s.n = 0
            def get_languages(s):
                return s.i
            def get_current_language(s):
                s.n += 1
                if s.n > 1:
                    s.c = s.i[(s.i.index(s.c) + 1) % len(s.i)]
                return True, s.c
        return Fake()

    def test_a_language_with_no_lcid_still_reaches_the_fallback(self):
        h = self._helper(["en-US", "fr-FR"], native=True)
        ok, got = h.set_language("ty", "PF")        # no Windows culture "ty_pf"
        self.assertTrue(ok, got)
        self.assertEqual(got, "fr-FR")

    def test_a_failed_LoadKeyboardLayout_still_reaches_the_fallback(self):
        import ctypes
        from unittest.mock import MagicMock, patch
        user32 = MagicMock()
        user32.LoadKeyboardLayoutW.return_value = 0      # the documented failure
        windll = MagicMock(user32=user32)
        h = self._helper(["en-US", "de-DE"], native=True)
        # de-DE HAS an LCID, so this gets past the first branch and into the
        # Win32 call — the branch that used to return False outright.
        with patch.object(ctypes, "windll", windll, create=True):
            ok, got = h.set_language("de", "DE")
        self.assertTrue(ok, got)
        self.assertEqual(got, "de-DE")
        user32.LoadKeyboardLayoutW.assert_called_once()

    def test_the_setting_off_takes_the_inherited_path(self):
        h = self._helper(["en-US", "fr-FR"], native=False)
        ok, got = h.set_language("ty", "PF")
        self.assertTrue(ok, got)
        self.assertEqual(got, "fr-FR")


class ThreeMapsTest(unittest.TestCase):
    """The maps are counterparts, not copies — only their KEY SETS line up."""

    def test_every_linux_key_exists_on_the_other_platforms(self):
        """A fold added for Linux and not mirrored goes QUIET: that language
        simply reports no compatible layout on Windows and macOS, on a machine
        that has exactly the right one installed. Nothing else notices."""
        linux = set(LangComp("linux").mapping)
        self.assertTrue(linux, "the Linux map parsed to nothing")
        for platform in ("macos", "windows"):
            with self.subTest(platform=platform):
                missing = sorted(linux - set(LangComp(platform).mapping))
                self.assertEqual(missing, [],
                                 f"{platform} has no fold for: {missing}")

    def test_the_tag_maps_carry_no_xkb_layout_codes(self):
        """`ara` and `latam` are xkb layout names, not languages. Pasted into
        a tag-vocabulary file they would match nothing and be skipped — the
        fold would go quiet rather than fail."""
        for platform in ("macos", "windows"):
            for country, tags in LangComp(platform).mapping.items():
                for tag in tags:
                    with self.subTest(platform=platform, country=country, tag=tag):
                        self.assertNotIn(tag, {"ara", "latam"})
                        self.assertRegex(tag, r"^[a-z]{2}(-[a-z]{2})?$")

    def test_the_linux_map_is_still_xkb_and_not_tags(self):
        """The reverse guard: a tag pasted into the Linux file would be handed
        to `qdbus setLayout` as a layout name and match nothing there."""
        for country, codes in LangComp("linux").mapping.items():
            for code in codes:
                with self.subTest(country=country, code=code):
                    self.assertNotIn("-", code, f"{country}={code} looks like a tag")


if __name__ == "__main__":
    unittest.main()
