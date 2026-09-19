"""Cross-process advisory file lock (``flock`` on POSIX, ``msvcrt`` on Windows).

An OS lock, not a pid file: the kernel drops it when the holder dies however it
dies, so a crash can never leave the guarded resource permanently locked.

Shared rather than written twice. There are two callers — the control
endpoint's instance claim (:mod:`polyhost.server.instance`) and the settings
read-merge-write (:mod:`polyhost.settings`) — and a hand-written second copy is
exactly how this repo's plumbing has drifted before.

Qt-free and stdlib-only, so it stays importable from the Qt-free core and from
settings, which is read before logging is even configured.
"""
import contextlib
import os
import sys
import time

#: Poll interval while waiting for a contended lock.
POLL_S = 0.02


def try_lock(fd) -> bool:
    """Take an exclusive, non-blocking lock on ``fd``. False if held elsewhere."""
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


def unlock(fd) -> None:
    """Release a lock taken with :func:`try_lock`. Never raises.

    Best effort: closing the descriptor drops the lock regardless, and on
    Windows unlocking a region that was never locked raises by design."""
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


@contextlib.contextmanager
def exclusive(path, timeout=2.0):
    """Hold an exclusive lock on ``path`` for the block. Yields whether it was taken.

    Deliberately BEST EFFORT — it yields False rather than raising when the
    lock cannot be taken in time, because every caller has work that matters
    more than the lock. Losing a settings save to a wedged lock holder is worse
    than the rare interleaving the lock exists to prevent.

    The lock file is never unlinked: removing it would race another process
    that already has it open, and an empty file costs nothing."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        # Can't even create the lock file (read-only dir, exhausted handles).
        # The caller's work still has to happen.
        yield False
        return
    try:
        deadline = time.monotonic() + max(0.0, timeout)
        locked = try_lock(fd)
        while not locked and time.monotonic() < deadline:
            time.sleep(POLL_S)
            locked = try_lock(fd)
        try:
            yield locked
        finally:
            if locked:
                unlock(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            # Already closed, or the interpreter is tearing down. The lock is
            # gone either way.
            pass
