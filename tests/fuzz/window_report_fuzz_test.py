"""Properties of the network window-report endpoint (server/window_report_server.py)
and the shortcut list it carries (services/shortcut_relay.py).

This is the one listener reachable from another computer, so its frames are the
most attacker-shaped input the daemon reads. A frame is JSON as ``json.loads``
reads it, which includes ``NaN`` and ``Infinity``.
"""
import base64
import json
import unittest

from hypothesis import given, strategies as st

from tests.fuzz.profile import load_profile
from polyhost.server import protocol as p
from polyhost.server.window_report_server import MAX_ICON_B64, MAX_NAMES, WindowReportServer
from polyhost.services import shortcut_relay
from polyhost.services.agents import remote
from polyhost.services.shortcut_source.model import Shortcut, displayable_hid

load_profile()

# Every value json.loads can produce from a frame (NaN and +-Infinity included).
JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats() | st.text(max_size=12),
    lambda inner: st.lists(inner, max_size=5)
    | st.dictionaries(st.text(max_size=8), inner, max_size=5),
    max_leaves=20)

DISPLAYABLE = [h for h in range(0x100) if displayable_hid(h)]
SHORTCUT_ITEM = st.one_of(
    JSON,
    st.lists(JSON, min_size=3, max_size=4),
    st.tuples(st.integers(-2, 0x12), st.sampled_from(DISPLAYABLE + [0, 3, 0x54, 0xE8]),
              st.one_of(st.text(max_size=8), st.text(min_size=60, max_size=70))).map(list))


def _as_int(value):
    """int(value), or None where Python's int() refuses it."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def decode_model(value):
    """(mods, hid, label) of each shortcut decode() must return, written from the
    wire format: at most MAX_SHORTCUTS entries are read, an entry is a list of at
    least three, mods is a nibble, the HID usage has a keycap slot, and the label
    is non-blank and at most MAX_LABEL characters after stripping."""
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value[:shortcut_relay.MAX_SHORTCUTS]:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        mods, hid = _as_int(item[0]), _as_int(item[1])
        if mods is None or hid is None or not 0 <= mods <= 0x0F or not displayable_hid(hid):
            continue
        label = str(item[2]).strip()[:shortcut_relay.MAX_LABEL]
        if label:
            out.append((mods, hid, label))
    return out


class _Conn:
    def __init__(self):
        self.sent = []

    def send_bytes(self, data):
        self.sent.append(json.loads(data.decode("utf-8")))


class _Log:
    def __init__(self):
        self.exceptions = []

    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass

    def exception(self, *a, **k):
        self.exceptions.append(a)


def _server(log, calls):
    def on_report(handle, name, title, **kw):
        calls.append((handle, name, title, kw))
        return True, {}

    def on_agents_report(params):
        return (remote.sanitize_report(params) is not None), "unusable report"

    return WindowReportServer(on_report, "0.0.1", log, bind_host="127.0.0.1", port=0,
                              authkey=b"fuzz", on_agents_report=on_agents_report)


class ShortcutRelayFuzzTest(unittest.TestCase):
    @given(st.one_of(JSON, st.lists(SHORTCUT_ITEM, max_size=12)))
    def test_decode_matches_the_model(self, value):
        got = shortcut_relay.decode(value)
        self.assertEqual([(s.mods, s.hid, s.label) for s in got], decode_model(value))
        self.assertTrue(all(s.displayable for s in got))

    @given(st.lists(st.tuples(st.integers(0, 0x0F), st.sampled_from(DISPLAYABLE),
                              st.text(max_size=80).filter(lambda t: t.strip())),
                    max_size=12))
    def test_encode_decode_round_trip(self, items):
        shortcuts = [Shortcut(label=label, role="menu item", accel="x", mods=mods,
                              keysym="x", hid=hid, displayable=True)
                     for mods, hid, label in items]
        wire = shortcut_relay.encode(shortcuts)
        self.assertEqual(json.loads(json.dumps(wire)), wire)
        got = shortcut_relay.decode(wire)
        self.assertEqual([(s.mods, s.hid, s.label) for s in got],
                         [(m, h, lab.strip()[:shortcut_relay.MAX_LABEL])
                          for m, h, lab in items
                          if lab.strip()[:shortcut_relay.MAX_LABEL].strip()])


class WindowReportServerFuzzTest(unittest.TestCase):
    ALLOWED = {p.ERR_INVALID_PARAMS, p.ERR_METHOD_NOT_FOUND, p.ERR_DEVICE}

    def _exchange(self, msg):
        log, calls, conn = _Log(), [], _Conn()
        _server(log, calls)._dispatch(conn, msg)
        return log, calls, conn.sent

    def _check_reply(self, msg, log, sent):
        req_id = msg.get("id") if isinstance(msg, dict) else None
        if req_id is None:
            self.assertEqual(sent, [])        # a notification gets no answer
            return None
        self.assertEqual(len(sent), 1)
        reply = sent[0]
        self.assertEqual(reply["id"], json.loads(json.dumps(req_id)))
        self.assertEqual(reply["jsonrpc"], "2.0")
        # A malformed frame is the sender's fault: an invalid-params answer, never
        # an internal error with a traceback in the daemon's log.
        self.assertEqual(log.exceptions, [])
        if "error" in reply:
            self.assertIn(reply["error"]["code"], self.ALLOWED)
        else:
            self.assertEqual(reply["result"].get("ok"), True)
        return reply

    @given(JSON)
    def test_any_frame(self, msg):
        log, _, sent = self._exchange(msg)
        self._check_reply(msg, log, sent)

    @given(st.integers(1, 1 << 40),
           st.sampled_from([p.M_WINDOW_REPORT, p.M_AGENTS_REPORT, p.M_STATUS_GET,
                            p.M_FW_FLASH, "", None]),
           JSON)
    def test_any_params(self, req_id, method, params):
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        log, calls, sent = self._exchange(msg)
        reply = self._check_reply(msg, log, sent)
        if method not in (p.M_WINDOW_REPORT, p.M_AGENTS_REPORT):
            self.assertEqual(reply["error"]["code"], p.ERR_METHOD_NOT_FOUND)
            self.assertEqual(calls, [])

    @given(st.integers(1, 1000), JSON, JSON, st.text(max_size=20),
           st.lists(JSON, max_size=12), st.lists(SHORTCUT_ITEM, max_size=8),
           st.binary(max_size=64))
    def test_a_well_formed_report_reaches_the_sink(self, req_id, handle, name, title,
                                                   names, shortcuts, icon):
        params = {"handle": handle, "name": name, "title": title, "names": names,
                  "shortcuts": shortcuts, "icon": base64.b64encode(icon).decode()}
        msg = {"jsonrpc": "2.0", "id": req_id, "method": p.M_WINDOW_REPORT,
               "params": params}
        log, calls, sent = self._exchange(msg)
        reply = self._check_reply(msg, log, sent)
        self.assertEqual(reply["result"], {"ok": True})
        self.assertEqual(len(calls), 1)
        got_handle, got_name, got_title, kw = calls[0]
        self.assertEqual((got_handle, got_name, got_title), (handle, name, title))
        self.assertEqual(kw["names"], tuple(str(n) for n in names[:MAX_NAMES]))
        self.assertEqual([(s.mods, s.hid, s.label) for s in kw["shortcuts"]],
                         decode_model(shortcuts))
        self.assertEqual(kw["icon"], icon or None)

    @given(st.one_of(JSON, st.text(max_size=40),
                     st.text("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",
                             max_size=40)))
    def test_decode_icon(self, value):
        try:
            got = WindowReportServer._decode_icon(value)
        except ValueError:
            return
        if not value:
            self.assertIsNone(got)
        else:
            self.assertIsInstance(value, str)
            self.assertLessEqual(len(value), MAX_ICON_B64)
            # The same bytes again, except the unused low bits of the last
            # character before the padding, which base64 does not check.
            encoded = base64.b64encode(got).decode()
            self.assertEqual(len(encoded), len(value))
            self.assertEqual(encoded.rstrip("=")[:-1], value.rstrip("=")[:-1])


if __name__ == "__main__":
    unittest.main()
