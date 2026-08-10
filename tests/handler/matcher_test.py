"""common.find_matching_entry — the shared window matcher (H4c-2).

Pulled out of OverlayHandler so the local and remote paths share one matcher,
and so the recursion is unit-testable without a display (active_window imports
pywinctl). Entries here are built in the *annotated* shape annotate() produces:
a `flags` list [overlay, remote, title, starts_with, ends_with, contains, url,
urls_contains, os] plus the matching sub-maps.
"""
import unittest

from polyhost.device.command_ids import OsType
from polyhost.handler.common import find_matching_entry, normalize_os, os_match_keys


def entry(overlay=True, remote=False, title=None, sw=None, ew=None, contains=None,
          url=None, urls_contains=None, os_map=None):
    e = {"flags": [overlay, remote, title is not None, bool(sw), bool(ew),
                   bool(contains), url is not None, bool(urls_contains), bool(os_map)]}
    if os_map:
        e["os"] = os_map
    if overlay:
        e["overlay"] = "ov"
    if remote:
        e["remote"] = "1.2.3.4"
    if title is not None:
        e["title"] = title
    if sw:
        e["titles-startswith"] = sw
    if ew:
        e["titles-endswith"] = ew
    if contains:
        e["titles-contains"] = contains
    if url is not None:
        e["url"] = url
    if urls_contains:
        e["urls-contains"] = urls_contains
    return e


class TestFindMatchingEntry(unittest.TestCase):
    def test_plain_overlay_matches_any_title(self):
        e = entry()
        self.assertIs(find_matching_entry("anything", e), e)
        self.assertIs(find_matching_entry("", e), e)

    def test_no_overlay_or_remote_never_matches(self):
        self.assertIsNone(find_matching_entry("x", entry(overlay=False)))

    def test_remote_only_matches(self):
        e = entry(overlay=False, remote=True)
        self.assertIs(find_matching_entry("x", e), e)

    def test_title_regex_gates_the_match(self):
        e = entry(title=r"- Editor$")
        self.assertIs(find_matching_entry("main.py - Editor", e), e)
        self.assertIsNone(find_matching_entry("notes.txt", e))

    def test_starts_with_recurses_to_subentry(self):
        leaf = entry(title=None)
        e = entry(sw={"Word0": leaf})
        self.assertIs(find_matching_entry("Word0 and the rest", e), leaf)
        # First word differs -> the sub-map isn't entered; the parent has no
        # title constraint, so it matches itself.
        self.assertIs(find_matching_entry("Other start", e), e)

    def test_ends_with_recurses(self):
        leaf = entry()
        e = entry(ew={"END": leaf})
        self.assertIs(find_matching_entry("foo bar END", e), leaf)

    def test_contains_recurses_on_any_word(self):
        leaf = entry()
        e = entry(sw={"x": {}}, contains={"NEEDLE": leaf})
        self.assertIs(find_matching_entry("a NEEDLE b", e), leaf)
        self.assertIs(find_matching_entry("no match words", e), e)  # parent, no title gate

    def test_contains_alone_recurses(self):
        # Regression: `titles-contains` used to be dead on its own, because the
        # word-split was gated on startswith/endswith only. An earlier version of
        # the test above papered over it by adding a dummy `titles-startswith`,
        # so the suite passed while the shipped browser entry's Miro/Outlook/Jira
        # keys could never match. Keep this entry free of any sibling title key.
        leaf = entry()
        e = entry(contains={"NEEDLE": leaf})
        self.assertIs(find_matching_entry("a NEEDLE b", e), leaf)
        self.assertIs(find_matching_entry("NEEDLE", e), leaf)
        self.assertIs(find_matching_entry("no match here", e), e)  # parent, no title gate

    def test_contains_matches_whole_words_only(self):
        # Documented limit, unchanged by the fix: the title is split on
        # whitespace, so a needle only matches a WHOLE word -- "Doc" does not
        # match "Docs", and a multi-word needle can never match at all.
        leaf = entry()
        e = entry(contains={"Doc": leaf})
        self.assertIs(find_matching_entry("My Doc here", e), leaf)
        self.assertIs(find_matching_entry("My Docs here", e), e)  # parent, not leaf

    def test_bad_regex_raises(self):
        import re as _re
        with self.assertRaises(_re.error):
            find_matching_entry("x", entry(title="("))


class TestUrlMatching(unittest.TestCase):
    def test_urls_contains_recurses_when_url_present(self):
        leaf = entry()
        e = entry(urls_contains={"mail.google.com": leaf})
        self.assertIs(
            find_matching_entry("Inbox", e, url="https://mail.google.com/u/0"), leaf)

    def test_urls_contains_falls_through_to_default_when_no_url(self):
        # A browser entry with a default overlay + urls-contains must still match
        # (its default) when no URL is known — urls-contains is not a hard gate.
        leaf = entry()
        e = entry(urls_contains={"mail.google.com": leaf})
        self.assertIs(find_matching_entry("Some title", e, url=None), e)

    def test_urls_contains_falls_through_when_url_hits_no_subkey(self):
        leaf = entry()
        e = entry(urls_contains={"mail.google.com": leaf})
        self.assertIs(find_matching_entry("t", e, url="https://example.com"), e)

    def test_url_wins_over_title_submap(self):
        # urls-contains is checked before titles-contains: the URL is the
        # stronger signal for which web-app is focused.
        by_url = entry()
        by_title = entry()
        e = entry(urls_contains={"jira": by_url}, contains={"Board": by_title})
        got = find_matching_entry("My Board", e, url="https://x.atlassian.net/jira")
        self.assertIs(got, by_url)

    def test_hard_url_regex_constraint_blocks_without_url(self):
        e = entry(url=r"github\.com")
        self.assertIsNone(find_matching_entry("anything", e, url=None))
        self.assertIs(find_matching_entry("t", e, url="https://github.com/x"), e)
        self.assertIsNone(find_matching_entry("t", e, url="https://gitlab.com/x"))

    def test_url_ignored_by_default_when_arg_omitted(self):
        # Callers that never pass url (the remote path) behave exactly as before.
        leaf = entry()
        e = entry(urls_contains={"mail.google.com": leaf})
        self.assertIs(find_matching_entry("anything", e), e)


if __name__ == "__main__":
    unittest.main()


class TestOsBranch(unittest.TestCase):
    """The `os:` sub-map — an app's keymap is a property of its platform.

    Sublime binds Cmd on macOS and Ctrl on Windows, so one app name needs two
    overlay sets. Guards the fallback direction in particular: an unknown OS must
    land on the DEFAULT artwork, never match a branch by accident.
    """

    def _entry(self):
        mac = entry()
        mac["overlay"] = "mac"
        return entry(os_map={"macos": mac})

    def test_matching_os_selects_the_branch(self):
        e = self._entry()
        self.assertEqual(find_matching_entry("t", e, None, OsType.MACOS)["overlay"], "mac")

    def test_other_os_falls_back_to_the_default_overlay(self):
        e = self._entry()
        for os_v in (OsType.WINDOWS, OsType.LINUX, OsType.LINUX_KDE, OsType.ANDROID):
            self.assertEqual(find_matching_entry("t", e, None, os_v)["overlay"], "ov", os_v)

    def test_unknown_or_absent_os_falls_back(self):
        """UNKNOWN(0)/None must not match any branch — default artwork wins."""
        e = self._entry()
        for os_v in (None, OsType.UNKNOWN, 0, "", "plan9"):
            self.assertEqual(find_matching_entry("t", e, None, os_v)["overlay"], "ov", repr(os_v))

    def test_entry_without_an_os_map_is_unaffected(self):
        e = entry()
        self.assertIs(find_matching_entry("t", e, None, OsType.MACOS), e)

    def test_os_branch_may_nest_further_constraints(self):
        """An OS branch recurses, so it can carry title/url gates of its own."""
        # `title` is matched against the WHOLE title, not the leading word.
        leaf = entry(title=r".*\.py\s.*")
        leaf["overlay"] = "mac-py"
        mac = entry(ew={"Editor": leaf})
        mac["overlay"] = "mac"
        e = entry(os_map={"macos": mac})
        self.assertEqual(
            find_matching_entry("main.py Editor", e, None, OsType.MACOS)["overlay"], "mac-py")
        # title gate misses -> the OS branch's own overlay, not the global default
        self.assertEqual(
            find_matching_entry("notes.txt Editor", e, None, OsType.MACOS)["overlay"], "mac")


class TestNormalizeOs(unittest.TestCase):
    def test_accepts_ostype_wire_int_and_names(self):
        for value in (OsType.MACOS, 2, "macos", "Mac", " darwin ", "OSX"):
            self.assertEqual(normalize_os(value), "macos", repr(value))
        self.assertEqual(normalize_os("win"), "windows")

    def test_linux_desktop_environments_stay_distinct(self):
        """A `gnome:` branch must not also fire on KDE — they really do differ."""
        self.assertEqual(normalize_os(OsType.LINUX), "linux")
        for value in (OsType.LINUX_GNOME, "gnome", "linux-gnome"):
            self.assertEqual(normalize_os(value), "linux_gnome", repr(value))
        for value in (OsType.LINUX_KDE, "kde", "plasma"):
            self.assertEqual(normalize_os(value), "linux_kde", repr(value))

    def test_unknown_is_none(self):
        for value in (None, OsType.UNKNOWN, 0, 99, "plan9", True):
            self.assertIsNone(normalize_os(value), repr(value))

    def test_mobile_os_types_are_not_matchable(self):
        """Android/iOS can never reach the matcher, so they resolve to nothing."""
        for value in (OsType.ANDROID, OsType.IOS, "android", "ios"):
            self.assertIsNone(normalize_os(value), repr(value))


class TestOsMatchKeys(unittest.TestCase):
    def test_plain_platforms_have_no_fallback(self):
        self.assertEqual(os_match_keys(OsType.WINDOWS), ["windows"])
        self.assertEqual(os_match_keys(OsType.MACOS), ["macos"])
        self.assertEqual(os_match_keys(OsType.LINUX), ["linux"])

    def test_desktop_environments_fall_back_to_linux(self):
        self.assertEqual(os_match_keys(OsType.LINUX_GNOME), ["linux_gnome", "linux"])
        self.assertEqual(os_match_keys(OsType.LINUX_KDE), ["linux_kde", "linux"])

    def test_unknown_matches_nothing(self):
        for value in (None, OsType.UNKNOWN, OsType.ANDROID, "plan9"):
            self.assertEqual(os_match_keys(value), [], repr(value))


class TestOsBranchDesktopEnvironments(unittest.TestCase):
    """GNOME/KDE specificity, in both directions."""

    def _entry(self, *keys):
        os_map = {}
        for k in keys:
            sub = entry()
            sub["overlay"] = k
            os_map[k] = sub
        return entry(os_map=os_map)

    def test_specific_de_branch_wins_over_linux(self):
        e = self._entry("linux", "gnome")
        self.assertEqual(
            find_matching_entry("t", e, None, OsType.LINUX_GNOME)["overlay"], "gnome")

    def test_gnome_branch_does_not_fire_on_kde(self):
        e = self._entry("gnome")
        self.assertEqual(find_matching_entry("t", e, None, OsType.LINUX_KDE)["overlay"], "ov")

    def test_linux_branch_still_catches_every_desktop(self):
        e = self._entry("linux")
        for os_v in (OsType.LINUX, OsType.LINUX_GNOME, OsType.LINUX_KDE):
            self.assertEqual(find_matching_entry("t", e, None, os_v)["overlay"], "linux", os_v)
