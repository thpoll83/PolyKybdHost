"""Socket-as-single-instance-lock for the control endpoint (headless-core H2).

The control socket doubles as the instance lock: if a process is already
serving the endpoint (answers ``hello``), a second launch should defer to
it rather than fight over the HID device. On POSIX a crashed previous run
can leave a stale socket file that would block ``Listener`` from binding;
``clear_stale_endpoint`` removes it only once we've confirmed nothing is
listening.
"""
import os
import sys

from multiprocessing.connection import Client

from polyhost.server import protocol


def probe_existing(address=None, authkey=None, timeout=0.5) -> bool:
    """Return True iff a live control server already answers the endpoint.

    Connects, reads the server's hello, and verifies the control-protocol
    version. Any failure (no server, refused, stale socket, bad/again hello,
    auth mismatch) means "not a usable running instance" -> False."""
    address = address or protocol.endpoint_address()
    authkey = authkey or protocol.load_or_create_authkey()
    conn = None
    try:
        conn = Client(address, authkey=authkey)
        if not conn.poll(timeout):
            return False
        msg = protocol.recv_message(conn)
        if msg.get("method") != protocol.HELLO:
            return False
        ok, _ = protocol.check_hello(msg.get("params") or {})
        return ok
    except Exception:
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def clear_stale_endpoint(address=None) -> None:
    """Remove a stale POSIX socket file so a fresh Listener can bind.

    Only call after :func:`probe_existing` returned False. No-op on Windows
    (named pipes don't persist as files) and when the path doesn't exist."""
    if sys.platform == "win32":
        return
    address = address or protocol.endpoint_address()
    try:
        if os.path.exists(address):
            os.unlink(address)
    except OSError:
        pass
