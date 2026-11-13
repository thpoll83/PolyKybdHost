"""PolyCore drives the agent keys on the mock keyboard: the reserved pool slots,
the push, a key press read back, and nothing sent to firmware older than v31."""
import threading
import unittest
import unittest.mock as mock

from polyhost.core.poly_core import PolyCore
from polyhost.services.agents.model import AgentState
from polyhost.settings import PolySettings


class AgentKeysCoreTest(unittest.TestCase):

    def _core(self, protocol, **overrides):
        real_get = PolySettings.get
        values = {"dev_mock_primary": True, "dev_mock_protocol": protocol,
                  "unicode_send_composition_mode": True,
                  "brightness_set_daylight_dependent": False,
                  "agents_enabled": True, "agents_title_scan": False, **overrides}

        def get(settings, name):
            return values[name] if name in values else real_get(settings, name)

        for p in (mock.patch.object(PolySettings, "get", get),
                  mock.patch.object(PolySettings, "save", lambda *a, **k: True)):
            p.start()
            self.addCleanup(p.stop)
        core = PolyCore(mock.MagicMock(), start_worker=False)
        core.worker.start()
        self.addCleanup(core.shutdown)
        core.apply_reconnect(core._reconnect_probe(threading.Event()))
        core.worker.run_sync("barrier", lambda c: None, timeout=30)
        self.assertTrue(core.connected)
        return core

    def _pass(self, core):
        core.worker.run_sync("agents", core._agents_periodic, timeout=30)

    def test_push_and_press(self):
        core = self._core(31)
        fw = core.keeb.firmware
        self.assertEqual(core.device_mgr.primary.cache.capacity, 600)   # nothing reserved
        self.assertTrue(core._agents_active())
        ok, agent = core.agents_report({"vendor": "claude-code", "session_id": "s1",
                                        "state": "waiting", "cwd": "/w/polykybd-docs"})
        self.assertTrue(ok)
        self._pass(core)
        self.assertEqual(fw.ai_states[0], AgentState.WAITING)
        cache = core.device_mgr.primary.cache
        card = cache.holds(("agentcard", 0))
        self.assertEqual(fw.ai_slots[0], card)
        self.assertEqual(len(fw.ai_cards[card]), 360)
        self.assertTrue(any(fw.ai_cards[card]))
        extras = [cache.holds(("agentcard", 10)), cache.holds(("agentcard", 11))]
        self.assertEqual(fw.ai_slots[10:], extras)                # '-' and '+'
        self.assertTrue(all(any(fw.ai_cards[s]) for s in extras))
        self.assertEqual(fw.ai_flags, 0x04 | 0x08)               # one waits; extra cards

        raised = threading.Event()
        core._agent_keys.raise_agent = lambda a: raised.set() or True
        fw.ai_press(0)
        core._agent_keys.note_console("ai ev 1 0\n")
        self._pass(core)
        self.assertTrue(raised.wait(5))
        listing = core.agents_list()
        self.assertEqual(listing["agents"][0]["state"], "waiting")   # waiting is not "seen"
        self.assertTrue(listing["active"])

    def test_cloud_sessions_connect_status_disconnect(self):
        import os
        import tempfile
        from polyhost.server import protocol
        from polyhost.services.agents import cloud_relay
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "cloud_relay.json")
        calls = []

        def http(url, method, rel, token=None, body=None):
            calls.append((method, rel))
            return (201 if method == "POST" else 200), {"ok": True}
        started = []
        for p in (mock.patch.object(protocol, "cloud_relay_path", lambda: path),
                  mock.patch.object(cloud_relay, "http_call", http),
                  mock.patch.object(cloud_relay.RelayClient, "start",
                                    lambda client: started.append(client))):
            p.start()
            self.addCleanup(p.stop)
        core = self._core(31)
        self.assertFalse(core.agents_cloud_status()["configured"])
        self.assertEqual(started, [])                    # no channel: no connection

        ok, status = core.agents_cloud_connect()
        self.assertTrue(ok, status)
        self.assertTrue(status["configured"])
        self.assertEqual(calls, [("POST", "/v1/channels")])
        self.assertEqual(len(started), 1)
        channel = cloud_relay.load_channel(path)
        self.assertEqual(status["setup"]["config"], cloud_relay.setup_config(channel))
        ok, _status = core.agents_cloud_connect()        # again: the same channel
        self.assertEqual(calls, [("POST", "/v1/channels")])
        self.assertEqual(len(started), 1)

        core.agents.report("claude-code", "c" * 32, "working", machine="cloud")
        core.agents.report("claude-code", "local", "working")
        ok, result = core.agents_cloud_disconnect()
        self.assertTrue(ok)
        self.assertEqual(result, "deleted")
        self.assertEqual(calls[-1], ("DELETE", f"/v1/c/{channel['channel']}"))
        self.assertFalse(os.path.exists(path))
        self.assertEqual([a.session_id for a in core.agents.agents()], ["local"])
        self.assertIsNone(core._cloud_relay)

    def test_removing_a_cloud_agent_removes_it_on_the_relay(self):
        from polyhost.services.agents import cloud_relay
        deleted = []
        core = self._core(31)          # built first: start-up also reads the channel
        for p in (mock.patch.object(cloud_relay, "load_channel", lambda path: {"x": 1}),
                  mock.patch.object(cloud_relay, "delete_session",
                                    lambda ch, k: deleted.append(k) or True)):
            p.start()
            self.addCleanup(p.stop)
        core.agents.report("claude-code", "c" * 32, "done", machine="cloud")
        core.agents.report("claude-code", "d" * 32, "working", machine="cloud")
        core.agents.report("codex", "local", "idle")
        core.agents.report("codex", "busy", "working")
        self.assertEqual(core.agents_forget("claude-code", "d" * 32), (True, "ok"))
        self.assertEqual(deleted, ["d" * 32])
        ok, n = core.agents_forget_inactive()
        self.assertEqual((ok, n), (True, 2))                    # the done cloud one, the idle local one
        self.assertEqual(deleted, ["d" * 32, "c" * 32])          # only cloud agents go to the relay
        self.assertEqual([a.session_id for a in core.agents.agents()], ["busy"])

    def test_old_firmware_gets_nothing(self):
        core = self._core(30)
        core.agents_report({"vendor": "codex", "session_id": "a", "state": "working"})
        self._pass(core)
        self.assertFalse(core._agents_active())
        self.assertEqual(core.keeb.firmware.refused, [])

    def test_remote_agents_need_their_own_opt_in(self):
        params = {"vendor": "codex", "session_id": "r1", "state": "waiting",
                  "machine": "laptop"}
        core = self._core(31)                                    # agents on, remote off
        ok, msg = core.agents_report_remote(params)
        self.assertFalse(ok)
        self.assertIn("agents_remote_enabled", msg)
        self.assertEqual(core.agents_list()["agents"], [])
        self.assertEqual(core.agent_relay_for("laptop"), {})
        logged = [c for c in core.log.info.call_args_list if "refused" in str(c)]
        self.assertEqual(len(logged), 1)
        core.agents_report_remote(params)                        # logged once only
        self.assertEqual(len([c for c in core.log.info.call_args_list
                              if "refused" in str(c)]), 1)
        core = self._core(31, agents_remote_enabled=True)
        ok, _ = core.agents_report_remote(params)
        self.assertTrue(ok)
        self.assertEqual(core.agent_relay_for("laptop"), {"agents_fast": True})
        core = self._core(31, agents_enabled=False, agents_remote_enabled=True)
        self.assertFalse(core.agents_report_remote(params)[0])

    def test_shutdown_and_turning_off_clear_the_keys(self):
        core = self._core(31)
        fw = core.keeb.firmware
        core.agents_report({"vendor": "codex", "session_id": "a", "state": "working"})
        self._pass(core)
        self.assertEqual(fw.ai_states[0], AgentState.WORKING)
        core.shutdown()
        self.assertEqual(list(fw.ai_states), [AgentState.EMPTY] * 10)

        core = self._core(31)
        fw = core.keeb.firmware
        core.agents_report({"vendor": "codex", "session_id": "a", "state": "waiting"})
        self._pass(core)
        with mock.patch.object(PolySettings, "get",
                               lambda s, n: False if n == "agents_enabled" else None):
            core.note_settings_changed({"agents_enabled"})
        core.worker.run_sync("barrier", lambda c: None, timeout=30)
        self.assertEqual(list(fw.ai_states), [AgentState.EMPTY] * 10)
        self.assertEqual(fw.ai_flags, 0)

    def test_off_sends_nothing(self):
        core = self._core(31, agents_enabled=False)
        core.agents_report({"vendor": "codex", "session_id": "a", "state": "working"})
        self._pass(core)
        self.assertFalse(core._agents_active())
        self.assertEqual(core.keeb.firmware.ai_cards, {})
        self.assertEqual(core.agents_list()["enabled"], False)


if __name__ == "__main__":
    unittest.main()
