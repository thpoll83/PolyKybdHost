"""Single-consumer HID worker thread.

The heart of the HID worker / command-queue refactor (see
``docs/hid-worker-refactor.md``). A dedicated daemon thread owns the device;
callers enqueue :class:`Job` objects via :meth:`HidWorker.submit` (fire and
forget) or :meth:`HidWorker.run_sync` (block for the result). Stale jobs are
superseded via *coalescing*. Periodic tasks run between jobs on the worker
thread. Firmware flashing gets exclusive access via :meth:`HidWorker.exclusive`.

Pure Python — no Qt. Callers bridge ``on_done`` (invoked on the worker thread)
to Qt signals themselves.
"""
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager

# 'PolyHost' is the repo-wide logger name convention.
_DEFAULT_LOG = logging.getLogger("PolyHost")

# How long the worker blocks waiting for a job before re-checking periodic
# tasks / suspend state. Bounds periodic-task scheduling granularity.
_POLL_GRANULARITY_S = 0.1


class Job:
    """A unit of work to run on the worker thread.

    ``fn`` receives the job's :attr:`cancel` event and should abort ASAP when
    it is set. After ``fn`` returns or raises, :attr:`done` is set and
    :attr:`result` holds the return value (or the raised exception object).
    """

    def __init__(self, name, fn, coalesce_key=None, on_done=None):
        self.name = name
        self.fn = fn
        self.coalesce_key = coalesce_key
        self.on_done = on_done
        self.cancel = threading.Event()
        self.done = threading.Event()
        self.result = None

    def __repr__(self):
        return f"<Job {self.name!r} key={self.coalesce_key!r}>"


class _Periodic:
    """Bookkeeping for a periodic task registered via add_periodic()."""

    def __init__(self, name, interval_s, fn):
        self.name = name
        self.interval_s = interval_s
        self.fn = fn
        self.next_due = time.monotonic()
        self.cancel = threading.Event()


class HidWorker:
    """FIFO single-consumer worker thread with coalescing and periodic tasks."""

    def __init__(self, log=None):
        self._log = log or _DEFAULT_LOG
        self._cond = threading.Condition()
        self._queue = deque()           # of Job
        self._periodics = []            # of _Periodic (guarded by _cond)
        self._inflight = None           # Job currently running (guarded by _cond)
        self._suspended = False         # guarded by _cond
        self._stopping = False          # guarded by _cond
        self._started = False
        self._thread = None

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def start(self):
        """Spawn the daemon worker thread. Not restartable after stop()."""
        if self._started:
            raise RuntimeError("HidWorker already started (cannot restart after stop)")
        self._started = True
        self._thread = threading.Thread(
            target=self._run, name="HidWorker", daemon=True)
        self._thread.start()

    def stop(self, timeout=5.0):
        """Cancel in-flight + queued jobs, wake the thread and join it.

        Idempotent. After stop() the worker cannot be restarted — create a new
        instance instead.
        """
        with self._cond:
            if self._stopping:
                thread = self._thread
            else:
                self._stopping = True
                if self._inflight is not None:
                    self._inflight.cancel.set()
                # Drop queued jobs: signal their events but do NOT call on_done.
                while self._queue:
                    job = self._queue.popleft()
                    job.cancel.set()
                    job.done.set()
                for p in self._periodics:
                    p.cancel.set()
                thread = self._thread
                self._cond.notify_all()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)

    # ------------------------------------------------------------------ #
    # submission
    # ------------------------------------------------------------------ #
    def submit(self, name, fn, coalesce_key=None, on_done=None, front=False):
        """Enqueue a job. Returns the :class:`Job`.

        ``front=True`` inserts at the head of the queue (used by run_sync).
        If ``coalesce_key`` is set, queued jobs with the same key are dropped
        (their cancel + done events are set, on_done is NOT called) and the
        in-flight job with the same key has its cancel event set; the new job
        still takes its normal place in the queue.
        """
        job = Job(name, fn, coalesce_key=coalesce_key, on_done=on_done)
        with self._cond:
            if self._stopping:
                # Worker is shutting down: never run, just signal completion.
                job.cancel.set()
                job.done.set()
                return job
            if coalesce_key is not None:
                self._coalesce_locked(coalesce_key)
            if front:
                self._queue.appendleft(job)
            else:
                self._queue.append(job)
            self._cond.notify_all()
        return job

    def _coalesce_locked(self, key):
        """Drop queued jobs with this key; cancel the in-flight one. Caller holds _cond."""
        survivors = deque()
        for job in self._queue:
            if job.coalesce_key == key:
                job.cancel.set()
                job.done.set()  # on_done deliberately NOT called for dropped jobs
            else:
                survivors.append(job)
        self._queue = survivors
        if self._inflight is not None and self._inflight.coalesce_key == key:
            self._inflight.cancel.set()

    def run_sync(self, name, fn, timeout=None):
        """Submit at the head of the queue and block until done.

        Returns fn's value; re-raises fn's exception in the caller; raises
        TimeoutError on timeout (and sets the job's cancel event); raises
        RuntimeError immediately if the worker is suspended.
        """
        with self._cond:
            if self._suspended:
                raise RuntimeError("HidWorker is suspended; run_sync would deadlock")
            if self._stopping:
                raise RuntimeError("HidWorker is stopping; cannot run_sync")
        job = self.submit(name, fn, coalesce_key=None, on_done=None, front=True)
        if not job.done.wait(timeout):
            job.cancel.set()
            raise TimeoutError(f"run_sync({name!r}) timed out after {timeout}s")
        if isinstance(job.result, BaseException):
            raise job.result
        return job.result

    # ------------------------------------------------------------------ #
    # periodic tasks
    # ------------------------------------------------------------------ #
    def add_periodic(self, name, interval_s, fn):
        """Register a periodic task to run on the worker thread when due.

        ``fn`` receives a cancel event (set on stop/suspend). The task is
        checked between jobs (<= 100 ms granularity), runs at most once per
        check even when overdue (no catch-up bursts), is not run while
        suspended, and keeps its schedule if it raises (the error is logged).
        """
        p = _Periodic(name, interval_s, fn)
        with self._cond:
            self._periodics.append(p)
            self._cond.notify_all()
        return p

    # ------------------------------------------------------------------ #
    # suspend / resume / exclusive
    # ------------------------------------------------------------------ #
    def suspend(self):
        """Stop running queued jobs and periodics; cancel the in-flight job.

        Submitted jobs keep queuing for later. Does not wait for the in-flight
        job to finish — use exclusive() for that.
        """
        with self._cond:
            self._suspended = True
            if self._inflight is not None:
                self._inflight.cancel.set()
            # Periodic fns receive a cancel event "set on stop/suspend" so a
            # long-running one (e.g. an overlay resend) aborts when a fw flash
            # takes over. resume() clears it again.
            for p in self._periodics:
                p.cancel.set()
            self._cond.notify_all()

    def resume(self):
        with self._cond:
            self._suspended = False
            for p in self._periodics:
                p.cancel.clear()
            self._cond.notify_all()

    def _wait_inflight_idle(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while self._inflight is not None:
                remaining = None
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                self._cond.wait(remaining)
            return True

    @contextmanager
    def exclusive(self):
        """Context manager granting exclusive device access.

        Suspends the worker, cancels the in-flight job and waits for it to
        finish, yields, then resumes on exit (even on error). While suspended,
        submit() still queues jobs for after resume.
        """
        self.suspend()
        try:
            self._wait_inflight_idle()
            yield
        finally:
            self.resume()

    # ------------------------------------------------------------------ #
    # worker thread
    # ------------------------------------------------------------------ #
    def _run(self):
        while True:
            job = None
            with self._cond:
                if self._stopping:
                    return
                if not self._suspended and self._queue:
                    job = self._queue.popleft()
                    self._inflight = job
                else:
                    # Nothing to run now: compute how long we may sleep before
                    # the next periodic is due, then wait (interruptible).
                    timeout = self._next_wait_locked()
                    self._cond.wait(timeout)
            if job is not None:
                self._execute(job)
                with self._cond:
                    self._inflight = None
                    self._cond.notify_all()
            else:
                self._run_due_periodics()

    def _next_wait_locked(self):
        """Seconds to wait before the next wakeup. Caller holds _cond."""
        if self._suspended or not self._periodics:
            return _POLL_GRANULARITY_S
        now = time.monotonic()
        soonest = min(p.next_due for p in self._periodics)
        return max(0.0, min(_POLL_GRANULARITY_S, soonest - now))

    def _execute(self, job):
        try:
            job.result = job.fn(job.cancel)
        except BaseException as exc:  # never let a job kill the worker
            self._log.exception("HID job %r raised", job.name)
            job.result = exc
        job.done.set()
        if job.on_done is not None:
            try:
                job.on_done(job.name, job.result)
            except BaseException:  # on_done must not kill the worker either
                self._log.exception("HID job %r on_done raised", job.name)

    def _run_due_periodics(self):
        now = time.monotonic()
        with self._cond:
            if self._suspended or self._stopping:
                return
            due = [p for p in self._periodics if p.next_due <= now]
        for p in due:
            with self._cond:
                # Re-check: state may have changed while running a sibling.
                if self._suspended or self._stopping:
                    return
            try:
                p.fn(p.cancel)
            except BaseException:
                self._log.exception("HID periodic %r raised", p.name)
            # Reschedule from now: an overdue task runs once, no catch-up burst.
            p.next_due = time.monotonic() + p.interval_s
