"""Socket-as-single-instance-lock: probe_existing detects a live control
server and clear_stale_endpoint removes a dead socket file. No Qt.
"""
import os
import sys
import tempfile
import unittest

from polyhost.server.control_server import ControlServer
from polyhost.server.instance import (
    probe_existing, clear_stale_endpoint, LIVE, STALE)


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
            self.assertEqual(probe_existing(addr, key), LIVE)
        finally:
            srv.stop()
        # After stop, nothing answers (a stale socket file may remain).
        self.assertEqual(probe_existing(addr, key), STALE)

    def test_probe_stale_when_nothing_listening(self):
        addr = _addr()
        self.assertEqual(probe_existing(addr, b"k"), STALE)

    def test_probe_auth_mismatch_is_not_stale(self):
        # A live server on a different authkey must NOT read as stale — clearing
        # its socket would let a second host start and fight over the device.
        from polyhost.server.instance import AUTH_MISMATCH
        addr = _addr()
        srv = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=b"right")
        srv.start()
        try:
            self.assertEqual(probe_existing(addr, b"wrong"), AUTH_MISMATCH)
        finally:
            srv.stop()

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
            self.assertEqual(probe_existing(addr, key), LIVE)
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
