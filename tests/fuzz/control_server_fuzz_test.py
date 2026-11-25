"""Properties of the local control socket's request dispatch (server/control_server.py).

The control socket is authkey-gated, but every handler reads ``params`` from a JSON
frame, and a frame's ``params`` can be any JSON value: an object, a list, a string,
a number, ``NaN``. Each request must get exactly one reply with its own id, and a
malformed request must be answered as invalid params, never as an internal error
(an internal error also writes a traceback to the log).

The core is a stub that accepts every call, so these tests check the server's own
handling of params, not PolyCore's validation.
"""
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.server import protocol as p
from polyhost.server.control_server import ControlServer

load_profile()

# Every value json.loads can produce from a frame (NaN and +-Infinity included).
JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=12),
    lambda inner: st.lists(inner, max_size=5)
    | st.dictionaries(st.text(max_size=8), inner, max_size=5),
    max_leaves=20)

# null counts as omitted params; false, 0, "" and [] are refused like any other.
NOT_AN_OBJECT = JSON.filter(lambda v: not isinstance(v, dict) and v is not None)


class _Log:
    def __init__(self):
        self.exceptions = []

    def exception(self, msg, *args, **kwargs):
        self.exceptions.append(msg % args if args else msg)

    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    info = error = debug


class _Core:
    """Accepts every PolyCore call and records it."""
    BOOT_LOOP_DEFAULT_ROUNDS = 3
    paused = False

    def __init__(self):
        self.calls = []

    def subscribe(self, cb):
        pass

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append(name)
            return True, {}
        return call


def _server():
    core, log = _Core(), _Log()
    server = ControlServer(core, "0.0.0", log, address="unused", authkey=b"k")
    replies = []
    server._reply = lambda conn, obj: replies.append(obj)
    return server, core, log, replies


METHODS = sorted(_server()[0].registry)
# Fields the handlers read, so the drawn objects reach past the first missing key.
FIELDS = sorted({"lang", "value", "idle", "row", "col", "cancel", "reset", "id", "action",
                 "vendor", "session_id", "text", "code", "replace", "files", "underlay",
                 "layer", "keycode", "steps", "label", "path", "apply", "bundle",
                 "bundle_id", "force", "source", "paused", "choice", "key", "enabled",
                 "handle", "name", "names", "mapping", "master_is_left", "split_vbus",
                 "lines", "which", "rounds", "modifier", "combos", "tap_dances"})
PARAMS = st.one_of(JSON, st.dictionaries(st.sampled_from(FIELDS), JSON, max_size=6))


class ControlServerFuzzTest(unittest.TestCase):
    def _one_reply(self, method, params, req_id=7):
        server, core, log, replies = _server()
        server._dispatch(object(), {"jsonrpc": "2.0", "id": req_id, "method": method,
                                    "params": params})
        self.assertEqual(len(replies), 1, replies)
        self.assertEqual(replies[0]["id"], req_id)
        return replies[0], core, log

    @given(st.sampled_from(METHODS), PARAMS)
    def test_every_request_gets_one_reply_and_no_internal_error(self, method, params):
        reply, _core, log = self._one_reply(method, params)
        if "error" in reply:
            self.assertIn(reply["error"]["code"], (p.ERR_INVALID_PARAMS, p.ERR_DEVICE),
                          (method, params, reply))
        else:
            self.assertIn("result", reply)
        self.assertEqual(log.exceptions, [], (method, params))

    @given(st.sampled_from(METHODS), NOT_AN_OBJECT)
    def test_params_that_are_not_an_object_are_refused_before_the_core(self, method, params):
        reply, core, _log = self._one_reply(method, params)
        self.assertEqual(reply.get("error", {}).get("code"), p.ERR_INVALID_PARAMS,
                         (method, params, reply))
        self.assertEqual(core.calls, [], (method, params))

    @given(st.text(max_size=20).filter(lambda m: m not in METHODS), PARAMS)
    def test_an_unknown_method(self, method, params):
        reply, core, _log = self._one_reply(method, params)
        self.assertEqual(reply["error"]["code"], p.ERR_METHOD_NOT_FOUND)
        self.assertEqual(core.calls, [])


if __name__ == "__main__":
    unittest.main()
