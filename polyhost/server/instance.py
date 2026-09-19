"""Socket-as-single-instance-lock for the control endpoint (headless-core H2).

The control socket doubles as the instance lock: if a process is already
serving the endpoint (answers ``hello``), a second launch should defer to
it rather than fight over the HID device. On POSIX a crashed previous run
can leave a stale socket file that would block ``Listener`` from binding;
``clear_stale_endpoint`` removes it only once we've confirmed nothing is
listening.

Probing, clearing and binding are three steps, so on their own they are a
check-then-act: two hosts starting in the same millisecond both read STALE,
both unlink the socket node and one loses the bind with ``EADDRINUSE`` — after
both have already opened the keyboard. :func:`claim_instance` closes that
window with an OS file lock held for the life of the host, and raises
:class:`EndpointBusy` so the loser stands down cleanly instead of dying in an
unhandled traceback.
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

#: Not a probe outcome: `claim_instance` reports it when another process holds
#: the instance lock but has not bound the endpoint yet, so there is nothing for
#: a probe to answer. That window is exactly the one the probe-only check used
#: to read as STALE, which is how two hosts both concluded they were alone.
LOCKED = "locked"


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


class EndpointBusy(RuntimeError):
    """Another process already owns the control endpoint.

    Raised by :func:`claim_instance` instead of letting the bind fail with
    ``EADDRINUSE``: losing the race is an expected outcome of two hosts
    starting at once, and the loser's job is to stand down quietly, not to die
    in a traceback. ``outcome`` carries the :func:`probe_existing` verdict that
    decided it (LIVE / INCOMPATIBLE / AUTH_MISMATCH), or :data:`LOCKED` when
    the lock is held by a process that has not bound the endpoint yet."""

    def __init__(self, outcome):
        super().__init__(f"control endpoint is already in use ({outcome})")
        self.outcome = outcome


def _try_lock(fd) -> bool:
    """Take an exclusive, non-blocking lock on ``fd``. False if held elsewhere.

    An OS file lock, not a pid file: the kernel drops it when the holder dies
    however it dies, so a crashed or killed host can never leave the endpoint
    permanently unclaimable."""
    if sys.platform == "win32":
        import msvcrt
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


class InstanceClaim:
    """Proof that this process, and only this process, owns the endpoint.

    Held for the life of the host: the OS file lock underneath it is what makes
    the control socket a real single-instance lock instead of a check-then-act
    one. :meth:`release` exists for tests and for a host that shuts down without
    exiting; a process that simply dies releases it too."""

    def __init__(self, fd, path):
        self._fd = fd
        self.path = path

    def release(self) -> None:
        """Drop the lock. Idempotent, never raises."""
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(fd)
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
        return False


def claim_instance(address=None, authkey=None) -> InstanceClaim:
    """Become the one host that owns the control endpoint, or raise.

    Take this BEFORE building anything that touches the keyboard, and hold it
    for the life of the process. ``probe_existing`` on its own is a
    check-then-act: two hosts starting in the same millisecond both read STALE,
    both unlink the socket node, and one loses the bind with ``EADDRINUSE``.
    That was survivable only in theory — the loser had already opened the
    keyboard from ``PolyCore.__init__``, and macOS makes the HID open
    exclusive, so the *winner* then got ``kIOReturnExclusiveAccess`` on every
    reconnect and the board stayed unreachable until the user replugged it 50
    minutes later (field, macOS 26.6, 2026-09-19).

    The file lock serialises probe -> clear-stale -> the caller's bind, and the
    claim outlives the bind so a second host is turned away for as long as this
    one runs. Raises :class:`EndpointBusy` when anything else owns it, which
    includes INCOMPATIBLE / AUTH_MISMATCH: unlinking a socket a live process is
    bound to would be the worse outcome."""
    address = address or protocol.endpoint_address()
    path = protocol.instance_lock_path(address)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    if not _try_lock(fd):
        # Someone holds the lock. They may not have bound the endpoint yet, so
        # the probe is the better answer when it has one — "locked" otherwise.
        os.close(fd)
        outcome = probe_existing(address, authkey)
        raise EndpointBusy(LOCKED if outcome == STALE else outcome)
    claim = InstanceClaim(fd, path)
    try:
        outcome = probe_existing(address, authkey)
        if outcome != STALE:
            raise EndpointBusy(outcome)
        clear_stale_endpoint(address)
    except BaseException:
        claim.release()
        raise
    return claim
