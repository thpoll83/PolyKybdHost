import logging
from logging.handlers import RotatingFileHandler
import os
import pathlib
import platform
import subprocess
import sys
import time
import webbrowser
import yaml

from PyQt5.QtCore import QTimer, Qt, pyqtSlot
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QAction,
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

from polyhost.gui.get_icon import get_icon
from polyhost.gui.icon_state_manager import IconStateManager
from polyhost.gui.log_viewer import LogViewerDialog
from polyhost.gui.layout_dialog.kb_layout_dialog import KbLayoutDialog
from polyhost.gui.settings_dialog import SettingsDialog
from polyhost.gui.cmd_menu import CommandsSubMenu
from polyhost.handler.active_window import OverlayHandler
from polyhost.handler.common import OverlayCommand
from polyhost.input.linux_gnome_helper import LinuxGnomeInputHelper
from polyhost.input.linux_kde_helper import LinuxPlasmaHelper
from polyhost.input.macos_helper import MacOSInputHelper
from polyhost.input.win_helper import WindowsInputHelper
from polyhost.services.lang_regions import LANG_REGION, LANG_REGION_ORDER, LANG_REGION_OVERRIDE
from polyhost.services.unicode_cache import UnicodeCache
from polyhost.settings import PolySettings
from polyhost.device.poly_kybd import PolyKybd
from polyhost.device.poly_kybd_mock import PolyKybdMock
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.device_manager import DeviceManager
from polyhost._version import __version__, __protocol__

from polyhost.input.unicode_input import get_input_method
from polyhost.services.sunlight_helper import Sunlight
from polyhost.services.updater import UpdateChecker, UpdateInstaller, FwUpDownloader, restart_app
from polyhost.gui.hid_fw_up_dialog import HidFwUpDialog
from polyhost.device.hid_worker import HidWorker
from polyhost.gui.worker_bridge import WorkerBridge, decide_reconnect_apply, decide_probe_publish

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

UPDATE_CYCLE_MSEC = 250
RECONNECT_CYCLE_MSEC = 1000
PERIODIC_10MIN_CYCLE_MSEC = 1000*60*10
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000

def sort_by_country_abc(item):
    return item[2:]


def get_overlay_path(filepath):
    return os.path.join(os.path.dirname(__file__), "res", "overlays", filepath)

def get_lang_and_country(combined : str):
    return combined[:2], combined[2:]


from polyhost.util.log_util import DEBUG_DETAILED, ColorFormatter, make_stream_handler, make_collapse_handler


class MultiLineFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        lines = message.splitlines()
        if len(lines)==1:
            return message.strip("\n")
        timestamp = self.formatTime(record)
        formatted_lines = [f"[{timestamp}] {line}" for line in lines[:-1]]
        return lines[0] + "\n".join(formatted_lines)


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


def _progress_dlg(label: str, title: str) -> QProgressDialog:
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
    return dlg


class PolyHost(QApplication):
    def __init__(self, log_level, debug_mode, ignore_version=False):
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

        # Add a file handler for 'b' (with a different filename)
        file_handler = RotatingFileHandler(
            filename="polykybd_console.txt",  # Separate log file for 'b'
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(MultiLineFormatter(fmt="[%(asctime)s] %(message)s"))
        self.keeb_log.addHandler(file_handler)
        self.keeb_log.propagate = False

        self.kb_sw_version = None
        self.connected = False
        self.paused = False
        self._ignore_version = ignore_version
        if ignore_version:
            self.log.warning("--ignore-version active: firmware version/protocol checks will be bypassed")
        self.poly_settings = PolySettings()
        self.device_settings = DeviceSettings()
        self.keeb = PolyKybd(self.device_settings, self.poly_settings)

        self.device_mgr = DeviceManager(self.device_settings)
        self.device_mgr.add(self.keeb, "PolyKybd", is_primary=True)
        if self.poly_settings.get("dev_mock_enabled"):
            mock = PolyKybdMock(self.device_settings, f"{__version__}")
            self.device_mgr.add(mock, "PolyKybdMock", is_primary=False)
            self.log.info("Mock device added as secondary.")

        connected = self.keeb.connect()
        self.device_mgr.connect_secondaries()
        self.device_mgr.reset_all_caches()
        if connected:
            self.log.info("Connected to PolyKybd.")
        else:
            self.log.info("Not yet connected to PolyKybd...")
        
        
        self.setApplicationName('PolyHost')

        # Persist the keyboard MRU just before the system sleeps (Linux/logind).
        self._install_sleep_listener()

        self.setQuitOnLastWindowClosed(False)
        self.is_closing = False
        self.debug_mode = debug_mode
        self._needs_overlay_reset = False

        # Create the menu
        self.log.debug("Building menu...")
        self.set_style()
        self.menu = QMenu()
        self.menu.setStyleSheet("QMenu {icon-size: 64px;} QMenu::item {icon-size: 64px; background: transparent;}")

        self.status = QAction(get_icon("sync.svg"), "Waiting for PolyKybd...", parent=self)
        self.status.setToolTip("Press to pause connection")
        # noinspection PyUnresolvedReferences
        self.status.triggered.connect(self.pause)
        self.exit = QAction(get_icon("power.svg"), "Quit", parent=self)
        # noinspection PyUnresolvedReferences
        self.exit.triggered.connect(self.quit_app)
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
        # Initial language enumeration is synchronous (runs once, before the
        # worker exists). The worker-driven reconnect path supplies the lang
        # list via the reconnect snapshot afterwards. The version query must
        # run first: enumerate_lang() gates on the firmware protocol version
        # (the packed list is protocol v2+) and it is still unknown here —
        # without it the startup enumeration always failed against protocol-2
        # firmware (seen in the field 2026-06-11).
        self.keeb.query_version_info()
        init_lang_ok, _ = self.keeb.enumerate_lang()
        init_lang_list = self.keeb.get_lang_list() if init_lang_ok else None
        init_current_lang = self.keeb.get_current_lang() if init_lang_ok else None
        self.add_supported_lang(self.menu, init_lang_list, init_current_lang)

        self.cmdMenu = CommandsSubMenu(self, self.keeb)
        self.cmdMenu.build_menu(self.menu)

        # TODO: enable/disable depending on MRU usage
        action = QAction(get_icon("overlays.svg"), "Send Shortcut Overlay...", parent=self)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.send_shortcuts)
        self.menu.addAction(action)

        self.layout_editor = QAction(get_icon("keyboard.svg"), "Configure Keymap", parent=self)
        # noinspection PyUnresolvedReferences
        self.layout_editor.triggered.connect(self.open_layout_editor)
        self.menu.addAction(self.layout_editor)
        self.menu.addAction(self.settings_dialog)
        self.menu.addAction(self.log_dialog)

        self.update_action = QAction(get_icon("sync.svg"), "Check for updates...", parent=self)
        # noinspection PyUnresolvedReferences
        self.update_action.triggered.connect(self._on_update_clicked)
        self.menu.addAction(self.update_action)
        self._pending_release = None
        self._update_checker = None
        self._update_installer = None
        self._update_progress = None
        self._await_manual_prompt = False

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

        entries = self.helper.get_languages()

        result, info = self.helper.get_current_language()
        if result:
            self.log.info("Current System Language: %s", info)
            self.current_lang = info
        else:
            self.icon_manager.set_warning("System language query not supported for this platform.", 5000)
            self.log.warning("System language query not supported for this platform: '%s'", info)

        if debug_mode>0:
            for e in entries:
                self.log.info(" - Enumerating input language %s", e)
                self.debug_lang_menu.addAction(e, self.change_system_language)

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

        self.log.debug("Read overlay mapping file...")
        self.mapping = {}
        self.read_overlay_mapping_file(os.path.join(pathlib.Path(__file__).parent.resolve(), "res/overlay-mapping.poly.yaml"))
        self.overlay_handler = OverlayHandler(self.mapping)

        self.log.debug("Get sunlight data...")
        self.sunlight = Sunlight(self.poly_settings.get("brightness_allow_online_location_lookup"), self.poly_settings.get("brightness_allow_online_irradiance_request"))

        # --- HID worker thread -------------------------------------------------
        # After __init__ completes, only the worker thread (or code holding
        # worker.exclusive()) calls into the device. The bridge marshals worker
        # on_done results back onto the Qt main thread via a queued signal.
        # _last_applied_connected is the worker-side notion of the host's last
        # applied connection state, used by _reconnect_probe to decide whether a
        # full re-query is needed. A bool read/write is atomic under the GIL:
        # the worker reads it, the main thread writes it in _apply_reconnect_result.
        self._last_applied_connected = self.connected
        # Consecutive failed probes (worker-thread only) — see decide_probe_publish.
        self._probe_fail_streak = 0
        self.bridge = WorkerBridge()
        # noinspection PyUnresolvedReferences
        self.bridge.job_done.connect(self._on_job_done)
        self.worker = HidWorker(log=self.log)
        self.worker.add_periodic("reconnect", RECONNECT_CYCLE_MSEC / 1000.0,
                                 self._reconnect_periodic)
        self.worker.add_periodic("console", UPDATE_CYCLE_MSEC / 1000.0,
                                 self._console_periodic)
        self.worker.add_periodic("brightness", PERIODIC_10MIN_CYCLE_MSEC / 1000.0,
                                 self._brightness_periodic)

        self.log.debug("Starting cyclic checks...")
        self.worker.start()
        QTimer.singleShot(UPDATE_CYCLE_MSEC * 2, self.active_window_reporter)
 

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
        
    def managed_connection_status(self):
        for action in self.menu.actions():
            action.setEnabled(self.connected and not self.paused)
        self.log_dialog.setEnabled(True)
        self.layout_editor.setEnabled(True)
        self.settings_dialog.setEnabled(True)
        self.update_action.setEnabled(True)
        self.firmware_update_action.setEnabled(self.connected)
        self.status.setEnabled(True)
        self.support.setEnabled(True)
        self.about.setEnabled(True)
        self.exit.setEnabled(True)
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
        self.paused = not self.paused
        if self.paused:
            self.status.setText("Reconnect")
            self.connected = False
            self._last_applied_connected = False
            self.status.setToolTip("")
            # suspend() is idempotent, so toggling pause while already suspended
            # (e.g. a flash holds exclusive()) is safe.
            self.worker.suspend()
        else:
            self.status.setToolTip("Press to pause connection")
            self.worker.resume()
        self.managed_connection_status()

    # ------------------------------------------------------------------
    # Reconnect: worker-side probe + main-thread apply
    # ------------------------------------------------------------------

    def _reconnect_periodic(self, cancel):
        """Worker periodic (1 s): probe the device, hand the snapshot to the
        main thread via the bridge. Skipped automatically while suspended."""
        snapshot = self._reconnect_probe(cancel)
        if snapshot is not None:
            self.bridge.job_done.emit("reconnect", snapshot)

    def _reconnect_probe(self, cancel):
        """Runs on the WORKER thread. Performs all device I/O for a reconnect
        and returns a plain dict snapshot (or None to publish nothing) — no
        Qt / PolyHost UI access.

        Only re-queries version/lang info when the probed connectivity differs
        from the host's last applied state (read atomically under the GIL)."""
        connected_now = False
        response = ""
        if self.keeb.hid is not None:
            # Flush replies that arrived after their command gave up waiting
            # (the keyboard answers late while it syncs a large overlay
            # transfer to the slave half) — otherwise they get misread as the
            # replies to this probe's queries.
            self.keeb.hid.drain_replies(timeout_ms=2)
        if self.keeb.connect():
            connected_now, response = self.keeb.query_current_lang()

        # Debounce: a busy keyboard misses probes without being disconnected.
        publish, self._probe_fail_streak = decide_probe_publish(
            connected_now, self._last_applied_connected, self._probe_fail_streak)
        if not publish:
            return None

        snapshot = {
            "connected_now": connected_now,
            "lang": response,
            "state_changed": connected_now != self._last_applied_connected,
            # Popped on every successful probe: the firmware sets the fresh-boot
            # marker on any reboot, including ones too fast for the host to see a
            # disconnect (watchdog reset, firmware apply). Consuming it only on
            # connectivity changes would leave a stale MRU cache. Not popped on a
            # failed probe so the marker survives until a probe that gets applied.
            "fresh_boot": self.keeb.pop_fresh_boot() if connected_now else False,
        }
        if not snapshot["state_changed"]:
            return snapshot

        if not connected_now:
            # Going disconnected: do NOT query version/languages — stale late
            # replies from the failed probe can make query_version_info
            # "succeed" and fake a fresh connect (cache reset + full overlay
            # resend) against a device that just failed to answer GET_LANG.
            snapshot.update({
                "version_ok": False,
                "version_msg": "Could not read reply from PolyKybd",
                "kb_version": None, "kb_proto": None, "kb_sw_version": None,
                "name": None, "hw_version": None,
                "lang_list": None, "current_lang": None,
            })
            return snapshot

        version_ok, version_msg = self.keeb.query_version_info()
        snapshot.update({
            "version_ok": version_ok,
            "version_msg": version_msg,
            "kb_version": self.keeb.get_sw_version(),
            "kb_proto": self.keeb.get_protocol_version(),
            "kb_sw_version": self.keeb.get_sw_version_number(),
            "name": self.keeb.get_name(),
            "hw_version": self.keeb.get_hw_version(),
        })
        # Enumerate languages for the menu rebuild (apply consumes the list).
        if version_ok or self._ignore_version:
            enum_ok, _ = self.keeb.enumerate_lang()
            snapshot["lang_list"] = self.keeb.get_lang_list() if enum_ok else None
            snapshot["current_lang"] = self.keeb.get_current_lang() if enum_ok else None
        else:
            snapshot["lang_list"] = None
            snapshot["current_lang"] = None
        return snapshot

    def _apply_reconnect_result(self, snapshot):
        """Runs on the MAIN thread. Reproduces the original reconnect decision
        tree exactly, then drives the language-changed flow."""
        if self.paused:
            return
        connected_now = snapshot["connected_now"]
        response = snapshot["lang"]

        if snapshot["state_changed"]:
            decision = decide_reconnect_apply(
                snapshot, __protocol__, __version__, self._ignore_version)

            # Mirror the original warning logs.
            if not snapshot["version_ok"] and self._ignore_version:
                self.log.warning(
                    "FW version string could not be parsed (%s) — continuing via --ignore-version",
                    snapshot["version_msg"])
            if "version_warning" in decision:
                expected, kb_version = decision["version_warning"]
                self.log.warning("Warning! Version mismatch, expected '%s', got '%s'.",
                                 expected, kb_version)
            if "ignore_bypass_msg" in decision:
                self.log.warning("Version/protocol mismatch bypassed via --ignore-version: %s",
                                 decision["ignore_bypass_msg"])

            self.connected = decision["connected"]
            if decision["icon"] is not None:
                self.status.setIcon(get_icon(decision["icon"]))
            if decision["text"] is not None:
                self.status.setText(decision["text"])
            if snapshot["version_ok"] or self._ignore_version:
                self.kb_sw_version = snapshot["kb_sw_version"]

            if decision["do_post_connect"]:
                self.add_supported_lang(self.menu, snapshot["lang_list"], snapshot["current_lang"])
                if connected_now and self.poly_settings.get("unicode_send_composition_mode"):
                    mode = get_input_method()
                    self.log.info("Setting unicode mode to str %s", mode)
                    # set_unicode_mode is device I/O -> worker job.
                    self.worker.submit("set_unicode_mode",
                                       lambda c, m=mode: self.keeb.set_unicode_mode(m))
                    self.update_ui_on_lang_change(response)
                self.device_mgr.reset_all_caches()
                self.overlay_handler.force_resend()
                self._needs_overlay_reset = True
                self.log.info("Connected: active window resend queued.")
                QTimer.singleShot(0, self._start_update_check)

        # The main thread now owns the applied-connection state the worker reads.
        self._last_applied_connected = self.connected
        self.managed_connection_status()
        self.icon_manager.update()

        if connected_now:
            kb_lang = response
        else:
            self.log.warning("Reconnect failed: '%s'", response if response else "NO RESPONSE")
            kb_lang = self.current_lang

        if not self.connected:
            return

        if snapshot["state_changed"] and self._needs_overlay_reset:
            self._needs_overlay_reset = False
            self.cmdMenu.reset_overlays_and_usage()
            self.log.info("Connected: overlay state cleared.")
        # Independent of state_changed: a fast reboot (no observed disconnect)
        # still must invalidate the host-side MRU cache.
        if snapshot.get("fresh_boot"):
            self.device_mgr.reset_all_caches()
            self.log.info("Firmware restart detected — overlay MRU cache reset.")

        # Language-changed flow (helper.set_language stays on the main thread).
        if kb_lang and self.current_lang != kb_lang:
            self.icon_manager.set_thinking()
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
        if lang_list is not None and current_lang is not None:
            self.current_lang = current_lang
            title = f"Selected Language: {self.current_lang[:2]} {self.langcode_to_flag(self.current_lang[2:])}"
            if self.keeb_lang_menu is None:
                # Place the language menu right under the first entry (the status
                # action) instead of appending it last. It may be created lazily
                # once the firmware version is known, by which point the rest of
                # the menu already exists, so insert rather than add.
                self.keeb_lang_menu = QMenu(title)
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
                    if lang == self.current_lang:
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
        self.layout_dialog = KbLayoutDialog(self.keeb, self.device_settings, worker=self.worker)
        self.layout_dialog.show()

    def open_settings(self):
        dlg = SettingsDialog()
        dlg.setup(self.poly_settings.get_all(), self.debug_mode)
        if dlg.exec_() == QDialog.Accepted:
            self.poly_settings.set_all(dlg.get_updated_settings())
        dlg.close()

    def open_log(self):
        # assignment is needed otherwise the dialog would go away immediately
        delta = time.perf_counter()
        self.log_viewer = LogViewerDialog({"PolyHost Log": "host_log.txt", "PolyKybd Console Log": "polykybd_console.txt"})
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

    def read_overlay_mapping_file(self, file):
        if not file:
            file = QFileDialog.getOpenFileName(None, 'Open file', '', "PolyKybd overlay mapping (*.poly.yaml)")
        if len(file) > 0:
            with open(file, 'r') as f:
                self.mapping = yaml.load(f, Loader=yaml.FullLoader)
        else:
            self.log.info("No file selected. Operation canceled.")

    def save_overlay_mapping_file(self, filename="overlay-mapping.poly.yaml"):
        with open(filename, "w") as f:
            f.write(yaml.dump(self.mapping))

    def _start_update_check(self, on_no_update=None, on_check_error=None):
        """Start a background update check.

        ``on_no_update`` is called when the check succeeds but finds no newer release.
        ``on_check_error`` is called (with a message string) when the API/network
        call itself fails — distinct from "no update available".
        Both are None for the automatic periodic check (silent failure).
        """
        if self._update_checker is not None and self._update_checker.isRunning():
            return
        self.log.debug("Starting update check...")
        fw_version = self.keeb.get_sw_version() if self.connected else None
        self._update_checker = UpdateChecker(current_fw_version=fw_version, parent=self)

        # Track whether the error signal fires before host_no_update so we can
        # suppress the "no update" callback and show the real failure reason.
        _error_seen = [False]

        def _on_error(msg):
            self.log.warning("Update check error: %s", msg)
            if not _error_seen[0] and on_check_error is not None:
                on_check_error(msg)
            _error_seen[0] = True
            # Reset firmware manual check regardless of which check failed — both
            # host and firmware errors emit the same signal, either can leave it stuck.
            if self._await_manual_fw_prompt:
                self._await_manual_fw_prompt = False
                self.firmware_update_action.setText(
                    f"Update firmware to v{self._pending_fw_release.version}…"
                    if self._pending_fw_release else "Check for firmware update…"
                )
                self.firmware_update_action.setEnabled(self.connected)

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

        # noinspection PyUnresolvedReferences
        self._update_checker.update_available.connect(self._on_update_available)
        # noinspection PyUnresolvedReferences
        self._update_checker.fw_up_available.connect(self._on_fw_up_available)
        # noinspection PyUnresolvedReferences
        self._update_checker.host_no_update.connect(_host_no_update)
        # noinspection PyUnresolvedReferences
        self._update_checker.fw_no_update.connect(_fw_no_update)
        # noinspection PyUnresolvedReferences
        self._update_checker.error.connect(_on_error)
        self._update_checker.start()

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
        if self._update_installer is not None and self._update_installer.isRunning():
            return
        if self._pending_release is not None:
            self._prompt_and_install(self._pending_release)
            return
        self.update_action.setText("Checking for updates...")
        self._await_manual_prompt = True
        self._start_update_check(
            on_no_update=self._on_manual_no_update,
            on_check_error=self._on_manual_check_error,
        )

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
        if self._update_installer is not None and self._update_installer.isRunning():
            self.log.debug("Update installer already running; ignoring re-entry")
            return

        self.update_action.setEnabled(False)
        self._update_progress = _progress_dlg(
            f"Downloading v{release.version}…", "PolyKybdHost Update")

        self._update_installer = UpdateInstaller(release, parent=self)
        # noinspection PyUnresolvedReferences
        self._update_installer.progress.connect(self._on_update_progress)
        # noinspection PyUnresolvedReferences
        self._update_installer.finished_ok.connect(self._on_update_done)
        # noinspection PyUnresolvedReferences
        self._update_installer.relay_needed.connect(self._on_relay_needed)
        # noinspection PyUnresolvedReferences
        self._update_installer.failed.connect(self._on_update_failed)
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

    def _on_balloon_clicked(self):
        if self._update_installer is not None and self._update_installer.isRunning():
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
        if self._fw_up_downloader is not None and self._fw_up_downloader.isRunning():
            return
        if self._pending_fw_release is not None:
            self._prompt_and_flash(self._pending_fw_release)
            return
        self.firmware_update_action.setText("Checking for firmware update…")
        self.firmware_update_action.setEnabled(False)
        self._await_manual_fw_prompt = True
        # No on_no_update here: the firmware result comes via _await_manual_fw_prompt
        # and the _fw_no_update closure in _start_update_check.
        self._start_update_check()

    def _on_manual_no_fw_update(self):
        self._await_manual_fw_prompt = False
        self.firmware_update_action.setText("Check for firmware update…")
        self.firmware_update_action.setEnabled(self.connected)
        fw_version = self.keeb.get_sw_version() if self.connected else "unknown"
        _msgbox(QMessageBox.Information, "PolyKybd Firmware",
                f"You are running the latest firmware (v{fw_version}).")

    def _prompt_and_flash(self, release):
        if not self.connected:
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
        if self._fw_up_downloader is not None and self._fw_up_downloader.isRunning():
            return

        self.firmware_update_action.setEnabled(False)
        self._fw_up_progress = _progress_dlg(
            f"Downloading firmware v{release.version}…", "Firmware Update")

        self._fw_up_downloader = FwUpDownloader(release, parent=self)
        # noinspection PyUnresolvedReferences
        self._fw_up_downloader.progress.connect(self._on_fw_download_progress)
        # noinspection PyUnresolvedReferences
        self._fw_up_downloader.finished.connect(self._on_fw_download_done)
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

    def quit_app(self):
        self.icon_manager.set_disconnected()
        self.is_closing = True
        # Persist the keyboard's MRU recents on a clean shutdown (the firmware
        # only writes if they changed). USB suspend covers the sleep case; this
        # covers a clean quit/logout where USB suspend may not fire. Run it
        # synchronously (short bounded wait) BEFORE stopping the worker, but never
        # let it block shutdown.
        try:
            self.worker.run_sync("save_mru", lambda c: self.keeb.save_mru(), timeout=2)
        except Exception as e:  # never let a save attempt break shutdown
            self.log.debug("MRU save request failed: %s: %s", type(e).__name__, e)
        self.worker.stop()
        self.overlay_handler.close()
        self.quit()

    def save_keeb_mru(self):
        """Best-effort request to persist the keyboard's emoji/language MRU.

        Safe to call when disconnected — the HID layer just reports failure and
        we swallow any error so shutdown/sleep is never blocked. Submitted as a
        normal worker job (device I/O stays on the worker thread)."""
        try:
            if self.keeb:
                self.worker.submit("save_mru", lambda c: self.keeb.save_mru())
        except Exception as e:  # never let a save attempt break shutdown/sleep
            self.log.debug("MRU save request failed: %s: %s", type(e).__name__, e)

    def _install_sleep_listener(self):
        """On Linux, ask systemd-logind to tell us just before the system sleeps
        so we can persist the keyboard MRU. No-op (logged) where unavailable."""
        # logind / Qt DBus is Linux-only; skip cleanly elsewhere so the QtDBus
        # import is never attempted on platforms (or minimal Qt builds) without it.
        if not sys.platform.startswith("linux"):
            self.log.debug("Sleep listener is Linux-only; skipping on %s.", sys.platform)
            return
        try:
            from PyQt5.QtDBus import QDBusConnection
            bus = QDBusConnection.systemBus()
            if not bus.isConnected():
                self.log.debug("System D-Bus not available; no sleep listener.")
                return
            ok = bus.connect(
                "org.freedesktop.login1", "/org/freedesktop/login1",
                "org.freedesktop.login1.Manager", "PrepareForSleep",
                self._on_prepare_for_sleep)
            self.log.debug("logind PrepareForSleep listener installed: %s", ok)
        except Exception as e:
            self.log.debug("Could not install sleep listener: %s: %s", type(e).__name__, e)

    # QtDBus only accepts pyqtSlot-decorated methods as signal targets — without
    # the decorator bus.connect() raises TypeError and the listener never
    # installs (seen in the field: MRU was not saved before system sleep).
    @pyqtSlot(bool)
    def _on_prepare_for_sleep(self, going_to_sleep):
        # PrepareForSleep(true) fires just before the system suspends.
        if going_to_sleep:
            self.log.info("System is about to sleep — saving keyboard MRU.")
            self.save_keeb_mru()

    # noinspection PyPep8Naming
    def closeEvent(self, _):
        self.cmdMenu.disable_overlays()

    def send_overlay_data(self, data):
        files = []
        if isinstance(data, str):
            files.append(get_overlay_path(data))
        else:
            for overlay in data:
                files.append(get_overlay_path(overlay))

        if len(files) == 0:
            return
        # Device I/O runs on the worker; coalesce_key="overlay" supersedes a
        # pending/in-flight send so rapid alt-tabbing doesn't replay transfers.
        self.icon_manager.set_thinking()
        self.worker.submit("overlay", lambda cancel: self._overlay_send_job(files, cancel),
                           coalesce_key="overlay", on_done=self._emit_done)

    def _overlay_send_job(self, files, cancel):
        """Worker-thread overlay send. Mirrors the original send_overlay_data
        body; reset/enable that accompany a send stay inside this job so
        ordering is preserved, and the cancel event is forwarded through."""
        try:
            mru_enabled = self.poly_settings.get("overlay_mru_cache_enabled")
            mock_mru_enabled = self.poly_settings.get("dev_mock_overlay_mru_cache_enabled")
            for entry in self.device_mgr.all_entries:
                if cancel.is_set():
                    return
                use_mru = entry.cache is not None and (
                    (entry.is_primary and mru_enabled) or
                    (not entry.is_primary and mock_mru_enabled)
                )
                if use_mru:
                    entry.device.send_overlays_mru(files, entry.cache, cancel)
                else:
                    entry.device.reset_overlays_and_usage()
                    entry.device.send_overlays(files, cancel)
        except Exception as e:
            msg = f"Failed to send overlays '{files}': {e}"
            self.log.warning(msg)
            # Runs on the worker thread — the tray icon update must hop to the
            # main thread via the bridge (set_warning touches Qt objects).
            self.bridge.job_done.emit("overlay_warning", msg)

        self.keeb.set_idle(False)

    def _overlay_cmd_job(self, cmd, cancel):
        """Worker-thread enable/disable of overlays on every device entry."""
        for entry in self.device_mgr.all_entries:
            if cancel.is_set():
                return
            if cmd == OverlayCommand.DISABLE:
                entry.device.disable_overlays()
            elif cmd == OverlayCommand.ENABLE:
                entry.device.enable_overlays()

    def _emit_done(self, name, result):
        """Worker-thread on_done shim: forward to the main thread via the bridge."""
        self.bridge.job_done.emit(name, result)

    def active_window_reporter(self):
        # Main-thread timer: NO device I/O. Window tracking (pywinctl) stays here;
        # everything that touches HID is submitted to the worker.
        if self.connected:
            data, cmd = self.overlay_handler.handle_active_window(
                UPDATE_CYCLE_MSEC, NEW_WINDOW_ACCEPT_TIME_MSEC)
            if cmd in (OverlayCommand.DISABLE, OverlayCommand.ENABLE):
                self.worker.submit("overlay", lambda c, cmd=cmd: self._overlay_cmd_job(cmd, c),
                                   coalesce_key="overlay")
            if data and cmd == OverlayCommand.OFF_ON:
                self.send_overlay_data(data)
        elif self.poly_settings.get("dev_run_window_detection_if_not_connected_to_poly_kybd"):
            self.overlay_handler.handle_active_window(UPDATE_CYCLE_MSEC, NEW_WINDOW_ACCEPT_TIME_MSEC)

        if not self.is_closing:
            QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)

    # ------------------------------------------------------------------
    # Worker periodics (console/serial reads, brightness) + result dispatch
    # ------------------------------------------------------------------

    def _console_periodic(self, cancel):
        """Worker periodic (250 ms): read serial + console; deliver via bridge."""
        kb_serial = self.keeb.read_serial()
        kb_log = self.keeb.get_console_output()
        if kb_serial or kb_log:
            self.bridge.job_done.emit("console", (kb_serial, kb_log))

    def _brightness_periodic(self, cancel):
        """Worker periodic (10 min): daylight-dependent brightness incl. the
        network lookups — kept entirely off the GUI thread."""
        if self.poly_settings.get("brightness_set_daylight_dependent"):
            min_val = self.poly_settings.get("irradiance_min")
            max_val = self.poly_settings.get("irradiance_max")
            prescaler = self.poly_settings.get("irradiance_prescaler")
            brightness = self.sunlight.get_brightness_now(min_val, max_val, prescaler)
            self.keeb.set_brightness(2 + brightness * 48)

    def _on_job_done(self, name, result):
        """Main-thread slot for the bridge's job_done signal."""
        if name == "reconnect":
            self._apply_reconnect_result(result)
        elif name == "console":
            kb_serial, kb_log = result
            if kb_serial:
                self.log.info("Received serial communication: %s", kb_serial)
            if kb_log:
                self.keeb_log.info(kb_log)
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
