"""Log viewer: the console tab's colours and the search field.

The console highlighter is pinned through the classifier in
tests/services/problem_scan_test.py; here it is enough that the console tab
gets it and the host tabs keep the level highlighter. The search tests drive the
real widgets: type in the field, step with next/previous, switch tabs, reload.
"""
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Only a missing PyQt5 skips. An error in the module under test must fail.
try:
    from PyQt5.QtWidgets import QApplication
    _IMPORT_ERR = None
except ImportError as e:  # pragma: no cover - PyQt5 not installed
    _IMPORT_ERR = e

if _IMPORT_ERR is None:
    from polyhost.gui import log_viewer as lv

HOST_LINES = (
    "[2026-10-09 08:01:15,999] INFO    {poly_kybd.py:1} Prepare for MRU send\n"
    "[2026-10-09 08:01:17,010] WARNING {poly_kybd.py:2} prepare failed: 0x3E5\n"
    "[2026-10-09 08:01:19,039] DEBUG   {poly_kybd.py:3} ID query failed: 0x3E5\n"
)
CONSOLE_LINES = (
    "[2026-10-09 08:00:00,000] Eden idle 5226ms (frame 33ms, core1)\n"
    "[2026-10-09 08:01:12,910] Stop idle.\n"
    "[2026-10-09 08:02:00,000] Eden idle 61256ms (frame 34ms, core1)\n"
)


@unittest.skipIf(_IMPORT_ERR is not None, f"PyQt5 unavailable: {_IMPORT_ERR}")
class LogViewerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = os.path.join(self.tmp.name, "host_log.txt")
        self.console = os.path.join(self.tmp.name, lv._CONSOLE_FILENAME)
        with open(self.host, "w", encoding="utf-8") as f:
            f.write(HOST_LINES)
        with open(self.console, "w", encoding="utf-8") as f:
            f.write(CONSOLE_LINES)
        self.dlg = lv.LogViewerDialog({"Host": self.host, "Console": self.console})
        self.dlg.tab_widget.setCurrentIndex(0)
        # Shown, because only the matches in view are tinted.
        self.dlg.resize(1200, 600)
        self.dlg.show()
        self.app.processEvents()

    def tearDown(self):
        self.dlg.close()
        self.dlg.deleteLater()
        self.tmp.cleanup()

    def _search(self, text):
        self.dlg.search_edit.setText(text)
        self.assertTrue(self.dlg._search_timer.isActive() or not text)   # debounced
        self.dlg._run_search()                                            # skip the wait
        return self.dlg.search_count.text()

    # -- highlighters ----------------------------------------------------------
    def test_only_the_console_tab_gets_the_console_highlighter(self):
        kinds = sorted(type(h).__name__ for h in self.dlg._highlighters)
        self.assertEqual(kinds, ["_ConsoleHighlighter", "_LogHighlighter"])

    # -- search ------------------------------------------------------------------
    def test_typing_counts_the_matches_case_insensitively(self):
        self.assertEqual(self._search("0x3e5"), "2 of 2")

    def test_a_fresh_search_lands_on_the_newest_match(self):
        # The log opens scrolled to the end, so the newest match is the one wanted.
        self._search("0x3e5")
        cursor = self.dlg._current_editor().textCursor()
        self.assertEqual(cursor.block().blockNumber(), 2)

    def test_next_and_previous_step_and_wrap(self):
        self._search("0x3e5")                                   # 2 of 2
        self.dlg.find_next()
        self.assertEqual(self.dlg.search_count.text(), "1 of 2")  # wrapped
        self.dlg.find_previous()
        self.assertEqual(self.dlg.search_count.text(), "2 of 2")

    def test_every_match_in_view_is_tinted_once(self):
        self._search("0x3e5")
        self.assertEqual(len(self.dlg._current_editor().extraSelections()), 2)

    def test_a_large_log_is_counted_and_stepped_without_a_cursor_per_match(self):
        # 20,000 lines with 3 hits each: the count is exact, stepping wraps, and the
        # tint stays bounded by what is in view.
        with open(self.host, "w", encoding="utf-8") as f:
            f.write("[t] INFO    x e e e\n" * 20000)
        self.dlg.load_log()
        self.assertEqual(self._search("e"), "60000 of 60000")
        self.dlg.find_next()
        self.assertEqual(self.dlg.search_count.text(), "1 of 60000")
        self.dlg.find_previous()
        self.assertEqual(self.dlg.search_count.text(), "60000 of 60000")
        # Every match in view is tinted, and only those: the view bounds the work.
        editor = self.dlg._current_editor()
        tinted = editor.extraSelections()
        self.assertGreater(len(tinted), 3)
        self.assertLess(len(tinted), 60000)

    def test_scrolling_re_tints_the_new_view_once_it_pauses(self):
        with open(self.host, "w", encoding="utf-8") as f:
            f.write("".join(f"[t] INFO    line {i} hit\n" for i in range(5000)))
        self.dlg.load_log()
        self._search("hit")
        editor = self.dlg._current_editor()
        bar = editor.verticalScrollBar()
        bar.setValue(0)                                  # from the end to the top
        self.assertTrue(self.dlg._tint_timer.isActive())  # deferred, not per step
        self.dlg._tint_visible()                          # skip the wait
        top = editor.firstVisibleBlock().blockNumber()
        tinted_lines = {sel.cursor.block().blockNumber() for sel in editor.extraSelections()}
        self.assertIn(top, tinted_lines)

    def test_a_view_full_of_matches_is_tinted_in_full(self):
        # No cap: one hit per character on screen, all of them tinted.
        with open(self.host, "w", encoding="utf-8") as f:
            f.write(("e" * 150 + "\n") * 2000)
        self.dlg.load_log()
        self._search("e")
        editor = self.dlg._current_editor()
        first = editor.firstVisibleBlock().position()
        last = editor.cursorForPosition(editor.viewport().rect().bottomRight()).position()
        visible_text = editor.toPlainText()[first:last + 1]
        self.assertGreater(len(editor.extraSelections()), 500)
        self.assertEqual(len(editor.extraSelections()), visible_text.count("e"))

    def test_no_match_says_so_and_tints_nothing(self):
        self.assertEqual(self._search("nothing like this"), "No matches")
        self.assertEqual(self.dlg._current_editor().extraSelections(), [])

    def test_clearing_the_field_clears_the_tint(self):
        self._search("0x3e5")
        self.assertEqual(self._search(""), "")
        self.assertEqual(self.dlg._current_editor().extraSelections(), [])

    def test_switching_tabs_searches_the_new_tab(self):
        self._search("eden idle")
        self.assertEqual(self.dlg.search_count.text(), "No matches")   # host tab
        self.dlg.tab_widget.setCurrentIndex(1)
        self.assertEqual(self.dlg.search_count.text(), "2 of 2")
        # The tab left behind keeps no stale tint.
        self.assertEqual(self.dlg.log_text["Host"].extraSelections(), [])

    def test_reload_searches_the_new_contents(self):
        self._search("0x3e5")
        with open(self.host, "a", encoding="utf-8") as f:
            f.write("[2026-10-09 08:01:21,059] WARNING {poly_kybd.py:4} again 0x3E5\n")
        self.dlg.load_log()
        self.assertEqual(self.dlg.search_count.text(), "3 of 3")


if __name__ == "__main__":
    unittest.main()
