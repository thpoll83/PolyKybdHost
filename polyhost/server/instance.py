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
        pass            # already gone -- nothing to clean up
    except OSError:
        pass            # a socket we cannot remove must not stop startup:
                        # refusing to launch over a filesystem fault leaves the
                        # user with no app at all. Fail OPEN, as acquire does.


# --------------------------------------------------------------- OS file lock

FORWARDER_LOCK = "forwarder"

# ⚠️ THE RETURNED HANDLE IS THE LOCK. Both `fcntl.flock` and `msvcrt.locking`
# release when the descriptor closes, so a caller that does not KEEP a
# reference has its lock collected out from under it at the next gc and a
# second instance starts with nothing to notice. Store it on the app object.


def _lock_path(name: str) -> str:
    return os.path.join(protocol._config_dir(), f"{name}.lock")


def acquire_singleton(name: str, log=None):
    """Take an exclusive OS lock for `name`. Returns the handle, or None.

    None means **another live process holds it**. Anything else -- the
    directory is unwritable, the platform has no locking primitive -- returns a
    handle so the caller starts anyway: a second forwarder is a degradation,
    while refusing to launch over an unrelated filesystem fault leaves the user
    with no forwarder at all. It never raises.

    ⚠️ The lock is held by the OS, NOT by a file's existence, which is what
    makes this different from `probe_existing` above and why it needs no
    `clear_stale_endpoint` sibling: a crashed or SIGKILLed process releases it
    when the kernel closes its descriptors, so there is no stale state to
    detect and no window in which a dead holder blocks a live launch.
    """
    try:
        os.makedirs(protocol._config_dir(), exist_ok=True)
        handle = open(_lock_path(name), "a+")
    except OSError as e:
        if log is not None:
            log.debug("single-instance lock unavailable (%s) — starting anyway", e)
        return _UNLOCKED

    try:
        if sys.platform == "win32":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Held by someone. Read their pid for the log, then give up the handle.
        # ⚠️ Read BEFORE closing: closing is what releases our own attempt.
        holder = ""
        try:
            handle.seek(0)
            holder = handle.read(32).strip()
        except OSError:
            pass        # the pid is for the LOG LINE only. A failed read costs
                        # a less informative message, never the refusal itself.
        # ⚠️ Explicit, though dropping it is INERT under CPython -- `handle` is
        # the last reference and refcounting closes the file at function exit,
        # so a mutation deleting this line cannot be caught by any test here
        # (measured: 5 refused calls leak no descriptor without it). It stays
        # because that is an implementation detail of the interpreter, not of
        # this function, and because a later edit that retains the handle would
        # make the leak real with nothing to notice.
        _close(handle)
        if log is not None:
            who = f" (pid {holder})" if holder.isdigit() else ""
            log.warning("Another PolyKybd forwarder is already running%s — "
                        "this one is exiting. Two forwarders report every window "
                        "change twice and only one can hold the browser-report "
                        "port.", who)
        return None
    except Exception as e:  # noqa: BLE001 - no locking primitive: start anyway
        if log is not None:
            log.debug("single-instance lock not supported (%s) — starting anyway", e)
        return handle

    try:
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
    except OSError:
        pass            # the pid is a convenience for the log, not the lock
    return handle


def _close(handle) -> None:
    try:
        handle.close()
    except OSError:
        pass            # releasing on the way out; there is nothing to recover
                        # to, and raising here would mask the real exit reason.


class _Unlocked:
    """Stand-in handle for 'we could not lock, and started regardless'.

    A real file object would be wrong here -- it carries no lock, so releasing
    it means nothing -- but returning None is worse still, since None is the
    caller's signal to EXIT. Hence a distinct truthy object.
    """

    def close(self) -> None:
        return None


_UNLOCKED = _Unlocked()
