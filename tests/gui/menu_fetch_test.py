"""MenuFetcher: a menu's core call runs off the GUI thread, and its answer is
applied on the GUI thread. A call that never returns must not block the GUI."""
import threading
import unittest

from PyQt5.QtWidgets import QApplication

from polyhost.gui.menu_fetch import MenuFetcher, ok_value


class MenuFetcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_a_stalled_call_does_not_block_the_caller(self):
        fetcher = MenuFetcher()
        release = threading.Event()
        applied = []
        fetcher.fetch("k", lambda: release.wait(10) and (True, 3), applied.append)
        # fetch() returned while the call is still blocked: nothing applied yet.
        self.assertEqual(applied, [])
        self.assertTrue(fetcher.busy())
        release.set()
        self.assertTrue(fetcher.wait_idle())
        self.assertEqual(applied, [(True, 3)])

    def test_apply_runs_on_the_gui_thread(self):
        fetcher = MenuFetcher()
        threads = []
        fetcher.fetch("k", lambda: threading.current_thread(),
                      lambda fetch_thread: threads.append((fetch_thread, threading.current_thread())))
        self.assertTrue(fetcher.wait_idle())
        fetch_thread, apply_thread = threads[0]
        self.assertIsNot(fetch_thread, threading.main_thread())
        self.assertIs(apply_thread, threading.main_thread())

    def test_one_call_per_key_in_flight(self):
        fetcher = MenuFetcher()
        release = threading.Event()
        calls = []

        def fn():
            calls.append(1)
            release.wait(10)
            return True, None

        self.assertTrue(fetcher.fetch("k", fn, lambda r: None))
        self.assertFalse(fetcher.fetch("k", fn, lambda r: None))
        self.assertTrue(fetcher.fetch("other", lambda: (True, None), lambda r: None))
        release.set()
        self.assertTrue(fetcher.wait_idle())
        self.assertEqual(len(calls), 1)

    def test_an_exception_reaches_apply_and_a_bad_apply_is_contained(self):
        fetcher = MenuFetcher()
        got = []

        def boom():
            raise RuntimeError("daemon gone")

        fetcher.fetch("k", boom, got.append)
        fetcher.fetch("j", lambda: (True, 1), lambda r: 1 / 0)
        self.assertTrue(fetcher.wait_idle())
        self.assertIsInstance(got[0], RuntimeError)
        self.assertEqual(ok_value(got[0]), (False, "daemon gone"))
        self.assertFalse(fetcher.busy())

    def test_clicks_run_in_order_one_at_a_time(self):
        fetcher = MenuFetcher()
        order, running, overlap = [], [0], []

        def make(i):
            def fn():
                running[0] += 1
                overlap.append(running[0])
                order.append(i)
                running[0] -= 1
                return True, i
            return fn

        applied = []
        for i in range(20):
            fetcher.call(make(i), applied.append)
        self.assertTrue(fetcher.wait_idle())
        self.assertEqual(order, list(range(20)))
        self.assertEqual(max(overlap), 1)
        self.assertEqual([v for _ok, v in applied], list(range(20)))

    def test_a_click_without_apply_is_still_run(self):
        fetcher = MenuFetcher()
        ran = threading.Event()
        fetcher.call(ran.set)
        self.assertTrue(fetcher.wait_idle())
        self.assertTrue(ran.is_set())

    def test_ok_value(self):
        self.assertEqual(ok_value((True, 5)), (True, 5))
        self.assertEqual(ok_value([1, "x"]), (True, "x"))
        self.assertEqual(ok_value(None), (False, None))


class TrayRefreshDoesNotWaitTest(unittest.TestCase):
    """Settings > Keyboard reads and sends off the GUI thread: a stalled core does
    not block the dialog, and the answer fills it when it comes."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _host(self, release):
        import logging
        import types
        from polyhost.host import PolyHost

        def stalled(*_a):
            release.wait(10)
            return True, 1

        core = types.SimpleNamespace(
            get_glyph_size=stalled, get_idle_style=stalled, get_glyph_script=stalled,
            get_idle_timeout=lambda: (stalled() and (True, (1, 60))),
            get_glyph_placement=stalled,
            get_tap_terms=lambda: (False, "no tap terms"))
        host = types.SimpleNamespace(_menu_fetch=MenuFetcher(), core=core,
                                     log=logging.getLogger("test"))
        host._core_click = lambda fn, done: PolyHost._core_click(host, fn, done)
        return host, PolyHost

    def test_keyboard_changes_return_while_the_core_is_stalled(self):
        from polyhost.gui import keyboard_settings as kbd
        release = threading.Event()
        host, PolyHost = self._host(release)
        reported = []
        host.core.set_glyph_size = lambda v: release.wait(10) and (False, "busy")
        host.report_device_result = lambda *a: reported.append(a)
        PolyHost._send_keyboard_changes(host, {kbd.GLYPH_SIZE: 2})   # returns at once
        self.assertEqual(reported, [])
        release.set()
        self.assertTrue(host._menu_fetch.wait_idle())
        self.assertEqual(len(reported), 1)          # the refusal is reported
        host._keyboard_settings_message.close()

    def test_keyboard_rows_fill_after_the_answer(self):
        from polyhost.gui import keyboard_settings as kbd
        from polyhost.gui.settings_dialog import SettingsDialog
        release = threading.Event()
        host, PolyHost = self._host(release)
        dlg = SettingsDialog()
        dlg.setup({"ui_theme": "auto"}, keyboard=True)
        host._settings_dlg = dlg
        host._menu_fetch.fetch("keyboard_settings", lambda: kbd.read_all(host.core),
                               lambda r: PolyHost._apply_keyboard_reads(host, r))
        size = dlg.keyboard_widgets[kbd.GLYPH_SIZE]
        self.assertFalse(size.isEnabled())          # still reading
        release.set()
        self.assertTrue(host._menu_fetch.wait_idle())
        self.assertTrue(size.isEnabled())
        self.assertEqual(size.value(), 1)
        # No tap terms on this keyboard: those rows stay disabled.
        self.assertFalse(dlg.keyboard_widgets[kbd.TAPPING_TERM].isEnabled())
        dlg.close()


if __name__ == "__main__":
    unittest.main()
