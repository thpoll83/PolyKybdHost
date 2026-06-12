"""Qt bridge between the HID worker thread and the GUI main thread.

The worker runs ``on_done`` callbacks on its own thread (see
``polyhost/device/hid_worker.py``); those callbacks must never touch Qt
objects directly. Instead they emit :class:`WorkerBridge.job_done`, a queued
signal that Qt delivers on the main thread, where the host dispatches on the
job name.

The reconnect decision logic lives in the Qt-free
``polyhost.core.decisions`` (it is consumed by the headless core);
re-exported here for compatibility with existing imports/tests.
"""
from PyQt5.QtCore import QObject, pyqtSignal

# Re-export: established import location for the pure decision helpers.
from polyhost.core.decisions import decide_probe_publish, decide_reconnect_apply  # noqa: F401


class WorkerBridge(QObject):
    """Carries worker-thread ``on_done`` results onto the Qt main thread."""

    # (job name, result) — result is fn's return value or the raised exception.
    job_done = pyqtSignal(str, object)
