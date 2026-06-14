"""RemoteCore — the GUI-as-socket-client adapter (headless-core H4a).

Drives a real ControlServer (backed by a tiny fake core) over the actual
wire protocol and checks that RemoteCore: caches status into its properties,
maps method calls to RPC + the (ok, payload) contract, fans server-pushed
events to local observers (keeping the cache fresh), and synthesizes a
disconnect on EOF. No Qt anywhere.
"""
import logging
import os
import sys
import tempfile
import threading
import time
import unittest

from polyhost.cli import polyctl
from polyhost.client.remote_core import RemoteCore
from polyhost.server.control_server import ControlServer


class FakeCore:
    def __init__(self):
        self._obs = []
        self.calls = []
        self.paused = False

    def subscribe(self, cb):
        self._obs.append(cb)

    def emit(self, name, payload):
        for cb in list(self._obs):
            cb(name, payload)

    def get_status(self):
        return {"connected": True, "device_present": True, "paused": False,
                "fw_version": "0.8.0", "current_lang": "enUS"}

    def list_languages(self):
        return ["enUS", "deDE"]

    def set_language(self, lang):
        self.calls.append(("set_language", lang))
        return (True, lang)

    def set_brightness(self, value):
        return (True, int(value))

    def send_overlay_data(self, files):
        self.calls.append(("send", list(files)))
        return True

    def flash_firmware(self, path, apply=False):
        self.calls.append(("flash", path, apply))
        return (True, {"queued": True, "apply": bool(apply)})

    def set_paused(self, paused):
        self.paused = bool(paused)

    def get_fw_version(self):
        return "0.8.0"

    def settings_list(self):
        return {"brightness": 25, "unicode_send_composition_mode": True}


def _addr():
    return os.path.join(tempfile.mkdtemp(prefix="polyrc_"), "ctl.sock")


def _quiet():
    lg = logging.getLogger("test.remotecore")
    lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


def _wait(pred, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return pred()


@unittest.skipIf(sys.platform == "win32", "UDS-based control socket test")
class TestRemoteCore(unittest.TestCase):

    def setUp(self):
        self.core = FakeCore()
        self.addr, self.key = _addr(), b"k"
        self.srv = ControlServer(self.core, "9.9.9", _quiet(),
                                 address=self.addr, authkey=self.key)
        self.srv.start()
        self.rc = RemoteCore(polyctl.connect(self.addr, self.key),
                             polyctl.connect(self.addr, self.key), _quiet())

    def tearDown(self):
        try:
            self.rc.shutdown()
        finally:
            self.srv.stop()

    def test_status_cached_into_properties(self):
        self.assertTrue(self.rc.connected)
        self.assertTrue(self.rc.device_present)
        self.assertFalse(self.rc.paused)
        self.assertEqual(self.rc.kb_sw_version, "0.8.0")

    def test_set_language_dispatches_and_unwraps(self):
        ok, payload = self.rc.set_language("deDE")
        self.assertTrue(ok)
        self.assertEqual(payload, "deDE")
        self.assertIn(("set_language", "deDE"), self.core.calls)

    def test_overlay_send_returns_queued_bool(self):
        self.assertTrue(self.rc.send_overlay_data(["a.png"]))
        self.assertIn(("send", ["a.png"]), self.core.calls)

    def test_flash_firmware_dispatch(self):
        ok, payload = self.rc.flash_firmware("fw.bin", apply=True)
        self.assertTrue(ok)
        self.assertEqual(payload, {"queued": True, "apply": True})
        self.assertIn(("flash", "fw.bin", True), self.core.calls)

    def test_settings_list_round_trips(self):
        settings = self.rc.settings_list()
        self.assertEqual(settings.get("brightness"), 25)
        self.assertTrue(settings.get("unicode_send_composition_mode"))

    def test_event_fanout_and_cache_refresh(self):
        seen = []
        self.rc.subscribe(lambda n, p: seen.append((n, p)))
        self.core.emit("status_changed", {"connected": False, "device_present": False})
        self.assertTrue(_wait(lambda: any(n == "status_changed" for n, _ in seen)))
        self.assertFalse(self.rc.connected)        # cache updated from the event


class _FakeRpc:
    def __init__(self, status):
        self._status = status

    def call(self, method, params=None):
        from polyhost.server import protocol as p
        return dict(self._status) if method == p.M_STATUS_GET else {}

    def close(self):
        pass


class _FakeEvt:
    """Event connection whose stream ends (EOF) only once the test releases it
    — lets us observe the synthesized disconnect deterministically, without the
    same-process socket-close-doesn't-wake-a-blocked-read quirk."""

    def __init__(self):
        self.released = threading.Event()

    def subscribe_events(self):
        pass

    def events(self):
        self.released.wait(3.0)   # block, then end the stream (EOF)
        return
        yield                     # noqa — makes this a generator

    def close(self):
        pass


class TestRemoteCorePumpEOF(unittest.TestCase):
    """The pump must synthesize a disconnect when the event stream ends (the
    daemon vanished), so the GUI greys out instead of hanging."""

    def test_synthesizes_disconnect_on_stream_end(self):
        evt = _FakeEvt()
        rc = RemoteCore(_FakeRpc({"connected": True, "device_present": True}),
                        evt, _quiet())
        seen = []
        rc.subscribe(lambda n, p: seen.append((n, p)))
        self.assertTrue(rc.connected)
        evt.released.set()        # event stream ends -> synthesize disconnect
        self.assertTrue(_wait(lambda: any(
            n == "status_changed" and (p or {}).get("connected") is False
            for n, p in seen)))
        self.assertFalse(rc.connected)


if __name__ == "__main__":
    unittest.main()
