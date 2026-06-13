"""Tests for the polyctl CLI — no Qt anywhere.

The "server" side is a tiny thread driving the real wire protocol over a
``multiprocessing.Pipe()``: it sends a hello notification, then answers each
request from a scripted ``{method: result-or-error}`` dict, and optionally
pushes an event for the watch test. The CLI's ``connect()`` is monkeypatched to
return an ``RpcClient`` wrapping the client end of the pipe, so ``main([...])``
runs against the fake server with the connection injected.
"""
import contextlib
import io
import sys
import threading
import unittest
from multiprocessing import Pipe

from polyhost.cli import polyctl
from polyhost.server import protocol


class FakeServer:
    """Drives the wire protocol from a scripted dict on its own thread."""

    def __init__(self, conn, responses, hello_params=None, push_events=None):
        self._conn = conn
        self._responses = responses          # {method: result} or {method: ("error", code, msg)}
        self._hello = hello_params if hello_params is not None else \
            protocol.hello_params("9.9.9")
        self._push_events = push_events or []  # list of (name, payload) to push on subscribe
        self.received = []                     # list of (method, params) the client sent
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def join(self, timeout=5):
        self._thread.join(timeout)

    def _run(self):
        # 1. hello handshake (server speaks first).
        protocol.send_message(self._conn, protocol.make_notification(protocol.HELLO, self._hello))
        try:
            while True:
                msg = protocol.recv_message(self._conn)
                method = msg.get("method")
                req_id = msg.get("id")
                self.received.append((method, msg.get("params")))
                if method == protocol.EVENTS_SUBSCRIBE:
                    protocol.send_message(self._conn, protocol.make_response(req_id, {"subscribed": True}))
                    for name, payload in self._push_events:
                        protocol.send_message(self._conn, protocol.make_event(name, payload))
                    # Stop after pushing events — closing the pipe ends watch().
                    break
                resp = self._responses.get(method, {})
                if isinstance(resp, tuple) and resp and resp[0] == "error":
                    protocol.send_message(self._conn, protocol.make_error(req_id, resp[1], resp[2]))
                else:
                    protocol.send_message(self._conn, protocol.make_response(req_id, resp))
        except EOFError:
            pass
        finally:
            self._conn.close()


def run_main(argv, responses, hello_params=None, push_events=None):
    """Run polyctl.main(argv) against a FakeServer; return (rc, stdout, stderr, server)."""
    client_conn, server_conn = Pipe()
    server = FakeServer(server_conn, responses, hello_params, push_events)
    server.start()

    # The RpcClient verifies the hello on construction (reads the first message).
    rpc = polyctl.RpcClient(client_conn)

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = polyctl._run_with_client(rpc, argv)
    rpc.close()  # let the server thread see EOF and exit its read loop
    server.join()
    return rc, out.getvalue(), err.getvalue(), server


class PolyctlTest(unittest.TestCase):
    def test_status_prints_fields(self):
        status = {"connected": True, "lang": "deDE", "name": "PolyKybd"}
        rc, out, err, _ = run_main(["status"], {protocol.M_STATUS_GET: status})
        self.assertEqual(rc, 0)
        self.assertIn("connected: True", out)
        self.assertIn("lang: deDE", out)
        self.assertIn("name: PolyKybd", out)

    def test_lang_set_sends_correct_method_and_params(self):
        rc, out, err, server = run_main(["lang", "set", "deDE"],
                                        {protocol.M_LANG_SET: [True, "ok"]})
        self.assertEqual(rc, 0)
        methods = [m for m, _ in server.received]
        self.assertIn(protocol.M_LANG_SET, methods)
        params = dict(server.received)[protocol.M_LANG_SET]
        self.assertEqual(params, {"lang": "deDE"})
        self.assertIn("language set to deDE", out)

    def test_error_response_returns_nonzero_and_prints_message(self):
        rc, out, err, _ = run_main(
            ["lang", "set", "xxYY"],
            {protocol.M_LANG_SET: ("error", protocol.ERR_DEVICE, "device said no")})
        self.assertNotEqual(rc, 0)
        self.assertIn("device said no", err)

    def test_hello_version_mismatch_refused(self):
        client_conn, server_conn = Pipe()
        # Server advertises a different control protocol version.
        bad_hello = {"control_protocol": protocol.CONTROL_PROTOCOL_VERSION + 1,
                     "host_version": "9.9.9"}
        server = FakeServer(server_conn, {}, hello_params=bad_hello)
        server.start()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with self.assertRaises(polyctl.RpcError) as ctx:
                polyctl.RpcClient(client_conn)
        client_conn.close()  # unblock the server's recv_message so join() is prompt
        server.join()
        self.assertIn("protocol mismatch", str(ctx.exception).lower())

    def test_hello_mismatch_via_main_returns_nonzero(self):
        # Drive the full main() path with connect() monkeypatched to a mismatching server.
        client_conn, server_conn = Pipe()
        bad_hello = {"control_protocol": protocol.CONTROL_PROTOCOL_VERSION + 1,
                     "host_version": "9.9.9"}
        server = FakeServer(server_conn, {}, hello_params=bad_hello)
        server.start()

        def fake_connect(address=None, authkey=None):
            return polyctl.RpcClient(client_conn)

        orig = polyctl.connect
        polyctl.connect = fake_connect
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = polyctl.main(["status"])
        finally:
            polyctl.connect = orig
            client_conn.close()  # unblock the server's recv_message so join() is prompt
        server.join()
        self.assertNotEqual(rc, 0)
        self.assertIn("mismatch", err.getvalue().lower())

    def test_keymap_set_parses_hex_keycode(self):
        rc, out, err, server = run_main(
            ["keymap", "set", "1", "2", "3", "0x29"],
            {protocol.M_KEYMAP_SET: [True, None]})
        self.assertEqual(rc, 0)
        params = dict(server.received)[protocol.M_KEYMAP_SET]
        self.assertEqual(params, {"layer": 1, "row": 2, "col": 3, "keycode": 41})

    def test_lang_list_prints_one_code_per_line(self):
        rc, out, err, _ = run_main(["lang", "list"],
                                   {protocol.M_LANG_LIST: ["enUS", "deDE", "frFR"]})
        self.assertEqual(rc, 0)
        self.assertEqual(out.split(), ["enUS", "deDE", "frFR"])

    def test_brightness_sends_int(self):
        rc, out, err, server = run_main(["brightness", "42"],
                                        {protocol.M_BRIGHTNESS_SET: [True, None]})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_BRIGHTNESS_SET], {"value": 42})

    def test_idle_on_sends_bool(self):
        rc, out, err, server = run_main(["idle", "on"],
                                        {protocol.M_IDLE_SET: [True, None]})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_IDLE_SET], {"idle": True})

    def test_pause_and_resume(self):
        rc, _, _, server = run_main(["pause"], {protocol.M_PAUSE_SET: {"paused": True}})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_PAUSE_SET], {"paused": True})

        rc, _, _, server = run_main(["resume"], {protocol.M_PAUSE_SET: {"paused": False}})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_PAUSE_SET], {"paused": False})

    def test_settings_set_json_parses_value(self):
        rc, _, _, server = run_main(["settings", "set", "brightness", "30"],
                                    {protocol.M_SETTINGS_SET: [True, None]})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_SETTINGS_SET],
                         {"key": "brightness", "value": 30})

    def test_settings_set_falls_back_to_string(self):
        rc, _, _, server = run_main(["settings", "set", "mode", "hex"],
                                    {protocol.M_SETTINGS_SET: [True, None]})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_SETTINGS_SET],
                         {"key": "mode", "value": "hex"})

    def test_fw_version_prints(self):
        rc, out, _, _ = run_main(["fw", "version"], {protocol.M_FW_VERSION: "0.7.3"})
        self.assertEqual(rc, 0)
        self.assertIn("0.7.3", out)

    def test_watch_prints_events(self):
        events = [("status_changed", {"connected": True}), ("lang_changed", {"lang": "deDE"})]
        rc, out, _, _ = run_main(["watch"], {}, push_events=events)
        self.assertEqual(rc, 0)
        self.assertIn("status_changed", out)
        self.assertIn("lang_changed", out)

    def test_overlay_send_passes_files(self):
        rc, out, _, server = run_main(["overlay", "send", "a.png", "b.png"],
                                      {protocol.M_OVERLAY_SEND: {"queued": True}})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_OVERLAY_SEND],
                         {"files": ["a.png", "b.png"]})


class StreamingServer:
    """Hello → answer events.subscribe + one scripted method call → push a
    list of (name, payload) event notifications → close. Models the
    subscribe-then-call-then-stream flow of `fw flash` / `update install`.
    """

    def __init__(self, conn, method, result, events):
        self._conn = conn
        self._method = method
        self._result = result
        self._events = events
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def join(self, timeout=5):
        self._thread.join(timeout)

    def _run(self):
        protocol.send_message(self._conn, protocol.make_notification(
            protocol.HELLO, protocol.hello_params("9.9.9")))
        try:
            while True:
                msg = protocol.recv_message(self._conn)
                rid, method = msg.get("id"), msg.get("method")
                if method == protocol.EVENTS_SUBSCRIBE:
                    protocol.send_message(self._conn, protocol.make_response(rid, {"subscribed": True}))
                elif method == self._method:
                    protocol.send_message(self._conn, protocol.make_response(rid, self._result))
                    for name, payload in self._events:
                        protocol.send_message(self._conn, protocol.make_event(name, payload))
                    break
                else:
                    protocol.send_message(self._conn, protocol.make_response(rid, {}))
        except EOFError:
            pass
        finally:
            self._conn.close()


def run_streaming(argv, method, result, events):
    client_conn, server_conn = Pipe()
    server = StreamingServer(server_conn, method, result, events)
    server.start()
    rpc = polyctl.RpcClient(client_conn)
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = polyctl._run_with_client(rpc, argv)
    rpc.close()
    server.join()
    return rc, out.getvalue(), err.getvalue()


class FwFlashUpdateTest(unittest.TestCase):
    def test_fw_flash_apply_streams_to_completion(self):
        events = [("fw_flash_progress", {"pct": 50, "msg": "writing"}),
                  ("fw_flash_done", {"ok": True, "msg": "staged"}),
                  ("fw_apply_progress", {"pct": 50, "msg": "applying"}),
                  ("fw_apply_done", {"ok": True, "msg": "applied"})]
        rc, out, err = run_streaming(["fw", "flash", "fw.bin", "--apply"],
                                     protocol.M_FW_FLASH, {"queued": True, "apply": True}, events)
        self.assertEqual(rc, 0)
        self.assertIn("applied", out)

    def test_fw_flash_done_without_apply_returns_zero(self):
        events = [("fw_flash_done", {"ok": True, "msg": "staged"})]
        rc, out, _ = run_streaming(["fw", "flash", "fw.bin"],
                                   protocol.M_FW_FLASH, {"queued": True, "apply": False}, events)
        self.assertEqual(rc, 0)
        self.assertIn("flash complete", out)

    def test_fw_flash_failure_returns_nonzero(self):
        events = [("fw_flash_done", {"ok": False, "msg": "crc mismatch"})]
        rc, _, err = run_streaming(["fw", "flash", "fw.bin"],
                                   protocol.M_FW_FLASH, {"queued": True, "apply": False}, events)
        self.assertNotEqual(rc, 0)
        self.assertIn("crc mismatch", err)

    def test_update_install_streams_to_restart(self):
        events = [("update_progress", {"pct": 40, "msg": "downloading"}),
                  ("update_finished_ok", {"version": "0.9.0"})]
        rc, out, _ = run_streaming(["update", "install"],
                                   protocol.M_UPDATE_INSTALL, {"queued": True, "version": "0.9.0"}, events)
        self.assertEqual(rc, 0)
        self.assertIn("restart", out.lower())

    def test_update_check_reports_availability(self):
        rc, out, _, _ = run_main(["update", "check"],
                                 {protocol.M_UPDATE_CHECK: {"available": True, "version": "0.9.0", "url": "http://x"}})
        self.assertEqual(rc, 0)
        self.assertIn("0.9.0", out)


class ImportGuardTest(unittest.TestCase):
    def test_cli_imports_without_pyqt5(self):
        import subprocess
        code = ("import sys; sys.modules['PyQt5'] = None; "
                "import polyhost.cli.polyctl; print('ok')")
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0,
                         msg=f"stdout={proc.stdout!r} stderr={proc.stderr!r}")
        self.assertIn("ok", proc.stdout)


if __name__ == "__main__":
    unittest.main()
