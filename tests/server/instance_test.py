"""Socket-as-single-instance-lock: probe_existing detects a live control
server and clear_stale_endpoint removes a dead socket file. No Qt.
"""
import os
import sys
import tempfile
import unittest

from polyhost.server.control_server import ControlServer
from polyhost.server.instance import probe_existing, clear_stale_endpoint


class _StubCore:
    """Minimal core: ControlServer.start only needs subscribe()."""
    def subscribe(self, cb):
        pass


def _addr():
    return os.path.join(tempfile.mkdtemp(prefix="polylock_"), "polykybd.sock")


@unittest.skipIf(sys.platform == "win32", "UDS-specific stale-file test")
class TestInstanceLock(unittest.TestCase):

    def test_probe_true_while_serving_false_after_stop(self):
        addr, key = _addr(), b"k"
        srv = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=key)
        srv.start()
        try:
            self.assertTrue(probe_existing(addr, key))
        finally:
            srv.stop()
        # After stop, nothing answers (a stale socket file may remain).
        self.assertFalse(probe_existing(addr, key))

    def test_probe_false_when_nothing_listening(self):
        addr = _addr()
        self.assertFalse(probe_existing(addr, b"k"))

    def test_clear_stale_endpoint_removes_dead_socket(self):
        addr, key = _addr(), b"k"
        srv = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=key)
        srv.start()
        srv.stop()
        # A stale socket file is left behind by UDS bind; clearing it lets a
        # fresh Listener rebind.
        clear_stale_endpoint(addr)
        self.assertFalse(os.path.exists(addr))
        # Re-binding the same address now succeeds.
        srv2 = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=key)
        srv2.start()
        try:
            self.assertTrue(probe_existing(addr, key))
        finally:
            srv2.stop()


def _quiet():
    import logging
    lg = logging.getLogger("test.instance")
    lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


if __name__ == "__main__":
    unittest.main()
