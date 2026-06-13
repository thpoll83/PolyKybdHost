"""Socket-as-single-instance-lock for the control endpoint (headless-core H2).

The control socket doubles as the instance lock: if a process is already
serving the endpoint (answers ``hello``), a second launch should defer to
it rather than fight over the HID device. On POSIX a crashed previous run
can leave a stale socket file that would block ``Listener`` from binding;
``clear_stale_endpoint`` removes it only once we've confirmed nothing is
listening.
"""
import os
import stat
import sys

from multiprocessing.connection import AuthenticationError, Client

from polyhost.server import protocol

# probe_existing outcomes. Only STALE means "nothing is really there, safe to
# unlink the socket and bind"; the other three all mean a real process owns the
# endpoint and a second host must defer.
LIVE = "live"                  # a compatible control server answered hello
INCOMPATIBLE = "incompatible"  # a process answered but with a bad/absent hello
AUTH_MISMATCH = "auth"         # a process is listening but rejected our authkey
STALE = "stale"                # nothing listening (refused / not found / EOF pre-hello)


def probe_existing(address=None, authkey=None, timeout=0.5) -> str:
    """Classify the control endpoint: LIVE, INCOMPATIBLE, AUTH_MISMATCH or STALE.

    Connects, reads the server's hello, and verifies the control-protocol
    version. Distinguishing the failure modes matters: a live-but-incompatible
    or auth-mismatched endpoint must NOT be treated as stale and unlinked
    (that would let a second host start and fight over the HID device)."""
    address = address or protocol.endpoint_address()
    authkey = authkey or protocol.load_or_create_authkey()
    try:
        conn = Client(address, authkey=authkey)
    except AuthenticationError:
        return AUTH_MISMATCH
    except (FileNotFoundError, ConnectionError, OSError):
        # Nothing accepted the connection — no listener / stale socket node.
        return STALE
    try:
        # Past Client(): something accepted, so the endpoint is in use. Any
        # failure from here on is INCOMPATIBLE, never STALE — we must not unlink
        # a socket a real process is bound to.
        if not conn.poll(timeout):
            return INCOMPATIBLE
        msg = protocol.recv_message(conn)
        if msg.get("method") != protocol.HELLO:
            return INCOMPATIBLE
        ok, _ = protocol.check_hello(msg.get("params") or {})
        return LIVE if ok else INCOMPATIBLE
    except (EOFError, OSError):
        return INCOMPATIBLE
    finally:
        try:
            conn.close()
        except OSError:
            pass


def clear_stale_endpoint(address=None) -> None:
    """Remove a stale POSIX socket file so a fresh Listener can bind.

    Only call when :func:`probe_existing` returned ``STALE``. No-op on Windows
    (named pipes don't persist as files). Guarded so it only ever unlinks an
    actual socket node — never a regular file that happens to share the path."""
    if sys.platform == "win32":
        return
    address = address or protocol.endpoint_address()
    try:
        if stat.S_ISSOCK(os.lstat(address).st_mode):
            os.unlink(address)
    except FileNotFoundError:
        pass
    except OSError:
        pass
