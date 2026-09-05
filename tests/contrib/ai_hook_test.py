"""Tests for the agent hook adapter (contrib/ai-hooks/polykybd_ai_hook.py).

It is not importable as a package (it is a standalone script a user points their
agent at), so it is loaded by path — which also proves it has no import-time
dependency on this repo.
"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

HOOK = (pathlib.Path(__file__).resolve().parents[2]
        / "contrib" / "ai-hooks" / "polykybd_ai_hook.py")


def load():
    spec = importlib.util.spec_from_file_location("polykybd_ai_hook", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DecideStateTest(unittest.TestCase):
    def setUp(self):
        self.hook = load()

    def test_an_explicit_state_wins(self):
        # A tool with no hook system drives the light with one plain command.
        self.assertEqual(self.hook.decide_state({"state": "busy"}), "busy")

    def test_claude_code_events(self):
        for event, expected in [("UserPromptSubmit", "working"),
                                ("Notification", "attention"),
                                ("Stop", "idle"),
                                ("SessionEnd", "off")]:
            self.assertEqual(
                self.hook.decide_state({"hook_event_name": event}), expected, event)

    def test_the_codex_turn_complete_event(self):
        self.assertEqual(
            self.hook.decide_state({"type": "agent-turn-complete"}), "idle")

    def test_an_unknown_event_decides_nothing(self):
        # Doing nothing is right: a tool may emit events we have no opinion about,
        # and guessing would make the light flicker between meanings.
        self.assertIsNone(self.hook.decide_state({"hook_event_name": "PreCompact"}))
        self.assertIsNone(self.hook.decide_state({}))

    def test_the_environment_variable_is_the_fallback_event_source(self):
        with patch.dict("os.environ", {"CLAUDE_HOOK_EVENT": "Notification"}):
            self.assertEqual(self.hook.decide_state({}), "attention")

    def test_every_mapped_state_is_one_polyctl_accepts(self):
        # The adapter's vocabulary has to be a subset of the daemon's, or a hook
        # fires and the state is silently refused at the far end.
        from polyhost.device.command_ids import AiState
        for state in set(self.hook.EVENT_STATE.values()):
            self.assertIsNotNone(AiState.parse(state), state)


class ReadEventTest(unittest.TestCase):
    def setUp(self):
        self.hook = load()

    def test_a_json_argv_argument_is_the_codex_shape(self):
        payload = json.dumps({"type": "agent-turn-complete"})
        with patch.object(sys, "argv", ["hook", payload]):
            self.assertEqual(self.hook.read_event()["type"], "agent-turn-complete")

    def test_a_bare_word_argument_is_a_state(self):
        with patch.object(sys, "argv", ["hook", "working"]):
            self.assertEqual(self.hook.read_event(), {"state": "working"})


class RunTest(unittest.TestCase):
    """End to end through the real script, with a stub standing in for polyctl."""

    def _run(self, stdin, argv=(), env_extra=None):
        import os
        stub = pathlib.Path(__file__).with_name("_polyctl_stub.py")
        stub.write_text("import sys, pathlib\n"
                        "pathlib.Path(sys.argv[0]).with_name('_polyctl_args.txt')"
                        ".write_text(' '.join(sys.argv[1:]))\n")
        args_file = stub.with_name("_polyctl_args.txt")
        if args_file.exists():
            args_file.unlink()
        env = dict(os.environ)
        env["POLYCTL"] = f"{sys.executable}"
        # $POLYCTL is a single executable, so route through a wrapper that adds the
        # stub path: the hook appends its own arguments after it.
        wrapper = stub.with_name("_polyctl_wrapper.sh")
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{stub}" "$@"\n')
        wrapper.chmod(0o755)
        env["POLYCTL"] = str(wrapper)
        env.update(env_extra or {})
        proc = subprocess.run([sys.executable, str(HOOK), *argv], input=stdin,
                              text=True, capture_output=True, env=env, timeout=30)
        called = args_file.read_text() if args_file.exists() else None
        return proc, called

    def test_a_notification_asks_for_attention(self):
        proc, called = self._run(json.dumps({"hook_event_name": "Notification"}))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(called, "ai state attention")

    def test_an_unknown_event_calls_nothing(self):
        proc, called = self._run(json.dumps({"hook_event_name": "Whatever"}))
        self.assertEqual(proc.returncode, 0)
        self.assertIsNone(called)

    def test_a_missing_polyctl_never_fails_the_agent(self):
        # A hook that exits non-zero can block the agent. A keyboard light is not
        # worth that, so every failure path has to exit 0.
        proc, _ = self._run(json.dumps({"hook_event_name": "Stop"}),
                            env_extra={"POLYCTL": "/nonexistent/polyctl"})
        self.assertEqual(proc.returncode, 0)
        self.assertIn("polykybd-ai-hook", proc.stderr)

    def test_garbage_on_stdin_never_fails_the_agent(self):
        proc, _ = self._run("not json at all")
        self.assertEqual(proc.returncode, 0)

    def tearDown(self):
        for name in ("_polyctl_stub.py", "_polyctl_args.txt", "_polyctl_wrapper.sh"):
            f = pathlib.Path(__file__).with_name(name)
            if f.exists():
                f.unlink()


if __name__ == "__main__":
    unittest.main()
