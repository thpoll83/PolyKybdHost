"""ControlServer: a real multiprocessing.connection client drives the server
over a temp socket. No Qt, no real device — a FakeCore stub stands in for
PolyCore. Threading is given short timeouts and the server is stopped in
tearDown so a hung test cannot wedge the suite.
"""
import multiprocessing.connection as mpc
import os
import tempfile
import threading
import time
import unittest

from polyhost.server import protocol as p
from polyhost.server.control_server import ControlServer, RpcError, _unwrap


class _NullLog:
    def exception(self, *a, **k):
        pass

    def debug(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


class FakeCore:
    """Minimal stand-in for PolyCore's command API + observer plumbing."""

    def __init__(self):
        self._observers = []
        self.paused = False
        self.lang_set_result = (True, "deDE")
        self.status = {
            "connected": True,
            "device_present": True,
            "paused": False,
            "name": "PolyKybd",
            "fw_version": "0.7.0",
            "protocol": 3,
            "hw_version": "split72",
            "current_lang": "enUS",
            "host_version": "0.8.31",
        }
        self.calls = []

    # observer plumbing -------------------------------------------------
    def subscribe(self, cb):
        self._observers.append(cb)

    def emit(self, name, payload):
        for cb in list(self._observers):
            cb(name, payload)

    # command API -------------------------------------------------------
    def get_status(self):
        return dict(self.status)

    def list_languages(self):
        return ["enUS", "deDE"]

    def set_language(self, lang):
        self.calls.append(("set_language", lang))
        return self.lang_set_result

    def set_brightness(self, value):
        return (True, int(value))

    def set_idle(self, idle):
        return (True, bool(idle))

    def enable_overlays(self):
        return (True, "on")

    def disable_overlays(self):
        return (True, "off")

    def reset_overlays(self):
        return (True, "reset")

    def send_overlay_data(self, data):
        self.calls.append(("send_overlay_data", data))
        return True

    def keymap_layer_count(self):
        return (True, 9)

    def keymap_default_layer(self):
        return (True, 0)

    def keymap_buffer(self):
        return (True, [1, 2, 3])

    def keymap_set(self, layer, row, col, keycode):
        return (True, [layer, row, col, keycode])

    def get_fw_version(self):
        return "0.7.0"

    def flash_firmware(self, path, apply=False):
        self.calls.append(("flash_firmware", path, apply))
        return (True, {"queued": True, "apply": bool(apply)})

    def check_update(self):
        return (True, {"available": True, "version": "0.9.0", "url": "http://x"})

    def install_update(self):
        return (True, {"queued": True, "version": "0.9.0"})

    def execute_commands(self, lines):
        self.calls.append(("execute_commands", list(lines)))
        return True

    def set_paused(self, paused):
        self.paused = bool(paused)

    def save_mru(self):
        self.calls.append(("save_mru",))

    def settings_get(self, key):
        return {"brightness": 25}.get(key)

    def settings_set(self, key, value):
        if key == "brightness":
            return (True, key)
        return (False, f"Unknown setting '{key}'")


class ControlServerTest(unittest.TestCase):
    def setUp(self):
        self.core = FakeCore()
        self._tmpdir = tempfile.mkdtemp(prefix="polykybd-cs-")
        self.address = os.path.join(self._tmpdir, "ctl.sock")
        self.authkey = b"testkey"
        self.shutdown_called = threading.Event()
        self.server = ControlServer(
            self.core, "0.8.31", _NullLog(),
            on_shutdown=self.shutdown_called.set,
            address=self.address, authkey=self.authkey)
        self.server.start()
        self._clients = []

    def tearDown(self):
        for c in self._clients:
            try:
                c.close()
            except Exception:
                pass
        try:
            self.server.stop()
        except Exception:
            pass
        try:
            import shutil
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        except Exception:
            pass

    # helpers -----------------------------------------------------------
    def _connect(self, authkey=None):
        # The socket is created by the listener thread; give it a beat.
        deadline = time.time() + 3.0
        last = None
        while time.time() < deadline:
            try:
                conn = mpc.Client(self.address,
                                  authkey=self.authkey if authkey is None else authkey)
                self._clients.append(conn)
                return conn
            except (FileNotFoundError, ConnectionRefusedError) as e:
                last = e
                time.sleep(0.02)
        raise AssertionError(f"could not connect: {last}")

    def _recv(self, conn, timeout=3.0):
        self.assertTrue(conn.poll(timeout), "timed out waiting for a message")
        return p.recv_message(conn)

    def _call(self, conn, req_id, method, params=None):
        p.send_message(conn, p.make_request(req_id, method, params or {}))
        return self._recv(conn)

    def _hello_then(self, conn):
        msg = self._recv(conn)
        self.assertEqual(msg["method"], p.HELLO)
        ok, why = p.check_hello(msg["params"])
        self.assertTrue(ok, why)
        return msg

    # tests -------------------------------------------------------------
    def test_hello_first(self):
        conn = self._connect()
        self._hello_then(conn)

    def test_status_get(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 1, p.M_STATUS_GET)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"], self.core.get_status())

    def test_lang_set_success(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 5, p.M_LANG_SET, {"lang": "deDE"})
        self.assertEqual(resp["result"], "deDE")
        self.assertIn(("set_language", "deDE"), self.core.calls)

    def test_lang_set_device_failure_is_err_device(self):
        self.core.lang_set_result = (False, "device busy")
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 6, p.M_LANG_SET, {"lang": "xxYY"})
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], p.ERR_DEVICE)
        self.assertEqual(resp["error"]["message"], "device busy")

    def test_unknown_method(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 9, "no.such.method")
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], p.ERR_METHOD_NOT_FOUND)

    def test_invalid_params(self):
        conn = self._connect()
        self._hello_then(conn)
        # lang.set requires "lang"
        resp = self._call(conn, 10, p.M_LANG_SET, {})
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], p.ERR_INVALID_PARAMS)

    def test_overlay_send_queued(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 11, p.M_OVERLAY_SEND, {"files": ["a", "b"]})
        self.assertEqual(resp["result"], {"queued": True})

    def test_pause_set(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 12, p.M_PAUSE_SET, {"paused": True})
        self.assertEqual(resp["result"], {"paused": True})
        self.assertTrue(self.core.paused)

    def test_host_shutdown(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 13, p.M_HOST_SHUTDOWN)
        self.assertEqual(resp["result"], {"shutting_down": True})
        # Teardown now fires after the reply is written (see _dispatch), so the
        # client sees the ack first; wait briefly for the deferred callback.
        self.assertTrue(self.shutdown_called.wait(2))

    def test_fw_flash_dispatch(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 30, p.M_FW_FLASH, {"path": "fw.bin", "apply": True})
        self.assertEqual(resp["result"], {"queued": True, "apply": True})
        self.assertIn(("flash_firmware", "fw.bin", True), self.core.calls)

    def test_update_check_and_install_dispatch(self):
        conn = self._connect()
        self._hello_then(conn)
        chk = self._call(conn, 31, p.M_UPDATE_CHECK)
        self.assertTrue(chk["result"]["available"])
        ins = self._call(conn, 32, p.M_UPDATE_INSTALL)
        self.assertEqual(ins["result"], {"queued": True, "version": "0.9.0"})

    def test_events_subscribe_then_emit(self):
        conn = self._connect()
        self._hello_then(conn)
        resp = self._call(conn, 20, p.EVENTS_SUBSCRIBE)
        self.assertEqual(resp["result"], {"subscribed": True})
        # The subscription is registered under the server lock when the
        # response was built, so it is live by the time we have the reply.
        self.core.emit("status_changed", {"connected": False})
        ev = self._recv(conn)
        self.assertEqual(ev["method"], p.EVENT_NOTIFICATION)
        self.assertEqual(ev["params"]["name"], "status_changed")
        self.assertEqual(ev["params"]["payload"], {"connected": False})

    def test_no_event_without_subscribe(self):
        conn = self._connect()
        self._hello_then(conn)
        # Not subscribed: emit must not reach this connection. Use a second
        # subscribed connection to know the emit fan-out has run.
        sub = self._connect()
        self._hello_then(sub)
        self._call(sub, 1, p.EVENTS_SUBSCRIBE)
        self.core.emit("status_changed", {"x": 1})
        ev = self._recv(sub)
        self.assertEqual(ev["params"]["name"], "status_changed")
        # The unsubscribed connection should have nothing pending.
        self.assertFalse(conn.poll(0.2))

    def test_wrong_authkey_fails(self):
        with self.assertRaises(Exception):
            bad = mpc.Client(self.address, authkey=b"wrongkey")
            # Some platforms only surface the auth failure on first I/O.
            bad.send_bytes(b"x")
            bad.recv_bytes()


class UnwrapTest(unittest.TestCase):
    def test_unwrap_ok(self):
        self.assertEqual(_unwrap((True, {"a": 1})), {"a": 1})

    def test_unwrap_failure_raises_err_device(self):
        with self.assertRaises(RpcError) as ctx:
            _unwrap((False, "boom"))
        self.assertEqual(ctx.exception.code, p.ERR_DEVICE)
        self.assertEqual(ctx.exception.message, "boom")


if __name__ == "__main__":
    unittest.main()
