"""kde_win_reporter.read_reply: the journal lines a KWin script run leaves,
turned into the active window. A read with no reply line is a failed read and
keeps the last window; only the script's explicit "none" means no window."""
import unittest
from pathlib import Path

from polyhost.handler import kde_win_reporter as kwr


class ReadReplyTest(unittest.TestCase):

    def setUp(self):
        kwr._last = None

    def tearDown(self):
        kwr._last = None

    def test_a_reply_is_the_window(self):
        w = kwr.read_reply(["js: polykybd-window:OpenRA;OpenRA - Tiberian Dawn;1450189"])
        self.assertEqual((w.getAppName(), w.title, w.getHandle()), ("OpenRA", "OpenRA - Tiberian Dawn", 1450189))

    def test_an_empty_read_keeps_the_last_window(self):
        first = kwr.read_reply(["js: polykybd-window:OpenRA;OpenRA - Tiberian Dawn;1450189"])
        for lines in ([""], [], ["js: something else KWin printed"]):
            with self.subTest(lines=lines):
                self.assertIs(kwr.read_reply(lines), first)

    def test_the_explicit_none_is_no_window(self):
        kwr.read_reply(["js: polykybd-window:OpenRA;OpenRA;1"])
        self.assertIsNone(kwr.read_reply(["js: polykybd-window:none"]))
        self.assertIsNone(kwr.read_reply([""]))               # and stays none on a failed read

    def test_a_kwin_line_before_the_reply_is_skipped(self):
        w = kwr.read_reply(["failed to read client connection (pid 1438781)",
                            "js: polykybd-window:google-chrome;Claude Code - Google Chrome;3265"])
        self.assertEqual(w.getAppName(), "google-chrome")

    def test_the_latest_reply_wins(self):
        w = kwr.read_reply(["js: polykybd-window:a;A;1", "js: polykybd-window:b;B;2"])
        self.assertEqual(w.getHandle(), 2)

    def test_a_semicolon_in_the_caption_is_kept(self):
        w = kwr.read_reply(["js: polykybd-window:kate;notes; draft.txt — Kate;42"])
        self.assertEqual((w.getAppName(), w.title, w.getHandle()), ("kate", "notes; draft.txt — Kate", 42))

    def test_a_malformed_reply_keeps_the_last_window(self):
        first = kwr.read_reply(["js: polykybd-window:a;A;1"])
        with self.assertLogs("PolyHost", "WARNING"):
            self.assertIs(kwr.read_reply(["js: polykybd-window:no separators"]), first)

    def test_the_script_always_prints_a_reply(self):
        js = (Path(kwr.__file__).parent / "active_win.js").read_text(encoding="utf-8")
        self.assertIn('print("polykybd-window:" + info)', js)
        self.assertIn('var info = "none"', js)


if __name__ == "__main__":
    unittest.main()
