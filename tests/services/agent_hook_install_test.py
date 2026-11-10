"""polyctl agents hooks install/uninstall: the plans for Claude Code, Codex and
Copilot CLI, on a temporary home directory."""
import json
import os
import tempfile
import unittest

from polyhost.cli import polyctl
from polyhost.services.agents import hook_install as hi

ARGV = ["/opt/poly/polyctl"]



def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()

class HookInstallTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def _write(self, rel, text):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_claude_keeps_the_users_hooks_and_skips_pretooluse(self):
        own = {"type": "command", "command": "my-linter"}
        old_ours = {"type": "command", "command": "polyctl agents hook claude-code"}
        self._write(".claude/settings.json", json.dumps({
            "model": "x",
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [own, old_ours]}],
                      "Stop": [{"hooks": [old_ours]}]}}))
        changes = hi.plan("claude-code", self.home, argv=ARGV)
        self.assertEqual(len(changes), 1)
        hi.apply(changes)
        data = json.loads(_read(changes[0].path))
        self.assertEqual(data["model"], "x")
        # The user's own PreToolUse hook stays; ours is gone from PreToolUse.
        self.assertEqual(data["hooks"]["PreToolUse"], [{"matcher": "Bash", "hooks": [own]}])
        self.assertEqual(set(data["hooks"]), set(hi.CLAUDE_EVENTS) | {"PreToolUse"})
        stop = data["hooks"]["Stop"]
        self.assertEqual(len(stop), 1)                       # replaced, not doubled
        self.assertEqual(stop[0]["hooks"][0]["command"],
                         "/opt/poly/polyctl agents hook claude-code")
        self.assertEqual(data["hooks"]["PostToolUse"][0]["matcher"], "*")
        self.assertTrue(os.path.exists(changes[0].path + ".polykybd.bak"))
        # Installing again changes nothing.
        self.assertEqual(hi.plan("claude-code", self.home, argv=ARGV), [])
        # Uninstall leaves only the user's hook.
        hi.apply(hi.plan("claude-code", self.home, install=False, argv=ARGV))
        data = json.loads(_read(changes[0].path))
        self.assertEqual(data["hooks"], {"PreToolUse": [{"matcher": "Bash", "hooks": [own]}]})

    def test_claude_without_a_settings_file(self):
        changes = hi.plan("claude-code", self.home, argv=ARGV)
        self.assertEqual(changes[0].before, "")
        hi.apply(changes)
        self.assertIn("SessionStart", json.loads(_read(changes[0].path))["hooks"])

    def test_codex_adds_notify_and_respects_an_own_one(self):
        path = self._write(".codex/config.toml", 'model = "o3"\n\n[tui]\nx = 1\n')
        hi.apply(hi.plan("codex", self.home, argv=ARGV))
        text = _read(path)
        self.assertTrue(text.startswith('notify = ["/opt/poly/polyctl", "agents", "hook", "codex"]\n'))
        self.assertIn("[tui]", text)
        self.assertEqual(hi.plan("codex", self.home, argv=ARGV), [])
        hi.apply(hi.plan("codex", self.home, install=False, argv=ARGV))
        self.assertNotIn("notify", _read(path))
        self._write(".codex/config.toml", 'notify = ["my-notifier"]\n')
        self.assertEqual(hi.plan("codex", self.home, argv=ARGV), [])
        self.assertIn("own notify", hi.codex_conflict(self.home))

    def test_copilot_file(self):
        changes = hi.plan("copilot", self.home, argv=["C:\\venv\\Scripts\\polyctl.exe"])
        hi.apply(changes)
        data = json.loads(_read(changes[0].path))
        self.assertEqual(data["version"], 1)
        self.assertEqual(set(data["hooks"]), set(hi.COPILOT_EVENTS))
        entry = data["hooks"]["agentStop"][0]
        self.assertEqual(entry["powershell"],
                         '& "C:\\venv\\Scripts\\polyctl.exe" agents hook copilot --event agentStop')
        self.assertEqual(entry["bash"],
                         '"C:\\venv\\Scripts\\polyctl.exe" agents hook copilot --event agentStop')
        hi.apply(hi.plan("copilot", self.home, install=False))
        self.assertFalse(os.path.exists(changes[0].path))

    def test_cli_is_local_and_dry_run_writes_nothing(self):
        args = polyctl.build_parser().parse_args(["agents", "hooks", "install", "copilot",
                                                  "--dry-run"])
        self.assertTrue(polyctl._is_local_command(args))
        self.assertIs(args.func, polyctl._cmd_agents_hooks)
        hook_args = polyctl.build_parser().parse_args(["agents", "hook", "codex"])
        self.assertFalse(polyctl._is_local_command(hook_args))

    def test_unknown_vendor(self):
        with self.assertRaises(ValueError):
            hi.plan("gemini", self.home)


if __name__ == "__main__":
    unittest.main()
