"""Socket-as-single-instance-lock: probe_existing detects a live control
server and clear_stale_endpoint removes a dead socket file. No Qt.
"""
import os
import socket
import subprocess
import sys
import tempfile
import unittest

from polyhost.server.control_server import ControlServer
from polyhost.server.instance import (
    probe_existing, clear_stale_endpoint, claim_instance, EndpointBusy,
    LIVE, LOCKED, STALE)


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


@unittest.skipIf(sys.platform == "win32", "flock-specific; Windows uses msvcrt")
class TestInstanceClaim(unittest.TestCase):
    """The claim is what makes the socket a real lock rather than a
    check-then-act. Before it, two daemons spawned in the same millisecond both
    read STALE, both unlinked the socket node, and one died on EADDRINUSE —
    having already opened the keyboard, which on macOS locked the winner out of
    the device for the rest of the session (field, 2026-09-19)."""

    def test_claim_then_bind_then_probe_live(self):
        addr, key = _addr(), b"k"
        claim = claim_instance(addr, key)
        try:
            srv = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=key)
            srv.start()
            try:
                self.assertEqual(probe_existing(addr, key), LIVE)
            finally:
                srv.stop()
        finally:
            claim.release()

    def test_second_claim_is_refused_while_the_first_is_held(self):
        """The whole point: the loser learns it lost BEFORE it opens the device.

        The first claimant has not bound yet, so there is nothing for a probe to
        answer — exactly the window the old probe-only check read as STALE."""
        addr, key = _addr(), b"k"
        claim = claim_instance(addr, key)
        try:
            with self.assertRaises(EndpointBusy) as ctx:
                claim_instance(addr, key)
            self.assertEqual(ctx.exception.outcome, LOCKED)
        finally:
            claim.release()

    def test_claim_reports_live_when_a_server_already_serves(self):
        addr, key = _addr(), b"k"
        srv = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=key)
        srv.start()
        try:
            with self.assertRaises(EndpointBusy) as ctx:
                claim_instance(addr, key)
            self.assertEqual(ctx.exception.outcome, LIVE)
        finally:
            srv.stop()

    def test_claim_refuses_an_endpoint_held_on_another_authkey(self):
        """AUTH_MISMATCH must never be treated as free: unlinking a socket a
        live process is bound to is the worse outcome."""
        from polyhost.server.instance import AUTH_MISMATCH
        addr = _addr()
        srv = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=b"right")
        srv.start()
        try:
            with self.assertRaises(EndpointBusy) as ctx:
                claim_instance(addr, b"wrong")
            self.assertEqual(ctx.exception.outcome, AUTH_MISMATCH)
        finally:
            srv.stop()

    def test_release_lets_the_next_host_claim(self):
        addr, key = _addr(), b"k"
        claim_instance(addr, key).release()
        claim_instance(addr, key).release()      # must not raise

    def test_claim_clears_a_stale_socket_node(self):
        """A crashed host leaves the socket node on disk with nothing behind it,
        and Listener() refuses to bind over it. Closing the socket does not
        unlink the path, so binding one and dropping it reproduces exactly that
        state."""
        addr, key = _addr(), b"k"
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(addr)
        sock.close()
        self.assertTrue(os.path.exists(addr))
        self.assertEqual(probe_existing(addr, key), STALE)
        claim = claim_instance(addr, key)
        try:
            self.assertFalse(os.path.exists(addr))
            # And the address is bindable again.
            srv = ControlServer(_StubCore(), "0.0.0", _quiet(), address=addr, authkey=key)
            srv.start()
            srv.stop()
        finally:
            claim.release()

    def test_a_dead_holder_does_not_wedge_the_endpoint(self):
        """The lock is an OS file lock, not a pid file, so the kernel drops it
        when the holder dies however it dies — a crashed host can never leave
        the endpoint permanently unclaimable."""
        addr, key = _addr(), b"k"
        code = (
            "import sys; sys.path.insert(0, %r);"
            "from polyhost.server.instance import claim_instance;"
            "claim_instance(%r, %r); print('held', flush=True)"
            % (os.getcwd(), addr, key)
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertIn("held", proc.stdout, proc.stderr)
        claim_instance(addr, key).release()      # the dead holder's lock is gone


def _quiet():
    import logging
    lg = logging.getLogger("test.instance")
    lg.addHandler(logging.NullHandler())
    lg.propagate = False
    return lg


if __name__ == "__main__":
    unittest.main()
