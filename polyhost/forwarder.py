import logging
from logging.handlers import RotatingFileHandler
import os
import ipaddress
import webbrowser
import socket
import sys
import time


import subprocess

from PyQt5.QtCore import QTimer, Qt, QObject, pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QMessageBox,
    QProgressDialog)
from polyhost._version import __version__
from polyhost.gui.get_icon import get_icon
from polyhost.gui.icon_state_manager import IconStateManager
from polyhost.gui.log_viewer import LogViewerDialog
from polyhost.handler.remote_window import TCP_PORT


IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"
_IS_WAYLAND = os.getenv("XDG_SESSION_TYPE") == "wayland"

if IS_PLASMA:
    import polyhost.handler.kde_win_reporter as pwc
elif _IS_WAYLAND:
    # pywinctl can't see native Wayland windows; use the GNOME Shell extension
    # reporter (untested — needs the 'Window Calls' extension). X11 is unaffected.
    import polyhost.handler.gnome_wayland_reporter as pwc
else:
    import pywinctl as pwc

UPDATE_CYCLE_MSEC = 250
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000
HEARTBEAT_MSEC = 15000  # resend current window state periodically so the host can catch up

from polyhost.util.log_util import DEBUG_DETAILED, make_stream_handler, make_collapse_handler  # noqa: F401  (registers debug_detailed on import)
from polyhost.handler.active_window import log_env_info

class _UpdateBridge(QObject):
    """Marshals the updater threads' callbacks (which fire off the Qt thread) back
    onto the Qt main thread via queued signals — the forwarder has no WorkerBridge."""
    available = pyqtSignal(object)
    no_update = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal()
    relay_needed = pyqtSignal(str)
    failed = pyqtSignal(str)


class PolyForwarder(QApplication):
    def __init__(self, log_level, host=None, host_file=None,
                 report_rpc=False, report_port=None, report_authkey_file=None):
        super().__init__(sys.argv)
        # Tray-only app: keep it out of the macOS Dock (no-op elsewhere).
        from polyhost.util.macos_ui import hide_dock_icon
        hide_dock_icon()
        self.host = host
        self.host_file = os.path.expanduser(host_file) if host_file else None

        # H4d: optionally push the active window over the authenticated network
        # window-report endpoint instead of the plaintext TCP relay. ⚠️ The RPC
        # transport is unit-tested but UNTESTED on hardware / cross-machine; the
        # default (report_rpc False) keeps the proven TCP path untouched.
        self._report_rpc = report_rpc
        self._report_port = report_port
        self._report_client = None
        self._report_authkey = None

        # This machine's OS, forwarded alongside the active window so the keyboard
        # reflects the OS of the computer you are working on (not just the one it is
        # plugged into). Constant for the process lifetime. An OsType value int.
        from polyhost.input.unicode_input import get_host_os
        self._os_value = get_host_os().value

        fmt = "[%(asctime)s] %(levelname)-7s {%(filename)s:%(lineno)d} - %(message)s"
        file_handler = RotatingFileHandler(
            filename="forwarder_log.txt",
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(fmt))
        logging.basicConfig(level=log_level, handlers=[
            make_collapse_handler(file_handler),
            make_collapse_handler(make_stream_handler(fmt)),
        ])
        self.log = logging.getLogger("PolyForwarder")
        log_env_info(self.log)

        if self._report_rpc:
            from polyhost.server import protocol as _proto
            if report_authkey_file:
                try:
                    with open(report_authkey_file, "rb") as f:
                        self._report_authkey = f.read().strip()
                except OSError as e:
                    self.log.error("Could not read report authkey file %s: %s",
                                   report_authkey_file, e)
            if not self._report_authkey:
                self._report_authkey = _proto.load_or_create_authkey(
                    _proto.window_report_authkey_path())
                self.log.warning(
                    "Using this machine's local window-report authkey; for a "
                    "different keyboard machine pass --report-authkey-file with "
                    "its polykybd-winreport.authkey.")
            self.log.info("Forwarder using the authenticated window-report endpoint (H4d).")

        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.icon_manager = IconStateManager(self, False, f"({__version__}) Forwarding to {host}")
        self.tray.setVisible(True)
        
        self.setQuitOnLastWindowClosed(False)
        self.win = None
        self.prev_win = None
        self.is_closing = False
        self.title = None
        self.last_update_msec = 0

        self.heartbeat_msec = 0

        self.tray.show()
        self.set_style()

        self.menu = QMenu()

        self.exit = QAction(get_icon("power.svg"), "Quit", parent=self)
        # noinspection PyUnresolvedReferences
        self.exit.triggered.connect(self.quit_app)
        self.support = QAction(get_icon("support.svg"), "Get Support", parent=self)
        # noinspection PyUnresolvedReferences
        self.support.triggered.connect(self.open_support)
        self.about = QAction(get_icon("home.svg"), "About", parent=self)
        # noinspection PyUnresolvedReferences
        self.about.triggered.connect(self.open_about)

        self.log_dialog = QAction(get_icon("log.svg"), "Log file...", parent=self)
        # noinspection PyUnresolvedReferences
        self.log_dialog.triggered.connect(self.open_log)
        self.log_viewer = None

        self.update_action = QAction(get_icon("sync.svg"), "Check for updates...", parent=self)
        # noinspection PyUnresolvedReferences
        self.update_action.triggered.connect(self._on_update_clicked)

        # Update plumbing (host-app update only — the forwarder has no device).
        self._update_bridge = _UpdateBridge()
        self._update_bridge.available.connect(self._on_update_available)
        self._update_bridge.no_update.connect(self._on_no_update)
        self._update_bridge.error.connect(self._on_check_error)
        self._update_bridge.progress.connect(self._on_update_progress)
        self._update_bridge.finished_ok.connect(self._on_update_done)
        self._update_bridge.relay_needed.connect(self._on_relay_needed)
        self._update_bridge.failed.connect(self._on_update_failed)
        self._update_checker = None
        self._update_installer = None
        self._update_progress = None

        self.menu.addAction(self.log_dialog)
        self.menu.addAction(self.update_action)
        self.menu.addAction(self.support)
        self.menu.addAction(self.about)
        self.menu.addAction(self.exit)
        
        self.tray.setContextMenu(self.menu)

        self.icon_manager.set_connected()
        
        QTimer.singleShot(1000, self.active_window_reporter)

    def set_style(self):
        self.setStyle("Fusion")
        # Now use a palette to switch to dark colors:
        palette = QPalette()
        base_color = QColor(35, 35, 35)
        window_base_color = QColor(80, 80, 80)
        text_color = QColor(200, 200, 200)
        highlight_text_color = QColor(255, 255, 255)
        palette.setColor(QPalette.Window, window_base_color)
        palette.setColor(QPalette.WindowText, text_color)
        palette.setColor(QPalette.Base, base_color)
        palette.setColor(QPalette.AlternateBase, window_base_color)
        palette.setColor(QPalette.ToolTipBase, base_color)
        palette.setColor(QPalette.ToolTipText, text_color)
        palette.setColor(QPalette.Text,text_color)
        palette.setColor(QPalette.Button, window_base_color)
        palette.setColor(QPalette.ButtonText, text_color)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, highlight_text_color)
        self.setPalette(palette)
        
    def _resolve_host(self):
        """Return the target host string (from --host or the host-file), or None."""
        host = self.host
        if self.host_file:
            try:
                with open(self.host_file) as f:
                    host = f.read().strip()
            except OSError:
                return None  # file absent means no active session
        return host or None

    def _send_via_rpc(self, handle, title, name):
        """Push the active window over the authenticated window-report endpoint
        (H4d). Keeps a persistent connection, reconnecting on any failure."""
        host = self._resolve_host()
        if not host:
            return False
        try:
            if self._report_client is None:
                from polyhost.server.window_report_client import connect
                self._report_client = connect(
                    host, self._report_port, self._report_authkey)
            self._report_client.report(handle, name, title, os=self._os_value)
            return True
        except Exception as e:
            self.log.error("Window-report RPC to %s failed: %s", host, e)
            if self._report_client is not None:
                self._report_client.close()
                self._report_client = None
            return False

    def send_to_host(self, handle, title, name):
        if self._report_rpc:
            return self._send_via_rpc(handle, title, name)
        host = self._resolve_host()
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = socket.gethostbyname(host)
        except OSError as err:
            self.log.error("Could not resolve %s: %s", host, err)
            return False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((str(ip), TCP_PORT))
            # 4th field = this machine's OS (an OsType value int); older daemons
            # split on ';' and read the first three fields, ignoring the extra one.
            s.send(f"{handle};{name};{title};{self._os_value}".encode("utf-8"))
            s.close()
            return True
        except socket.timeout as err:
            self.log.error("Connection timed out: %s",err)
        except ConnectionRefusedError as err:
            self.log.error("Connection refused: %s", err)
        except ConnectionAbortedError as err:
            self.log.error("Connection aborted: %s", err)
        except ConnectionResetError as err:
            self.log.error("Connection reset: %s", err)
        except ConnectionError as err:
            self.log.error("Connection error: %s", err)
        return False

    def open_log(self):
        # assignment is needed otherwise the dialog would go away immediately
        delta = time.perf_counter()
        self.log_viewer = LogViewerDialog({"Forwarder Log": "forwarder_log.txt"})
        self.log_viewer.show()
        delta = time.perf_counter() - delta
        self.log.info("Opened log dialog in '%f' sec", delta)
        
    @staticmethod
    def open_support():
        webbrowser.open("https://discord.gg/gW8JescH7M", new=0, autoraise=True)

    @staticmethod
    def open_about():
        webbrowser.open("https://ko-fi.com/polykb", new=0, autoraise=True)
        
    # ------------------------------------------------------------------
    # Host-app update (mirrors the tray app's flow, host-only — no firmware,
    # since the forwarder has no device). Threads marshal back via _update_bridge.
    # ------------------------------------------------------------------
    def _on_update_clicked(self):
        from polyhost.services.updater import UpdateChecker
        if self._update_installer is not None and self._update_installer.is_alive():
            return
        if self._update_checker is not None and self._update_checker.is_alive():
            return
        self.update_action.setText("Checking for updates...")
        ub = self._update_bridge
        self._update_checker = UpdateChecker(
            current_fw_version=None,   # host-only: the forwarder owns no keyboard
            on_update_available=lambda rel: ub.available.emit(rel),
            on_host_no_update=lambda: ub.no_update.emit(),
            on_error=lambda msg: ub.error.emit(msg),
        )
        self._update_checker.start()

    def _on_update_available(self, release):
        self.update_action.setText("Check for updates...")
        if QMessageBox.question(
                None, "Update PolyKybdHost",
                f"Version {release.version} is available.\n\n"
                "Download, install, and restart the forwarder now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) != QMessageBox.Yes:
            return
        self._run_update_installer(release)

    def _on_no_update(self):
        self.update_action.setText("Check for updates...")
        QMessageBox.information(
            None, "PolyKybdHost Update",
            f"You are running the latest version (v{__version__}).")

    def _on_check_error(self, msg):
        self.update_action.setText("Check for updates...")
        QMessageBox.warning(
            None, "PolyKybdHost Update",
            f"Could not check for updates:\n\n{msg}\n\nRun with --debug 1 for details.")

    def _run_update_installer(self, release):
        from polyhost.services.updater import UpdateInstaller
        if self._update_installer is not None and self._update_installer.is_alive():
            return
        self.update_action.setEnabled(False)
        self._update_progress = QProgressDialog(
            f"Downloading v{release.version}…", "", 0, 100)
        self._update_progress.setWindowTitle("PolyKybdHost Update")
        self._update_progress.setCancelButton(None)
        self._update_progress.setMinimumDuration(0)
        self._update_progress.show()
        ub = self._update_bridge
        self._update_installer = UpdateInstaller(
            release,
            on_progress=lambda pct, m: ub.progress.emit(pct, m),
            on_finished_ok=lambda: ub.finished_ok.emit(),
            on_relay_needed=lambda path: ub.relay_needed.emit(path),
            on_failed=lambda m: ub.failed.emit(m),
        )
        self._update_installer.start()

    def _on_update_progress(self, percent, message):
        if self._update_progress is None:
            return
        self._update_progress.setLabelText(message)
        if percent < 0:
            self._update_progress.setRange(0, 0)
        else:
            if self._update_progress.maximum() == 0:
                self._update_progress.setRange(0, 100)
            self._update_progress.setValue(percent)

    def _on_update_done(self):
        from polyhost.services.updater import restart_app
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None
        self.log.info("Update applied, restarting forwarder...")
        self.quit_app()
        restart_app()

    def _on_relay_needed(self, relay_path):
        if self._update_progress is not None:
            self._update_progress.setLabelText("Restarting to complete update…")
            self._update_progress.setValue(100)
        popen_kwargs = {"close_fds": False}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        subprocess.Popen([sys.executable, relay_path], **popen_kwargs)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        QTimer.singleShot(1200, self.quit)

    def _on_update_failed(self, message):
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None
        self.update_action.setEnabled(True)
        self.log.error("Update failed: %s", message)
        QMessageBox.warning(
            None, "Update failed", f"Could not apply the update:\n\n{message}")

    def quit_app(self):
        self.icon_manager.set_disconnected()
        self.is_closing = True
        if self._report_client is not None:
            self._report_client.close()
            self._report_client = None
        self.quit()

    def active_window_reporter(self):
        self.last_update_msec += UPDATE_CYCLE_MSEC
        self.heartbeat_msec += UPDATE_CYCLE_MSEC
        win = pwc.getActiveWindow()
        if win:
            try:
                if self.prev_win != win:
                    self.prev_win = win
                    self.last_update_msec = 0
                if self.last_update_msec > NEW_WINDOW_ACCEPT_TIME_MSEC:
                    #just to limit the time value:
                    self.last_update_msec = NEW_WINDOW_ACCEPT_TIME_MSEC * 2
                    changed = (
                        self.win is None
                        or win.getHandle() != self.win.getHandle()
                        or win.title != self.title
                    )
                    if changed or self.heartbeat_msec >= HEARTBEAT_MSEC:
                        self.win = win
                        self.title = win.title
                        app_name = win.getAppName()
                        handle = win.getHandle()
                        self.send_to_host(handle, self.title, app_name)
                        if changed:
                            self.log.info("Active App: '%s' %s %d", self.title, app_name, handle)
                        else:
                            self.log.debug("Heartbeat: '%s' %s %d", self.title, app_name, handle)
                        self.heartbeat_msec = 0
            except Exception as e:
                self.log.warning("Exception in window reporter: %s", e)
        elif self.win:
            self.log.info("No active window")
            self.win = None
            self.title = None
            self.heartbeat_msec = 0
            self.send_to_host(0, "", "")

        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)
        else:
            self.log.info("No more active window reporting.")
