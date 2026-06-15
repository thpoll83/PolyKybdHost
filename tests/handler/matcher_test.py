"""common.find_matching_entry — the shared window matcher (H4c-2).

Pulled out of OverlayHandler so the local and remote paths share one matcher,
and so the recursion is unit-testable without a display (active_window imports
pywinctl). Entries here are built in the *annotated* shape annotate() produces:
a `flags` list [overlay, remote, title, starts_with, ends_with, contains] plus
the matching sub-maps.
"""
import unittest

from polyhost.handler.common import find_matching_entry


def entry(overlay=True, remote=False, title=None, sw=None, ew=None, contains=None):
    e = {"flags": [overlay, remote, title is not None, bool(sw), bool(ew), bool(contains)]}
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


if __name__ == "__main__":
    unittest.main()
