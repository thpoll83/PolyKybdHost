"""Tests for the shortcut-probe watch loop.

The loop is meant to run unattended for a working day, so the properties worth
pinning are the ones whose failure only shows up hours later: that a label is
counted once per window VISIT rather than once per probe, that a decided `text`
hint never enters the queue, and that Ctrl+C leaves a readable log behind.
"""

import argparse
import contextlib
import io
import itertools
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import shortcut_probe as sp  # noqa: E402


# Bold is a CATALOG-ONLY concept (icon name, no codepoint) and Save has both, so
# the fixture exercises each shape. System is a `text` hint.
WINDOWS = {
    "Word": [("Ctrl+B", "Bold"), ("Ctrl+T", "Transpose"), ("Ctrl+S", "Save")],
    "mousepad": [("Ctrl+T", "Transpose"), ("Ctrl+m", "Menubar"),
                 ("Alt+Space", "System")],
}


class WatchLoopTest(unittest.TestCase):
    def _run(self, focus_script, log_path):
        """Drive watch() with a scripted focus sequence and a stub probe."""
        ticks = itertools.count()
        state = {"window": focus_script[0]}

        def fake_focus(_backend):
            i = next(ticks)
            if i >= len(focus_script):
                raise KeyboardInterrupt        # stands in for the user's Ctrl+C
            state["window"] = focus_script[i]
            return ("pid", focus_script[i])

        def fake_probe(_args):
            name = state["window"]
            shortcuts = [sp.Shortcut(label=label, role="button", accel=accel,
                                     mods=0, keysym="", hid=4, displayable=True)
                         for accel, label in WINDOWS[name]]
            with contextlib.redirect_stdout(io.StringIO()):
                return [sp.report(name, shortcuts, 0,
                                  icons=sp._icon_matcher(), quiet=True)]

        original = (sp._focus_key, sp._focus_title, sp.main_atspi)
        sp._focus_key, sp._focus_title = fake_focus, lambda _b: state["window"]
        sp.main_atspi = fake_probe
        args = argparse.Namespace(unmatched=log_path, interval=0.0, reprobe=0.0001,
                                  app=None, all=False, focused=False, icons=True,
                                  quiet=True, max_nodes=20000)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                sp.watch(args, "atspi")
        finally:
            sp._focus_key, sp._focus_title, sp.main_atspi = original
        labels = {}
        if os.path.exists(log_path):
            with open(log_path, encoding="utf-8") as fh:
                labels = json.load(fh)["labels"]
        return labels, out.getvalue()

    def test_a_label_is_counted_once_per_visit_not_once_per_probe(self):
        """The property the ranking depends on.

        Re-probing one window all day would give Word's labels several hundred
        counts against another app's one, which destroys the frequency ordering
        the log exists to provide. Here Word is focused for four consecutive
        ticks and re-probed on every one.
        """
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.json")
            labels, _ = self._run(["Word"] * 4, log)
            self.assertEqual(labels["transpose"]["count"], 1)

    def test_revisiting_a_window_counts_again(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.json")
            labels, _ = self._run(["Word", "mousepad", "Word"], log)
            # Word twice + mousepad once, and both apps recorded.
            self.assertEqual(labels["transpose"]["count"], 3)
            self.assertEqual(sorted(labels["transpose"]["apps"]),
                             ["Word", "mousepad"])
            self.assertEqual(labels["menubar"]["count"], 1)

    def test_a_suppressed_label_never_enters_the_queue(self):
        """"System" is a decided `text` hint, so it must not be logged at all.

        Otherwise it resurfaces on every run and the review queue stops being read.
        """
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.json")
            labels, _ = self._run(["mousepad", "mousepad"], log)
            self.assertNotIn("system", labels)
            self.assertIn("transpose", labels)

    def test_a_catalog_only_match_does_not_crash_the_probe(self):
        """Bold has an icon NAME but no codepoint, and report() formatted the
        codepoint unconditionally -- so the first such match killed the run.

        The watch loop guards the probe call, which turned the crash into a
        silently missing label; only a test that reaches report() directly shows
        it as what it is.
        """
        with tempfile.TemporaryDirectory() as d:
            labels, out = self._run(["Word", "Word"], os.path.join(d, "l.json"))
            self.assertNotIn("probe failed", out)
            self.assertIn("transpose", labels)

    def test_ctrl_c_prints_a_summary_and_the_review(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "log.json")
            _, out = self._run(["Word", "mousepad"], log)
            self.assertIn("window visit(s)", out)
            self.assertIn("most frequent first", out)

    def test_a_session_that_logged_nothing_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "never-written.json")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = sp.review_unmatched(missing)
            self.assertEqual(rc, 0)
            self.assertIn("nothing logged yet", out.getvalue())

    def test_a_failing_probe_does_not_end_the_session(self):
        """A window can close mid-probe; an all-day run must survive it."""
        ticks = itertools.count()

        def fake_focus(_backend):
            if next(ticks) >= 3:
                raise KeyboardInterrupt
            return ("pid", "Boom")

        def exploding_probe(_args):
            raise RuntimeError("window vanished")

        original = (sp._focus_key, sp._focus_title, sp.main_atspi)
        sp._focus_key, sp._focus_title = fake_focus, lambda _b: "Boom"
        sp.main_atspi = exploding_probe
        with tempfile.TemporaryDirectory() as d:
            args = argparse.Namespace(unmatched=os.path.join(d, "l.json"),
                                      interval=0.0, reprobe=0.0001, app=None,
                                      all=False, focused=False, icons=True,
                                      quiet=True, max_nodes=20000)
            try:
                with contextlib.redirect_stdout(io.StringIO()) as out:
                    sp.watch(args, "atspi")
            finally:
                sp._focus_key, sp._focus_title, sp.main_atspi = original
        self.assertIn("probe failed", out.getvalue())
        self.assertIn("window visit(s)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
