"""The agent registry, the hook and title adapters, the card, and the controller
against the emulated firmware (cmd 45/46, protocol v30)."""
import unittest

from polyhost.services.agents import hooks, registry as reg_mod
from polyhost.services.agents.card import (card_bytes, fit_text, render_card,
                                           render_dictation_card, render_next_waiting_card)
from polyhost.services.agents import dictation
from polyhost.services.agents.controller import (DICTATION_KEY, NEXT_WAITING_KEY, NO_SLOT,
                                                 PAGER_KEY, AgentKeysController)
from polyhost.services.agents.model import ENDED, AgentState
from polyhost.services.agents.raiser import raise_agent
from polyhost.services.agents.registry import AgentRegistry
from polyhost.services.agents.titles import TitleScanner, parse_title


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        self.r = AgentRegistry(clock=self.clock)

    def test_slots_are_stable_and_reused(self):
        self.r.report("claude-code", "a", "working")
        self.r.report("codex", "b", "working")
        self.r.report("gemini", "c", "idle")
        self.r.report("codex", "b", "done")           # a state change keeps the key
        self.assertEqual([a.slot for a in self.r.agents()], [0, 1, 2])
        self.r.report("codex", "b", ENDED)
        self.r.report("aider", "d", "working")        # takes the freed key 1
        slots = {a.session_id: a.slot for a in self.r.agents()}
        self.assertEqual(slots, {"a": 0, "d": 1, "c": 2})

    def test_pages(self):
        for i in range(12):
            self.r.report("claude-code", f"s{i}", "working")
        self.assertEqual(self.r.page_count(), 2)
        page2 = self.r.page(1)
        self.assertEqual([a.session_id if a else None for a in page2[:3]], ["s10", "s11", None])
        self.r.report("claude-code", "s11", "waiting")
        self.assertTrue(self.r.waiting_elsewhere(0))
        self.assertFalse(self.r.waiting_elsewhere(1))

    def test_mark_seen_turns_done_into_idle(self):
        self.r.report("claude-code", "a", "done")
        self.r.mark_seen("claude-code", "a")
        self.assertEqual(self.r.agents()[0].state, AgentState.IDLE)
        # Claude Code's idle reminder after that changes nothing.
        self.r.report("claude-code", "a", "done", event="idle_prompt")
        self.assertEqual(self.r.agents()[0].state, AgentState.IDLE)

    def test_inferred_waiting_for_vendors_without_a_permission_event(self):
        self.r.report("antigravity", "a", "working", event="pretool")
        self.r.report("claude-code", "b", "working", event="pretool")
        self.clock.t += reg_mod.PENDING_TOOL_WAIT_S + 0.1
        self.r.tick()
        states = {a.vendor: a for a in self.r.agents()}
        self.assertEqual(states["antigravity"].state, AgentState.WAITING)
        self.assertTrue(states["antigravity"].waiting_inferred)
        self.assertEqual(states["claude-code"].state, AgentState.WORKING)

    def test_post_tool_clears_the_inference(self):
        self.r.report("copilot", "a", "working", event="pretool")
        self.clock.t += 1
        self.r.report("copilot", "a", "working", event="posttool")
        self.clock.t += reg_mod.PENDING_TOOL_WAIT_S + 1
        self.r.tick()
        self.assertEqual(self.r.agents()[0].state, AgentState.WORKING)

    def test_stale_and_forget(self):
        self.r.report("codex", "a", "working")
        self.clock.t += reg_mod.STALE_AFTER_S + 1
        self.r.tick()
        self.assertEqual(self.r.agents()[0].state, AgentState.STALE)
        self.clock.t += reg_mod.FORGET_AFTER_S
        self.r.tick()
        self.assertEqual(self.r.agents(), [])

    def test_a_hook_replaces_title_entries_of_its_vendor(self):
        self.r.report("claude-code", "title:1", "done", source="title")
        self.assertEqual(len(self.r.agents()), 1)
        self.r.report("claude-code", "real", "working")
        self.assertEqual([a.session_id for a in self.r.agents()], ["real"])
        self.assertIsNone(self.r.report("claude-code", "title:2", "done", source="title"))

    def test_headline_order(self):
        self.r.report("codex", "a", "working", cwd="/home/u/polykybd-docs/")
        self.assertEqual(self.r.agents()[0].display_headline, "polykybd-docs")
        self.r.report("codex", "a", None, headline="fix the build")
        self.assertEqual(self.r.agents()[0].display_headline, "fix the build")
        self.r.label("codex", "a", "docs")
        self.assertEqual(self.r.agents()[0].display_headline, "docs")

    def test_same_folder_is_numbered(self):
        # Two Claude Code sessions in C:\\ws\\agent (field, 2026-11-10): both showed
        # "agent". They are numbered in key order; a unique one stays plain.
        self.r.report("claude-code", "a", "working", cwd="C:\\ws\\team-core2")
        self.r.report("claude-code", "b", "idle", cwd="C:\\ws\\agent")
        self.r.report("claude-code", "c", "idle", cwd="C:\\ws\\agent")
        self.assertEqual([a.display_headline for a in self.r.agents()],
                         ["team-core2", "agent 1", "agent 2"])
        self.r.label("claude-code", "c", "review")
        self.assertEqual([a.display_headline for a in self.r.agents()],
                         ["team-core2", "agent", "review"])

    def test_refuses_without_vendor_or_session(self):
        self.assertIsNone(self.r.report("", "a", "working"))
        self.assertIsNone(self.r.report("codex", "", "working"))
        with self.assertRaises(ValueError):
            self.r.report("codex", "a", "sleepy")


class HookTest(unittest.TestCase):
    def test_claude_code(self):
        base = {"session_id": "s1", "cwd": "/w/repo"}
        cases = {
            "SessionStart": AgentState.IDLE, "UserPromptSubmit": AgentState.WORKING,
            "PreToolUse": AgentState.WORKING, "PermissionRequest": AgentState.WAITING,
            "Stop": AgentState.DONE, "SessionEnd": ENDED,
        }
        for event, state in cases.items():
            r = hooks.interpret({**base, "hook_event_name": event, "prompt": "secret"})
            self.assertEqual(r["state"], state, event)
            self.assertEqual(r["session_id"], "s1")
            self.assertNotIn("secret", repr(r))
        n = hooks.interpret({**base, "hook_event_name": "Notification",
                             "notification_type": "permission_prompt"})
        self.assertEqual(n["state"], AgentState.WAITING)
        n = hooks.interpret({**base, "hook_event_name": "Notification",
                             "notification_type": "idle_prompt"})
        self.assertEqual((n["state"], n["event"]), (AgentState.DONE, "idle_prompt"))
        self.assertIsNone(hooks.interpret({**base, "hook_event_name": "SubagentStop"}))

    def test_other_vendors(self):
        self.assertEqual(hooks.interpret({"type": "agent-turn-complete", "thread-id": "t"})["state"],
                         AgentState.DONE)                                   # Codex notify
        self.assertEqual(hooks.interpret({"hook_event_name": "BeforeTool", "session_id": "g",
                                          })["event"], "pretool")           # Gemini
        self.assertEqual(hooks.interpret({"hookEventName": "preToolUse", "sessionId": "c"})["event"],
                         "pretool")                                         # Copilot
        oc = hooks.interpret({"type": "permission.asked", "properties": {"sessionID": "o"}})
        self.assertEqual((oc["session_id"], oc["state"]), ("o", AgentState.WAITING))  # OpenCode

    def test_transcript_title(self):
        import json
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"type": "user", "message": "secret prompt"}) + "\n")
                fh.write(json.dumps({"type": "summary", "summary": "Old title"}) + "\n")
                fh.write("not json\n")
                fh.write(json.dumps({"type": "summary", "summary": "Fix  the\nbuild"}) + "\n")
                fh.write(json.dumps({"type": "assistant", "message": "x"}) + "\n")
            self.assertEqual(hooks.transcript_title(path), "Fix the build")   # newest
            self.assertEqual(hooks.transcript_title(os.path.join(tmp, "missing")), "")
        self.assertEqual(hooks.transcript_title(None), "")

    def test_copilot_with_the_event_on_the_command_line(self):
        # Copilot CLI's hook JSON may name neither the event nor a session.
        r = hooks.interpret({"cwd": "C:\\ws\\app", "toolName": "bash"}, event="preToolUse")
        self.assertEqual((r["session_id"], r["state"], r["event"]),
                         ("cwd:C:\\ws\\app", AgentState.WORKING, "pretool"))
        self.assertEqual(hooks.interpret({"cwd": "/w"}, event="agentStop")["state"],
                         AgentState.DONE)
        self.assertEqual(hooks.interpret({"cwd": "/w"}, event="errorOccurred")["state"],
                         AgentState.DONE)
        self.assertEqual(hooks.interpret({"cwd": "/w"}, event="sessionEnd")["state"], ENDED)
        # --event takes priority over a name in the payload.
        self.assertEqual(hooks.interpret({"session_id": "s", "hook_event_name": "Stop"},
                                         event="userPromptSubmitted")["state"],
                         AgentState.WORKING)
        self.assertIsNone(hooks.interpret({}, event="agentStop"))   # no session, no cwd

    def test_garbage(self):
        self.assertIsNone(hooks.interpret({"hook_event_name": "Stop"}))   # no session
        self.assertIsNone(hooks.interpret({"session_id": "a", "hook_event_name": "Whatever"}))
        self.assertIsNone(hooks.interpret([1, 2]))


class TitleTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_title("✳ Fix the build"),
                         ("claude-code", AgentState.DONE, "Fix the build"))
        self.assertEqual(parse_title("◐ Fix the build")[:2],
                         ("claude-code", AgentState.WORKING))
        self.assertIsNone(parse_title("✳︎ qwen session"))       # Qwen, not Claude
        self.assertEqual(parse_title("✋  Action Required (repo)")[:2],
                         ("gemini", AgentState.WAITING))
        self.assertEqual(parse_title("[ ! ] Action Required")[:2], ("codex", AgentState.WAITING))
        self.assertIsNone(parse_title("vim claude.md"))
        self.assertIsNone(parse_title(""))

    def test_scanner_adds_and_drops(self):
        r = AgentRegistry()
        windows = [("1", "✳ topic"), ("2", "bash")]
        scanner = TitleScanner(r, log=None, lister=lambda: windows)
        scanner.scan_once()
        self.assertEqual([(a.session_id, a.window) for a in r.agents()], [("title:1", "1")])
        windows[:] = [("2", "bash")]
        scanner.scan_once()
        self.assertEqual(r.agents(), [])


class CardTest(unittest.TestCase):
    def test_card_is_360_bytes_and_inside_the_panel(self):
        img = render_card("claude-code", AgentState.WAITING, "polykybd-docs", marks=None)
        self.assertEqual(img.shape, (40, 72))
        self.assertTrue(img.any())
        self.assertEqual(len(card_bytes(img)), 360)

    def test_extra_cards(self):
        for img in (render_dictation_card(), render_next_waiting_card(0),
                    render_next_waiting_card(3), render_next_waiting_card(250)):
            self.assertEqual(img.shape, (40, 72))
            self.assertTrue(img.any())
        self.assertFalse((render_next_waiting_card(0) == render_next_waiting_card(3)).all())

    def test_fit_text(self):
        self.assertEqual(fit_text("short"), "short")
        from polyhost.services.agents.card import _measure
        long = fit_text("a headline that is far too long for one key")
        self.assertTrue(long.endswith("."))
        # Measured as DRAWN (no anti-aliasing), which is wider than font.getbbox says.
        self.assertLessEqual(_measure(long)[2], 70)
        self.assertLessEqual(_measure(fit_text("polykybd-docs"))[2], 70)


class _FakeKeeb:
    """Records what the controller sends; events are injected by tests."""
    def __init__(self):
        self.cards, self.keys, self.events, self.newest = {}, [], [], 0

    def ai_upload_card(self, slot, data):
        self.cards[slot] = data
        return True, "ok"

    def ai_set_keys(self, states, esc, slots):
        self.keys.append((states, esc, slots))
        return True, "ok"

    def ai_read_events(self, last_seq):
        newer = [e for e in self.events if e[0] > last_seq]
        return True, (self.newest, newer)

    def press(self, key):
        self.newest += 1
        self.events.append((self.newest, key))


class _NoMarks:
    version = 0

    def get(self, vid):
        return None


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.r = AgentRegistry()
        self.raised = []
        self.dictated = []
        from polyhost.device.overlay_cache import OverlayMRUCache
        self.cache = OverlayMRUCache(600)
        self.c = AgentKeysController(self.r, lambda: self.cache,
                                     raise_agent=lambda a: self.raised.append(a.session_id) or True,
                                     marks=_NoMarks(),
                                     dictate=lambda: self.dictated.append(1) or True)
        self.c._raise = lambda agent: self.c.raise_agent(agent)   # no thread in tests
        self.c._run_dictate = lambda: self.c.dictate()
        self.kb = _FakeKeeb()

    def test_pushes_only_changes(self):
        self.r.report("claude-code", "a", "working")
        self.c.sync(self.kb)
        # Slots borrowed from the empty cache: key 1, '-', '+' in that order.
        self.assertEqual(sorted(self.kb.cards), [0, 1, 2])
        states, flags, slots = self.kb.keys[-1]
        self.assertEqual(states[:2], [AgentState.WORKING, AgentState.EMPTY])
        self.assertEqual(slots[:2], [0, NO_SLOT])
        self.assertEqual(slots[10:], [1, 2])
        self.assertEqual(flags, 0x08)                    # extra cards only: one page, none waits
        self.c.sync(self.kb)
        self.assertEqual(len(self.kb.keys), 1)            # nothing changed: nothing sent
        self.r.report("claude-code", "a", "waiting")
        self.kb.cards.clear()
        self.c.sync(self.kb)
        # The card shows the state, and '+' shows the waiting count.
        self.assertEqual(sorted(self.kb.cards), [0, 2])
        self.assertEqual(self.kb.keys[-1][1], 0x08 | 0x04)
        self.assertEqual(len(self.kb.keys), 2)

    def test_reconnect_resends(self):
        self.r.report("codex", "a", "working")
        self.c.sync(self.kb)
        self.c.forget_device()
        kb2 = _FakeKeeb()
        self.c.sync(kb2)
        self.assertEqual(sorted(kb2.cards), [0, 1, 2])
        self.assertEqual(len(kb2.keys), 1)

    def test_press_raises_and_marks_seen(self):
        self.r.report("codex", "a", "done")
        self.c.sync(self.kb)                    # first read sets the baseline
        self.kb.press(0)
        self.c.note_console("ai ev 1 0\n")
        self.c.sync(self.kb)
        self.assertEqual(self.raised, ["a"])
        self.assertEqual(self.r.agents()[0].state, AgentState.IDLE)

    def test_press_is_read_without_a_console_line_or_G(self):
        # In steady state the host polls GET_LANG, not GET_ID, so G does not move,
        # and the console line can be lost: the ring is read on every pass.
        self.r.report("codex", "a", "done")
        self.c.sync(self.kb)
        self.kb.press(0)
        self.c.sync(self.kb)
        self.assertEqual(self.raised, ["a"])

    def test_console_line_split_over_two_reads(self):
        self.c.sync(self.kb)
        self.c.note_console("x ai e")
        self.c.note_console("v 3 1\n")
        self.assertTrue(self.c._read_events)

    def test_last_press_says_what_happened(self):
        # The real _raise (it records the result), still without a thread.
        self.c._raise = lambda agent: AgentKeysController._raise(self.c, agent)
        self.r.report("codex", "a", "done")
        self.c.sync(self.kb)
        self.kb.press(4)                       # key 5: nobody there
        self.c.sync(self.kb)
        self.assertEqual(self.c.last_press["result"], "no agent on this key")
        self.kb.press(0)
        self.c.sync(self.kb)
        self.assertEqual(self.c.last_press["result"], "raised")
        self.assertIn("codex", self.c.last_press["agent"])

    def test_presses_before_the_first_read_are_ignored(self):
        self.r.report("codex", "a", "done")
        self.kb.press(0)
        self.c.sync(self.kb)
        self.assertEqual(self.raised, [])

    def test_pager(self):
        for i in range(11):
            self.r.report("claude-code", f"s{i}", "working")
        self.c.sync(self.kb)
        self.kb.press(PAGER_KEY)
        self.c.note_state_generation(5)
        self.c.sync(self.kb)
        self.assertEqual(self.c.page, 1)
        states = self.kb.keys[-1][0]
        self.assertEqual(states[:2], [AgentState.WORKING, AgentState.EMPTY])
        self.kb.press(PAGER_KEY)
        self.c.note_state_generation(6)
        self.c.sync(self.kb)
        self.assertEqual(self.c.page, 0)

    def test_esc_attention_for_a_waiting_agent_on_another_page(self):
        for i in range(11):
            self.r.report("claude-code", f"s{i}", "working")
        self.r.report("claude-code", "s10", "waiting")
        self.c.sync(self.kb)
        self.assertEqual(self.kb.keys[-1][1], 0x01 | 0x02 | 0x04 | 0x08)

    def test_more_pages_flag_only_with_a_second_page(self):
        for i in range(10):
            self.r.report("claude-code", f"s{i}", "working")
        self.c.sync(self.kb)
        self.assertFalse(self.kb.keys[-1][1] & 0x02)
        self.r.report("claude-code", "s10", "working")
        self.c.sync(self.kb)
        self.assertTrue(self.kb.keys[-1][1] & 0x02)

    def test_plus_cycles_the_waiting_agents_across_pages(self):
        for i in range(12):
            self.r.report("claude-code", f"s{i}", "working")
        for sid in ("s3", "s11"):
            self.r.report("claude-code", sid, "waiting")
        self.c.sync(self.kb)
        for expected_page, expected in ((0, "s3"), (1, "s11"), (0, "s3")):
            self.kb.press(NEXT_WAITING_KEY)
            self.c.note_console("ai ev")
            self.c.sync(self.kb)
            self.assertEqual(self.raised[-1], expected)
            self.assertEqual(self.c.page, expected_page)

    def test_minus_dictates(self):
        self.c.sync(self.kb)
        self.kb.press(DICTATION_KEY)
        self.c.note_console("ai ev")
        self.c.sync(self.kb)
        self.assertEqual(self.dictated, [1])

    def test_a_switch_evicts_a_card_and_the_next_pass_uploads_it_again(self):
        self.r.report("codex", "a", "working")
        self.c.sync(self.kb)
        first = self.kb.keys[-1][2][0]
        self.cache.forget_slot(first)            # what an eviction leaves behind
        self.kb.cards.clear()
        self.c.sync(self.kb)
        again = self.kb.keys[-1][2][0]
        self.assertIn(again, self.kb.cards)       # uploaded into its new slot
        self.assertEqual(self.cache.holds(("agentcard", 0)), again)

    def test_a_full_pool_shows_no_card_rather_than_evict_the_shown_app(self):
        from polyhost.device.overlay_cache import OverlayMRUCache
        self.cache = OverlayMRUCache(3)
        with self.cache.batch():
            for k in range(3):
                self.cache.get_or_allocate(("app.png", 0, k))   # one switch fills it
        self.r.report("codex", "a", "working")
        self.c.sync(self.kb)
        self.assertEqual(self.kb.keys[-1][2][0], NO_SLOT)
        self.assertFalse(self.kb.keys[-1][1] & 0x08)             # no extra cards either
        self.assertEqual(self.kb.cards, {})


def _pynput_usable():
    """pynput picks a backend at import and raises without a display (X11)."""
    try:
        from pynput import keyboard  # noqa: F401  (import is the check)
        return True
    except Exception:  # noqa: BLE001 - any backend failure means "not here"
        return False


class DictationTest(unittest.TestCase):
    def test_shortcut_choice(self):
        self.assertEqual(dictation.shortcut_for("", "win32"), "<cmd>+h")
        self.assertEqual(dictation.shortcut_for("", "darwin"), "")
        self.assertEqual(dictation.shortcut_for("", "linux"), "")
        self.assertEqual(dictation.shortcut_for(" <ctrl>+<alt>+d ", "linux"), "<ctrl>+<alt>+d")

    @unittest.skipUnless(_pynput_usable(), "pynput needs a display (run under xvfb-run)")
    def test_send_presses_and_releases_in_order(self):
        events = []

        class _Ctl:
            def press(self, k):
                events.append(("p", str(k)))

            def release(self, k):
                events.append(("r", str(k)))

        self.assertTrue(dictation.send_shortcut("<ctrl>+<alt>+d", controller=_Ctl(), delay_s=0))
        self.assertEqual([e[0] for e in events], ["p", "p", "p", "r", "r", "r"])
        self.assertEqual(events[0][1], events[-1][1])     # first pressed, last released
        self.assertFalse(dictation.send_shortcut("", controller=_Ctl(), delay_s=0))
        self.assertFalse(dictation.send_shortcut("<nosuchkey>+x", controller=_Ctl(), delay_s=0))


class _Win:
    def __init__(self, handle, pid, title):
        self.handle, self.pid, self.title, self.active = handle, pid, title, False

    def getHandle(self):
        return self.handle

    def getPID(self):
        return self.pid

    def activate(self):
        self.active = True


class RaiserTest(unittest.TestCase):
    def test_by_window_then_pid_then_title(self):
        r = AgentRegistry()
        wins = [_Win("1", 10, "bash"), _Win("2", 4242, "zsh"), _Win("3", 11, "repo - Code")]
        r.report("x", "a", "done", window="1", source="hook")
        self.assertTrue(raise_agent(r.agents()[0], windows=wins))
        self.assertTrue(wins[0].active)
        r.report("x", "b", "done", pid=4242)
        self.assertTrue(raise_agent(r.agents()[1], windows=wins))
        self.assertTrue(wins[1].active)
        r.report("x", "c", "done", headline="repo")
        self.assertTrue(raise_agent(r.agents()[2], windows=wins))
        self.assertTrue(wins[2].active)
        r.report("x", "d", "done", headline="nowhere")
        self.assertFalse(raise_agent(r.agents()[3], windows=wins))

    def test_by_the_vendors_own_title(self):
        # Windows Terminal is not an ancestor of the agent's process, so the window is
        # found by Claude Code's own title; the one naming the headline first.
        r = AgentRegistry()
        r.report("claude-code", "s", "waiting", cwd="/w/qmk_firmware", pid=99999)
        wins = [_Win("1", 1, "bash"), _Win("2", 2, "\u2733 polykybd docs"),
                _Win("3", 3, "\u2733 qmk_firmware build")]
        self.assertTrue(raise_agent(r.agents()[0], windows=wins))
        self.assertTrue(wins[2].active)
        r.report("claude-code", "t", "waiting", cwd="/w/elsewhere")
        wins = [_Win("2", 2, "\u25d0 something")]
        self.assertTrue(raise_agent(r.agents()[1], windows=wins))
        self.assertTrue(wins[0].active)


if __name__ == "__main__":
    unittest.main()
