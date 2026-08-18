"""The one ``subscribe``/``emit`` observer seam the two cores share.

:class:`~polyhost.core.poly_core.PolyCore` (in-process) and
:class:`~polyhost.client.remote_core.RemoteCore` (socket-backed) both publish
results the same way — a list of ``callable(name, payload)`` observers, fired on
whatever thread produced the event — and both carried their own identical copy
of the plumbing.

Two details make it worth having exactly one implementation rather than two:

* **``emit`` snapshots under the lock and fires outside it.** Observers are Qt
  slots, control-socket fan-outs and test probes; calling them while holding the
  lock would let an observer that subscribes another one deadlock the core, and
  would serialize the whole event stream behind the slowest consumer.
* **A raising observer is caught, logged and left subscribed.** The emitting
  side is a core/worker thread — the reconnect probe, a flash job — so an
  exception escaping here does not "fail an event", it kills the thread that
  owns the device. One broken client must never take the core with it.

Qt-free and dependency-free by construction: ``PolyCore`` must stay importable
without PyQt5 (``tests/core/import_guard_test.py``), and ``RemoteCore`` speaks
only the stdlib protocol.
"""
import threading


class Observable:
    """Mixin providing the ``subscribe`` / ``emit`` observer contract.

    ``log`` only needs an ``exception(fmt, *args)`` method. Subclasses that build
    themselves without calling ``__init__`` (the ``__new__`` + attribute-set
    pattern the core tests use) can initialise the seam with
    ``Observable.__init__(self, log)``.
    """

    def __init__(self, log):
        self.log = log
        self._observers = []
        self._observers_lock = threading.Lock()

    def subscribe(self, callback):
        """Register ``callable(name, payload)``; fired on core/worker threads."""
        with self._observers_lock:
            self._observers.append(callback)

    def emit(self, name, payload):
        """Publish an event to every observer, isolating each from the others."""
        with self._observers_lock:
            observers = list(self._observers)
        for cb in observers:
            try:
                cb(name, payload)
            except Exception:  # one broken client must not break the core
                self.log.exception("Event observer failed for %r", name)
