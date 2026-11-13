"""Tray > AI Agents: the submenu built from core.agents_list(), the switch and the
raise. Driven on the real PolyHost methods with a stand-in self."""
import os
import types
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication, QMenu
    from polyhost.host import PolyHost
    _QT = True
except Exception:  # noqa: BLE001 - no Qt or no display: skip
    _QT = False


class _Stub:
    """A stand-in self; a plain class, because Qt needs a weak reference to a bound
    method's owner when a signal is connected to it."""


@unittest.skipUnless(_QT, "needs PyQt5 and a display (xvfb-run)")
class AgentsMenuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _host(self):
        host = _Stub()
        host.agents_menu = QMenu()
        host.core = mock.MagicMock()
        host.calls = []
        host._core_click = lambda fn, done: (host.calls.append(fn), done(*fn()))
        host.log = mock.MagicMock()
        host.report_device_result = mock.MagicMock()
        for name in ("_build_agents_menu", "_set_agent_rows", "_apply_agents_menu",
                     "_toggle_agents_enabled", "_raise_agent_clicked", "_show_pairing_code",
                     "_show_cloud_sessions"):
            setattr(host, name, types.MethodType(getattr(PolyHost, name), host))
        host._build_agents_menu()
        return host

    def _texts(self, menu):
        return [a.text() for a in menu.actions() if not a.isSeparator()]

    def test_lists_agents_and_raises_on_click(self):
        host = self._host()
        host.core.agents_raise.return_value = (True, "raising")
        host._apply_agents_menu({"enabled": True, "agents": [
            {"vendor": "claude-code", "session_id": "s1", "state": "waiting", "key": 0,
             "page": 0, "headline": "fix the build"},
            {"vendor": "codex", "session_id": "s2", "state": "idle", "key": 0,
             "page": 1, "headline": "docs"}]})
        texts = self._texts(host.agents_menu)
        self.assertEqual(texts[0], "Show on the Number Row")
        self.assertTrue(host.agents_menu.actions()[0].isChecked())
        self.assertIn("Key 1: Claude Code, waiting, fix the build", texts)
        self.assertIn("Page 2, Key 1: Codex, idle, docs", texts)
        self.assertIn("Set Up Hooks", texts)
        self.assertIn("Pair a Forwarder…", texts)
        act = next(a for a in host.agents_menu.actions() if a.text().startswith("Key 1: Claude"))
        host.sender = lambda: act
        host._raise_agent_clicked()
        host.core.agents_raise.assert_called_once_with("claude-code", "s1")

    def test_empty_and_switch(self):
        host = self._host()
        host.core.settings_set.return_value = (True, "agents_enabled")
        host._apply_agents_menu({"enabled": False, "agents": []})
        self.assertIn("No agents reported", self._texts(host.agents_menu))
        self.assertFalse(host.agents_menu.actions()[0].isChecked())
        host._toggle_agents_enabled(True)
        host.core.settings_set.assert_called_once_with("agents_enabled", True, source="tray")
        host.report_device_result.assert_not_called()

    def test_set_up_hooks_is_there_before_the_agent_list_arrives(self):
        host = self._host()            # built, no core.agents_list() answer yet
        texts = self._texts(host.agents_menu)
        self.assertEqual(texts, ["Show on the Number Row", "No agents reported",
                                 "Set Up Hooks", "Pair a Forwarder…",
                                 "Connect Cloud Sessions…"])

    def test_set_up_hooks_and_pair_have_icons(self):
        host = self._host()
        acts = {a.text(): a for a in host.agents_menu.actions()}
        self.assertFalse(acts["Set Up Hooks"].icon().isNull())
        self.assertFalse(acts["Pair a Forwarder…"].icon().isNull())
        self.assertFalse(acts["Connect Cloud Sessions…"].icon().isNull())

    def test_a_failed_fetch_keeps_the_menu(self):
        host = self._host()
        host._apply_agents_menu({"enabled": True, "agents": [
            {"vendor": "codex", "session_id": "s", "state": "done", "key": 2, "headline": "x"}]})
        before = self._texts(host.agents_menu)
        host._apply_agents_menu(RuntimeError("daemon busy"))
        self.assertEqual(self._texts(host.agents_menu), before)

    def test_rows_are_replaced_not_added(self):
        host = self._host()
        rows = [{"vendor": "codex", "session_id": "s", "state": "done", "key": 0,
                 "headline": "x"}]
        host._apply_agents_menu({"enabled": True, "agents": rows})
        host._apply_agents_menu({"enabled": True, "agents": rows})
        texts = self._texts(host.agents_menu)
        self.assertEqual(texts.count("Key 1: Codex, done, x"), 1)
        self.assertEqual(texts.count("Set Up Hooks"), 1)
        self.assertNotIn("No agents reported", texts)


@unittest.skipUnless(_QT, "needs PyQt5 and a display (xvfb-run)")
class AgentHooksMenuTest(unittest.TestCase):
    """gui/agent_hooks.py: the submenu the tray app and the forwarder share."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_menu_lists_the_vendors_and_installs_on_click(self):
        from polyhost.gui import agent_hooks
        menu = QMenu()
        sub = agent_hooks.add_setup_menu(menu, mock.MagicMock(), title="Set Up Agent Hooks")
        self.assertEqual(sub.title(), "Set Up Agent Hooks")
        self.assertEqual([a.text() for a in sub.actions()],
                         ["Claude Code", "Codex", "Copilot CLI", "Gemini CLI", "Qwen Code",
                      "OpenCode"])
        with mock.patch.object(agent_hooks, "install") as install:
            sub.actions()[1].trigger()
        self.assertEqual(install.call_args[0][0], "codex")


@unittest.skipUnless(_QT, "needs PyQt5 and a display (xvfb-run)")
class AgentOpenRequestTest(unittest.TestCase):
    """A cloud session's key found no window: the tray asks before opening."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _host(self):
        host = _Stub()
        host.log = mock.MagicMock()
        host._on_agent_open_request = types.MethodType(PolyHost._on_agent_open_request, host)
        self.addCleanup(lambda: getattr(host, "_agent_open_box", None)
                        and host._agent_open_box.close())
        return host

    def test_asks_and_opens_only_on_open(self):
        url = "https://claude.ai/code/session_abc"
        host = self._host()
        with mock.patch("PyQt5.QtGui.QDesktopServices.openUrl") as open_url:
            host._on_agent_open_request({"url": url, "title": "Fix the build"})
            box = host._agent_open_box
            self.assertTrue(box.isVisible())
            self.assertIn("Fix the build", box.text())
            self.assertEqual(box.informativeText(), url)
            open_url.assert_not_called()
            host._on_agent_open_request({"url": url + "2", "title": "Other"})
            self.assertIs(host._agent_open_box, box)          # one box, newest wins
            box.buttonClicked.emit(host._agent_open_button)
            self.assertEqual(open_url.call_args[0][0].toString(), url + "2")

    def test_a_foreign_address_is_not_offered(self):
        host = self._host()
        host._on_agent_open_request({"url": "https://evil.example/", "title": "x"})
        host._on_agent_open_request("garbage")
        self.assertIsNone(getattr(host, "_agent_open_box", None))


if __name__ == "__main__":
    unittest.main()
