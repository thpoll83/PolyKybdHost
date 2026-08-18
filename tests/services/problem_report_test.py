"""The report body is destined for a PUBLIC issue tracker, so most of these
tests are about what must NOT end up in it."""
import unittest

from polyhost.services import problem_report as pr


class ScrubPathsTest(unittest.TestCase):
    def test_replaces_the_home_directory(self):
        out = pr.scrub_paths("Logs: /home/tom/PolyKybdHost", home="/home/tom")
        self.assertEqual("Logs: ~/PolyKybdHost", out)

    def test_replaces_a_windows_home_directory(self):
        out = pr.scrub_paths(r"Config: C:\Users\Tom\AppData\Roaming\PolyHost",
                             home=r"C:\Users\Tom")
        self.assertNotIn("Tom", out)
        self.assertIn("AppData", out)

    def test_scrubs_a_user_dir_that_is_not_this_users_home(self):
        """A daemon started under another account, or a bundle written to
        another drive, still names somebody."""
        out = pr.scrub_paths(r"D:\Users\alice\logs and /home/bob/x", home="/home/tom")
        self.assertNotIn("alice", out)
        self.assertNotIn("bob", out)

    def test_macos_users_dir(self):
        self.assertNotIn("tom", pr.scrub_paths("/Users/tom/Library/x", home="/nope"))

    def test_leaves_ordinary_text_alone(self):
        text = "PolyKybdHost 0.12.0 (HID protocol P11)\nKeyboard: Split72"
        self.assertEqual(text, pr.scrub_paths(text, home="/home/tom"))

    def test_empty_input(self):
        self.assertEqual("", pr.scrub_paths("", home="/home/tom"))


class TitleTest(unittest.TestCase):
    def test_first_line_becomes_the_title(self):
        self.assertEqual("Overlays stop after sleep",
                         pr.default_title("Overlays stop after sleep\n\nMore detail"))

    def test_long_titles_are_truncated(self):
        title = pr.default_title("x" * 300)
        self.assertLessEqual(len(title), 90)
        self.assertTrue(title.endswith("…"))

    def test_empty_description_still_yields_a_title(self):
        for desc in ("", "   ", "\n\n"):
            self.assertEqual("Problem report", pr.default_title(desc))


class ComposeBodyTest(unittest.TestCase):
    def test_carries_description_and_diagnostics(self):
        body = pr.compose_body("It broke", diagnostics="PolyKybdHost 0.12.0")
        self.assertIn("### What happened", body)
        self.assertIn("It broke", body)
        self.assertIn("PolyKybdHost 0.12.0", body)

    def test_diagnostics_are_scrubbed(self):
        body = pr.compose_body("x", diagnostics="Logs: /home/tom/app", home="/home/tom")
        self.assertNotIn("/home/tom", body)

    def test_expected_section_is_optional(self):
        self.assertNotIn("What I expected", pr.compose_body("x"))
        self.assertIn("What I expected", pr.compose_body("x", expected="not that"))

    def test_asks_the_user_to_attach_the_bundle(self):
        body = pr.compose_body("x", bundle_name="polyhost-logs-1.zip")
        self.assertIn("polyhost-logs-1.zip", body)
        self.assertIn("attach", body.lower())

    def test_flags_an_unredacted_bundle(self):
        redacted = pr.compose_body("x", bundle_name="b.zip", redacted=True)
        raw = pr.compose_body("x", bundle_name="b.zip", redacted=False)
        self.assertIn("masked", redacted)
        self.assertIn("NOT masked", raw)

    def test_never_embeds_log_lines(self):
        """Logs travel as an attachment the reporter can inspect, never inlined
        into a public issue on their behalf."""
        body = pr.compose_body("x", diagnostics="PolyKybdHost 0.12.0",
                               bundle_name="b.zip")
        self.assertNotIn("Active App Changed", body)
        self.assertNotIn("[2026-", body)

    def test_empty_description_is_marked_not_guessed(self):
        self.assertIn("_(not described)_", pr.compose_body(""))


class IssueUrlTest(unittest.TestCase):
    def test_prefills_title_and_body(self):
        url = pr.new_issue_url("Broken", "Body here")
        self.assertIn("github.com/thpoll83/PolyKybdHost/issues/new", url)
        self.assertIn("title=Broken", url)
        self.assertIn("Body+here", url)

    def test_labels_are_included(self):
        self.assertIn("labels=bug%2Chost", pr.new_issue_url("t", labels=["bug", "host"]))

    def test_short_body_is_prefilled(self):
        url, prefilled = pr.issue_url_for("t", "short body")
        self.assertTrue(prefilled)
        self.assertIn("body=", url)

    def test_oversized_body_falls_back_to_a_blank_form(self):
        """A too-long URL is truncated or refused somewhere between the browser
        and GitHub; a blank form plus the clipboard beats a mangled report."""
        url, prefilled = pr.issue_url_for("t", "x" * (pr.MAX_URL_BYTES + 1))
        self.assertFalse(prefilled)
        self.assertNotIn("body=", url)
        self.assertIn("title=t", url)

    def test_special_characters_survive_encoding(self):
        url = pr.new_issue_url("a&b=c", "line1\nline2 #tag")
        self.assertNotIn(" ", url)
        self.assertIn("%23tag", url)


class BundleNameTest(unittest.TestCase):
    def test_basename_only(self):
        self.assertEqual("b.zip", pr.bundle_display_name("/tmp/deep/b.zip"))

    def test_none_passes_through(self):
        self.assertIsNone(pr.bundle_display_name(None))


class BodyFitsInAUrlTest(unittest.TestCase):
    """A realistic report must actually prefill, or the whole flow degrades to
    'paste it yourself' for everyone."""

    def test_a_typical_report_prefills(self):
        diagnostics = "\n".join([
            "PolyKybdHost 0.12.0 (HID protocol P11)",
            "Mode: daemon client  |  Uptime: 3h 12m",
            "Python 3.11.9 · Qt 5.15.10 · Windows 11",
            "Keyboard: PolyKybd Split72 (connected)",
            "  Firmware 0.13.1 · protocol P11",
            "  Hardware 1.0 · Language en-US (156 loaded)",
            "Overlay mappings: 42 apps",
            "Config: ~/AppData/Roaming/PolyHost",
            "Logs: ~/PolyKybdHost",
        ])
        body = pr.compose_body(
            "Overlays stop updating after the laptop wakes from sleep. "
            "The keycaps keep showing the previous app until I replug." * 3,
            expected="the keycaps follow the focused app",
            diagnostics=diagnostics, bundle_name="polyhost-logs-20260818-051429.zip")
        _url, prefilled = pr.issue_url_for(pr.default_title("Overlays stop"), body)
        self.assertTrue(prefilled, "a normal-sized report should prefill the form")


if __name__ == "__main__":
    unittest.main()
