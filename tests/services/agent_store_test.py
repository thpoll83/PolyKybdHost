"""services/agents/store.py: the agent registry across a host restart."""
import json
import os
import tempfile
import unittest

from polyhost.services.agents.model import AgentState
from polyhost.services.agents.registry import AgentRegistry
from polyhost.services.agents.store import AgentStore


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class AgentStoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "agents.json")

    def tearDown(self):
        self.dir.cleanup()

    def _registry(self, alive=(), mono=1000.0):
        return AgentRegistry(clock=_Clock(mono), is_alive=lambda pid: pid in alive)

    def test_round_trip_keeps_state_slot_and_title(self):
        wall = _Clock(50_000.0)
        first = self._registry(alive={42})
        first.report("claude-code", "a", "waiting", headline="Fix the build", pid=42,
                     cwd="/src/app")
        first.report("codex", "b", "done", machine="laptop", pid=7)
        AgentStore(first, self.path, wall_clock=wall).save_if_changed()

        wall.t += 120                                # the host was off for 2 min
        second = self._registry(alive={42}, mono=5.0)
        self.assertEqual(AgentStore(second, self.path, wall_clock=wall).load(), 2)
        got = {a.session_id: a for a in second.agents()}
        self.assertEqual(got["a"].state, AgentState.WAITING)
        self.assertEqual(got["a"].headline, "Fix the build")
        self.assertEqual(got["a"].slot, 0)
        self.assertEqual(got["b"].slot, 1)
        self.assertEqual(got["b"].machine, "laptop")   # a remote pid is not checked
        self.assertAlmostEqual(5.0 - got["a"].last_event, 120.0)

    def test_a_local_agent_whose_process_ended_is_not_restored(self):
        wall = _Clock()
        first = self._registry(alive={42})
        first.report("claude-code", "a", "idle", pid=42)
        AgentStore(first, self.path, wall_clock=wall).save_if_changed()
        second = self._registry(alive=())            # pid 42 is gone after the restart
        self.assertEqual(AgentStore(second, self.path, wall_clock=wall).load(), 0)
        self.assertEqual(second.agents(), [])

    def test_title_scan_entries_are_not_saved(self):
        reg = self._registry()
        reg.report("gemini", "win1", "working", source="title")
        AgentStore(reg, self.path).save_if_changed()
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["agents"], [])

    def test_the_time_rules_count_the_time_the_host_was_off(self):
        wall = _Clock(0.0)
        first = self._registry()
        first.report("codex", "a", "idle")
        AgentStore(first, self.path, wall_clock=wall).save_if_changed()
        wall.t += 5 * 3600                           # longer than the 4 h forget time
        second = self._registry()
        AgentStore(second, self.path, wall_clock=wall).load()
        second.tick()
        self.assertEqual(second.agents(), [])

    def test_writes_only_after_a_change(self):
        reg = self._registry()
        store = AgentStore(reg, self.path)
        reg.report("codex", "a", "idle")
        self.assertTrue(store.save_if_changed())
        self.assertFalse(store.save_if_changed())
        reg.report("codex", "a", "idle")            # every report counts (event time)
        self.assertTrue(store.save_if_changed())

    def test_missing_or_broken_file_restores_nothing(self):
        reg = self._registry()
        self.assertEqual(AgentStore(reg, self.path).load(), 0)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(AgentStore(reg, self.path).load(), 0)
        self.assertEqual(reg.agents(), [])


if __name__ == "__main__":
    unittest.main()
