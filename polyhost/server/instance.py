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
import time

from multiprocessing.connection import AuthenticationError, Client

from polyhost.server import protocol
from polyhost.util import filelock

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
        filelock.unlock(fd)
        try:
            os.close(fd)
        except OSError:
            # Already closed — a double release, or the interpreter tearing
            # down around us. The descriptor is gone, which is all release()
            # promises.
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
        return False


#: How long :func:`claim_gui` waits for a departing tray to drop its claim.
#: The lock overlaps by design on two ordinary paths — the post-update relaunch
#: spawns the replacement before this process exits, and a user who quits the
#: tray and immediately starts it again catches the old one still tearing down.
#: Both resolve in well under a second; the wait only costs a genuine duplicate
#: launch, which exits silently either way.
GUI_CLAIM_WAIT_S = 3.0

#: Poll interval while waiting for the GUI claim.
_GUI_CLAIM_POLL_S = 0.05


def claim_gui(timeout=GUI_CLAIM_WAIT_S) -> InstanceClaim:
    """Claim the right to be the one tray icon, or raise :class:`EndpointBusy`.

    Under daemon-by-default a GUI never owns the endpoint — it is a client — so
    the endpoint lock cannot keep a second tray from appearing. The gap it
    leaves is real: the daemon spawn is deferred until after the PyQt imports
    load, ~9 s on a cold first start, and for that whole window
    ``probe_existing`` answers STALE, so every GUI launched inside it also
    decides to spawn a daemon and also shows a tray. A first-time macOS install
    hit it with two launches 691 ms apart and came up with two icons
    (2026-09-19).

    Held for the life of the tray process, and taken BEFORE the spawn decision
    rather than around it, so a second launch settles at once instead of waiting
    out the window. ``--connect`` does not take it: an extra client GUI against
    a running core is an explicit, supported thing to ask for."""
    path = protocol.gui_lock_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    # Same ownership rule as claim_instance: the claim takes the descriptor
    # straight away, so every exit closes it. This one waits, so an interrupt
    # landing in the sleep is one more way out of the loop.
    claim = InstanceClaim(fd, path)
    deadline = time.monotonic() + max(0.0, timeout)
    try:
        while not filelock.try_lock(fd):
            if time.monotonic() >= deadline:
                raise EndpointBusy(LOCKED)
            time.sleep(_GUI_CLAIM_POLL_S)
    except BaseException:
        claim.release()
        raise
    return claim


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
    # Hand the descriptor to the claim immediately, so every exit path from
    # here on closes it. Taking the lock first would leak the descriptor for
    # the life of the process if anything between the open and the assignment
    # raised.
    claim = InstanceClaim(fd, path)
    try:
        if not filelock.try_lock(fd):
            # Someone holds the lock. They may not have bound the endpoint yet,
            # so the probe is the better answer when it has one — LOCKED
            # otherwise.
            outcome = probe_existing(address, authkey)
            raise EndpointBusy(LOCKED if outcome == STALE else outcome)
        outcome = probe_existing(address, authkey)
        if outcome != STALE:
            raise EndpointBusy(outcome)
        clear_stale_endpoint(address)
    except BaseException:
        claim.release()
        raise
    return claim
