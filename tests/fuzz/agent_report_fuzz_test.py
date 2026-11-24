"""Properties of the agent-key report parsers: services/agents/hooks.py (the JSON an
agent's hook gets on stdin, written by Claude Code, Codex, Gemini CLI, ...) and
services/agents/remote.py (``agents.report`` over the network endpoint, and the
raise requests in the replies to a forwarder)."""
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.services.agents import hooks, remote
from polyhost.services.agents.model import ENDED, AgentState

load_profile()

JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=12),
    lambda inner: st.lists(inner, max_size=4)
    | st.dictionaries(st.text(max_size=10), inner, max_size=5),
    max_leaves=16)

EVENT_NAMES = (list(hooks._EVENTS) + ["Stop", "PreToolUse", "SessionEnd", "session.status",
                                      "Notification", "notification", "unknown", ""])
FIELD_VALUE = st.one_of(st.text(max_size=12), st.integers(), st.none(), st.booleans(),
                        st.lists(st.integers(), max_size=2))
HOOK_FIELDS = (hooks._EVENT_FIELDS + hooks._SESSION_FIELDS + hooks._CWD_FIELDS
               + ("reason", "status", "notification_type", "message"))


@st.composite
def hook_payloads(draw):
    """A dict with the field names the vendors use, sometimes one level down in
    "properties" (OpenCode)."""
    fields = draw(st.dictionaries(st.sampled_from(HOOK_FIELDS),
                                  st.one_of(FIELD_VALUE, st.sampled_from(EVENT_NAMES)),
                                  max_size=6))
    if draw(st.booleans()):
        inner = draw(st.dictionaries(st.sampled_from(HOOK_FIELDS), FIELD_VALUE, max_size=4))
        fields["properties"] = inner
    return fields


def first_model(payload, names):
    """The first of `names` whose value is a non-empty str or an int, as text."""
    for name in names:
        value = payload.get(name)
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return ""


def flat_model(payload):
    props = payload.get("properties")
    if not isinstance(props, dict):
        return payload
    out = dict(props)
    out.update({k: v for k, v in payload.items() if k != "properties"})
    return out


STATES = {AgentState.IDLE, AgentState.WORKING, AgentState.WAITING, AgentState.DONE, ENDED, None}


class HookPayloadFuzzTest(unittest.TestCase):
    @given(st.one_of(JSON, hook_payloads()), st.sampled_from(["", "Stop", "agentStop", "x"]))
    def test_interpret(self, payload, event):
        got = hooks.interpret(payload, event)
        name = hooks.event_name(payload, event)
        self.assertIsInstance(name, str)
        if got is None:
            return
        self.assertIsInstance(payload, dict)
        flat = flat_model(payload)
        self.assertEqual(set(got), {"session_id", "state", "event", "cwd"})
        session = first_model(flat, hooks._SESSION_FIELDS)
        cwd = first_model(flat, hooks._CWD_FIELDS)
        self.assertEqual(got["session_id"], session or "cwd:" + cwd)
        self.assertEqual(got["cwd"], cwd)
        self.assertIn(got["state"], STATES)
        self.assertTrue(got["state"] is not None or got["event"])
        self.assertLessEqual(len(got["event"]), 24)
        if event:
            self.assertIn(hooks.normalise_event(event), hooks._EVENTS)

    @given(hook_payloads(), st.sampled_from(sorted(hooks._EVENTS)))
    def test_a_known_event_maps_through_the_table(self, payload, event):
        payload = dict(payload, session_id="s1")
        got = hooks.interpret(payload, event)
        state, tag = hooks._EVENTS[event]
        if event == "sessionend":
            return                       # read from the reason (test_interpret covers it)
        if state is None and not tag:
            self.assertIsNone(got)
        else:
            self.assertEqual((got["session_id"], got["state"], got["event"]),
                             ("s1", state, tag))

    @given(st.text(max_size=30))
    def test_normalise_event(self, name):
        got = hooks.normalise_event(name)
        self.assertTrue(all("a" <= c <= "z" for c in got))
        self.assertEqual(got, "".join(c for c in name.lower() if "a" <= c <= "z"))


def sanitize_model(params):
    """What the network endpoint may store, from the field table in remote.py."""
    if not isinstance(params, dict):
        return None
    out = {}
    for name, limit in remote.MAX_TEXT.items():
        value = params.get(name)
        if value is None:
            continue
        if not isinstance(value, (str, int)):
            return None
        out[name] = str(value)[:limit]
    state = params.get("state")
    if state is not None:
        if not isinstance(state, str) or state.lower() not in remote.STATES:
            return None
        out["state"] = state.lower()
    pid = params.get("pid")
    if type(pid) is int and 0 < pid < 2 ** 31:
        out["pid"] = pid
    if not out.get("vendor") or not out.get("session_id"):
        return None
    out.setdefault("machine", "remote")
    if not out["machine"]:
        out["machine"] = "remote"
    return out


REPORT_FIELDS = list(remote.MAX_TEXT) + ["state", "pid", "extra"]


class RemoteReportFuzzTest(unittest.TestCase):
    @given(st.one_of(JSON, st.dictionaries(
        st.sampled_from(REPORT_FIELDS),
        st.one_of(FIELD_VALUE, st.text(max_size=500), st.sampled_from(
            ["working", "WAITING", "Done", "nope"]), st.integers(-5, 2 ** 32)),
        max_size=10)))
    def test_sanitize_report(self, params):
        got = remote.sanitize_report(params)
        self.assertEqual(got, sanitize_model(params))
        if got is not None:
            for name, value in got.items():
                if name in remote.MAX_TEXT:
                    self.assertLessEqual(len(value), remote.MAX_TEXT[name])

    @given(st.lists(st.one_of(JSON, st.builds(
        lambda seq, agent: {"agent_raise": {"seq": seq, "agent": agent}},
        st.integers(-3, 20) | st.floats() | st.none(), JSON)), max_size=12))
    def test_raise_follower(self, replies):
        follower = remote.RemoteRaiseFollower()
        highest = None
        for i, reply in enumerate(replies):
            raise_ = reply.get("agent_raise") if isinstance(reply, dict) else None
            seq = raise_.get("seq") if isinstance(raise_, dict) else None
            got = follower.follow(reply)
            if got is not None:
                # Only a reply after the first, with an int seq above every
                # seq seen so far, raises, and it raises its own agent dict.
                self.assertGreater(i, 0)
                self.assertIs(type(seq), int)
                self.assertGreater(seq, highest)
                self.assertIs(got, raise_["agent"])
                self.assertIsInstance(got, dict)
            if isinstance(seq, int):
                highest = seq if highest is None else max(highest, seq)
            elif highest is None:
                highest = 0


if __name__ == "__main__":
    unittest.main()
