"""services/agents/cloud_hook.py: the cloud-session hook and its encryption.

The relay side is tested by agent-relay/test/e2e_test.py against `wrangler dev`."""
import io
import json
import os
import tempfile
import unittest
import unittest.mock as mock

from polyhost.services.agents import cloud_hook as ch


class SealTest(unittest.TestCase):
    def setUp(self):
        self.key = bytes(range(32))

    def test_round_trip_and_fresh_nonce(self):
        a = ch.seal(self.key, b'{"state":"working"}')
        b = ch.seal(self.key, b'{"state":"working"}')
        self.assertNotEqual(a, b)
        self.assertEqual(ch.open_sealed(self.key, a), b'{"state":"working"}')
        self.assertNotIn("working", a)

    def test_known_vector(self):
        # Pins the format: the host and every installed cloud hook must agree.
        # A change here breaks every installed cloud hook until the host matches.
        token = ch.seal(self.key, b"abc", nonce=bytes(16))
        self.assertEqual(token, "AQAAAAAAAAAAAAAAAAAAAAD8ceQNzkpY-s_J8j4u14CC6mIy")
        self.assertEqual(ch.open_sealed(self.key, token), b"abc")

    def test_wrong_key_and_tampering_are_refused(self):
        token = ch.seal(self.key, b"hello")
        with self.assertRaises(ValueError):
            ch.open_sealed(bytes(32), token)
        raw = bytearray(ch.base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        raw[20] ^= 1
        tampered = ch.base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")
        with self.assertRaises(ValueError):
            ch.open_sealed(self.key, tampered)
        for bad in ("", "!!", "AAAA"):
            with self.assertRaises(ValueError):
                ch.open_sealed(self.key, bad)

    def test_session_slot_hides_the_id(self):
        slot = ch.session_slot(self.key, "cse_abc")
        self.assertRegex(slot, r"^[0-9a-f]{32}$")
        self.assertNotEqual(slot, ch.session_slot(bytes(32), "cse_abc"))


class ConfigTest(unittest.TestCase):
    def test_round_trip(self):
        chan = ch.new_channel()
        text = ch.format_config("https://relay.example/", chan["channel"],
                                chan["write_token"], chan["key"])
        cfg = ch.parse_config(text)
        self.assertEqual(cfg, {"url": "https://relay.example", "channel": chan["channel"],
                               "write_token": chan["write_token"], "key": chan["key"]})
        self.assertNotIn(chan["read_token"], text)

    def test_refuses_bad_strings(self):
        chan = ch.new_channel()
        good = ch.format_config("https://r.example", chan["channel"], chan["write_token"], chan["key"])
        for bad in ("", "pkr1|x", good.replace("https://", "http://"),
                    good.replace(chan["channel"], "zz"), good.replace("pkr1", "pkr9")):
            with self.assertRaises(ValueError, msg=bad):
                ch.parse_config(bad)


class HookTest(unittest.TestCase):
    def setUp(self):
        self.chan = ch.new_channel()
        self.env = {ch.CONFIG_ENV: ch.format_config("https://r.example", self.chan["channel"],
                                                    self.chan["write_token"], self.chan["key"]),
                    "CLAUDE_CODE_REMOTE_SESSION_ID": "cse_" + os.urandom(6).hex()}
        self.sent = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        slot = ch.session_slot(self.chan["key"], self.env["CLAUDE_CODE_REMOTE_SESSION_ID"])
        for path in (ch._last_sent_path(slot), ch._last_sent_path(slot) + ".lock"):
            if os.path.exists(path):
                os.remove(path)

    def hook(self, event, **extra):
        return ch.run_hook(json.dumps(dict(hook_event_name=event, **extra)), environ=self.env,
                           poster=lambda cfg, slot, blob, ended: self.sent.append((slot, blob, ended)))

    def states(self):
        return [json.loads(ch.open_sealed(self.chan["key"], b))["state"] for _, b, _ in self.sent]

    def test_states_and_deduplication(self):
        self.assertTrue(self.hook("SessionStart"))
        self.assertTrue(self.hook("UserPromptSubmit"))
        self.assertFalse(self.hook("PreToolUse"))
        self.assertFalse(self.hook("PostToolUse"))
        self.assertTrue(self.hook("PermissionRequest"))
        self.assertTrue(self.hook("PostToolUse"))
        self.assertFalse(self.hook("Notification", notification_type="auth_success"))
        self.assertTrue(self.hook("Stop"))
        self.assertTrue(self.hook("SessionEnd"))
        self.assertEqual(self.states(), ["idle", "working", "waiting", "working", "done", "ended"])
        self.assertEqual([e for _, _, e in self.sent], [False] * 5 + [True])

    def test_report_has_url_title_and_folder_only(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "user", "message": "secret prompt"}) + "\n")
            fh.write(json.dumps({"type": "ai-title", "aiTitle": "Fix the build"}) + "\n")
        self.addCleanup(os.remove, fh.name)
        self.hook("UserPromptSubmit", transcript_path=fh.name, cwd="/home/user/PolyKybdHost",
                  prompt="secret prompt")
        report = json.loads(ch.open_sealed(self.chan["key"], self.sent[0][1]))
        sid = self.env["CLAUDE_CODE_REMOTE_SESSION_ID"]
        self.assertEqual({k: v for k, v in report.items() if k != "ts"},
                         {"state": "working", "title": "Fix the build", "cwd": "PolyKybdHost",
                          "url": "https://claude.ai/code/session_" + sid[4:]})
        self.assertNotIn("secret", json.dumps(report))

    def test_a_title_that_left_the_transcript_tail_is_kept(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "ai-title", "aiTitle": "Fix the build"}) + "\n")
        self.addCleanup(os.remove, fh.name)
        self.hook("UserPromptSubmit", transcript_path=fh.name)
        with open(fh.name, "w", encoding="utf-8") as out:      # the title record is gone
            out.write(json.dumps({"type": "user"}) + "\n")
        self.hook("Stop", transcript_path=fh.name)
        titles = [json.loads(ch.open_sealed(self.chan["key"], b))["title"] for _, b, _ in self.sent]
        self.assertEqual(titles, ["Fix the build", "Fix the build"])

    def _cloud_transcript(self, *prompts):
        # A cloud transcript: no title record, meta records, tool results.
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "user", "isMeta": True,
                                 "message": {"content": [{"type": "text", "text": "restarted"}]}}) + "\n")
            for prompt in prompts:
                fh.write(json.dumps({"type": "user", "message": {"content": prompt}}) + "\n")
                fh.write(json.dumps({"type": "user", "message": {
                    "content": [{"type": "tool_result", "content": "x"}]}}) + "\n")
        self.addCleanup(os.remove, fh.name)
        return fh.name

    def titles(self):
        return [json.loads(ch.open_sealed(self.chan["key"], b))["title"] for _, b, _ in self.sent]

    def test_a_cloud_session_is_named_by_its_first_prompt(self):
        path = self._cloud_transcript()
        # The very first prompt: the transcript does not have it yet.
        self.hook("UserPromptSubmit", transcript_path=path, cwd="/home/user",
                  prompt="Fix the HID reconnect after resume on Windows please")
        path2 = self._cloud_transcript("Fix the HID reconnect after resume on Windows please",
                                       "now also add a test")
        self.hook("Stop", transcript_path=path2, cwd="/home/user")
        self.hook("UserPromptSubmit", transcript_path=path2, cwd="/home/user",
                  prompt="now also add a test")
        self.assertEqual(self.titles(), ["Fix the HID reconnect after resume on…"] * 3)

    def test_prompt_titles_can_be_turned_off(self):
        self.env[ch.PROMPT_TITLE_ENV] = "0"
        self.hook("UserPromptSubmit", transcript_path=self._cloud_transcript("secret plan"),
                  cwd="/home/user", prompt="secret plan")
        report = json.loads(ch.open_sealed(self.chan["key"], self.sent[0][1]))
        self.assertEqual((report["title"], report["cwd"]), ("", "user"))
        self.assertNotIn("secret", json.dumps(report))

    def test_prompt_words(self):
        self.assertEqual(ch.prompt_words("  short   prompt "), "short prompt")
        self.assertEqual(ch.prompt_words("x" * 50), "x" * 40 + "…")
        self.assertEqual(ch.prompt_words("<command-name>/clear</command-name>"), "")
        for empty in ("", "   ", None, 3):
            self.assertEqual(ch.prompt_words(empty), "")
        self.assertLessEqual(len(ch.prompt_words("word " * 30)), ch.PROMPT_TITLE_CHARS + 1)

    def test_main_never_raises_or_prints(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {ch.CONFIG_ENV: "garbage"}), \
                mock.patch("sys.stdin", io.StringIO("not json")), \
                mock.patch("sys.stdout", out):
            self.assertEqual(ch.main([]), 0)
        self.assertEqual(out.getvalue(), "")


class PostTest(unittest.TestCase):
    def test_post_names_itself(self):
        # Cloudflare answers Python's default User-Agent with 403 (error 1010).
        sent = []

        class Resp:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *exc): return False

        def fake_urlopen(req, timeout, context=None):
            sent.append(req)
            self.assertIsNotNone(context)    # never urllib's implicit default
            return Resp()
        cfg = {"url": "https://r.example", "channel": "a" * 32, "write_token": "b" * 64}
        with mock.patch.object(ch.urllib.request, "urlopen", fake_urlopen):
            self.assertEqual(ch.post(cfg, "c" * 32, "blob", False), 200)
        self.assertEqual(sent[0].get_header("User-agent"), ch.USER_AGENT)
        self.assertEqual(sent[0].full_url, "https://r.example/v1/c/" + "a" * 32 + "/event")


class InstallTest(unittest.TestCase):
    def test_merges_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, ".claude", "settings.json")
            os.makedirs(os.path.dirname(path))
            mine = {"permissions": {"allow": ["Bash(ls)"]},
                    "hooks": {"Stop": [{"matcher": "", "hooks": [{"type": "command",
                                                                  "command": "my-stop.sh"}]}]}}
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(mine, fh)
            self.assertTrue(ch.install(path, "python3 /x/hook"))
            self.assertFalse(ch.install(path, "python3 /x/hook"))
            with open(path, encoding="utf-8") as fh:
                got = json.load(fh)
            self.assertEqual(got["permissions"], mine["permissions"])
            stop_cmds = [h["command"] for g in got["hooks"]["Stop"] for h in g["hooks"]]
            self.assertEqual(stop_cmds, ["my-stop.sh", "python3 /x/hook"])
            self.assertEqual(set(got["hooks"]), set(ch.EVENT_STATES))

    def test_creates_a_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "settings.json")
            self.assertTrue(ch.install(path, "python3 /x/hook"))
            with open(path, encoding="utf-8") as fh:
                self.assertIn("UserPromptSubmit", json.load(fh)["hooks"])


if __name__ == "__main__":
    unittest.main()
