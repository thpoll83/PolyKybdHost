"""common.find_matching_entry — the shared window matcher (H4c-2).

Pulled out of OverlayHandler so the local and remote paths share one matcher,
and so the recursion is unit-testable without a display (active_window imports
pywinctl). Entries here are built in the *annotated* shape annotate() produces:
a `flags` list [overlay, remote, title, starts_with, ends_with, contains, url,
urls_contains] plus the matching sub-maps.
"""
import unittest

from polyhost.handler.common import find_matching_entry


def entry(overlay=True, remote=False, title=None, sw=None, ew=None, contains=None,
          url=None, urls_contains=None):
    e = {"flags": [overlay, remote, title is not None, bool(sw), bool(ew),
                   bool(contains), url is not None, bool(urls_contains)]}
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
        # has both starts_with and contains so the title is split into words.
        self.assertIs(find_matching_entry("a NEEDLE b", e), leaf)
        self.assertIs(find_matching_entry("no match words", e), e)  # parent, no title gate

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
