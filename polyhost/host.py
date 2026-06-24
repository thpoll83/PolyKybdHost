import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QActionGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QFileDialog,
    QProgressDialog,
    QSizePolicy,
    QStyle,
    QVBoxLayout, )

from polyhost.device.command_ids import IdleStyle
from polyhost.gui.get_icon import get_icon
from polyhost.gui.icon_state_manager import IconStateManager
from polyhost.gui.log_viewer import LogViewerDialog
from polyhost.gui.layout_dialog.kb_layout_dialog import KbLayoutDialog
from polyhost.gui.settings_dialog import SettingsDialog
from polyhost.gui.cmd_menu import CommandsSubMenu
from polyhost.input.linux_gnome_helper import LinuxGnomeInputHelper
from polyhost.input.linux_kde_helper import LinuxPlasmaHelper
from polyhost.input.macos_helper import MacOSInputHelper
from polyhost.input.win_helper import WindowsInputHelper
from polyhost.services.lang_regions import LANG_REGION, LANG_REGION_ORDER, LANG_REGION_OVERRIDE
from polyhost.services.unicode_cache import UnicodeCache
from polyhost._version import __version__

from polyhost.services.updater import (
    UpdateChecker, UpdateInstaller, FwUpDownloader, restart_app,
    get_last_check_time, set_last_check_time)
from polyhost.gui.hid_fw_up_dialog import HidFwUpDialog
from polyhost.gui.dialog_util import position_near_tray
from polyhost.gui.worker_bridge import WorkerBridge
from polyhost.server.control_server import ControlServer

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

UPDATE_CYCLE_MSEC = 250
RECONNECT_CYCLE_MSEC = 1000
PERIODIC_10MIN_CYCLE_MSEC = 1000*60*10
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000

def sort_by_country_abc(item):
    return item[2:]


def get_lang_and_country(combined : str):
    return combined[:2], combined[2:]


from polyhost.util.log_util import DEBUG_DETAILED, MultiLineFormatter, make_stream_handler, make_collapse_handler


# Shared dimensions for all update / firmware dialogs — 2:1 aspect ratio.
_UPD_DLG_W = 400
_UPD_DLG_H = 160


def _fmt_release_date(published_at: str) -> str:
    """Return a human-readable date string from an ISO 8601 timestamp, or '' on failure."""
    if not published_at:
        return ""
    try:
        import datetime
        dt = datetime.datetime.strptime(published_at[:10], "%Y-%m-%d")
        return dt.strftime("%B %d, %Y").replace(" 0", " ")
    except (ValueError, TypeError):
        return ""


def _msgbox(icon, title: str, text: str,
            buttons=QMessageBox.Ok, default=None) -> int:
    """QDialog-based message box so setFixedSize is reliably respected."""
    _ICON_MAP = {
        QMessageBox.Information: QStyle.SP_MessageBoxInformation,
        QMessageBox.Warning:     QStyle.SP_MessageBoxWarning,
        QMessageBox.Critical:    QStyle.SP_MessageBoxCritical,
        QMessageBox.Question:    QStyle.SP_MessageBoxQuestion,
    }
    _BTN_MAP = {
        QMessageBox.Ok:     QDialogButtonBox.Ok,
        QMessageBox.Yes:    QDialogButtonBox.Yes,
        QMessageBox.No:     QDialogButtonBox.No,
        QMessageBox.Cancel: QDialogButtonBox.Cancel,
    }

    dlg = QDialog(None)
    dlg.setWindowTitle(title)
    dlg.setFixedSize(_UPD_DLG_W, _UPD_DLG_H)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(16, 16, 16, 12)
    outer.setSpacing(12)

    # Icon + text row
    row = QHBoxLayout()
    row.setSpacing(12)
    icon_lbl = QLabel()
    sp = _ICON_MAP.get(icon)
    if sp is not None:
        px = dlg.style().standardPixmap(sp)
        icon_lbl.setPixmap(px)
    icon_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    row.addWidget(icon_lbl, 0, Qt.AlignTop)

    text_lbl = QLabel(text)
    text_lbl.setWordWrap(True)
    text_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    row.addWidget(text_lbl, 1)
    outer.addLayout(row, 1)

    # Button row
    db_flags = QDialogButtonBox.StandardButtons()
    for mb_flag, db_flag in _BTN_MAP.items():
        if buttons & mb_flag:
            db_flags |= db_flag
    btn_box = QDialogButtonBox(db_flags)
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)
    outer.addWidget(btn_box, 0, Qt.AlignRight)

    # Set default button focus
    if default is not None:
        db_default = _BTN_MAP.get(default)
        if db_default is not None:
            b = btn_box.button(db_default)
            if b:
                b.setDefault(True)
                b.setFocus()

    result = dlg.exec_()

    # Map QDialog result back to QMessageBox codes
    if result == QDialog.Accepted:
        if buttons & QMessageBox.Yes:
            return QMessageBox.Yes
        return QMessageBox.Ok
    else:
        if buttons & QMessageBox.No:
            return QMessageBox.No
        return QMessageBox.Cancel


def _progress_dlg(label: str, title: str, tray_icon=None) -> QProgressDialog:
    dlg = QProgressDialog(label, None, 0, 100, None)
    dlg.setWindowTitle(title)
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setCancelButton(None)
    dlg.setValue(0)
    dlg.setFixedSize(_UPD_DLG_W, _UPD_DLG_H)
    lbl = dlg.findChild(QLabel)
    if lbl:
        lbl.setWordWrap(True)
    layout = dlg.layout()
    if layout is not None:
        m = layout.contentsMargins()
        layout.setContentsMargins(m.left(), m.top(), m.right(),
                                  m.bottom() + _UPD_DLG_H // 10)
    dlg.show()
    # Snap to the tray corner like HidFwUpDialog (defer a tick so the WM has
    # finalised the frame size); harmless when no tray icon is available.
    QTimer.singleShot(0, lambda: position_near_tray(dlg, tray_icon))
    return dlg


class PolyHost(QApplication):
    def __init__(self, log_level, debug_mode, ignore_version=False,
                 client_mode=False, endpoint=None, connect_retry=False):
        super().__init__(sys.argv)
        fmt = "[%(asctime)s] %(levelname)-7s {%(filename)s:%(lineno)d} %(message)s" if debug_mode>0 else "[%(asctime)s] %(levelname)-7s %(message)s"
        level = DEBUG_DETAILED if debug_mode>1 else log_level

        file_handler = RotatingFileHandler(
            filename="host_log.txt",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(fmt))

        stream_handler = make_collapse_handler(make_stream_handler(fmt))
        file_handler = make_collapse_handler(file_handler)

        logging.basicConfig(level=level, handlers=[file_handler, stream_handler])
        self.log = logging.getLogger('PolyHost')

        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        self.icon_manager = IconStateManager(self, False, f"PolyKybdHost {__version__}")
        self.tray.setVisible(True)

        self.keeb_log = logging.getLogger("PolyKybdConsole")
        self.keeb_log.setLevel(logging.INFO)  # Set log level for logger 'b'

        # Persist the keyboard console to its own file — but only when this
        # process OWNS the device. In --connect client mode the daemon owns the
        # device and writes polykybd_console.txt; if the client also opened a
        # RotatingFileHandler on the same co-located file, two processes would
        # fight over it (and its rotation). The client still receives forwarded
        # `console` events for live use, but drops them to a NullHandler; the
        # log viewer reads the daemon-written file.
        if client_mode:
            self.keeb_log.addHandler(logging.NullHandler())
        else:
            file_handler = RotatingFileHandler(
                filename="polykybd_console.txt",  # Separate log file for 'b'
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
                encoding="utf-8"
            )
            file_handler.setFormatter(MultiLineFormatter(fmt="[%(asctime)s] %(message)s"))
            self.keeb_log.addHandler(file_handler)
        self.keeb_log.propagate = False

        self._ignore_version = ignore_version
        if ignore_version:
            self.log.warning("--ignore-version active: firmware version/protocol checks will be bypassed")

        # The Qt adapter: core events fire on core/worker threads and are
        # marshalled onto the Qt main thread through the bridge's queued
        # signal. Event names match _on_job_done's dispatch by contract
        # (polyhost/core/events.py).
        self.bridge = WorkerBridge()
        # noinspection PyUnresolvedReferences
        self.bridge.job_done.connect(self._on_job_done)

        # The operational core. Normally an in-process Qt-free PolyCore that
        # owns the device stack + HID worker (H1). In CLIENT mode (H4a,
        # `--connect`) the core lives in another process (a headless daemon or
        # another GUI's embedded server) and RemoteCore proxies its API over
        # the control socket — there are no in-process device objects here.
        self.client_mode = client_mode
        if client_mode:
            from polyhost.client.remote_core import RemoteCore
            from polyhost.cli.polyctl import RpcError
            from polyhost.settings import PolySettings
            from polyhost.device.device_settings import DeviceSettings
            if connect_retry:
                # Daemon-by-default: we just spawned the daemon and it's still
                # booting. Connect in the background so the tray appears now and
                # fills in once the daemon binds its socket (never blocks/exits).
                self.core = RemoteCore.connect_deferred(self.log, address=endpoint or None)
            else:
                try:
                    self.core = RemoteCore.connect(self.log, address=endpoint or None)
                except (RpcError, OSError, EOFError) as e:
                    self.log.error("Cannot reach a running PolyKybdHost core (%s)", e)
                    print(f"error: cannot connect to a PolyKybdHost core ({e}). "
                          "Start one first (e.g. `python -m polyhost --headless`).",
                          file=sys.stderr)
                    sys.exit(1)
            # No in-process device objects — the daemon owns them. Client-side
            # settings (the shared XDG file when co-located) feed the input
            # helper; the settings/layout dialogs are deferred (H4a-2).
            self.keeb = None
            self.worker = None
            self.device_mgr = None
            self.overlay_handler = None
            self.poly_settings = PolySettings()
            self.device_settings = DeviceSettings()
            # Whether the first connected status render (language-menu build) has
            # run — the client likely missed the daemon's fresh-connect event.
            self._remote_connected_rendered = False
        else:
            # Imported here, not at module top: PolyCore pulls in the whole
            # device + brightness stack (pvlib/pandas/scipy via sunlight_helper),
            # which is dead weight in --connect client mode and just delays the
            # tray. The client uses RemoteCore instead and never imports this.
            from polyhost.core.poly_core import PolyCore
            self.core = PolyCore(log=self.log, ignore_version=ignore_version,
                                 start_worker=False,
                                 allow_key_injection=debug_mode > 0)
            self.keeb = self.core.keeb
            self.worker = self.core.worker
            self.device_mgr = self.core.device_mgr
            self.poly_settings = self.core.poly_settings
            self.device_settings = self.core.device_settings
            self.overlay_handler = self.core.overlay_handler
        self.core.subscribe(self._on_core_event)

        self.setApplicationName('PolyHost')

        self.setQuitOnLastWindowClosed(False)
        self.is_closing = False
        self.debug_mode = debug_mode

        # Create the menu
        self.log.debug("Building menu...")
        self.set_style()
        self.menu = QMenu()

        self.status = QAction(get_icon("sync.svg"), "Waiting for PolyKybd...", parent=self)
        self.status.setToolTip("Press to pause connection")
        # noinspection PyUnresolvedReferences
        self.status.triggered.connect(self.pause)
        self.exit = QAction(get_icon("power.svg"), "Quit", parent=self)
        # noinspection PyUnresolvedReferences
        self.exit.triggered.connect(self.quit_app)
        # In daemon/client mode, plain Quit leaves the daemon (which owns the
        # device) running. Offer an explicit "stop the daemon too" action — only
        # meaningful as a client; in-process Quit already stops everything.
        self.exit_with_daemon = None
        if client_mode:
            self.exit_with_daemon = QAction(get_icon("power.svg"),
                                            "Quit && stop background daemon", parent=self)
            # noinspection PyUnresolvedReferences
            self.exit_with_daemon.triggered.connect(self.quit_app_and_daemon)
        self.support = QAction(get_icon("support.svg"), "Get Support", parent=self)
        # noinspection PyUnresolvedReferences
        self.support.triggered.connect(self.open_support)
        self.about = QAction(get_icon("home.svg"), "About", parent=self)
        # noinspection PyUnresolvedReferences
        self.about.triggered.connect(self.open_about)

        self.settings_dialog = QAction(get_icon("settings.svg"), "Settings...", parent=self)
        # noinspection PyUnresolvedReferences
        self.settings_dialog.triggered.connect(self.open_settings)

        self.log_dialog = QAction(get_icon("log.svg"), "Log file...", parent=self)
        # noinspection PyUnresolvedReferences
        self.log_dialog.triggered.connect(self.open_log)
        self.log_viewer = None

        self.current_lang = None
        self.keeb_lang_menu = None
        self.debug_lang_menu = None

        self.unicode_cache = UnicodeCache()
        #self.reconnect()
        self.menu.addAction(self.status)
        # No synchronous language enumeration here: self.connected is still
        # False at this point (only the reconnect decision tree may set it —
        # that's where the protocol/version gate lives), so the first worker
        # probe always sees a False→True transition and runs the full fresh-
        # connect flow anyway: enumerate_lang + add_supported_lang + unicode
        # mode + cache reset. Enumerating here as well just did all of that
        # twice within the first second (double menu build seen in the field
        # 2026-06-13). The language menu is inserted right after the status
        # action whenever it is created, so arriving ~1 s late costs nothing.

        # The commands submenu now routes every action through the core
        # (worker job in-process, RPC in client mode), so it works in both
        # modes (H4a-2c). Send-Shortcut still reads the in-process device_mgr,
        # so it stays in-process only.
        self.cmdMenu = CommandsSubMenu(self)
        self.cmdMenu.build_menu(self.menu)
        if not self.client_mode:
            # TODO: enable/disable depending on MRU usage
            action = QAction(get_icon("overlays.svg"), "Send Shortcut Overlay...", parent=self)
            # noinspection PyUnresolvedReferences
            action.triggered.connect(self.send_shortcuts)
            self.menu.addAction(action)
        # The layout editor and settings dialog are device-independent of the
        # in-process worker — they drive the device through core.keymap_* /
        # settings.* (RPC in client mode), so both work in either mode (H4a-2).
        self.layout_editor = QAction(get_icon("keyboard.svg"), "Configure Keymap", parent=self)
        # noinspection PyUnresolvedReferences
        self.layout_editor.triggered.connect(self.open_layout_editor)
        self.menu.addAction(self.layout_editor)

        # Idle anti-burn-in style (firmware v4+). Device-coupled: it drives the
        # device through core.get/set_idle_style (worker run_sync in-process, RPC
        # in client mode), so it works in both modes; the blanket enable/disable
        # in managed_connection_status greys the whole submenu while disconnected.
        self.idle_style_menu = self.menu.addMenu(get_icon("backlight_high.svg"), "Idle Anti-Burn-In")
        idle_group = QActionGroup(self)
        idle_group.setExclusive(True)
        self.idle_pulse_action = QAction("Pulse (legacy)", parent=self, checkable=True)
        self.idle_pulse_action.setData(IdleStyle.PULSE.value)
        self.idle_jitter_action = QAction("Jitter (move legend)", parent=self, checkable=True)
        self.idle_jitter_action.setData(IdleStyle.JITTER.value)
        for act in (self.idle_pulse_action, self.idle_jitter_action):
            idle_group.addAction(act)
            # noinspection PyUnresolvedReferences
            act.triggered.connect(self.change_idle_style)
            self.idle_style_menu.addAction(act)
        # noinspection PyUnresolvedReferences
        self.idle_style_menu.aboutToShow.connect(self.refresh_idle_style_menu)

        self.menu.addAction(self.settings_dialog)
        self.menu.addAction(self.log_dialog)

        self.update_action = QAction(get_icon("sync.svg"), "Check for updates...", parent=self)
        # noinspection PyUnresolvedReferences
        self.update_action.triggered.connect(self._on_update_clicked)
        self.menu.addAction(self.update_action)
        self._pending_release = None
        self._update_checker = None
        self._update_check_last = None   # wall-clock ts of last AUTOMATIC check this session
        self._update_installer = None
        self._update_progress = None
        self._await_manual_prompt = False
        # Per-check closures wired up by _start_update_check; invoked from the Qt
        # main thread via the bridge (see _on_job_done) since the checker
        # callbacks fire on its worker thread.
        self._update_check_error = None
        self._update_host_no_update = None
        self._update_fw_no_update = None

        # The keyboard-firmware release flow downloads the .bin locally then
        # flashes over HID — that can't drive a remote daemon, so it's
        # in-process only (client mode flashes a local .bin via RPC instead;
        # daemon-side release download is a later slice).
        self.firmware_update_action = None
        if not self.client_mode:
            self.firmware_update_action = QAction(get_icon("keyboard.svg"), "Check for firmware update…", parent=self)
            # noinspection PyUnresolvedReferences
            self.firmware_update_action.triggered.connect(self._on_fw_up_clicked)
            self.menu.addAction(self.firmware_update_action)
        self._pending_fw_release = None
        self._fw_up_downloader = None
        self._fw_up_progress = None
        self._await_manual_fw_prompt = False

        if debug_mode > 0:
            debug_menu = self.menu.addMenu(get_icon("info.svg"), "Debugging")
            self.debug_lang_menu = debug_menu.addMenu(get_icon("language.svg"), "Change System Input Language")
            if not self.client_mode:
                # MRU inspector + mock dump read the in-process device_mgr.
                mru_action = QAction(get_icon("overlays.svg"), "Inspect MRU Cache...", parent=self)
                # noinspection PyUnresolvedReferences
                mru_action.triggered.connect(self.open_mru_inspector)
                debug_menu.addAction(mru_action)
                dump_action = QAction(get_icon("overlays.svg"), "Dump Mock Bitmaps...", parent=self)
                # noinspection PyUnresolvedReferences
                dump_action.triggered.connect(self.dump_mock_bitmaps)
                debug_menu.addAction(dump_action)

        self.menu.addAction(self.support)
        self.menu.addAction(self.about)
        self.menu.addAction(self.exit)
        if self.exit_with_daemon is not None:
            self.menu.addAction(self.exit_with_daemon)

        self.log.debug("Create OS dependent input helper...")
        self.helper = None
        if platform.system() == "Windows":
            self.helper = WindowsInputHelper(self.poly_settings)
        elif platform.system() == "Linux":
            if IS_PLASMA:
                self.helper = LinuxPlasmaHelper()
            else:
                self.helper = LinuxGnomeInputHelper()
        elif platform.system() == "Darwin":
            self.helper = MacOSInputHelper()

        if not self.helper:
            self.log.error("Unsupported OS! Exiting...")
            sys.exit(-1)
        self.log.info("Input helper: %s", type(self.helper).__name__)

        # Detecting the OS input language shells out to PowerShell on Windows
        # (each cold powershell.exe start is hundreds of ms) — and it's only
        # needed once a keyboard connects (OS-language sync), not to show the
        # tray. Probe it on a background thread and apply the result on the Qt
        # main thread via the bridge, so the tray appears immediately.
        threading.Thread(target=self._probe_input_language, args=(debug_mode > 0,),
                         name="input-language-probe", daemon=True).start()

        self.managed_connection_status()
        
        self.log.debug("Display tray...")
        # Add the menu to the tray
        # self.tray.activated.connect(self.on_activated)
        self.tray.setContextMenu(self.menu)
        # noinspection PyUnresolvedReferences
        self.tray.messageClicked.connect(self._on_balloon_clicked)
        self.tray.show()

        QTimer.singleShot(15_000, self._start_update_check)
        self._update_timer = QTimer(self)
        # noinspection PyUnresolvedReferences
        self._update_timer.timeout.connect(self._start_update_check)
        self._update_timer.start(24 * 60 * 60 * 1000)

        # Device-owning startup is in-process only. In CLIENT mode the daemon
        # owns the worker, the active-window poll, and the control socket — the
        # GUI just renders the daemon's events and issues RPC commands.
        self.control_server = None
        if not self.client_mode:
            # After __init__ completes, only the worker thread (or code holding
            # worker.exclusive()) calls into the device. The core owns the
            # worker and all periodics; results arrive as core events.
            self.log.debug("Starting cyclic checks...")
            self.core.worker.start()
            QTimer.singleShot(UPDATE_CYCLE_MSEC * 2, self.active_window_reporter)

            # Control socket (M1): embed the JSON-RPC server so a CLI / headless
            # client can drive this running tray app. host.shutdown fires on a
            # server thread, so hop to the Qt main thread via the bridge.
            try:
                self.control_server = ControlServer(
                    self.core, __version__, self.log,
                    on_shutdown=lambda: self.bridge.job_done.emit("host_shutdown", None))
                self.control_server.start()
            except Exception as e:
                # A failed control socket must never stop the tray app running.
                self.log.warning("Control server not started (%s: %s).", type(e).__name__, e)
 

    # ------------------------------------------------------------------
    # Core adapter: events + shared connection state
    # ------------------------------------------------------------------

    def _probe_input_language(self, want_debug_menu):
        """Background-thread input-language probe (PowerShell on Windows is
        slow). Posts the result to the Qt main thread; never touches Qt here."""
        try:
            entries = self.helper.get_languages()
            result, info = self.helper.get_current_language()
        except Exception as e:  # noqa: BLE001 — a probe failure must not crash the GUI
            self.log.warning("Input-language probe failed: %s", e)
            return
        self.bridge.job_done.emit("input_language_probe", {
            "entries": entries or [], "ok": bool(result), "info": info,
            "debug": want_debug_menu})

    def _apply_input_language_probe(self, result):
        """Main-thread half of the input-language probe (see _probe_input_language)."""
        if result.get("ok"):
            self.log.info("Current System Language: %s", result["info"])
            self.current_lang = result["info"]
        else:
            self.icon_manager.set_warning("System language query not supported for this platform.", 5000)
            self.log.warning("System language query not supported for this platform: '%s'",
                             result.get("info"))
        if result.get("debug") and self.debug_lang_menu is not None:
            for e in result.get("entries", []):
                self.log.info(" - Enumerating input language %s", e)
                self.debug_lang_menu.addAction(e, self.change_system_language)

    def _on_core_event(self, name, payload):
        """Core observer (fires on core/worker threads): hop to the Qt main
        thread via the bridge's queued signal. Never touch Qt here."""
        self.bridge.job_done.emit(name, payload)

    def _emit_done(self, name, result):
        """Worker-thread on_done shim: forward to the main thread via the bridge."""
        self.bridge.job_done.emit(name, result)

    # Connection state lives in the core (the worker-side probe reads it; a
    # bool read/write is atomic under the GIL). These properties keep the
    # GUI code and dialogs reading/writing the single source of truth.
    @property
    def connected(self):
        return self.core.connected

    @connected.setter
    def connected(self, value):
        self.core.connected = value

    @property
    def device_present(self):
        return self.core.device_present

    @device_present.setter
    def device_present(self, value):
        self.core.device_present = value

    @property
    def paused(self):
        return self.core.paused

    @property
    def _last_applied_connected(self):
        return self.core.last_applied_connected

    @_last_applied_connected.setter
    def _last_applied_connected(self, value):
        self.core.last_applied_connected = value

    @property
    def mapping(self):
        return self.core.mapping

    @property
    def kb_sw_version(self):
        return self.core.kb_sw_version

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
        
    def _fw_actions_allowed(self):
        """Firmware flash/apply must stay reachable whenever a device is
        present — including on a protocol/version mismatch, which is exactly
        when the user needs to update. The HID flash protocol (hid_fw_up) is
        dispatched independently of PROTOCOL_VERSION in the firmware, so it
        only needs a present device, not a compatible one."""
        return (self.connected or self.device_present) and not self.paused

    def managed_connection_status(self):
        enabled = self.connected and not self.paused
        fw_enabled = self._fw_actions_allowed()
        for action in self.menu.actions():
            action.setEnabled(enabled)
        # Re-enable the firmware actions inside the commands submenu (the loop
        # above just disabled its parent action on a mismatch). Both modes.
        self.cmdMenu.update_enabled(enabled, fw_enabled)
        if not self.client_mode:
            self.firmware_update_action.setEnabled(fw_enabled)
        # Available in both modes (driven via core methods).
        self.layout_editor.setEnabled(True)
        self.settings_dialog.setEnabled(True)
        self.log_dialog.setEnabled(True)
        self.update_action.setEnabled(True)
        self.status.setEnabled(True)
        self.support.setEnabled(True)
        self.about.setEnabled(True)
        self.exit.setEnabled(True)
        if self.exit_with_daemon is not None:
            # Always available — stopping/quitting must work even when the device
            # is disconnected or the menu is otherwise greyed out.
            self.exit_with_daemon.setEnabled(True)
        if self.connected:
            self.icon_manager.set_connected()
        else:
            self.icon_manager.set_disconnected()

    def report_device_result(self, title, msg, result=False):
        # Logs only; no UI popup. Errors go to warning, anything else to info.
        if not result:
            level = logging.WARNING if title == "Error" else logging.INFO
            self.log.log(level, "%s: %s", title, msg)

    def pause(self):
        self.core.set_paused(not self.paused)
        if self.paused:
            self.status.setText("Reconnect")
            self.status.setToolTip("")
        else:
            self.status.setToolTip("Press to pause connection")
        self.managed_connection_status()

    # ------------------------------------------------------------------
    # Reconnect: worker-side probe + main-thread apply
    # ------------------------------------------------------------------

    def _apply_reconnect_result(self, snapshot):
        """Runs on the MAIN thread. Reproduces the original reconnect decision
        tree exactly, then drives the language-changed flow."""
        if self.paused:
            return
        # Operational half (state, decision tree, post-connect jobs, cache
        # resets) is the core's; this method renders the result: status
        # entry, language menu, OS-language switch, update-check kick-off.
        applied = self.core.apply_reconnect(snapshot)
        if applied is None:
            return
        connected_now = applied["connected_now"]
        response = applied["lang"]
        decision = applied["decision"]

        if decision is not None:
            if decision["icon"] is not None:
                self.status.setIcon(get_icon(decision["icon"]))
            if decision["text"] is not None:
                self.status.setText(decision["text"])
            if decision["do_post_connect"]:
                self.add_supported_lang(self.menu, snapshot["lang_list"], snapshot["current_lang"])
                if connected_now and self.poly_settings.get("unicode_send_composition_mode"):
                    self.update_ui_on_lang_change(response)
                QTimer.singleShot(0, self._start_update_check)

        self.managed_connection_status()
        self.icon_manager.update()

        kb_lang = response if connected_now else self.current_lang

        if not self.connected:
            return

        if applied["do_overlay_reset"]:
            self.core.reset_overlays()   # reset overlays + usage (in-process)
            self.log.info("Connected: overlay state cleared.")

        # Language-changed flow (helper.set_language stays on the main thread).
        if kb_lang and self.current_lang != kb_lang:
            self.icon_manager.set_thinking()
            # Reflect the keyboard's active language in the tray menu. This also
            # covers a language changed ON THE KEYBOARD itself (its _LL layer):
            # the probe reports the keyboard's current language every cycle, but
            # the menu title/checkmark are otherwise only redrawn at (re)connect,
            # so a keyboard-side switch would leave the tray menu stale.
            self.update_ui_on_lang_change(kb_lang)
            lang, country = get_lang_and_country(kb_lang)
            success, msg = self.helper.set_language(lang, country)
            if success:
                data = self.overlay_handler.get_overlay_data()
                if data:
                    self.send_overlay_data(data)
            else:
                warning = f"Could not change OS language {kb_lang}."
                self.icon_manager.set_warning(warning, 5000)
                self.log.warning("%s (%s)", warning, msg)
            self.current_lang = kb_lang
            self.icon_manager.set_idle()

    # ------------------------------------------------------------------
    # Client mode (H4a): render from the daemon's status_changed events
    # ------------------------------------------------------------------

    def _render_remote_status(self, payload):
        """Client-mode status renderer (the daemon applied the reconnect and
        pushed status_changed; RemoteCore re-emitted it). Mirrors the rendering
        half of _apply_reconnect_result: status entry, language menu, and the
        CLIENT-side OS-language switch (the daemon can't change this machine's
        OS language).

        The daemon emits status_changed every probe cycle, but only state
        *changes* carry text/icon, and a client that connected after the
        daemon's fresh-connect event missed it — so synthesize a descriptive
        status from the cached device info, and build the language menu on the
        first connected render rather than only on state_changed."""
        if self.paused or not isinstance(payload, dict):
            return
        connected = bool(payload.get("connected"))
        self.status.setIcon(get_icon(payload.get("icon") or
                                     ("sync.svg" if connected else "sync_disabled.svg")))
        self.status.setText(payload.get("text") or self._remote_status_text(connected))

        lang = payload.get("lang") or payload.get("current_lang")
        if connected and (payload.get("state_changed") or not self._remote_connected_rendered):
            langs = self.core.list_languages()
            if langs:
                self.add_supported_lang(self.menu, langs, lang)
            self._remote_connected_rendered = True
        elif not connected:
            self._remote_connected_rendered = False

        self.managed_connection_status()
        self.icon_manager.update()

        if connected and lang and self.current_lang != lang:
            self.icon_manager.set_thinking()
            self.update_ui_on_lang_change(lang)
            lng, country = get_lang_and_country(lang)
            success, msg = self.helper.set_language(lng, country)
            if not success:
                warning = f"Could not change OS language {lang}."
                self.icon_manager.set_warning(warning, 5000)
                self.log.warning("%s (%s)", warning, msg)
            self.current_lang = lang
            self.icon_manager.set_idle()

    def _remote_status_text(self, connected):
        """Descriptive status line from the cached device info (client mode)."""
        if not connected:
            return "Waiting for PolyKybd..."
        st = self.core.status_snapshot()
        name = st.get("name") or "PolyKybd"
        hw = st.get("hw_version") or ""
        fw = st.get("fw_version") or "?"
        proto = st.get("protocol")
        if proto is not None:
            return f"PolyKybd {name} {hw} (FW {fw}, P{proto})"
        return f"PolyKybd {name} {hw} ({fw})"

    def _client_flash_firmware(self, apply=True):
        """Client-mode firmware flash: pick a local .bin and have the daemon
        flash it over RPC. The path must be readable by the daemon — works when
        the GUI and daemon share a filesystem (co-located / same machine).
        Progress arrives as fw_flash_*/fw_apply_* events (see _on_flash_*)."""
        path, _ = QFileDialog.getOpenFileName(
            None, "Select firmware .bin", "", "Firmware image (*.bin)")
        if not path:
            return
        # Same polished dialog as the in-process flash (tray-corner + ETA), just
        # fed by the daemon's fw_flash_*/fw_apply_* events instead of a local HID
        # worker (external=True). Without this the client got a bare QProgressDialog.
        self._flash_dialog = HidFwUpDialog(
            None, path, parent=None, apply_after=apply, tray_icon=self.tray, external=True)
        self._flash_dialog.show()
        ok, payload = self.core.flash_firmware(path, apply=apply)
        if not ok:
            self._flash_dialog.feed_finished(False, str(payload))

    def _client_apply_staged(self):
        """Client-mode 'apply staged firmware' over RPC, with the event-driven
        progress dialog (fw_apply_* events)."""
        self._flash_dialog = HidFwUpDialog(
            None, "", parent=None, tray_icon=self.tray, external=True, apply_only=True)
        self._flash_dialog.show()
        ok, payload = self.core.apply_staged_firmware()
        if not ok:
            self._flash_dialog.feed_apply_finished(False, str(payload))

    def _on_flash_progress(self, name, payload):
        dlg = getattr(self, "_flash_dialog", None)
        if dlg is None or not isinstance(payload, dict):
            return
        pct = payload.get("pct")
        pct = pct if isinstance(pct, int) and pct >= 0 else 0
        msg = payload.get("msg", "")
        if name == "fw_apply_progress":
            dlg.feed_apply_progress(pct, msg)
        else:
            dlg.feed_progress(pct, msg)

    def _on_flash_done(self, name, payload):
        dlg = getattr(self, "_flash_dialog", None)
        payload = payload or {}
        ok = bool(payload.get("ok"))
        msg = payload.get("msg", "")
        # The dialog drives its own staging→apply chaining (apply_after=True) and
        # finalizes itself (showing a Close button), so we just feed the result.
        if dlg is not None:
            if name == "fw_flash_done":
                dlg.feed_finished(ok, msg)
            else:  # fw_apply_done
                dlg.feed_apply_finished(ok, msg)
        if ok:
            self.icon_manager.set_idle()
        else:
            phase = "apply" if name == "fw_apply_done" else "flash"
            self.icon_manager.set_warning(f"Firmware {phase} failed", 5000)

    @staticmethod
    def langcode_to_flag(lang_code):
        result = ""
        for ch in lang_code:
            num = 0x1F1E6 + ord(ch.upper()) - ord('A')
            result = f"{result}{chr(num)}"
        return result

    def add_supported_lang(self, menu, lang_list, current_lang):
        # Consumes the language list/current language from the reconnect snapshot
        # (or the synchronous initial enumerate) — never queries the device here,
        # which keeps this method off the HID worker's ownership path.
        # Deliberately does NOT touch self.current_lang: that field tracks the
        # language the OS is set to, and _apply_reconnect_result compares it
        # against the keyboard's language to decide whether to switch the OS.
        # Overwriting it here (this runs first in the reconnect apply) made the
        # comparison always equal, silently skipping the OS switch on reconnect.
        if lang_list is not None and current_lang is not None:
            title = f"Selected Language: {current_lang[:2]} {self.langcode_to_flag(current_lang[2:])}"
            if self.keeb_lang_menu is None:
                # Place the language menu right under the first entry (the status
                # action) instead of appending it last. It may be created lazily
                # once the firmware version is known, by which point the rest of
                # the menu already exists, so insert rather than add.
                self.keeb_lang_menu = QMenu(title)
                # Enlarge only the language menu's icons — the per-language flag
                # icons are the ones worth showing big. Applying this on the whole
                # tray menu (the old behaviour) instead inflated the submenu-title
                # glyphs (All Commands / Font Pack / Idle Anti-Burn-In / Fix
                # Left-Right Side), which looked oversized next to the normal
                # action icons. Scoping it here keeps those at the default size.
                self.keeb_lang_menu.setStyleSheet(
                    "QMenu {icon-size: 64px;} QMenu::item {icon-size: 64px; background: transparent;}")
                self.keeb_lang_menu.menuAction().setIcon(get_icon("language.svg"))
                actions = menu.actions()
                if len(actions) > 1:
                    menu.insertMenu(actions[1], self.keeb_lang_menu)
                else:
                    menu.addMenu(self.keeb_lang_menu)
            else:
                self.keeb_lang_menu.setTitle(title)
                self.keeb_lang_menu.clear()

            # Group by region, preserving alphabetical-by-country order within each.
            all_languages = sorted(lang_list, key=sort_by_country_abc)
            self.log.debug("Adding %s to language menu", all_languages)
            by_region: dict[str, list] = {}
            for lang in all_languages:
                region = LANG_REGION_OVERRIDE.get(lang, LANG_REGION.get(lang[2:].upper(), "Other"))
                by_region.setdefault(region, []).append(lang)

            for region in LANG_REGION_ORDER + (["Other"] if "Other" in by_region else []):
                langs = by_region.get(region)
                if not langs:
                    continue
                sub = self.keeb_lang_menu.addMenu(region)
                for lang in langs:
                    text = f"{lang[:2]} {lang[2:].upper()}"
                    if lang == current_lang:
                        text = f"{text} {chr(0x2714)}"
                    item = sub.addAction(text, self.change_keeb_language)
                    item.setData(lang)
                    item.setIcon(self.unicode_cache.get_icon_for(lang[2:]))
        else:
            self.log.warning("Enumerating PolyKybd languages failed")

    def _lang_actions(self):
        """Iterate every language QAction across all region submenus."""
        if not self.keeb_lang_menu:
            return
        for region_action in self.keeb_lang_menu.actions():
            sub = region_action.menu()
            if sub is not None:
                yield from sub.actions()

    def update_ui_on_lang_change(self, new_lang):
        if self.keeb_lang_menu:
            self.keeb_lang_menu.setTitle(f"Selected Language: {new_lang[:2]} {self.langcode_to_flag(new_lang[2:])}")
            for action in self._lang_actions():
                lang = action.data()
                text = f"{lang[:2]} {self.langcode_to_flag(lang[2:])}"
                if lang == new_lang:
                    text = f"{text} {chr(0x2714)}"
                action.setText(text)

    def open_layout_editor(self):
        # Driven through the core's keymap_* methods, so it works in-process
        # (worker run_sync) and in client mode (RPC) alike.
        self.layout_dialog = KbLayoutDialog(self.core, self.device_settings)
        self.layout_dialog.show()

    def open_settings(self):
        dlg = SettingsDialog()
        # Client mode edits the DAEMON's settings over RPC (the local file may
        # be shared when co-located, but the daemon holds the live copy).
        current = self.core.settings_list() if self.client_mode else self.poly_settings.get_all()
        dlg.setup(current, self.debug_mode)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_updated_settings()
            if self.client_mode:
                for key, value in updated.items():
                    if current.get(key) != value:
                        self.core.settings_set(key, value)
            else:
                self.poly_settings.set_all(updated)
                # In-process mode writes settings directly (bypassing
                # core.settings_set), so nudge the core to recompute + push the
                # daylight brightness now rather than waiting for the next cycle.
                self.core.refresh_daylight_brightness()
        dlg.close()

    def open_log(self):
        # assignment is needed otherwise the dialog would go away immediately
        delta = time.perf_counter()
        log_files = {"PolyHost Log": "host_log.txt",
                     "PolyKybd Console Log": "polykybd_console.txt"}
        # In daemon mode the operational core runs in a separate headless process
        # that writes its own daemon_log.txt (the GUI's host_log.txt only covers
        # the client side). Surface it as a tab when present so the daemon's
        # reconnect/overlay/window activity is visible from the tray GUI.
        if os.path.exists("daemon_log.txt"):
            log_files["Daemon Log"] = "daemon_log.txt"
        # The pre-GUI launch phase (daemon spawn/attach, autostart, single-instance)
        # logs to startup_log.txt — invaluable when the app fails to come up at all
        # (especially under Windows pythonw, where print() goes nowhere).
        if os.path.exists("startup_log.txt"):
            log_files["Startup Log"] = "startup_log.txt"
        self.log_viewer = LogViewerDialog(log_files)
        self.log_viewer.show()
        delta = time.perf_counter() - delta
        self.log.info("Opened log dialog in '%f' sec", delta)

    def open_mru_inspector(self):
        from polyhost.gui.mru_inspector_dialog import MRUInspectorDialog
        caches = [(e.name, e.cache) for e in self.device_mgr.all_entries if e.cache is not None]
        if not caches:
            QMessageBox.information(None, "MRU Cache", "MRU cache is not active (device not connected or MRU mode disabled).")
            return
        dlg = MRUInspectorDialog(caches, self.device_settings)
        dlg.exec_()

    def dump_mock_bitmaps(self):
        import subprocess
        import tempfile
        import numpy as np

        mock_entry = next((e for e in self.device_mgr.all_entries if not e.is_primary), None)
        if mock_entry is None:
            QMessageBox.information(None, "Mock Dump", "No mock device active.\nEnable dev_mock_enabled in settings.")
            return

        store = mock_entry.device._sim._store
        if not store:
            QMessageBox.information(None, "Mock Dump", "Mock has no stored bitmaps yet.\nSwitch to an app to trigger an overlay send.")
            return

        out_dir = tempfile.mkdtemp(prefix="polykybd_mock_")
        from polyhost.device.overlay_sim import _write_png_gray8
        for pool_slot, bitmap in sorted(store.items()):
            keycode_slot = pool_slot % 90
            modifier_var = pool_slot // 90
            if keycode_slot < 80:
                kc = keycode_slot + 0x04        # KC_A base
            elif keycode_slot < 82:
                kc = keycode_slot - 80 + 0x64   # KC_NONUS_BACKSLASH base
            else:
                kc = keycode_slot - 82 + 0xE0   # KC_LEFT_CTRL base
            fname = f"slot{pool_slot:03d}_kc0x{kc:02x}_mod{modifier_var}.png"
            bits = np.unpackbits(np.frombuffer(bitmap, dtype=np.uint8))
            pixels = (bits[:40 * 72].reshape(40, 72) * 255).astype(np.uint8)
            _write_png_gray8(os.path.join(out_dir, fname), pixels)

        self.log.info("Mock bitmaps dumped to %s", out_dir)
        if platform.system() == "Windows":
            os.startfile(out_dir)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", out_dir])
        else:
            subprocess.Popen(["xdg-open", out_dir])
        QMessageBox.information(None, "Mock Dump", f"Saved {len(store)} bitmaps to:\n{out_dir}")

    @staticmethod
    def open_support():
        webbrowser.open("https://discord.gg/gW8JescH7M", new=0, autoraise=True)

    @staticmethod
    def open_about():
        webbrowser.open("https://ko-fi.com/polykb", new=0, autoraise=True)

    def send_shortcuts(self):
        file_name = QFileDialog.getOpenFileName(None, 'Open file', '', "Image files (*.jpg *.gif *.png *.bmp *.jpeg)")
        if file_name[0]:
            path = file_name[0]

            def _job(cancel):
                for entry in self.device_mgr.all_entries:
                    if cancel.is_set():
                        return
                    entry.device.send_overlays([path], cancel)

            self.worker.submit("send_shortcuts", _job)
        else:
            self.log.info("No file selected. Operation canceled.")

    def change_system_language(self):
        self.icon_manager.set_thinking()
        
        requested_lang = self.sender().text()
        lang, country = get_lang_and_country(requested_lang)
        result, output = self.helper.set_language(lang, country)
        if not result:
            msg = f"Changing input language to '{requested_lang}' failed with:\n\"{output}\""
            self.icon_manager.set_warning(msg)
            self.report_device_result("Error", msg)
        else:
            self.log.info("Change input language to '%s'.", requested_lang)
        
        self.icon_manager.set_idle()

    def change_keeb_language(self):
        lang = self.sender().data()

        if self.client_mode:
            # No local worker/keeb — change via the daemon over RPC. The menu
            # checkmark also follows the daemon's next status_changed, but
            # update it now for immediate feedback.
            ok, msg = self.core.set_language(lang)
            if ok:
                self.update_ui_on_lang_change(lang)
            elif self.keeb_lang_menu is not None:
                self.keeb_lang_menu.setTitle(f"Could not set {lang}: {msg}")
            return

        def _job(cancel):
            result, msg = self.keeb.change_language(lang)
            return (lang, result, msg)

        self.worker.submit("change_keeb_language", _job, on_done=self._emit_done)

    def _on_change_keeb_language_done(self, result):
        lang, ok, msg = result
        if ok and msg == lang:
            self.update_ui_on_lang_change(lang)
        else:
            self.keeb_lang_menu.setTitle(f"Could not set {lang}: {msg}")

    def refresh_idle_style_menu(self):
        # Read the current style straight from the device (core marshals the HID
        # round-trip onto the worker in-process, or over RPC in client mode) and
        # tick the matching item. On failure (old firmware / disconnected) leave
        # both unchecked rather than guessing.
        ok, value = self.core.get_idle_style()
        self.idle_pulse_action.setChecked(bool(ok) and value == IdleStyle.PULSE.value)
        self.idle_jitter_action.setChecked(bool(ok) and value == IdleStyle.JITTER.value)

    def change_idle_style(self):
        value = self.sender().data()
        ok, msg = self.core.set_idle_style(value)
        if ok:
            self.log.info("Idle anti-burn-in style set to %s.", IdleStyle(value).name.lower())
        else:
            # Firmware too old (needs v4+) or device busy — log and re-sync the
            # checkmark to the device's actual style so the menu doesn't lie.
            self.report_device_result("Error", f"Could not set idle style: {msg}")
            self.refresh_idle_style_menu()

    def read_overlay_mapping_file(self, file):
        if not file:
            file = QFileDialog.getOpenFileName(None, 'Open file', '', "PolyKybd overlay mapping (*.poly.yaml)")
        if len(file) > 0:
            self.core.load_overlay_mapping(file)

    def save_overlay_mapping_file(self, filename="overlay-mapping.poly.yaml"):
        self.core.save_overlay_mapping(filename)

    def _start_update_check(self, on_no_update=None, on_check_error=None, force=False):
        """Start a background update check.

        ``on_no_update`` is called when the check succeeds but finds no newer release.
        ``on_check_error`` is called (with a message string) when the API/network
        call itself fails — distinct from "no update available".
        Both are None for the automatic periodic check (silent failure).
        ``force`` bypasses the throttle for user-initiated (menu) checks.
        """
        # Throttle AUTOMATIC checks (startup / 24h timer / on-connect). GitHub's
        # unauthenticated API allows only ~60 requests/hour per IP, and a connect
        # triggers a check — so reconnects (every firmware flash reboots the
        # keyboard) and several machines behind one office IP exhaust it
        # ("GitHub rate limit reached"). The throttle is PERSISTED (wall clock,
        # via the updater's cache) so it survives restarts — an in-memory-only
        # throttle reset on every launch, and frequent restarts (or repeated
        # rate-limited 403s, which still count) burned the quota. Skip an
        # automatic check when one ran in the last 6 h. The timestamp is recorded
        # before the request, so a 403 also backs off for 6 h instead of
        # retrying. A MANUAL menu check passes force=True and always runs.
        if not force:
            now = time.time()
            last = self._update_check_last
            if last is None:
                last = get_last_check_time()    # persisted across restarts
            if last and now - last < 6 * 3600:
                self.log.debug("Update check throttled (%.0f min since last automatic check)",
                               (now - last) / 60)
                return False
            self._update_check_last = now
            set_last_check_time(now)
        if self._update_checker is not None and self._update_checker.is_alive():
            # A check is already in flight with its own (auto) callbacks — do
            # NOT start a second. Returns False so a manual caller knows its
            # on_no_update/on_error closures were not installed and can avoid
            # switching the UI into a "checking…" state it can't clear.
            return False
        self.log.debug("Starting update check...")
        # device_present (not connected): the firmware version is known even on
        # a protocol mismatch, and that's exactly when an update must be offered.
        # Read it via the core-backed property (self.keeb is None in client
        # mode). In client mode we skip the firmware check entirely — the
        # keyboard-firmware release/flash flow is in-process only, so there's no
        # firmware_update_action to drive (a falsy fw_version skips the fw check).
        fw_version = self.kb_sw_version \
            if (self._fw_actions_allowed() and not self.client_mode) else None

        # Track whether the error event fires before host_no_update so we can
        # suppress the "no update" callback and show the real failure reason.
        # The checker callbacks run on its own thread and are marshalled to the
        # Qt main thread through the bridge (see _on_job_done); these closures
        # capture this call's on_no_update/on_check_error and therefore live on
        # self for the bridge dispatch to reach them.
        _error_seen = [False]

        def _on_error(msg):
            self.log.warning("Update check error: %s", msg)
            if not _error_seen[0] and on_check_error is not None:
                on_check_error(msg)
            _error_seen[0] = True
            # Reset firmware manual check regardless of which check failed — both
            # host and firmware errors emit the same event, either can leave it stuck.
            if self._await_manual_fw_prompt:
                self._await_manual_fw_prompt = False
                self.firmware_update_action.setText(
                    f"Update firmware to v{self._pending_fw_release.version}…"
                    if self._pending_fw_release else "Check for firmware update…"
                )
                self.firmware_update_action.setEnabled(self._fw_actions_allowed())

        def _host_no_update():
            if _error_seen[0]:
                return  # error was already surfaced via on_check_error
            self.log.debug("No host update available")
            if on_no_update is not None:
                on_no_update()

        def _fw_no_update():
            self.log.debug("No firmware update available")
            if self._await_manual_fw_prompt:
                self._await_manual_fw_prompt = False
                self._on_manual_no_fw_update()

        self._update_check_error = _on_error
        self._update_host_no_update = _host_no_update
        self._update_fw_no_update = _fw_no_update

        b = self.bridge
        self._update_checker = UpdateChecker(
            current_fw_version=fw_version,
            on_update_available=lambda r: b.job_done.emit("update_available", r),
            on_fw_up_available=lambda r: b.job_done.emit("fw_up_available", r),
            on_host_no_update=lambda: b.job_done.emit("update_host_no_update", None),
            on_fw_no_update=lambda: b.job_done.emit("update_fw_no_update", None),
            on_error=lambda msg: b.job_done.emit("update_check_error", msg),
        )
        self._update_checker.start()
        return True

    def _on_update_available(self, release):
        self._pending_release = release
        self.update_action.setText(f"Update to v{release.version} available")
        self.log.info("Update available: %s", release.version)
        if self._await_manual_prompt:
            self._await_manual_prompt = False
            self._prompt_and_install(release)
        else:
            self.show_balloon(
                "PolyKybdHost Update",
                f"Version {release.version} is available. "
                "Click the tray icon to update.",
            )

    def _on_update_clicked(self):
        if self._update_installer is not None and self._update_installer.is_alive():
            return
        if self._pending_release is not None:
            self._prompt_and_install(self._pending_release)
            return
        # Only switch the UI into "checking" mode if a run actually started —
        # otherwise an in-flight auto-check (with silent callbacks) would leave
        # the action stuck on "Checking…" and drop the manual error dialog.
        if self._start_update_check(
            on_no_update=self._on_manual_no_update,
            on_check_error=self._on_manual_check_error,
            force=True,
        ):
            self.update_action.setText("Checking for updates...")
            self._await_manual_prompt = True

    def _on_manual_no_update(self):
        self._await_manual_prompt = False
        self.update_action.setText("No updates available")
        _msgbox(QMessageBox.Information, "PolyKybdHost Update",
                f"You are running the latest version (v{__version__}).")
        self.update_action.setText("Check for updates...")

    def _on_manual_check_error(self, msg: str):
        self._await_manual_prompt = False
        self.update_action.setText("Check for updates...")
        _msgbox(QMessageBox.Warning, "PolyKybdHost Update",
                f"Could not check for updates:\n\n{msg}\n\n"
                "Run with --debug 1 for details.")

    def _prompt_and_install(self, release):
        date_str = _fmt_release_date(release.published_at)
        info = f"Released: {date_str}\n" if date_str else ""
        if _msgbox(QMessageBox.Question, "Update PolyKybdHost",
                   f"Version {release.version} is available.\n{info}\n"
                   "Download, install, and restart now?",
                   QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) != QMessageBox.Yes:
            return
        self._run_update_installer(release)

    def _run_update_installer(self, release):
        if self._update_installer is not None and self._update_installer.is_alive():
            self.log.debug("Update installer already running; ignoring re-entry")
            return

        self.update_action.setEnabled(False)
        self._update_progress = _progress_dlg(
            f"Downloading v{release.version}…", "PolyKybdHost Update",
            tray_icon=self.tray)

        b = self.bridge
        self._update_installer = UpdateInstaller(
            release,
            on_progress=lambda pct, msg: b.job_done.emit("update_progress", (pct, msg)),
            on_finished_ok=lambda: b.job_done.emit("update_finished_ok", None),
            on_relay_needed=lambda path: b.job_done.emit("update_relay_needed", path),
            on_failed=lambda msg: b.job_done.emit("update_failed", msg),
        )
        self._update_installer.start()

    def _on_update_progress(self, percent, message):
        if self._update_progress is None:
            return
        self._update_progress.setLabelText(message)
        if percent < 0:
            self._update_progress.setRange(0, 0)  # indeterminate / busy pulse
        else:
            if self._update_progress.maximum() == 0:
                self._update_progress.setRange(0, 100)
            self._update_progress.setValue(percent)

    def _on_update_done(self):
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None
        self.log.info("Update applied, restarting...")
        self.quit_app()
        restart_app()

    def _on_relay_needed(self, relay_path: str):
        """Windows: some files (e.g. hidapi.dll) were locked by the running process.

        A relay script was written that will copy them once we exit and release
        the handles, then relaunch the app.  All non-DLL files were already copied.
        """
        self.log.info("Relay restart needed for locked files: %s", relay_path)
        if self._update_progress is not None:
            self._update_progress.setLabelText("Restarting to complete update…")
            self._update_progress.setValue(100)
        popen_kwargs: dict = {"close_fds": False}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        subprocess.Popen([sys.executable, relay_path], **popen_kwargs)  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        # Brief pause so the user sees the "Restarting" label before the window vanishes.
        QTimer.singleShot(1200, self.quit)

    def _on_update_failed(self, message):
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None
        self.update_action.setEnabled(True)
        self.log.error("Update failed: %s", message)
        _msgbox(QMessageBox.Warning, "Update failed",
                f"Could not apply the update:\n\n{message}")

    # ------------------------------------------------------------------
    # Balloon notifications
    # ------------------------------------------------------------------

    def show_balloon(self, title: str, message: str, msec: int = 8000):
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, msec)

    # ------------------------------------------------------------------
    # Font-pack flash progress (auto on connect, or manual via polyctl)
    # ------------------------------------------------------------------

    def _on_fontpack_progress(self, result):
        """Surface a font-pack transfer in the tray. The keyboard can't service
        keys while flashing, so a quiet first-connect transfer would otherwise be
        invisible — announce it once, then keep a live percentage in the tooltip."""
        result = result or {}
        if not getattr(self, "_fontpack_flashing", False):
            self._fontpack_flashing = True
            self.show_balloon("PolyKybd",
                              "Updating keyboard fonts — please wait, do not unplug…", 5000)
        pct = result.get("pct")
        if pct is not None:
            self.tray.setToolTip(f"PolyKybd — updating fonts ({pct}%)")

    def _on_fontpack_done(self, result):
        result = result or {}
        self._fontpack_flashing = False
        self.tray.setToolTip("")
        if result.get("ok"):
            self.show_balloon("PolyKybd", "Keyboard fonts are up to date.", 4000)
        else:
            self.tray.showMessage("PolyKybd",
                                  f"Font update failed: {result.get('msg', '')}",
                                  QSystemTrayIcon.Warning, 6000)

    def _on_balloon_clicked(self):
        if self._update_installer is not None and self._update_installer.is_alive():
            return
        if self._pending_release is not None:
            self._prompt_and_install(self._pending_release)
        elif self._pending_fw_release is not None:
            self._prompt_and_flash(self._pending_fw_release)

    # ------------------------------------------------------------------
    # Firmware update
    # ------------------------------------------------------------------

    def _on_fw_up_available(self, release):
        self._pending_fw_release = release
        self.firmware_update_action.setText(f"Update firmware to v{release.version}…")
        self.firmware_update_action.setVisible(True)
        self.managed_connection_status()
        self.log.info("Firmware update available: %s", release.version)
        if self._await_manual_fw_prompt:
            self._await_manual_fw_prompt = False
            self._prompt_and_flash(release)
        else:
            self.show_balloon(
                "PolyKybd Firmware Update",
                f"New firmware v{release.version} is available. "
                "Click the tray icon to update.",
            )

    def _on_fw_up_clicked(self):
        if self._fw_up_downloader is not None and self._fw_up_downloader.is_alive():
            return
        if self._pending_fw_release is not None:
            self._prompt_and_flash(self._pending_fw_release)
            return
        # No on_no_update here: the firmware result comes via _await_manual_fw_prompt
        # and the _fw_no_update closure in _start_update_check. Only flip the UI
        # if a run actually started (see _on_update_clicked).
        if self._start_update_check(force=True):
            self.firmware_update_action.setText("Checking for firmware update…")
            self.firmware_update_action.setEnabled(False)
            self._await_manual_fw_prompt = True

    def _on_manual_no_fw_update(self):
        self._await_manual_fw_prompt = False
        self.firmware_update_action.setText("Check for firmware update…")
        self.firmware_update_action.setEnabled(self._fw_actions_allowed())
        fw_version = self.keeb.get_sw_version() if self._fw_actions_allowed() else "unknown"
        _msgbox(QMessageBox.Information, "PolyKybd Firmware",
                f"You are running the latest firmware (v{fw_version}).")

    def _prompt_and_flash(self, release):
        # Deliberately NOT gated on self.connected: a protocol-mismatched
        # keyboard reports connected=False but must remain updatable.
        if not self._fw_actions_allowed():
            _msgbox(QMessageBox.Warning, "Firmware Update",
                    "The keyboard must be connected to update the firmware.")
            return
        date_str = _fmt_release_date(release.published_at)
        info = f"Released: {date_str}\n" if date_str else ""
        if _msgbox(QMessageBox.Question, "Update PolyKybd Firmware",
                   f"Firmware {release.version} is available.\n{info}\n"
                   "Both halves update over HID and reboot automatically.\n\n"
                   "Download and flash now?",
                   QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) != QMessageBox.Yes:
            return
        self._run_fw_up_downloader(release)

    def _run_fw_up_downloader(self, release):
        if self._fw_up_downloader is not None and self._fw_up_downloader.is_alive():
            return

        self.firmware_update_action.setEnabled(False)
        self._fw_up_progress = _progress_dlg(
            f"Downloading firmware v{release.version}…", "Firmware Update",
            tray_icon=self.tray)

        b = self.bridge
        self._fw_up_downloader = FwUpDownloader(
            release,
            on_progress=lambda pct, msg: b.job_done.emit("fw_download_progress", (pct, msg)),
            on_finished=lambda ok, err, path: b.job_done.emit("fw_download_done", (ok, err, path)),
        )
        self._fw_up_downloader.start()

    def _on_fw_download_progress(self, percent: int, message: str):
        if self._fw_up_progress is None:
            return
        self._fw_up_progress.setLabelText(message)
        self._fw_up_progress.setValue(percent)

    def _on_fw_download_done(self, ok: bool, error: str, bin_path: str):
        if self._fw_up_progress is not None:
            self._fw_up_progress.close()
            self._fw_up_progress = None

        if not ok:
            self.firmware_update_action.setEnabled(True)
            self.log.error("Firmware download failed: %s", error)
            _msgbox(QMessageBox.Warning, "Firmware Update Failed",
                    f"Could not download the firmware:\n\n{error}")
            return

        import os
        # Hold the worker off for the whole flash + apply. Otherwise the periodic
        # reconnect probe keeps re-acquiring the HID device while the flash dialog's
        # own QThread stages chunks and the keyboard reboots to apply — contending
        # for the re-enumerating device and corrupting the transfer. exclusive()
        # suspends periodics, cancels the in-flight job and waits for it to finish.
        with self.worker.exclusive():
            try:
                dlg = HidFwUpDialog(self.keeb.hid, bin_path, parent=None, apply_after=True,
                                   tray_icon=self.tray)
                dlg.exec_()
            finally:
                if os.path.exists(bin_path):
                    os.unlink(bin_path)

        self._pending_fw_release = None
        self.firmware_update_action.setVisible(False)
        self.managed_connection_status()

    def quit_app_and_daemon(self):
        """Client mode: ask the core daemon (which owns the device) to exit too,
        then quit this GUI. Plain Quit leaves the daemon running so the keyboard
        keeps working for the next GUI launch / other clients. Must run BEFORE
        quit_app closes the client sockets — the request travels over them."""
        self.log.info("Quit requested including the background daemon.")
        try:
            result = self.core.request_host_shutdown()
            if isinstance(result, dict) and result.get("error"):
                self.log.warning("Daemon shutdown request returned: %s", result["error"])
        except Exception as e:  # noqa: BLE001 — best effort; quit the GUI regardless
            self.log.warning("Could not ask the core daemon to shut down: %s", e)
        self.quit_app()

    def quit_app(self):
        self.icon_manager.set_disconnected()
        self.is_closing = True
        # Stop accepting control clients first, then the operational shutdown
        # (MRU persist, sleep listener, worker stop, window-handler close) —
        # both best-effort, never block on failure.
        if getattr(self, "control_server", None) is not None:
            self.control_server.stop()
        self.core.shutdown()
        self.quit()

    def save_keeb_mru(self):
        """Best-effort MRU persist — delegated to the core (worker job)."""
        self.core.save_mru()

    # noinspection PyPep8Naming
    def closeEvent(self, _):
        self.cmdMenu.disable_overlays()

    def send_overlay_data(self, data):
        # Device I/O runs on the core's worker (coalesced). The tray icon is
        # driven by the core's "overlay_activity"/"overlay" events, not set here.
        self.core.send_overlay_data(data)

    def active_window_reporter(self):
        # Main-thread timer: the active-window poll (pywinctl) must stay on the
        # Qt main thread (macOS constraint, per the worker refactor); the core
        # does the switching decision and routes all HID through its worker.
        self.core.tick_window_tracking(UPDATE_CYCLE_MSEC, NEW_WINDOW_ACCEPT_TIME_MSEC)
        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)

    def _on_job_done(self, name, result):
        """Main-thread slot for the bridge's job_done signal."""
        if name == "reconnect":
            # In-process: render from the probe snapshot via apply_reconnect.
            # Client mode renders from status_changed instead (RemoteCore has
            # no apply_reconnect), so ignore the raw snapshot there.
            if not self.client_mode:
                self._apply_reconnect_result(result)
        elif name == "input_language_probe":
            self._apply_input_language_probe(result)
        elif name == "status_changed":
            if self.client_mode:
                self._render_remote_status(result)
        elif name in ("fw_flash_progress", "fw_apply_progress"):
            self._on_flash_progress(name, result)
        elif name in ("fw_flash_done", "fw_apply_done"):
            self._on_flash_done(name, result)
        elif name == "fontpack_flash_progress":
            self._on_fontpack_progress(result)
        elif name == "fontpack_flash_done":
            self._on_fontpack_done(result)
        elif name == "host_shutdown":
            # A control client (polyctl shutdown) asked the app to quit; the
            # request arrived on a server thread and was hopped here.
            self.quit_app()
        elif name == "console":
            kb_serial, kb_log = result
            if kb_serial:
                self.log.info("Received serial communication: %s", kb_serial)
            if kb_log:
                self.keeb_log.info(kb_log)
        elif name == "overlay_activity":
            # Core signalled a send was queued — show the thinking icon.
            if isinstance(result, dict) and result.get("state") == "thinking":
                self.icon_manager.set_thinking()
        elif name == "overlay":
            # A coalesced (superseded) overlay send leaves the icon thinking;
            # the superseding send's on_done settles it.
            self.icon_manager.set_idle()
        elif name == "overlay_warning":
            self.icon_manager.set_warning(result, 5000)
        elif name == "change_keeb_language":
            if not isinstance(result, BaseException):
                self._on_change_keeb_language_done(result)
        elif name == "cmd_result":
            self.report_device_result(*result)
        # Updater events: the updater threads (UpdateChecker / UpdateInstaller /
        # FwUpDownloader) fire plain callbacks on their own thread; those callbacks
        # emit through the bridge so the GUI handlers below run on the main thread.
        elif name == "update_available":
            self._on_update_available(result)
        elif name == "fw_up_available":
            self._on_fw_up_available(result)
        elif name == "update_host_no_update":
            if self._update_host_no_update is not None:
                self._update_host_no_update()
        elif name == "update_fw_no_update":
            if self._update_fw_no_update is not None:
                self._update_fw_no_update()
        elif name == "update_check_error":
            if self._update_check_error is not None:
                self._update_check_error(result)
        elif name == "update_progress":
            self._on_update_progress(*result)
        elif name == "update_finished_ok":
            self._on_update_done()
        elif name == "update_relay_needed":
            self._on_relay_needed(result)
        elif name == "update_failed":
            self._on_update_failed(result)
        elif name == "fw_download_progress":
            self._on_fw_download_progress(*result)
        elif name == "fw_download_done":
            self._on_fw_download_done(*result)
