"""Headless mode (headless-core plan, H3 / M2).

``python -m polyhost --headless`` runs the operational core + the control
socket with **no Qt import anywhere** in the process — for machines without
a display, or SSH/service use. Drive it with ``polyctl`` (or any client
speaking ``polyhost.server.protocol``).

This module must never import PyQt5 (guarded by
``tests/core/import_guard_test.py`` and ``tests/headless/*``). It owns the
same operational pieces as the GUI client, minus the GUI:

- a :class:`~polyhost.core.poly_core.PolyCore` (device stack, worker,
  periodics, reconnect),
- a :class:`~polyhost.server.control_server.ControlServer` on the same
  control socket the tray app uses (so ``polyctl`` is identical either way),
- the active-window tick on the **core's own thread** (the GUI uses a
  main-thread QTimer instead; here there is no main loop).
"""
import logging
import threading

from polyhost._version import __version__
from polyhost.core.poly_core import PolyCore
from polyhost.server.control_server import ControlServer


class HeadlessHost:
    """Qt-free host: core + control server + core-owned window tick."""

    def __init__(self, log, ignore_version=False):
        self.log = log
        self._stop = threading.Event()
        self.core = PolyCore(log=log, ignore_version=ignore_version,
                             start_worker=False, apply_reconnect_in_core=True)
        self.control_server = ControlServer(
            self.core, __version__, log, on_shutdown=self.request_stop)

    def start(self):
        self.core.worker.start()
        # Core-owned active-window tracking (no-op without a display).
        self.core.start_window_tracking()
        self.control_server.start()
        self.log.info("PolyKybdHost running headless. Drive it with `polyctl`.")

    def request_stop(self):
        """Signal the run loop to exit (called from a server thread)."""
        self._stop.set()

    def stop(self):
        # Stop accepting clients first, then the operational shutdown.
        try:
            self.control_server.stop()
        finally:
            self.core.shutdown()

    def run(self):
        """Start and block until a shutdown is requested (or KeyboardInterrupt)."""
        self.start()
        try:
            while not self._stop.wait(0.5):
                pass
        except KeyboardInterrupt:
            self.log.info("Interrupted — shutting down.")
        finally:
            self.stop()


def run_headless(log_level=logging.INFO, ignore_version=False):
    """Entry point for ``--headless`` (see polyhost/main_app.py)."""
    logging.basicConfig(level=log_level)
    log = logging.getLogger("PolyHost")
    host = HeadlessHost(log, ignore_version=ignore_version)
    host.run()
