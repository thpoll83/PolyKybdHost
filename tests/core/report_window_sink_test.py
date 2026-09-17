"""The network dispatch driven against the REAL PolyCore sink.

⚠️ This exists because `window_report_server_test` cannot catch the bug it was
written after. That suite hands `WindowReportServer` a test double, so the
double's signature IS the contract it checks -- update the server and the
double together and the pair agrees with itself while the production sink,
`PolyCore.report_window` (wired in `headless.py`), rejects the very call the
server makes. Measured 2026-09-17, from a forwarder in the field:

    TypeError: PolyCore.report_window() got an unexpected keyword argument
    'names'. Did you mean 'name'?

So the seam worth pinning is server -> real sink -> handler, with only the
handler faked. Everything below drives `dispatch` exactly as the socket does.
"""

import base64
import logging
import unittest

import polyhost.server.protocol as p
from polyhost.core.poly_core import PolyCore
from polyhost.server.window_report_server import WindowReportServer

ICON = b"\x89PNG\r\n\x1a\n" + b"icon-bytes"


class _FakeRemote:
    """Records the call; answers want_icon the way RemoteHandler does."""

    def __init__(self, want_icon=False):
        self.calls = []
        self._want_icon = want_icon

    def report_window(self, handle, name, title, os=None, url=None,
                      names=(), icon_key=None, icon=None):
        self.calls.append(dict(handle=handle, name=name, title=title, os=os,
                               url=url, names=names, icon_key=icon_key,
                               icon=icon))
        return {"want_icon": True} if self._want_icon else None


class _FakeHandler:
    def __init__(self, remote):
        self.remote_handler = remote


def _server(core):
    # dispatch() touches only _on_report, so skip __init__ and its authkey/
    # socket setup rather than standing a real listener up.
    srv = WindowReportServer.__new__(WindowReportServer)
    srv._on_report = core.report_window
    return srv


def _core(remote):
    core = PolyCore.__new__(PolyCore)
    core.log = logging.getLogger("test.polycore.reportwindow")
    core.overlay_handler = _FakeHandler(remote)
    return core


def _params(**kw):
    out = {"handle": 7, "name": "code", "title": "main.py"}
    out.update(kw)
    return out


class DispatchReachesTheRealSinkTest(unittest.TestCase):

    def test_the_full_param_set_the_server_sends_is_ACCEPTED(self):
        # The regression: this raised TypeError inside the daemon and the
        # forwarder logged it as "Window-report RPC failed".
        remote = _FakeRemote()
        resp = _server(_core(remote)).dispatch(
            None, 1, p.M_WINDOW_REPORT,
            _params(os=2, url="https://x", names=["Visual Studio Code"],
                    icon_key="k1", icon=base64.b64encode(ICON).decode()))
        self.assertNotIn("error", resp, resp)
        self.assertEqual(len(remote.calls), 1)

    def test_every_field_reaches_the_handler(self):
        remote = _FakeRemote()
        _server(_core(remote)).dispatch(
            None, 1, p.M_WINDOW_REPORT,
            _params(os=2, url="https://example/x", names=["Visual Studio Code"],
                    icon_key="k1", icon=base64.b64encode(ICON).decode()))
        call = remote.calls[0]
        self.assertEqual(call["os"], 2)
        # ⚠️ url was accepted by the sink and dropped on the floor from the day
        # the parameter was added -- the one field here that was broken on main
        # rather than on the icon branch.
        self.assertEqual(call["url"], "https://example/x")
        self.assertEqual(call["names"], ("Visual Studio Code",))
        self.assertEqual(call["icon_key"], "k1")
        self.assertEqual(call["icon"], ICON)

    def test_want_icon_survives_the_ok_payload_tuple(self):
        # The quieter half: PolyCore answers (ok, payload), so a dict-only
        # merge in dispatch discarded want_icon and the forwarder never sent
        # the icon -- no error anywhere, just no mark on the keyboard.
        resp = _server(_core(_FakeRemote(want_icon=True))).dispatch(
            None, 1, p.M_WINDOW_REPORT, _params(icon_key="k1"))
        self.assertTrue(resp["result"]["ok"])
        self.assertTrue(resp["result"].get("want_icon"),
                        "the forwarder decides whether to send the icon from "
                        "this field; without it the follow-up never happens")

    def test_no_want_icon_when_the_handler_does_not_ask(self):
        resp = _server(_core(_FakeRemote(want_icon=False))).dispatch(
            None, 1, p.M_WINDOW_REPORT, _params(icon_key="k1"))
        self.assertTrue(resp["result"]["ok"])
        self.assertNotIn("want_icon", resp["result"])

    def test_a_sink_failure_is_still_surfaced_as_an_error(self):
        core = PolyCore.__new__(PolyCore)
        core.log = logging.getLogger("test.polycore.reportwindow")
        core.overlay_handler = None          # -> (False, "...unavailable")
        resp = _server(core).dispatch(None, 1, p.M_WINDOW_REPORT, _params())
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], p.ERR_DEVICE)


class ControlSocketCallShapeTest(unittest.TestCase):
    """The control socket reaches the same sink and must bind the same way."""

    def test_the_control_server_kwargs_bind(self):
        import inspect
        # Mirrors control_server's M_WINDOW_REPORT lambda exactly.
        inspect.signature(PolyCore.report_window).bind(
            None, 7, "code", "main.py", os=2, url=None,
            names=(), icon_key=None)


if __name__ == "__main__":
    unittest.main()
