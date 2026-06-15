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
        self._stopped = False
        # Set when a self-update lands so run() re-execs into the new version
        # after a clean stop (there is no GUI prompt to drive the restart).
        self._restart_after_stop = False
        self._relay_path = None
        self.core = PolyCore(log=log, ignore_version=ignore_version,
                             start_worker=False, apply_reconnect_in_core=True)
        # React to a core-driven self-update (`polyctl update install`): the
        # core only applies + emits; the host owns the restart.
        self.core.subscribe(self._on_update_event)
        # Persist the keyboard console (uprintf output: "Stop idle." etc.) to
        # its own file, like the GUI does — the daemon owns the device, so it's
        # the right writer. The handler is installed by run_headless; here we
        # just log to the named logger when a `console` event arrives.
        self.keeb_log = logging.getLogger("PolyKybdConsole")
        self.keeb_log.setLevel(logging.INFO)
        self.core.subscribe(self._on_console_event)
        self.control_server = ControlServer(
            self.core, __version__, log, on_shutdown=self.request_stop)
        # Optional network window-report listener (H4d) — opt-in, off by
        # default. Serves ONLY `window.report` (auth + version gated) so a
        # remote forwarder can push the active window over an authenticated
        # connection instead of the plaintext TCP relay. Built in start() so a
        # bind failure can't break construction; never exposes device control.
        self._winreport_server = None

    def _on_console_event(self, name, payload):
        """Mirror the GUI: route the keyboard's console output to its log file.
        Fires on the core/worker thread (logging is thread-safe)."""
        if name != "console":
            return
        kb_serial, kb_log = payload
        if kb_serial:
            self.log.info("Received serial communication: %s", kb_serial)
        if kb_log:
            self.keeb_log.info(kb_log)

    def _on_update_event(self, name, payload):
        """Restart (or hand off to the Windows relay) once an update applies.
        Fires on the installer thread — just flag + request stop; run()'s
        finally does the actual re-exec after server/core are down."""
        if name == "update_finished_ok":
            self.log.info("Self-update applied; restarting headless host.")
            self._restart_after_stop = True
            self.request_stop()
        elif name == "update_relay_needed":
            self._relay_path = (payload or {}).get("relay_path")
            self._restart_after_stop = True
            self.request_stop()

    def start(self):
        self.core.worker.start()
        # Core-owned active-window tracking (no-op without a display).
        self.core.start_window_tracking()
        self.control_server.start()
        self._maybe_start_window_report_server()
        self.log.info("PolyKybdHost running headless. Drive it with `polyctl`.")

    def _maybe_start_window_report_server(self):
        """Start the opt-in network window-report listener if enabled."""
        try:
            enabled = bool(self.core.settings_get("window_report_network_enabled"))
        except Exception:
            enabled = False
        if not enabled:
            return
        from polyhost.server.window_report_server import WindowReportServer
        try:
            self._winreport_server = WindowReportServer(
                self.core.report_window, __version__, self.log)
            self._winreport_server.start()
        except Exception:
            self.log.exception("Could not start the window-report network listener")
            self._winreport_server = None

    def request_stop(self):
        """Signal the run loop to exit (called from a server thread)."""
        self._stop.set()

    def stop(self):
        # Idempotent: run() calls this in its finally, but a signal handler or
        # test may call it too. Stop accepting clients first, then the
        # operational shutdown.
        if self._stopped:
            return
        self._stopped = True
        try:
            if self._winreport_server is not None:
                try:
                    self._winreport_server.stop()
                except Exception:
                    pass
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
            self._restart_if_requested()

    def _restart_if_requested(self):
        """Re-exec into the freshly-installed version (or launch the Windows
        locked-file relay, which relaunches us). No-op unless a self-update
        completed."""
        if not self._restart_after_stop:
            return
        from polyhost.services import updater
        if self._relay_path:
            import subprocess
            import sys
            # The relay waits for this process to exit, copies the locked files,
            # then relaunches — so we just spawn it and let run() return.
            subprocess.Popen([sys.executable, self._relay_path], close_fds=False)
            return
        updater.restart_app()


def run_headless(log_level=logging.INFO, ignore_version=False):
    """Entry point for ``--headless`` (see polyhost/main_app.py).

    Logs to a rotating ``daemon_log.txt`` **and** to the stream. The file
    matters because a GUI-spawned daemon (daemon-by-default, H4b) runs detached
    with its stdio sent to DEVNULL — without a file its logs would be lost. The
    stream handler keeps a manual ``--headless`` run in a terminal readable. The
    daemon uses its own filename (the GUI writes ``host_log.txt``) so a
    co-located daemon + ``--connect`` GUI never write the same log file. Both
    handlers get the repeat-collapse wrapper so the reconnect-probe spam while
    the keyboard is in the bootloader doesn't flood the file."""
    from logging.handlers import RotatingFileHandler
    from polyhost.util.log_util import (
        make_stream_handler, make_collapse_handler, MultiLineFormatter)

    fmt = "[%(asctime)s] %(levelname)-7s %(message)s"
    file_handler = RotatingFileHandler(
        filename="daemon_log.txt", maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt))
    logging.basicConfig(level=log_level, handlers=[
        make_collapse_handler(file_handler),
        make_collapse_handler(make_stream_handler(fmt)),
    ])

    # The keyboard console gets its own file (matching the GUI's
    # polykybd_console.txt), fed by HeadlessHost's `console` subscription. The
    # daemon is the device owner, so it's the writer; a co-located --connect GUI
    # only reads this file in its log viewer (its own console handler is a
    # NullHandler — see host.py).
    keeb_log = logging.getLogger("PolyKybdConsole")
    keeb_log.setLevel(logging.INFO)
    keeb_handler = RotatingFileHandler(
        filename="polykybd_console.txt", maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8")
    keeb_handler.setFormatter(MultiLineFormatter(fmt="[%(asctime)s] %(message)s"))
    keeb_log.addHandler(keeb_handler)
    keeb_log.propagate = False

    log = logging.getLogger("PolyHost")
    log.info("PolyKybdHost %s running headless.", __version__)
    host = HeadlessHost(log, ignore_version=ignore_version)
    host.run()
