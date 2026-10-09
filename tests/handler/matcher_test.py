"""common.find_matching_entry — the shared window matcher (H4c-2).

Pulled out of OverlayHandler so the local and remote paths share one matcher,
and so the recursion is unit-testable without a display (active_window imports
pywinctl). Entries here are built in the *annotated* shape annotate() produces:
a `flags` list [overlay, remote, title, starts_with, ends_with, contains, url,
urls_contains, os] plus the matching sub-maps.
"""
import unittest

from polyhost.device.command_ids import OsType
from polyhost.handler.common import (
    find_matching_entry, mapping_key, normalize_os, os_match_keys)


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
        # match "Docs".
        leaf = entry()
        e = entry(contains={"Doc": leaf})
        self.assertIs(find_matching_entry("My Doc here", e), leaf)
        self.assertIs(find_matching_entry("My Docs here", e), e)  # parent, not leaf

    def test_contains_matches_a_multi_word_needle(self):
        # Up to host 1.12.x a needle with a space could never equal a single
        # word, so a multi-word key looked reasonable and silently never fired.
        # It now matches the words adjacent; TestPhraseKeys covers the rules.
        leaf = entry()
        e = entry(contains={"My Doc": leaf})
        self.assertIs(find_matching_entry("My Doc here", e), leaf)
        self.assertIs(find_matching_entry("My Doc", e), leaf)
        self.assertIs(find_matching_entry("My Docs", e), e)       # whole words only

    def test_bad_regex_raises(self):
        import re as _re
        with self.assertRaises(_re.error):
            find_matching_entry("x", entry(title="("))


class TestPhraseKeys(unittest.TestCase):
    """A title sub-map key may be several words, matched as adjacent whole words."""

    def test_contains_phrase_needs_adjacent_words(self):
        leaf = entry()
        e = entry(contains={"Claude Code": leaf})
        self.assertIs(find_matching_entry("Fix it - Claude Code - Chrome", e), leaf)
        self.assertIs(find_matching_entry("Claude wrote Code", e), e)
        self.assertIs(find_matching_entry("Claude Coder", e), e)

    def test_longest_phrase_wins_whatever_the_yaml_order(self):
        short, long_ = entry(), entry()
        for order in (("Claude", "Claude Code"), ("Claude Code", "Claude")):
            subs = {"Claude": short, "Claude Code": long_}
            e = entry(contains={k: subs[k] for k in order})
            self.assertIs(find_matching_entry("x - Claude Code", e), long_, order)
            self.assertIs(find_matching_entry("chat - Claude", e), short, order)

    def test_earliest_key_in_the_title_still_wins(self):
        miro, jira = entry(), entry()
        e = entry(contains={"Jira": jira, "Google Docs": miro})
        self.assertIs(find_matching_entry("Google Docs about Jira", e), miro)
        self.assertIs(find_matching_entry("Jira notes in Google Docs", e), jira)

    def test_a_failed_phrase_falls_back_to_the_shorter_key(self):
        short = entry()
        gated = entry(title="never")
        e = entry(contains={"Claude": short, "Claude Code": gated})
        self.assertIs(find_matching_entry("x - Claude Code", e), short)

    def test_starts_and_ends_with_take_phrases(self):
        head, tail = entry(), entry()
        e = entry(sw={"Untitled Document": head}, ew={"LibreOffice Writer": tail})
        self.assertIs(find_matching_entry("Untitled Document 1", e), head)
        self.assertIs(find_matching_entry("Untitled 1 - LibreOffice Writer", e), tail)
        self.assertIs(find_matching_entry("Writer", e), e)

    def test_extra_whitespace_in_key_or_title_is_ignored(self):
        leaf = entry()
        e = entry(contains={" Google  Docs ": leaf})
        self.assertIs(find_matching_entry("a -  Google\tDocs", e), leaf)


def named(e, overlay):
    e["overlay"] = overlay
    return e


class TestUrlMatching(unittest.TestCase):
    def test_urls_contains_recurses_when_url_present(self):
        # The site's entry, with the browser's overlay layered UNDER its own
        # (see TestBrowserLayering); everything else is the leaf's.
        leaf = named(entry(), "site")
        e = named(entry(urls_contains={"mail.google.com": leaf}), "browser")
        got = find_matching_entry("Inbox", e, url="https://mail.google.com/u/0")
        self.assertEqual(got["overlay"], ["browser", "site"])
        self.assertEqual(got["flags"], leaf["flags"])

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
        by_url = named(entry(), "by_url")
        by_title = named(entry(), "by_title")
        e = named(entry(urls_contains={"jira": by_url}, contains={"Board": by_title}),
                  "browser")
        got = find_matching_entry("My Board", e, url="https://x.atlassian.net/jira")
        self.assertEqual(got["overlay"], ["browser", "by_url"])

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

    def test_known_url_suppresses_the_titles_contains_fallback(self):
        # The shipped browser entry's shape. A known URL that matched no needle
        # is positive evidence about the site, and outranks a word in the title:
        # searching google.com for "jira" must NOT load the Jira overlay.
        by_url = entry()
        by_title = entry()
        e = entry(urls_contains={"atlassian.net": by_url}, contains={"Jira": by_title})
        self.assertIs(
            find_matching_entry("How to use Jira", e,
                                url="https://www.google.com/search?q=jira"), e)

    def test_titles_contains_fallback_runs_when_url_unknown(self):
        # ...but with no URL at all (no extension / stale report) the title
        # fallback is the only signal there is, so it still fires.
        by_url = named(entry(), "by_url")
        by_title = named(entry(), "by_title")
        e = named(entry(urls_contains={"atlassian.net": by_url}, contains={"Jira": by_title}),
                  "browser")
        got = find_matching_entry("PolyKybd - Jira", e, url=None)
        self.assertEqual(got["overlay"], ["browser", "by_title"])

    def test_known_url_does_not_suppress_contains_without_urls_contains(self):
        # The suppression is scoped to entries that actually declare
        # urls-contains; a plain titles-contains entry is unaffected by a URL
        # merely being known for the window.
        leaf = entry()
        e = entry(contains={"Jira": leaf})
        self.assertIs(
            find_matching_entry("PolyKybd - Jira", e, url="https://example.com"), leaf)


class TestBrowserLayering(unittest.TestCase):
    """A web app runs inside the browser, so the browser's shortcuts stay.

    A browser entry is one that declares `urls-contains`. A site matched under it
    (by URL, or by title when no URL is known) gets the browser's overlay files
    FIRST and its own after: templates resolve last-one-wins per key, so the site
    wins the keys it draws and the browser keeps the rest.
    """

    def _browser(self):
        self.site = named(entry(), ["site.mods.png", "site.combo.mods.png"])
        self.by_title = named(entry(), "titled.mods.png")
        return named(entry(urls_contains={"site.com": self.site},
                           contains={"Titled": self.by_title}),
                     ["browser.mods.png", "browser.combo.mods.png"])

    def test_site_goes_last_so_it_wins_its_keys(self):
        got = find_matching_entry("x", self._browser(), url="https://site.com/a")
        self.assertEqual(got["overlay"], ["browser.mods.png", "browser.combo.mods.png",
                                          "site.mods.png", "site.combo.mods.png"])

    def test_the_entries_themselves_are_not_modified(self):
        e = self._browser()
        find_matching_entry("x", e, url="https://site.com/a")
        self.assertEqual(self.site["overlay"], ["site.mods.png", "site.combo.mods.png"])
        self.assertEqual(e["overlay"], ["browser.mods.png", "browser.combo.mods.png"])
        self.assertEqual(sorted(self.site), ["flags", "overlay"])

    def test_same_window_returns_the_same_object(self):
        # The handler re-matches every tick; one object per window keeps the
        # ENABLE-vs-OFF_ON decision cheap and stable.
        e = self._browser()
        a = find_matching_entry("x", e, url="https://site.com/a")
        b = find_matching_entry("x", e, url="https://site.com/b")
        self.assertIs(a, b)
        self.assertEqual(a, b)

    def test_title_fallback_layers_too(self):
        got = find_matching_entry("A Titled page", self._browser(), url=None)
        self.assertEqual(got["overlay"], ["browser.mods.png", "browser.combo.mods.png",
                                          "titled.mods.png"])

    def test_a_site_repeating_a_browser_file_keeps_it_last(self):
        # chatgpt.com/codex lists the browser's own set as its overlay.
        e = self._browser()
        self.site["overlay"] = ["browser.combo.mods.png", "site.mods.png"]
        got = find_matching_entry("x", e, url="https://site.com/")
        self.assertEqual(got["overlay"], ["browser.mods.png", "browser.combo.mods.png",
                                          "site.mods.png"])

    def test_no_site_match_is_the_browser_alone(self):
        e = self._browser()
        self.assertIs(find_matching_entry("x", e, url="https://other.com/"), e)

    def test_the_browsers_files_are_marked_as_underlays(self):
        # The keyboard draws an Underlay's icons dimmed (cmd 33, protocol v23), so
        # the site's own shortcuts stand out. The site's files stay plain.
        got = find_matching_entry("x", self._browser(), url="https://site.com/a")
        marks = [getattr(f, "underlay", False) for f in got["overlay"]]
        self.assertEqual(marks, [True, True, False, False])

    def test_a_browser_file_the_site_lists_too_is_the_sites(self):
        # chatgpt.com/codex: the repeated file keeps the site's position AND full
        # strength, or the site's own copy would be drawn dimmed.
        e = self._browser()
        self.site["overlay"] = ["browser.combo.mods.png", "site.mods.png"]
        got = find_matching_entry("x", e, url="https://site.com/")
        marks = [getattr(f, "underlay", False) for f in got["overlay"]]
        self.assertEqual(marks, [True, False, False])

    def test_views_differing_only_in_marks_compare_unequal(self):
        # The handler resends only when the matched entry changes (==). One site
        # listing the browser's file (plain) and one not listing it (dimmed) give
        # equal file lists, so the marks must be part of the comparison.
        e = named(entry(urls_contains={
                      "a.com": named(entry(), ["browser.mods.png", "site.mods.png"]),
                      "b.com": named(entry(), ["site.mods.png"])}),
                  ["browser.mods.png"])
        a = find_matching_entry("x", e, url="https://a.com/")
        b = find_matching_entry("x", e, url="https://b.com/")
        self.assertEqual(a["overlay"], b["overlay"])
        self.assertNotEqual(a, b)

    def test_the_browser_alone_is_not_marked(self):
        e = self._browser()
        got = find_matching_entry("x", e, url="https://other.com/")
        self.assertFalse(any(getattr(f, "underlay", False) for f in got["overlay"]))

    def test_title_submaps_of_other_apps_still_replace(self):
        # Not a browser (no urls-contains): a window mode of one app is not
        # running inside another, so its overlay replaces as before.
        leaf = named(entry(), "dialog")
        e = named(entry(contains={"Settings": leaf}), "app")
        self.assertIs(find_matching_entry("App Settings", e), leaf)


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


class TestMappingKey(unittest.TestCase):
    """macOS reports Adobe apps with a release year, `Adobe Photoshop 2025`."""

    M = {"adobe photoshop": 1, "code": 1, "photoshop 2": 1}

    def test_exact_name_wins(self):
        self.assertEqual(mapping_key("code", self.M), "code")

    def test_a_trailing_release_year_is_dropped(self):
        self.assertEqual(mapping_key("adobe photoshop 2025", self.M), "adobe photoshop")
        self.assertEqual(mapping_key("adobe photoshop 2031", self.M), "adobe photoshop")

    def test_only_a_trailing_four_digit_year_is_dropped(self):
        # A version that is not a year, or a year mid-name, is part of the name.
        self.assertIsNone(mapping_key("adobe photoshop 25", self.M))
        self.assertIsNone(mapping_key("adobe 2025 photoshop", self.M))
        self.assertEqual(mapping_key("photoshop 2", self.M), "photoshop 2")

    def test_unknown_and_empty_names_resolve_to_none(self):
        self.assertIsNone(mapping_key("notepad", self.M))
        self.assertIsNone(mapping_key("", self.M))
        self.assertIsNone(mapping_key(None, self.M))


if __name__ == "__main__":
    unittest.main()
