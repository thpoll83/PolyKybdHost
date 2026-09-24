import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import subprocess
import sys
import threading
import time

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
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
    QProgressDialog,
    QSizePolicy,
    QStyle,
    QVBoxLayout, )

from polyhost.core.events import flash_kind_label
from polyhost.device.command_ids import IdleStyle, IdleTimeout, GlyphScript, GlyphSize
from polyhost.gui.file_dialogs import get_open_file_name
from polyhost.gui.get_icon import get_icon
from polyhost.services import log_bundle
from polyhost.gui.theme import apply_theme
from polyhost.services import os_theme
from polyhost.services.os_theme import THEME_AUTO
from polyhost.settings import read_setting
from polyhost.gui.update_ui import UpdateProgressController
from polyhost.gui.update_dialog import confirm_update
from polyhost.gui.tray_notify import (balloons_are_delivered, updates_menu_title,
                                      updates_tooltip)

# Tray labels for the Glyph Script submenu. Generic names (no franchise
# branding — trademark caveat on the fictional scripts); the fonts themselves
# are OK to embed. Keys cover every GlyphScript so the menu builds from the enum.
GLYPH_SCRIPT_LABELS = {
    GlyphScript.STANDARD: "Standard (normal legends)",
    GlyphScript.TENGWAR:  "Tengwar (fantasy)",
    GlyphScript.RUNES:    "Elder Futhark runes",
    GlyphScript.AUREBESH: "Aurebesh (sci-fi)",
    GlyphScript.SGA:      "Standard Galactic",
    GlyphScript.CIRTH:    "Cirth / Angerthas",
    GlyphScript.IBMVGA:   "IBM VGA / CP437",
    GlyphScript.C64:      "Commodore 64",
    GlyphScript.AMIGA:    "Amiga Topaz",
    GlyphScript.APL:      "APL",
    GlyphScript.BRAILLE:  "Braille",
}

# Keys cover every GlyphSize so the menu builds from the enum. Worded as what the
# user sees on the keycap, not as the internal enum name.
GLYPH_SIZE_LABELS = {
    GlyphSize.SMALL:  "Small (standard)",
    GlyphSize.MEDIUM: "Medium",
    GlyphSize.LARGE:  "Large",
}
from polyhost.gui.icon_state_manager import IconStateManager
from polyhost.gui.qt_crash import install_qt_message_handler
from polyhost.gui.tray_wait import TrayVisibilityWaiter
from polyhost.gui.log_viewer import LogViewerDialog
from polyhost.gui.layout_dialog.kb_layout_dialog import KbLayoutDialog
from polyhost.gui.settings_dialog import SettingsDialog
from polyhost.gui.cmd_menu import CommandsSubMenu
from polyhost.input.linux_gnome_helper import LinuxGnomeInputHelper
from polyhost.input.linux_kde_helper import LinuxPlasmaHelper
from polyhost.input.macos_helper import MacOSInputHelper
from polyhost.input.win_helper import WindowsInputHelper
from polyhost.input.unicode_input import wincompose_running
from polyhost.services import wincompose_install
from polyhost.services.lang_regions import LANG_REGION, LANG_REGION_ORDER, LANG_REGION_OVERRIDE
from polyhost.services.unicode_cache import UnicodeCache
from polyhost._version import __version__, __protocol__

from polyhost.services.updater import (
    UpdateChecker, UpdateInstaller, FwUpDownloader, discard_fw_download,
    AUTO_CHECK_INTERVAL_S, claim_automatic_check)
from polyhost.gui.hid_fw_up_dialog import HidFwUpDialog
from polyhost.gui.dialog_util import bring_to_front, position_near_tray
from polyhost.gui import about_dialog
from polyhost.gui.worker_bridge import WorkerBridge
from polyhost.server.control_server import ControlServer

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

# The project links surfaced in the About dialog live in gui/about_dialog
# (PROJECT_LINKS) — the forwarder builds its About from the same module, and a
# second hand-kept copy of those URLs is how one of the two goes stale.

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


def _progress_dlg(label: str, title: str, tray_icon=None, on_cancel=None) -> QProgressDialog:
    dlg = QProgressDialog(label, None, 0, 100, None)
    dlg.setWindowTitle(title)
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    if on_cancel is not None:
        # Keep the dialog on screen after Cancel is pressed (showing "Cancelling…")
        # until the worker actually stops and the caller closes it.
        dlg.setAutoReset(False)
        dlg.setCancelButtonText("Cancel")
        dlg.canceled.connect(on_cancel)
    else:
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
    def __init__(self, log_level, verbosity=0, developer=False, ignore_version=False,
                 client_mode=False, endpoint=None, connect_retry=False):
        super().__init__(sys.argv)
        # Wall-clock start, for the About dialog's uptime line.
        self._start_time = time.monotonic()
        # Per-feature support of the connected firmware (feature -> bool), cached
        # from the reconnect/status payload so feature submenus can be gated by the
        # device's protocol, not just by connectivity. See self.supports().
        self._capabilities = {}
        # Newer-firmware dialog bookkeeping (see _maybe_prompt_newer_firmware):
        # remember which protocol we've already prompted for so the ~1 s reconnect
        # probe can't re-raise the modal, and guard against stacking it.
        self._newer_fw_prompt_open = False
        self._newer_fw_prompted_proto = None
        # The Developer submenu (created only in developer mode), kept reachable
        # so it stays enabled in newer-firmware safe mode. None when off.
        self._developer_menu = None
        # Tray-only app: keep it out of the macOS Dock (no-op elsewhere).
        from polyhost.util.macos_ui import hide_dock_icon
        hide_dock_icon()
        # ⚠️ Directly after it, because it is the COST of the line above: an
        # accessory app is never promoted to active by opening a window, so
        # without this every dialog the tray opens lands behind whatever the
        # user was in. One filter rather than a call at each `show()` -- there
        # are a dozen sites across the two apps and `.exec_()` modals among
        # them. See `gui.dialog_util.install_front_on_show`.
        from polyhost.gui.dialog_util import install_front_on_show
        install_front_on_show(self)
        # `verbosity` is the log level knob (--dev N); `developer` is the feature
        # surface (the --dev flag, else the persisted developer_mode setting) —
        # the two are deliberately separate, so the settings toggle can reveal the
        # developer tools without also turning the log to DEBUG.
        fmt = "[%(asctime)s] %(levelname)-7s {%(filename)s:%(lineno)d} %(message)s" if verbosity>0 else "[%(asctime)s] %(levelname)-7s %(message)s"
        level = DEBUG_DETAILED if verbosity>1 else log_level

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
        # Qt's own diagnostics (including the qFatal message PyQt emits just
        # before aborting on an unhandled exception in a slot) go to stderr,
        # which is /dev/null under pythonw. Route them here instead.
        install_qt_message_handler(self.log)

        # Create the tray. Showing it is deliberately NOT unconditional: at
        # logon the notification area may not exist yet, and an icon added then
        # is lost for the WHOLE session (see gui/tray_wait.py). The waiter shows
        # it now when it can and retries when it can't.
        self.tray = QSystemTrayIcon(parent=self)
        # The tray's resting tooltip, and what _refresh_tray_tooltip falls back
        # to once a flash or a pending update stops claiming it.
        self._idle_tooltip = f"PolyKybdHost {__version__}"
        self.icon_manager = IconStateManager(self, False, self._idle_tooltip)
        self._tray_waiter = TrayVisibilityWaiter(
            show=lambda: self.tray.setVisible(True),
            is_available=QSystemTrayIcon.isSystemTrayAvailable,
            log=self.log)
        self._tray_waiter.start()

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
                                 allow_key_injection=developer)
            self.keeb = self.core.keeb
            self.worker = self.core.worker
            self.device_mgr = self.core.device_mgr
            self.poly_settings = self.core.poly_settings
            self.device_settings = self.core.device_settings
            self.overlay_handler = self.core.overlay_handler
        self.core.subscribe(self._on_core_event)
        # NOTE: there is deliberately no first-run telemetry dialog — a modal on
        # every upgrade is a poor trade for a disclosure that arrives after the
        # install. Rationale and the disclosure surface: docs/telemetry.md.

        self.setApplicationName('PolyHost')

        self.setQuitOnLastWindowClosed(False)
        self.is_closing = False
        # Set when a self-update lands: main_app re-execs after exec_() returns
        # (clean, fully-unwound loop) instead of os.execv from inside a slot.
        self.wants_restart = False
        self.developer_mode = developer

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
            self.exit_with_daemon = QAction(get_icon("power_off.svg"),
                                            "Quit && stop background daemon", parent=self)
            # noinspection PyUnresolvedReferences
            self.exit_with_daemon.triggered.connect(self.quit_app_and_daemon)
        # "Get Support" is no longer a separate menu item — its Discord link now
        # lives in the About dialog (keeps the tray menu shorter).
        self.about = QAction(get_icon("info.svg"), "About", parent=self)
        # noinspection PyUnresolvedReferences
        self.about.triggered.connect(self.show_about_dialog)

        self.settings_dialog = QAction(get_icon("settings.svg"), "Settings...", parent=self)
        # noinspection PyUnresolvedReferences
        self.settings_dialog.triggered.connect(self.open_settings)

        self.log_dialog = QAction(get_icon("log.svg"), "Log file...", parent=self)
        # noinspection PyUnresolvedReferences
        self.log_dialog.triggered.connect(self.open_log)
        self.log_viewer = None

        # The guided path: describe the problem, bundle the logs, open a
        # pre-filled issue. "Collect logs..." below is the manual half, for when
        # someone already knows where they are sending the file.
        self.report_problem_action = QAction(get_icon("feedback.svg"),
                                             "Report a Problem...", parent=self)
        # noinspection PyUnresolvedReferences
        self.report_problem_action.triggered.connect(self.open_report_problem)
        self.report_problem_dialog = None
        self.crash_alert_dialog = None

        # "Send me your log" is otherwise a request nobody can satisfy: the logs
        # are five rotating files in the working directory, and in daemon mode
        # the half that matters is the daemon's, not this process's.
        self.collect_logs_action = QAction(get_icon("archive.svg"),
                                           "Collect logs...", parent=self)
        # noinspection PyUnresolvedReferences
        self.collect_logs_action.triggered.connect(self.open_log_bundle)
        self.log_bundle_dialog = None

        self.fontpack_inspector_action = QAction(get_icon("frame_inspect.svg"), "Inspect Font Packs...", parent=self)
        # noinspection PyUnresolvedReferences
        self.fontpack_inspector_action.triggered.connect(self.open_fontpack_inspector)

        self.current_lang = None
        self.keeb_lang_menu = None
        self.debug_lang_menu = None

        self.unicode_cache = UnicodeCache()
        #self.reconnect()
        self.menu.addAction(self.status)
        # Pause used to be reachable ONLY by clicking the status line, advertised
        # by a tooltip nobody reads. Explicit entry; the status click still works.
        self.pause_action = QAction(get_icon("pause_circle.svg"), "Pause", parent=self)
        # noinspection PyUnresolvedReferences
        self.pause_action.triggered.connect(self.pause)
        self.menu.addAction(self.pause_action)
        # Newer firmware than this host: the choice is a session policy taken in a
        # modal that fires once per protocol. Without a way back, a user who picked
        # (or dismissed into) safe mode was stuck with it until a restart. This
        # entry re-opens the same dialog and is VISIBLE ONLY while safe mode is on,
        # so it costs nothing in the normal menu.
        self.newer_fw_action = QAction(get_icon("sync_problem.svg"),
                                       "Firmware newer than this app \u2014 safe mode\u2026",
                                       parent=self)
        self.newer_fw_action.setToolTip("Choose how to handle a keyboard whose firmware "
                                        "is newer than this host app.")
        # noinspection PyUnresolvedReferences
        self.newer_fw_action.triggered.connect(self._on_newer_fw_action)
        self.newer_fw_action.setVisible(False)
        self.menu.addAction(self.newer_fw_action)
        self.menu.addSeparator()
        # No synchronous language enumeration here: self.connected is still
        # False at this point (only the reconnect decision tree may set it —
        # that's where the protocol/version gate lives), so the first worker
        # probe always sees a False→True transition and runs the full fresh-
        # connect flow anyway: enumerate_lang + add_supported_lang + unicode
        # mode + cache reset. Enumerating here as well just did all of that
        # twice within the first second (double menu build seen in the field
        # 2026-06-13). The language menu inserts itself at the top of the
        # device group when it is created, so arriving ~1 s late costs nothing.

        # Device commands live in two places now: the small set a normal user
        # needs (Maintenance, below) and the diagnostic/bulk rest under Developer.
        # Both are built by CommandsSubMenu, which routes every action through the
        # core (worker job in-process, RPC in client mode) so they work in both
        # modes (H4a-2c).
        self.cmdMenu = CommandsSubMenu(self)

        # Brightness: promoted out of the old "All PolyKybd Commands" list — it is
        # the most-used device control and sat three levels deep.
        self.brightness_menu = self.cmdMenu.build_brightness_menu(self.menu)
        # The language menu is built lazily (see add_supported_lang) and inserts
        # itself before this anchor, so it lands at the top of the device group
        # rather than wherever the menu happened to end.
        self._lang_anchor = self.brightness_menu.menuAction()

        # Idle display style (firmware v4+). Device-coupled: it drives the device
        # through core.get/set_idle_style (worker run_sync in-process, RPC in
        # client mode), so it works in both modes; managed_connection_status greys
        # the whole submenu out while disconnected or on too-old firmware.
        self.idle_style_menu = self.menu.addMenu(get_icon("bedtime.svg"), "Idle Display")
        idle_group = QActionGroup(self)
        idle_group.setExclusive(True)
        self.idle_pulse_action = QAction("Pulse (legacy)", parent=self, checkable=True)
        self.idle_pulse_action.setData(IdleStyle.PULSE.value)
        self.idle_jitter_action = QAction("Jitter (move legend)", parent=self, checkable=True)
        self.idle_jitter_action.setData(IdleStyle.JITTER.value)
        # Attract-demo screensaver: needs doom-enabled firmware — an unsupported
        # keyboard NACKs the set, surfaced by change_idle_style's error path.
        self.idle_iddqd_action = QAction("IDDQD (attract demo)", parent=self, checkable=True)
        self.idle_iddqd_action.setData(IdleStyle.IDDQD.value)
        # Eden screensaver: loops the boot animation (split72 only; a no-op that
        # behaves like Pulse on split42).
        self.idle_eden_action = QAction("Eden", parent=self, checkable=True)
        self.idle_eden_action.setData(IdleStyle.EDEN.value)
        for act in (self.idle_pulse_action, self.idle_jitter_action, self.idle_iddqd_action,
                    self.idle_eden_action):
            idle_group.addAction(act)
            # noinspection PyUnresolvedReferences
            act.triggered.connect(self.change_idle_style)
            self.idle_style_menu.addAction(act)
        # noinspection PyUnresolvedReferences
        self.idle_style_menu.aboutToShow.connect(self.refresh_idle_style_menu)

        # Idle TIMEOUT (firmware v18+): how long before the style above engages.
        # NESTED inside "Idle Display" rather than added as a twelfth top-level row:
        # the tray's normal tier is a deliberately short list whose exact shape
        # tests/gui/host_client_test.py pins, and "which idle animation" and "how
        # long until it starts" are the same question asked twice. It carries its
        # OWN protocol gate below, because a keyboard can support the styles (v4+)
        # and not the timeout (v18+), in which case this one submenu greys out and
        # the styles above it keep working.
        self.idle_style_menu.addSeparator()
        self.idle_timeout_menu = self.idle_style_menu.addMenu("Idle After")
        idle_timeout_group = QActionGroup(self)
        idle_timeout_group.setExclusive(True)
        self.idle_timeout_actions = []
        for preset in IdleTimeout:
            act = QAction(preset.label, parent=self, checkable=True)
            act.setData(preset.value)
            idle_timeout_group.addAction(act)
            # noinspection PyUnresolvedReferences
            act.triggered.connect(self.change_idle_timeout)
            self.idle_timeout_menu.addAction(act)
            self.idle_timeout_actions.append(act)
        # noinspection PyUnresolvedReferences
        self.idle_timeout_menu.aboutToShow.connect(self.refresh_idle_timeout_menu)

        # Glyph-script override (firmware v9+). Same device-coupled pattern as the
        # idle style. Named "Keycap Script" in the menu: "glyph script" is our
        # internal vocabulary, what the user sees is the letters on their keycaps.
        # "Standard" restores the normal language legends; the others override the
        # letter/digit legends with an alternative script (from the fantasy bundle).
        self.glyph_script_menu = self.menu.addMenu(get_icon("text_fields.svg"), "Keycap Script")
        glyph_group = QActionGroup(self)
        glyph_group.setExclusive(True)
        # One radio entry per GlyphScript (labels in GLYPH_SCRIPT_LABELS). Built
        # from the enum so new scripts appear automatically.
        self.glyph_actions = {}
        for script in GlyphScript:
            act = QAction(GLYPH_SCRIPT_LABELS[script], parent=self, checkable=True)
            act.setData(script.value)
            glyph_group.addAction(act)
            # noinspection PyUnresolvedReferences
            act.triggered.connect(self.change_glyph_script)
            self.glyph_script_menu.addAction(act)
            self.glyph_actions[script.value] = act
            if script is GlyphScript.STANDARD:
                self.glyph_script_menu.addSeparator()
        # Each entry previews its own script (icon + a bigger sample on hover),
        # drawn from the shipped fantasy bundle — built on the first show, not
        # here, so a user who never opens the submenu pays nothing at startup.
        self.glyph_script_menu.setToolTipsVisible(True)
        self._glyph_previews_built = False
        # noinspection PyUnresolvedReferences
        self.glyph_script_menu.aboutToShow.connect(self.refresh_glyph_script_menu)

        # Keycap legend size (firmware v13+). Same device-coupled radio pattern.
        # It sizes a key's MAIN legend only — the shift/AltGr previews stay put —
        # and the bigger faces are latin, from the `latinbig` font-pack bundle; a
        # keycap they do not cover keeps drawing at the small size.
        self.glyph_size_menu = self.menu.addMenu(get_icon("format_size.svg"), "Keycap Size")
        size_group = QActionGroup(self)
        size_group.setExclusive(True)
        self.glyph_size_actions = {}
        for size in GlyphSize:
            act = QAction(GLYPH_SIZE_LABELS[size], parent=self, checkable=True)
            act.setData(size.value)
            size_group.addAction(act)
            # noinspection PyUnresolvedReferences
            act.triggered.connect(self.change_glyph_size)
            self.glyph_size_menu.addAction(act)
            self.glyph_size_actions[size.value] = act
        # noinspection PyUnresolvedReferences
        self.glyph_size_menu.aboutToShow.connect(self.refresh_glyph_size_menu)

        # The layout editor is device-independent of the in-process worker — it
        # drives the device through core.keymap_* (RPC in client mode), so it
        # works in either mode (H4a-2).
        self.layout_editor = QAction(get_icon("keyboard.svg"), "Configure Keymap", parent=self)
        # noinspection PyUnresolvedReferences
        self.layout_editor.triggered.connect(self.open_layout_editor)
        self.menu.addAction(self.layout_editor)

        self.menu.addSeparator()

        # --- Updates: every "get something newer" path in one place -------------
        self.updates_menu = self.menu.addMenu(get_icon("update.svg"), "Updates")

        self.update_action = QAction(get_icon("browser_updated.svg"), "Check for host update...", parent=self)
        # noinspection PyUnresolvedReferences
        self.update_action.triggered.connect(self._on_update_clicked)
        self.updates_menu.addAction(self.update_action)
        self._pending_release = None
        # Versions already offered through the no-balloon fallback dialog this
        # session. The 24 h timer re-reports the same release, and a modal that
        # reopens on its own is worse than the silence it replaces.
        self._auto_prompted_host_version = None
        self._auto_prompted_fw_version = None
        # One check reports host THEN firmware, and a modal dialog dispatches
        # the second event while the first is open — see _fallback_prompt.
        self._fallback_prompt_busy = False
        self._fallback_prompt_queue = []
        self._update_checker = None
        # A firmware check asked for while a host-only check was in flight;
        # `_on_update_check_finished` runs it once that check ends.
        self._update_check_fw_retry = False
        self._update_installer = None
        self._update_ui = UpdateProgressController(self.log)
        self._await_manual_prompt = False
        # Per-check closures wired up by _start_update_check; invoked from the Qt
        # main thread via the bridge (see _on_job_done) since the checker
        # callbacks fire on its worker thread.
        self._update_check_error = None
        self._update_host_no_update = None
        self._update_fw_no_update = None


        # The keyboard-firmware release flow checks GitHub for a newer release,
        # downloads the .bin, then flashes it. In CLIENT mode the GUI has no
        # local HID, so the download still happens here (network only) but the
        # flash is handed to the daemon over the fw.flash RPC — the temp .bin is
        # on the same machine, so the daemon can read it (see _on_fw_download_done).
        # Available in both modes as of the daemon-default regression fix.
        self.firmware_update_action = QAction(get_icon("memory.svg"),
                                              "Check for keyboard firmware update\u2026", parent=self)
        # noinspection PyUnresolvedReferences
        self.firmware_update_action.triggered.connect(self._on_fw_up_clicked)
        self.updates_menu.addAction(self.firmware_update_action)

        # Keyboard fonts. The comparison is LOCAL (cached GET_ID block vs the
        # shipped manifest, no device I/O), so the entry can label itself with the
        # answer on open instead of hiding it behind a status dialog nobody opens.
        self.fontpack_update_action = QAction(get_icon("font_download.svg"),
                                              "Keyboard fonts", parent=self)
        # noinspection PyUnresolvedReferences
        self.fontpack_update_action.triggered.connect(self._on_sync_fontpack_clicked)
        self.updates_menu.addAction(self.fontpack_update_action)
        # noinspection PyUnresolvedReferences
        self.updates_menu.aboutToShow.connect(self._refresh_fontpack_action)
        self._pending_fw_release = None
        # The tray tooltip has TWO writers (a font-pack flash's percentage and
        # the pending-update marker). This holds the flash's claim; see
        # _refresh_tray_tooltip, which is the only place that calls setToolTip.
        self._fontpack_flashing = False
        self._fontpack_tooltip = ""
        self._fw_up_downloader = None
        self._fw_up_progress = None
        # Mutable one-element cancel flag shared with the firmware-download thread
        # (set True to abort the GitHub .bin download); None while no download runs.
        self._fw_download_cancel = None
        self._await_manual_fw_prompt = False
        # Set in client mode to the downloaded temp .bin that the daemon flashes
        # asynchronously — cleaned up on the terminal flash event (_on_flash_done).
        self._pending_fw_tmp_path = None

        # WinCompose is what gives the keyboard full unicode output on Windows
        # (see polyhost/input/unicode_input.py). Offer to install our build when
        # it isn't running — hidden on every other OS and once it IS running.
        # Network + a local installer only, so it works in client mode too.
        self.wincompose_action = None
        self._wincompose_downloader = None
        self._wincompose_progress = None
        self._wincompose_cancel = None
        self._wincompose_was_running = None
        if platform.system() == "Windows":
            self.wincompose_action = QAction(get_icon("arrow_circle_down.svg"),
                                             "Install WinCompose\u2026", parent=self)
            # noinspection PyUnresolvedReferences
            self.wincompose_action.triggered.connect(self._on_install_wincompose_clicked)
            self.wincompose_action.setVisible(False)   # until the first probe
            self.updates_menu.addAction(self.wincompose_action)
            # Re-probe each time the tray menu opens: the entry must disappear
            # once WinCompose is installed and running (and reappear if it is
            # quit), without polling in the background.
            # noinspection PyUnresolvedReferences
            self.menu.aboutToShow.connect(self._refresh_wincompose_action)

        # The OS theme can change while the tray sits there for weeks, so
        # re-follow it whenever the menu opens — that is when a mismatch is on
        # screen, and the check is a registry read (a cached one elsewhere).
        # noinspection PyUnresolvedReferences
        self.menu.aboutToShow.connect(self._refresh_theme)

        # --- Maintenance: the rare-but-legitimate repair actions ---------------
        self.cmdMenu.build_maintenance_menu(self.menu)

        # --- Developer: everything diagnostic / bulk, off by default -----------
        if developer:
            debug_menu = self.menu.addMenu(get_icon("bug_report.svg"), "Developer")
            self._developer_menu = debug_menu
            self.debug_lang_menu = debug_menu.addMenu(get_icon("translate.svg"), "Change System Input Language")
            # Font-pack inspector: offline tool (no device needed), so it's
            # available in both modes — kept behind developer mode.
            debug_menu.addAction(self.fontpack_inspector_action)
            if not self.client_mode:
                # MRU inspector + mock dump read the in-process device_mgr.
                mru_action = QAction(get_icon("history.svg"), "Inspect MRU Cache...", parent=self)
                # noinspection PyUnresolvedReferences
                mru_action.triggered.connect(self.open_mru_inspector)
                debug_menu.addAction(mru_action)
                dump_action = QAction(get_icon("image.svg"), "Dump Mock Bitmaps...", parent=self)
                # noinspection PyUnresolvedReferences
                dump_action.triggered.connect(self.dump_mock_bitmaps)
                debug_menu.addAction(dump_action)
            # Re-run the two things the app normally does by itself, for when the
            # environment changed under it (a fresh WinCompose install; an MRU
            # cache you want on disk before pulling the plug).
            unicode_action = QAction(get_icon("translate.svg"),
                                     "Refresh unicode input mode", parent=self)
            # noinspection PyUnresolvedReferences
            unicode_action.triggered.connect(self._refresh_unicode_mode_clicked)
            debug_menu.addAction(unicode_action)
            mru_save_action = QAction(get_icon("history.svg"), "Save MRU cache now", parent=self)
            # noinspection PyUnresolvedReferences
            mru_save_action.triggered.connect(self._save_mru_clicked)
            debug_menu.addAction(mru_save_action)

            debug_menu.addSeparator()
            # The device-command half that no normal user should meet: overlay
            # resets, idle start/stop, font-pack wipe, staged-firmware handling.
            self.cmdMenu.build_developer_menus(debug_menu)

        self.menu.addSeparator()
        self.menu.addAction(self.settings_dialog)

        # --- Help & About: the read-only, always-available corner --------------
        self.help_menu = self.menu.addMenu(get_icon("help.svg"), "Help && About")
        self.help_menu.addAction(self.about)
        self.help_menu.addAction(self.report_problem_action)
        self.help_menu.addAction(self.log_dialog)
        self.help_menu.addAction(self.collect_logs_action)
        # settings.yaml + overlay-mapping.poly.yaml live in a platformdirs path
        # nobody can guess; editing a mapping meant reading it out of About first.
        self.open_config_action = QAction(get_icon("file_open.svg"),
                                          "Open config folder", parent=self)
        # noinspection PyUnresolvedReferences
        self.open_config_action.triggered.connect(self._open_config_folder)
        self.help_menu.addAction(self.open_config_action)

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
            self.log.info(
                "macOS: PolyKybd needs 'Input Monitoring' (HID access to the "
                "keyboard) and 'Accessibility' (Unicode input + window tracking) "
                "in System Settings > Privacy & Security. This is a one-time grant "
                "(see the macOS permissions note in the README).")

        if not self.helper:
            self.log.error("Unsupported OS! Exiting...")
            sys.exit(-1)
        self.log.info("Input helper: %s", type(self.helper).__name__)

        # Detecting the OS input language shells out to PowerShell on Windows
        # (each cold powershell.exe start is hundreds of ms) — and it's only
        # needed once a keyboard connects (OS-language sync), not to show the
        # tray. Probe it on a background thread and apply the result on the Qt
        # main thread via the bridge, so the tray appears immediately.
        threading.Thread(target=self._probe_input_language, args=(developer,),
                         name="input-language-probe", daemon=True).start()

        self.managed_connection_status()
        
        self.log.debug("Display tray...")
        # Add the menu to the tray
        # self.tray.activated.connect(self.on_activated)
        self.tray.setContextMenu(self.menu)
        # noinspection PyUnresolvedReferences
        self.tray.messageClicked.connect(self._on_balloon_clicked)
        if not self._balloons_reach_user():
            self.log.info("Tray balloons are not delivered on this platform; "
                          "update prompts open directly and the Updates menu "
                          "row carries the version.")
        # Re-assert now that the icon has its menu; a no-op while the waiter is
        # still waiting, so this can never start a second retry chain.
        self._tray_waiter.start()

        QTimer.singleShot(15_000, self._start_update_check)
        self._update_timer = QTimer(self)
        # noinspection PyUnresolvedReferences
        self._update_timer.timeout.connect(self._start_update_check)
        # The same interval as the throttle, so a session that stays up learns
        # of a release within 6 h rather than 24. The throttle keeps a restart
        # or a reconnect in between from costing a request.
        self._update_timer.start(int(AUTO_CHECK_INTERVAL_S * 1000))

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
            self.core.start_telemetry()
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
    def safe_mode(self):
        """Newer-firmware restricted mode (core is the source of truth; RemoteCore
        mirrors it from the daemon's status)."""
        return getattr(self.core, "safe_mode", False)

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
        """Fusion, dark or light per the OS — shared with PolyForwarder
        (gui/theme.py). `ui_theme` ('auto' by default) overrides the desktop."""
        self._theme = apply_theme(self, read_setting("ui_theme", THEME_AUTO))

    def _refresh_theme(self):
        """Re-follow the OS theme, so switching the desktop to light does not
        need a restart. Called when the tray menu opens (the moment a mismatch
        is visible) and after the settings dialog, which can change `ui_theme`.

        A palette change propagates to the open widgets by itself; the
        glyph-script previews do not, because they are rendered pixmaps whose
        ink was picked for the old palette — so drop them and let the submenu
        rebuild them on its next show."""
        os_theme.forget_detected()
        theme = apply_theme(self, read_setting("ui_theme", THEME_AUTO))
        if theme != getattr(self, "_theme", None):
            self.log.info("Switched to the %s theme.", theme)
            self._theme = theme
            self._glyph_previews_built = False
            for act in self.glyph_actions.values():
                act.setIcon(QIcon())

    @property
    def _update_progress(self):
        """The live update progress dialog, owned by ``_update_ui``.

        A property (rather than a second attribute) so the controller stays the
        single owner and the two can never disagree about whether a dialog is
        up — the bug shape that leaves a modal progress dialog on screen after
        the update it was tracking has finished."""
        return self._update_ui.dialog

    @_update_progress.setter
    def _update_progress(self, dialog):
        self._update_ui.dialog = dialog

    def _fw_actions_allowed(self):
        """Firmware flash/apply must stay reachable whenever a device is
        present — including on a protocol/version mismatch, which is exactly
        when the user needs to update. The HID flash protocol (hid_fw_up) is
        dispatched independently of PROTOCOL_VERSION in the firmware, so it
        only needs a present device, not a compatible one."""
        return (self.connected or self.device_present) and not self.paused

    def supports(self, feature):
        """Whether the connected firmware's protocol supports ``feature``.

        Reads the capabilities cached from the reconnect/status payload
        (``poly_kybd.FEATURE_MIN_PROTOCOL`` names). Used to gate feature submenus
        by the device's protocol now that a protocol-mismatched keyboard still
        connects — a feature its firmware is too old for is hidden/disabled rather
        than only erroring on click. Works identically in-process and client mode."""
        return bool(self._capabilities.get(feature))

    def _maybe_prompt_newer_firmware(self, pending, proto, name, fw):
        """Raise the newer-firmware dialog when the core reports an undecided
        newer-firmware state (``newer_fw_pending``). Shown once per protocol per
        session — the guard stops the ~1 s reconnect probe re-raising it, and a
        different (newly flashed) protocol re-prompts. Driven off the status payload
        so it works in-process and in --connect client mode alike."""
        if (not pending or proto is None
                or self._newer_fw_prompt_open
                or self._newer_fw_prompted_proto == proto):
            return
        self._newer_fw_prompted_proto = proto
        self._newer_fw_prompt_open = True
        try:
            from polyhost.gui.newer_firmware_dialog import confirm_newer_firmware
            choice = confirm_newer_firmware(__protocol__, proto, name, fw)
        finally:
            self._newer_fw_prompt_open = False
        if choice == "update":
            # Look for a host-app update that matches the firmware; if none is
            # found (or the check errors), fall back to safe mode. force=True so a
            # throttled auto-check doesn't swallow our callbacks.
            started = self._start_update_check(
                on_no_update=lambda: self.core.set_newer_firmware_policy("safe"),
                on_check_error=lambda _msg=None: self.core.set_newer_firmware_policy("safe"),
                force=True)
            if not started:
                self.core.set_newer_firmware_policy("safe")
        else:
            # "ignore" -> connect fully; "safe" (or dismissed) -> stay restricted.
            self.core.set_newer_firmware_policy(choice if choice == "ignore" else "safe")

    def _on_newer_fw_action(self):
        """Re-open the newer-firmware choice from the tray (see the menu entry).

        Clears the once-per-protocol guard first so the shared prompt path runs
        again, and drives it off the CURRENT status rather than a remembered
        payload — the user may have re-flashed since the modal first appeared.
        """
        st = {}
        try:
            st = self.core.get_status() or {}
        except Exception as exc:  # noqa: BLE001 — never let a status read kill the menu
            self.log.warning("Could not read status for the newer-firmware prompt: %s", exc)
        proto = st.get("protocol")
        if proto is None:
            self.log.info("Newer-firmware prompt: no keyboard protocol known, ignoring.")
            return
        self._newer_fw_prompted_proto = None
        self._maybe_prompt_newer_firmware(True, proto,
                                          st.get("name") or "PolyKybd",
                                          st.get("fw_version") or "?")

    def _refresh_fontpack_action(self):
        """Label the font entry with the actual answer, on menu open.

        `fontpack_bundle_status` compares the cached GET_ID version block against
        the shipped manifest — no device I/O either side of the RPC — so this is
        cheap enough to run every time the Updates menu opens. Hidden when there
        is nothing to say (no device, no shipped bundles, or an older core with
        no such call) rather than showing a dead row.
        """
        action = self.fontpack_update_action
        getter = getattr(self.core, "fontpack_bundle_status", None)
        if getter is None or not self.device_present:
            action.setVisible(False)
            return
        try:
            ok, info = getter()
        except Exception as exc:  # noqa: BLE001
            self.log.debug("Font-pack status unavailable: %s", exc)
            action.setVisible(False)
            return
        if not ok or not isinstance(info, dict) or not info.get("shipped"):
            action.setVisible(False)
            return
        stale = [b for b in info.get("bundles", []) if b.get("stale")]
        # A bundle whose flash failed can still report a current version, so it would
        # sit under "up to date" with no way to retry it from the UI \u2014 which is exactly
        # how a failed `symbol` flash became unreachable in the field (2026-08-17).
        retry = [b for b in info.get("bundles", []) if b.get("retry") and not b.get("stale")]
        action.setVisible(True)
        if stale or retry:
            todo = stale + retry
            if retry and not stale:
                action.setText(f"Retry keyboard fonts ({len(retry)} failed)\u2026")
                tip = ("Re-flash the font bundles whose last attempt failed: "
                       + ", ".join(b["id"] for b in retry))
                last = [b.get("last_error") for b in retry if b.get("last_error")]
                if last:
                    tip += "\n" + last[0]
            else:
                action.setText(f"Update keyboard fonts ({len(todo)})\u2026")
                tip = ("Flash the font bundles the keyboard is missing, behind on, or "
                       "failed to take: " + ", ".join(b["id"] for b in todo))
            action.setToolTip(tip)
            action.setEnabled(self._fw_actions_allowed())
        else:
            action.setText("Keyboard fonts: up to date")
            action.setToolTip("Every shipped font bundle is already on the keyboard.\n"
                              "Developer \u2192 Font Pack \u2192 Re-flash all bundles forces a "
                              "re-send if the keycaps still render wrong.")
            action.setEnabled(False)

    def _on_sync_fontpack_clicked(self):
        self.cmdMenu.sync_fontpack()

    def _refresh_unicode_mode_clicked(self):
        ok, msg = self.core.refresh_unicode_mode()
        if ok:
            self.log.info("Unicode input mode refreshed: %s", msg)
        else:
            self.report_device_result("Error", f"Could not refresh the unicode mode: {msg}")

    def _save_mru_clicked(self):
        self.core.save_mru()
        self.log.info("MRU cache saved.")

    def _open_config_folder(self):
        """Open the config directory (settings.yaml + overlay-mapping.poly.yaml)
        in the desktop's file manager."""
        import platformdirs
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        path = platformdirs.user_config_dir("PolyHost")
        self.log.info("Opening config folder %s", path)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            # No file manager (headless-ish desktop, missing xdg-open): the path
            # itself is the useful part, so show it instead of failing silently.
            _msgbox(QMessageBox.Information, "Config folder", path)

    def managed_connection_status(self):
        # Newer-firmware safe mode: connected but operationally restricted — only
        # the firmware-update mechanism + debugging stay live, like a mismatch.
        enabled = self.connected and not self.paused and not self.safe_mode
        fw_enabled = self._fw_actions_allowed()
        for action in self.menu.actions():
            action.setEnabled(enabled)
        # Re-enable the firmware actions inside the commands submenu (the loop
        # above just disabled its parent action on a mismatch). Both modes.
        self.cmdMenu.update_enabled(enabled, fw_enabled)
        self.firmware_update_action.setEnabled(fw_enabled)
        # Feature submenus gate on the DEVICE's protocol, not just connectivity:
        # a protocol-mismatched keyboard now connects, so disable the submenus
        # whose firmware support is missing instead of letting them error on click
        # (the blanket loop above already set them to `enabled`).
        self.idle_style_menu.menuAction().setEnabled(enabled and self.supports("idle_style"))
        # Nested inside the one above, so the blanket top-level loop never touches it
        # and its own (later) protocol gate is the only thing that decides.
        self.idle_timeout_menu.menuAction().setEnabled(enabled and self.supports("idle_timeout"))
        self.glyph_script_menu.menuAction().setEnabled(enabled and self.supports("glyph_script"))
        self.glyph_size_menu.menuAction().setEnabled(enabled and self.supports("glyph_size"))
        # The Developer parent stays enabled UNCONDITIONALLY: several of its
        # entries are offline tools (the font-pack inspector inspects the shipped
        # bundles with no device at all, the mock-bitmap dump writes files), and a
        # disabled parent makes the whole submenu unreachable — so a disconnected
        # keyboard used to hide the very tools you reach for when it won't connect.
        # The device-coupled children are gated individually by
        # cmdMenu.update_enabled, so nothing inside becomes clickable that
        # shouldn't be.
        if self._developer_menu is not None:
            self._developer_menu.menuAction().setEnabled(True)
        # Available in both modes (driven via core methods).
        self.layout_editor.setEnabled(True)
        self.settings_dialog.setEnabled(True)
        self.log_dialog.setEnabled(True)
        self.fontpack_inspector_action.setEnabled(True)   # inspects shipped bundles offline
        self.update_action.setEnabled(True)
        # Group parents the blanket loop above just greyed out. A disabled parent
        # makes its whole submenu unreachable, so anything that must survive a
        # disconnect has to be re-enabled here even though its children are gated
        # individually: Updates (host update works with no keyboard at all, the
        # firmware entry re-gates itself on fw_enabled) and Help & About (About /
        # the log file are read-only and always valid).
        self.updates_menu.menuAction().setEnabled(True)
        self.help_menu.menuAction().setEnabled(True)
        self.pause_action.setEnabled(True)
        # Only meaningful while the core is actually holding the keyboard at
        # arm's length; it disappears again once the situation is resolved.
        self.newer_fw_action.setVisible(bool(self.safe_mode))
        self.newer_fw_action.setEnabled(True)
        self.status.setEnabled(True)
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
            self.pause_action.setText("Resume")
            self.pause_action.setIcon(get_icon("play_circle.svg"))
        else:
            self.status.setToolTip("Press to pause connection")
            self.pause_action.setText("Pause")
            self.pause_action.setIcon(get_icon("pause_circle.svg"))
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
        # Refresh the cached per-feature capabilities from the (now-populated)
        # device protocol so the feature-submenu gating below reflects this probe.
        # Use the core's reported view so safe mode masks them to all-False, same
        # as a --connect client sees.
        self._capabilities = self.core._reported_capabilities()
        connected_now = applied["connected_now"]
        response = applied["lang"]
        decision = applied["decision"]
        # Prompt for a newer-firmware choice off the same decision the core made
        # (mirrors the client path, which reads it from the status payload).
        if decision is not None:
            self._maybe_prompt_newer_firmware(
                decision.get("newer_fw_pending"), snapshot.get("kb_proto"),
                snapshot.get("name") or "", snapshot.get("kb_version") or "")

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
        # Cache the daemon-reported per-feature capabilities for menu gating; the
        # daemon carries them on every status_changed (a state-change event may be
        # missed by a late-attaching client, so fall back to the status snapshot).
        caps = payload.get("capabilities")
        if caps is None:
            caps = self.core.status_snapshot().get("capabilities")
        if caps is not None:
            self._capabilities = caps
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

        # Newer-firmware prompt: the daemon flags an undecided newer-firmware
        # state in the status; the snapshot backfills fields a steady-state event
        # omits (and covers a late-attaching client).
        snap = self.core.status_snapshot()
        self._maybe_prompt_newer_firmware(
            payload.get("newer_fw_pending", snap.get("newer_fw_pending")),
            payload.get("protocol", snap.get("protocol")),
            snap.get("name") or "", snap.get("fw_version") or "")

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
        path, _ = get_open_file_name(
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
        # Client-mode GitHub update flow: the downloaded temp .bin must persist
        # until the daemon's async flash/apply finishes. Clean it up once the
        # flow reaches a terminal state — apply done, or flash failed (no apply
        # follows). Guarded by _pending_fw_tmp_path so the manual flash (user's
        # own file) is untouched.
        if self._pending_fw_tmp_path and (
                name == "fw_apply_done" or (name == "fw_flash_done" and not ok)):
            self._cleanup_fw_release_tmp()
            # The async client-mode flash is done — restore the manual
            # "Check for firmware update…" action (it was hidden while flashing).
            self._pending_fw_release = None
            self._reset_fw_update_action()

    @staticmethod
    def langcode_to_flag(lang_code):
        # On macOS a pair of regional-indicator codepoints renders as a real
        # flag emoji — which would duplicate the flag PNG icon already shown on
        # each language entry (e.g. "de 🇦🇹" + the 🇦🇹 icon). Show the plain
        # upper-case country code there instead, so the user sees "de AT" plus
        # the icon, not two flags. Windows/Linux don't render the pair as a flag,
        # so they keep the regional-indicator text unchanged.
        if platform.system() == "Darwin":
            return lang_code.upper()
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
                # Place the language menu at the head of the device group (just
                # above Brightness) instead of appending it last. It is created
                # lazily once the firmware answers, by which point the rest of the
                # menu already exists, so insert at the anchor rather than add.
                self.keeb_lang_menu = QMenu(title)
                self.keeb_lang_menu.menuAction().setIcon(get_icon("language.svg"))
                anchor = getattr(self, "_lang_anchor", None)
                if anchor is not None:
                    menu.insertMenu(anchor, self.keeb_lang_menu)
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
        # Offer the glyph-script reset button when the connected firmware supports
        # glyph scripts (v9+; works over RPC in client mode too); it force-restores
        # the normal language legends. Gated on the capability, not mere presence,
        # so a keyboard too old for cmd 30 doesn't show a button that only errors.
        reset_cb = self.reset_glyph_script_to_standard if self.supports("glyph_script") else None
        dlg.setup(current, self.developer_mode, reset_glyph_script=reset_cb)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_updated_settings()
            if self.client_mode:
                for key, value in updated.items():
                    if current.get(key) != value:
                        self.core.settings_set(key, value)
            else:
                self.poly_settings.set_all(updated)
                # In-process mode writes settings directly (bypassing
                # core.settings_set), so the core has to be told: it owns every
                # side effect a setting has on the live device — the daylight
                # brightness push, the unicode settle watcher — and which ones
                # exist is its business, not the dialog's.
                self.core.note_settings_changed()
            # `ui_theme` may be among them — apply it now rather than at the
            # next restart.
            self._refresh_theme()
        dlg.close()

    def open_log(self):
        # assignment is needed otherwise the dialog would go away immediately
        delta = time.perf_counter()
        # Derived from log_bundle.LOG_SOURCES, not hand-listed: the daemon log
        # (daemon-by-default puts the interesting half there), the pre-GUI
        # startup log and the crash log all appear once they exist. Both tray
        # apps used to build this dict by hand and drifted apart.
        log_files = log_bundle.viewer_files(always=("host", "keyboard-console"))
        self.log_viewer = LogViewerDialog(log_files, collect_cb=self.open_log_bundle)
        self.log_viewer.show()
        delta = time.perf_counter() - delta
        self.log.info("Opened log dialog in '%f' sec", delta)

    def open_report_problem(self):
        """Open the guided problem-report dialog.

        Same retained-instance rule as open_log_bundle: this is the only strong
        reference (the dialog is parentless) and its collection QThread is
        parented to it, so rebuilding on a second click can destroy a running
        thread — and it would also throw away a half-written description."""
        from polyhost.gui.report_problem_dialog import ReportProblemDialog
        if self.report_problem_dialog is None:
            self.report_problem_dialog = ReportProblemDialog(
                parent=None,
                diagnostics_cb=lambda: self._diagnostics_text(self._gather_about_info()))
        self.report_problem_dialog.show()
        bring_to_front(self.report_problem_dialog)

    def _on_crash_detected(self, payload):
        """The core found a firmware crash record in the keyboard's console.

        One modeless dialog per session, retained on self for the same reason as
        the report dialog; a further record (the other half, or a second crash)
        is appended to the open one rather than stacking windows."""
        from polyhost.services.crash_report import CrashRecord
        from polyhost.gui.crash_alert_dialog import CrashAlertDialog
        try:
            rec = CrashRecord.from_dict(payload or {})
        except Exception:  # noqa: BLE001 — a malformed payload must not take the tray down
            self.log.warning("Ignoring an unreadable crash record: %r", payload, exc_info=True)
            return
        self.log.warning("Keyboard crash record: %s", rec.as_console_line())
        if self.crash_alert_dialog is None:
            self.crash_alert_dialog = CrashAlertDialog(
                parent=None,
                diagnostics_cb=lambda: self._diagnostics_text(self._gather_about_info()),
                report_cb=self._open_report_with_crash,
                host_version=__version__,
                clear_cb=self.core.clear_crash_record)
        self.crash_alert_dialog.add_record(rec)
        self.crash_alert_dialog.show()
        bring_to_front(self.crash_alert_dialog)

    def _open_report_with_crash(self, description: str, title: str) -> None:
        """Open Report-a-Problem with the crash written into the description."""
        self.open_report_problem()
        self.report_problem_dialog.set_description(description, title)

    def open_log_bundle(self):
        """Open the log-collection dialog (bundle .zip / clipboard).

        Kept out of __init__ so PyQt only imports it on demand. The dialog is
        modeless and stashed on self — a local would be garbage-collected the
        moment this returns, taking the window with it (the same reason
        open_log holds self.log_viewer).

        ⚠️ The instance is REUSED, not rebuilt. self.log_bundle_dialog is the
        only strong reference (the dialog is parentless), so re-assigning it on
        a second click drops the previous one — and its collection QThread is
        parented to it, so a rebuild mid-collection can destroy a running
        thread. Reuse also keeps the timeframe/redaction choice across opens."""
        from polyhost.gui.log_bundle_dialog import LogBundleDialog
        if self.log_bundle_dialog is None:
            # The bundle embeds the same text as About's "Copy diagnostics"
            # button, so it identifies the versions and connection state it came
            # from without a second round trip.
            self.log_bundle_dialog = LogBundleDialog(
                parent=None,
                diagnostics_cb=lambda: self._diagnostics_text(self._gather_about_info()))
        self.log_bundle_dialog.show()
        bring_to_front(self.log_bundle_dialog)

    def open_fontpack_inspector(self):
        from polyhost.gui.fontpack_inspector_dialog import FontPackInspectorDialog
        # Inspects the bundles shipped with the host (no device needed), so it
        # works in normal, client and disconnected states alike.
        dlg = FontPackInspectorDialog(parent=None)
        dlg.exec_()

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

    def _format_uptime(self) -> str:
        """Human-readable time since this process started (for the About dialog)."""
        secs = max(0, int(time.monotonic() - self._start_time))
        d, rem = divmod(secs, 86400)
        h, rem = divmod(rem, 3600)
        m, s = divmod(rem, 60)
        if d:
            return f"{d}d {h}h {m}m"
        if h:
            return f"{h}h {m}m"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    def _gather_about_info(self) -> dict:
        """Collect everything the About dialog + diagnostics text show, in one
        place. Reads only cached status (no device I/O; works in client mode over
        RPC too) and never raises — a failed read just yields blanks/defaults."""
        import platformdirs
        from PyQt5.QtCore import qVersion
        try:
            st = self.core.get_status() or {}
        except Exception:  # noqa: BLE001 — a status read must never break About
            st = {}
        try:
            n_lang = len(self.core.list_languages() or [])
        except Exception:  # noqa: BLE001
            n_lang = 0
        n_maps = len(getattr(self.core, "mapping", {}) or {})
        return {
            "version": __version__,
            "host_protocol": __protocol__,
            "mode": "daemon client" if self.client_mode else "standalone",
            "python": platform.python_version(),
            "qt": qVersion(),
            "os": f"{platform.system()} {platform.release()}".strip(),
            "uptime": self._format_uptime(),
            "present": bool(st.get("device_present")),
            "connected": bool(st.get("connected")),
            "paused": bool(st.get("paused")),
            "name": st.get("name") or "PolyKybd",
            "fw": st.get("fw_version") or "?",
            "hw": st.get("hw_version") or "?",
            "lang": st.get("current_lang") or "?",
            "n_lang": n_lang,
            "kb_proto": st.get("protocol"),
            "n_maps": n_maps,
            "config_dir": platformdirs.user_config_dir("PolyHost"),
            "log_dir": os.getcwd(),
            "fontpack": self._fontpack_summary(),
            "unsupported": ", ".join(
                sorted(f for f, ok in (st.get("capabilities") or {}).items() if not ok)),
        }

    def _fontpack_summary(self) -> str:
        """One line of per-bundle font-pack state, or '' when unknown.

        `fontpack_bundle_status()` compares the cached GET_ID version block
        against the shipped bundles.json — local on both sides of the RPC, so
        this costs no device I/O. A bundle can read as current and still have
        failed to flash, so failures are named separately from staleness."""
        getter = getattr(self.core, "fontpack_bundle_status", None)
        if getter is None:
            return ""
        try:
            ok, info = getter()
        except Exception as exc:  # noqa: BLE001 — diagnostics must never break About
            self.log.debug("Font-pack status unavailable for diagnostics: %s", exc)
            return ""
        if not ok or not isinstance(info, dict) or not info.get("shipped"):
            return ""
        bundles = info.get("bundles") or []
        if not bundles:
            return ""
        stale = [b.get("id") for b in bundles if b.get("stale")]
        failed = [b.get("id") for b in bundles if b.get("last_error")]
        parts = [f"{len(bundles)} bundles"]
        parts.append(f"stale: {', '.join(stale)}" if stale else "all current")
        if failed:
            parts.append(f"FAILED: {', '.join(failed)}")
        return " · ".join(parts)

    @staticmethod
    def _about_state_word(info: dict) -> str:
        if info["paused"]:
            return "paused"
        if info["connected"]:
            return "connected"
        return "present — not connected (protocol/version)"

    def _about_status_html(self, info: dict) -> str:
        """Keyboard-status block: name, firmware + its protocol (flagged when it
        mismatches the host), hardware, language count, and connection state.
        Degrades to 'No keyboard connected' when nothing is present."""
        if not info["present"]:
            return ("<b>Keyboard</b><br>"
                    "<span style='color:gray;'>No keyboard connected.</span>")
        kb_proto = info["kb_proto"]
        proto_txt = f"P{kb_proto}" if kb_proto is not None else "P?"
        if kb_proto is not None and kb_proto != info["host_protocol"]:
            proto_txt += " <span style='color:#c0392b;'>⚠ mismatch</span>"
        lang_line = info["lang"] + (
            f" · {info['n_lang']} languages loaded" if info["n_lang"] else "")
        rows = [
            f"<b>Connected keyboard:</b> {info['name']} "
            f"<span style='color:gray;'>({self._about_state_word(info)})</span>",
            f"<b>Firmware:</b> {info['fw']} &nbsp;·&nbsp; protocol {proto_txt}",
            f"<b>Hardware:</b> {info['hw']}",
            f"<b>Language:</b> {lang_line}",
        ]
        return about_dialog.rows_html(rows)

    def _about_env_html(self, info: dict) -> str:
        """Host environment block: uptime, overlay-mapping count (when known),
        and the config + log-file locations (handy for support)."""
        rows = [f"<b>Uptime:</b> {info['uptime']}"]
        if info["n_maps"]:
            rows.append(f"<b>Overlay mappings:</b> {info['n_maps']} apps")
        rows.append(f"<b>Config:</b> {info['config_dir']}")
        rows.append(f"<b>Logs:</b> {info['log_dir']}")
        return about_dialog.rows_html(rows, muted=True)

    def _diagnostics_text(self, info: dict) -> str:
        """Plain-text version of the About info, for the clipboard button."""
        lines = [
            f"PolyKybdHost {info['version']} (HID protocol P{info['host_protocol']})",
            f"Mode: {info['mode']}  |  Uptime: {info['uptime']}",
            f"Python {info['python']} · Qt {info['qt']} · {info['os']}",
        ]
        if info["present"]:
            kb_proto = info["kb_proto"]
            proto = f"P{kb_proto}" if kb_proto is not None else "P?"
            if kb_proto is not None and kb_proto != info["host_protocol"]:
                proto += " (MISMATCH)"
            lines += [
                f"Keyboard: {info['name']} ({self._about_state_word(info)})",
                f"  Firmware {info['fw']} · protocol {proto}",
                f"  Hardware {info['hw']} · Language {info['lang']}"
                + (f" ({info['n_lang']} loaded)" if info["n_lang"] else ""),
            ]
        else:
            lines.append("Keyboard: not connected")
        if info["n_maps"]:
            lines.append(f"Overlay mappings: {info['n_maps']} apps")
        # Two device-side facts that are LOCAL reads (a cached GET_ID block vs the
        # shipped manifest, and the protocol-gate table) — no device I/O on either
        # side of the RPC, so they are safe on the menu/GUI thread. Both answer a
        # recurring class of report on their own: "the glyphs are wrong" (a stale
        # or failed font-pack bundle) and "this menu is greyed out" (a feature the
        # attached firmware is too old for).
        if info.get("fontpack"):
            lines.append(f"Font pack: {info['fontpack']}")
        if info.get("unsupported"):
            lines.append(f"Features unavailable on this firmware: {info['unsupported']}")
        lines += [f"Config: {info['config_dir']}", f"Logs: {info['log_dir']}"]
        return "\n".join(lines)

    def _build_about_dialog(self) -> QDialog:
        """Construct the About dialog (host + keyboard info, project links, and
        Copy-diagnostics / OK buttons).

        The chrome is `gui/about_dialog.build_about_dialog`, shared with the
        forwarder; this method supplies only the content. Split from
        :meth:`show_about_dialog` so it can be built and inspected in a test
        without the modal ``exec_()`` blocking. Works in client mode too — it
        only shows info about this host program, no device access."""
        info = self._gather_about_info()
        return about_dialog.build_about_dialog(
            heading=about_dialog.heading_html(
                info["version"],
                f" &nbsp;·&nbsp; HID protocol P{info['host_protocol']}",
                f"Python {info['python']} · Qt {info['qt']} · "
                f"{platform.system()} · {info['mode']}"),
            description=(
                "Host software for the PolyKybd split keyboard with per-keycap "
                "OLED displays — tracks the active window and pushes overlays, "
                "language and keymap updates to the keyboard."),
            # Cached snapshot of the connected keyboard; the keyboard's own
            # protocol sits next to the host's above, so a mismatch is
            # diagnosable right here.
            boxed=self._about_status_html(info),
            muted=self._about_env_html(info),
            diagnostics_cb=lambda: self._diagnostics_text(
                self._gather_about_info()),
            clipboard=self.clipboard())

    def show_about_dialog(self):
        """Show the modal About dialog, snapped near the tray icon."""
        dlg = self._build_about_dialog()
        QTimer.singleShot(0, lambda: position_near_tray(dlg, self.tray))
        dlg.exec_()

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
        self.idle_iddqd_action.setChecked(bool(ok) and value == IdleStyle.IDDQD.value)
        self.idle_eden_action.setChecked(bool(ok) and value == IdleStyle.EDEN.value)

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

    def refresh_idle_timeout_menu(self):
        # Same shape as refresh_idle_style_menu: read the device, tick the match,
        # and on failure leave everything unchecked rather than guessing.
        ok, value = self.core.get_idle_timeout()
        # (preset, seconds) in-process; JSON turns it into a list over RPC.
        preset = value[0] if ok and value else None
        for act in self.idle_timeout_actions:
            act.setChecked(bool(ok) and act.data() == preset)

    def change_idle_timeout(self):
        value = self.sender().data()
        ok, msg = self.core.set_idle_timeout(value)
        if ok:
            self.log.info("Idle timeout set to %s.", IdleTimeout(value).label)
        else:
            # Firmware too old (needs v18+) or device busy — log and re-sync the
            # checkmark to the device's actual value so the menu doesn't lie.
            self.report_device_result("Error", f"Could not set idle timeout: {msg}")
            self.refresh_idle_timeout_menu()

    def _build_glyph_script_previews(self):
        # Give each entry a preview of its own script, rendered from the shipped
        # fantasy bundle (STANDARD previews the normal Latin face) — the icon is
        # two glyphs, which is all a 16 px menu icon can carry, and the tooltip a
        # longer sample. Built once, on the first show; a bundle that is missing
        # or unreadable just leaves the menu as it was.
        if self._glyph_previews_built:
            return
        self._glyph_previews_built = True
        try:
            from polyhost.gui.glyph_script_icon import glyph_script_icon, glyph_script_tooltip
            for value, act in self.glyph_actions.items():
                icon = glyph_script_icon(value)
                if icon is not None:
                    act.setIcon(icon)
                tip = glyph_script_tooltip(value)
                if tip:
                    act.setToolTip(tip)
        except Exception as e:  # noqa: BLE001 - a preview must never cost the menu
            self.log.debug("No glyph-script previews: %s", e)

    def refresh_glyph_script_menu(self):
        self._build_glyph_script_previews()
        # Read the active glyph script from the device and tick the matching entry;
        # on failure (old firmware / disconnected) leave all unchecked.
        ok, value = self.core.get_glyph_script()
        for sval, act in self.glyph_actions.items():
            act.setChecked(bool(ok) and value == sval)

    def change_glyph_script(self):
        value = self.sender().data()
        ok, msg = self.core.set_glyph_script(value)
        if ok:
            self.log.info("Glyph script set to %s.", GlyphScript(value).name.lower())
        else:
            # Firmware too old (needs v9+) or device busy — log and re-sync the
            # checkmark to the device's actual script so the menu doesn't lie.
            self.report_device_result("Error", f"Could not set glyph script: {msg}")
            self.refresh_glyph_script_menu()

    def refresh_glyph_size_menu(self):
        # Read the active legend size from the device and tick the matching entry;
        # on failure (old firmware / disconnected) leave all unchecked.
        ok, value = self.core.get_glyph_size()
        for sval, act in self.glyph_size_actions.items():
            act.setChecked(bool(ok) and value == sval)

    def change_glyph_size(self):
        value = self.sender().data()
        ok, msg = self.core.set_glyph_size(value)
        if ok:
            self.log.info("Keycap legend size set to %s.", GlyphSize(value).name.lower())
        else:
            # Firmware too old (needs v13+) or device busy — log and re-sync the
            # checkmark to the device's actual size so the menu doesn't lie.
            self.report_device_result("Error", f"Could not set keycap size: {msg}")
            self.refresh_glyph_size_menu()

    def reset_glyph_script_to_standard(self):
        """Force the glyph script back to Standard (used by the settings-dialog
        'Reset script to Standard' button)."""
        ok, msg = self.core.set_glyph_script(GlyphScript.STANDARD.value)
        if ok:
            self.log.info("Glyph script reset to standard.")
        else:
            self.report_device_result("Error", f"Could not reset glyph script: {msg}")

    def read_overlay_mapping_file(self, file):
        if not file:
            file, _ = get_open_file_name(None, 'Open file', '', "PolyKybd overlay mapping (*.poly.yaml)")
        if file:
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
        # Throttle AUTOMATIC checks (startup / 6 h timer / on-connect). GitHub's
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
        #
        # device_present (not connected): the firmware version is known even on
        # a protocol mismatch, and that's exactly when an update must be offered.
        # Read it via the core-backed property (self.kb_sw_version works in both
        # in-process and client mode — self.keeb itself is None in client mode).
        # The firmware check runs in both modes now: the client downloads the
        # release and flashes it via the daemon's fw.flash RPC.
        fw_version = self.kb_sw_version if self._fw_actions_allowed() else None
        if self._update_checker is not None and self._update_checker.is_alive():
            # A check is already in flight with its own (auto) callbacks — do
            # NOT start a second. Returns False so a manual caller knows its
            # on_no_update/on_error closures were not installed and can avoid
            # switching the UI into a "checking…" state it can't clear.
            #
            # ⚠️ Tested BEFORE the throttle claims anything, and a firmware ask
            # that lands here is REMEMBERED. The usual case is the 15 s startup
            # check still running host-only when the keyboard connects: claiming
            # first stamped `fw_checked_at` for a firmware check that never
            # started, and dropping the ask left firmware unchecked for the
            # whole throttle window (CodeRabbit, #271).
            if fw_version and not force and not self._update_checker.checks_firmware:
                self._update_check_fw_retry = True
            return False
        # ⚠️ The throttle is decided AFTER the firmware version is read, and
        # keeps a separate firmware stamp: a check that runs before the
        # keyboard's version is known must not throttle the one that can ask
        # about firmware (see `claim_automatic_check`).
        if not force and not claim_automatic_check(time.time(), bool(fw_version)):
            self.log.debug("Update check throttled (firmware %s)",
                           "known" if fw_version else "not known yet")
            return False
        self.log.debug("Starting update check (firmware %s)...", fw_version or "not known")

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
            if self._pending_release is not None:
                # A release reported EARLIER this session is gone — withdrawn, or
                # unpublished while a bad build was replaced. Drop it: the menu row
                # would go on advertising a version that no longer exists, and
                # clicking it would install from a URL that now 404s. Only a
                # SUCCESSFUL check does this; a check error returns above, because
                # an unreachable GitHub says nothing about the release.
                self.log.info("Previously reported host update %s is no longer offered",
                              self._pending_release.version)
                self._pending_release = None
                self._auto_prompted_host_version = None
                self.update_action.setText("Check for updates...")
                self._refresh_updates_marker()
            self.log.debug("No host update available")
            if on_no_update is not None:
                on_no_update()

        def _fw_no_update(blocked=None):
            if blocked is not None:
                self.log.warning("Firmware %s is newer but has no flashable .bin",
                                 getattr(blocked, "version", "?"))
            elif self._pending_fw_release is not None:
                # Same as the host side. Deliberately NOT in the `blocked` branch
                # above: there the checker is telling us the newest release has no
                # .bin, which says nothing about the older one we are holding —
                # that one is still flashable and still worth offering.
                self.log.info("Previously reported firmware update %s is no longer offered",
                              self._pending_fw_release.version)
                self._pending_fw_release = None
                self._auto_prompted_fw_version = None
                self._reset_fw_update_action()   # also refreshes the marker
            else:
                self.log.debug("No firmware update available")
            if self._await_manual_fw_prompt:
                self._await_manual_fw_prompt = False
                self._on_manual_no_fw_update(blocked)

        self._update_check_error = _on_error
        self._update_host_no_update = _host_no_update
        self._update_fw_no_update = _fw_no_update

        b = self.bridge
        self._update_checker = UpdateChecker(
            current_fw_version=fw_version,
            on_update_available=lambda r: b.job_done.emit("update_available", r),
            on_fw_up_available=lambda r: b.job_done.emit("fw_up_available", r),
            on_host_no_update=lambda: b.job_done.emit("update_host_no_update", None),
            on_fw_no_update=lambda blocked=None: b.job_done.emit("update_fw_no_update", blocked),
            on_error=lambda msg: b.job_done.emit("update_check_error", msg),
            on_finished=lambda: b.job_done.emit("update_check_finished", None),
        )
        self._update_checker.start()
        return True

    def _on_update_check_finished(self):
        """Run the firmware check that arrived while a host-only one was busy.

        The finished event is emitted from inside the checker's `run()`, so the
        thread can still read alive here; it has nothing left to do but return,
        which is why a short join is enough.
        """
        if not self._update_check_fw_retry:
            return
        self._update_check_fw_retry = False
        if self._update_checker is not None:
            self._update_checker.join(timeout=2)
        self._start_update_check()

    def _on_update_available(self, release):
        self._pending_release = release
        self.update_action.setText(f"Update to v{release.version} available")
        self._refresh_updates_marker()
        self.log.info("Update available: %s", release.version)
        if self._await_manual_prompt:
            self._await_manual_prompt = False
            self._fallback_prompt(self._prompt_and_install, release)
        elif self._balloons_reach_user():
            self.show_balloon(
                "PolyKybdHost Update",
                f"Version {release.version} is available. "
                "Click the tray icon to update.",
            )
        elif self._auto_prompted_host_version != release.version:
            # No balloon here and no messageClicked either, so "click the tray
            # icon to update" would be an instruction to click something that
            # was never shown. Open the same dialog the click would have — what
            # the forwarder has always done on every platform.
            self._auto_prompted_host_version = release.version
            self._fallback_prompt(self._prompt_and_install, release)

    def _on_update_clicked(self):
        if self._update_installer is not None and self._update_installer.is_alive():
            return
        if self._pending_release is not None:
            self._fallback_prompt(self._prompt_and_install, self._pending_release)
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
                "Run with --dev 1 for details.")

    def _prompt_and_install(self, release):
        date_str = _fmt_release_date(release.published_at)
        info = f"Released: {date_str}\n" if date_str else ""
        message = f"Version {release.version} is available.\n{info}"
        if not confirm_update("Update PolyKybdHost", message,
                              notes=getattr(release, "notes", ""),
                              html_url=getattr(release, "html_url", ""),
                              release_name=getattr(release, "name", ""),
                              question="Download, install, and restart now?"):
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

        if self.client_mode:
            # Daemon-by-default (H4b): the daemon owns the device AND the
            # protocol gate (its loaded `_version.__protocol__`), so it must be
            # the process that overwrites the files and re-execs. A GUI-side
            # install would refresh only this client — the daemon would keep
            # running the pre-update code and stay on the OLD protocol, so it
            # would go on rejecting the keyboard with "Protocol mismatch, please
            # update" until manually restarted (the field-reported bug). Drive
            # the daemon's installer over RPC instead; its update_* events stream
            # back through RemoteCore to the same _on_job_done handlers, and the
            # daemon re-execs itself on completion (see _on_update_done). The
            # `release` is re-resolved daemon-side, so it isn't passed here.
            ok, payload = self.core.install_update()
            if not ok:
                self._on_update_failed(str(payload))
            return

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
        self._update_ui.on_progress(percent, message)

    def _on_update_done(self):
        if self._update_progress is not None:
            self._update_progress.close()
            self._update_progress = None
        if self.client_mode:
            # The daemon applied the update in-process and re-execs itself
            # (headless.py `_on_update_event`), so it comes up on the new code
            # and the new protocol. This GUI just has to reconnect — but wait
            # for the daemon to actually go down and rebind first: restarting now
            # would re-attach to the still-live OLD daemon (leaving the daemon on
            # the old protocol — the bug), and racing its re-exec risks spawning
            # a second daemon. See _await_daemon_restart_then_relaunch.
            self.log.info("Update applied by the daemon; waiting for it to restart…")
            self._await_daemon_restart_then_relaunch()
            return
        self.log.info("Update applied, restarting...")
        # Re-exec after the event loop unwinds (main_app checks wants_restart),
        # not with os.execv from inside this slot while the tray/worker are
        # still live — same clean-restart pattern as the forwarder + daemon.
        self.wants_restart = True
        self.quit_app()

    def _await_daemon_restart_then_relaunch(self):
        """Client mode: after a daemon-driven self-update, the daemon re-execs
        itself. Poll the control endpoint until it has gone down (old daemon
        tearing down) and come back LIVE (new daemon bound on the updated code),
        then relaunch this GUI so it reconnects to the fresh daemon and runs the
        new GUI code too. Requiring the observed down→up transition is what stops
        us re-attaching to the still-up old daemon; polling until LIVE is what
        stops the relaunch from race-spawning a competing daemon."""
        from polyhost.server import instance as inst
        address = getattr(self.core, "_address", None)
        authkey = getattr(self.core, "_authkey", None)
        interval_ms = 400
        state = {"saw_down": False, "elapsed_ms": 0}

        def _relaunch(reason):
            self.log.info("Relaunching GUI to reconnect to the core daemon (%s).", reason)
            self.wants_restart = True
            self.quit_app()

        def poll():
            if self.is_closing:
                return
            try:
                outcome = inst.probe_existing(address, authkey, timeout=0.3)
            except Exception:  # noqa: BLE001 — a probe error means "not reachable"
                outcome = inst.STALE
            if not state["saw_down"]:
                if outcome != inst.LIVE:
                    state["saw_down"] = True
            elif outcome == inst.LIVE:
                _relaunch("daemon back up on the new version")
                return
            state["elapsed_ms"] += interval_ms
            if state["elapsed_ms"] >= 30000:
                # Never observed the clean transition (daemon slow, or it never
                # dropped). Relaunch anyway — main_app will spawn a daemon if
                # none is live, so we still end up on the new code.
                _relaunch("timed out waiting for the daemon restart")
                return
            QTimer.singleShot(interval_ms, poll)

        QTimer.singleShot(interval_ms, poll)

    def _on_relay_needed(self, relay_path: str):
        """Windows: some files (e.g. hidapi.dll) were locked by the running process.

        A relay script was written that will copy them once we exit and release
        the handles, then relaunch the app.  All non-DLL files were already copied.
        """
        if self.client_mode:
            # The daemon ran the installer, so the daemon owns this relay — its
            # own headless `_on_update_event` spawns the relay script, which
            # copies the daemon's locked files after it exits and relaunches the
            # daemon. This GUI must NOT spawn the relay too; it only needs to
            # reconnect once the daemon is back, exactly like the clean path.
            self.log.info("Daemon staged a locked-file relay (%s); "
                          "waiting for it to restart.", relay_path)
            if self._update_progress is not None:
                self._update_progress.close()
                self._update_progress = None
            self._await_daemon_restart_then_relaunch()
            return
        self.log.info("Relay restart needed for locked files: %s", relay_path)
        # Detached + windowless (updater.spawn_detached): the relay must outlive
        # this process, must not hand the restarted app a console, and must not
        # die with a job object (VS Code debug session) we happen to sit in.
        if not self._update_ui.stage_relay(relay_path):
            # Nothing will finish the locked-file copy if we exit now, and the
            # tree is already partially rewritten — surface it and stay up.
            self._on_update_failed(
                "Could not start the update relay; the update is incomplete. "
                "See the log for details.")
            return
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

    def _fallback_prompt(self, prompt, release):
        """Open a no-balloon fallback dialog, never two at once.

        ⚠️ ONE check reports the host release and then the firmware release,
        and both arrive as events QUEUED to the main thread. A modal dialog
        spins a nested event loop, so the firmware event is dispatched while
        the host dialog is still open and stacks a second dialog on top of it:
        the user answers them in reverse order, and accepting the host update
        can start an install-and-restart while a firmware flash is running.
        Queue the second one and run it when the first closes.

        ⚠️ **EVERY update prompt goes through here — grep for
        `_prompt_and_install(` / `_prompt_and_flash(` and the only callers left
        should be this method.** The serialization was first applied only to the
        automatic fallback, which left the MANUAL branches (`_await_manual_*`,
        i.e. the user's own "Check for update…" click) opening a modal with
        `_fallback_prompt_busy` still False — so the other check's event,
        dispatched by that modal's nested loop, stacked a dialog anyway
        (CodeRabbit, #257, the same defect for the third time). A per-call-site
        wrapper is the shape that keeps missing one; one door does not. On a
        platform that delivers balloons the queue is always empty, so wrapping
        those paths changes nothing there.

        ⚠️ **A dialog the user ACCEPTED ends the drain.** Serializing the two
        windows is only half of it: `_prompt_and_install` returns as soon as it
        has STARTED the installer, so draining the queue behind it would open
        the firmware prompt anyway and reach the same install-and-restart
        racing a flash, one step later (CodeRabbit, #257). A declined dialog
        starts nothing, so the next prompt runs normally. Whatever is dropped
        here is still on the Updates row and in the menu."""
        if self._fallback_prompt_busy:
            self._fallback_prompt_queue.append((prompt, release))
            return
        self._fallback_prompt_busy = True
        try:
            prompt(release)
            while self._fallback_prompt_queue and not self._update_in_flight():
                queued_prompt, queued_release = self._fallback_prompt_queue.pop(0)
                queued_prompt(queued_release)
            self._fallback_prompt_queue.clear()
        finally:
            self._fallback_prompt_busy = False

    def _update_in_flight(self):
        """True once an accepted dialog has started a download/install/flash.
        Both progress dialogs are created by the run_* helpers the prompts call
        and cleared at every terminal outcome, so they are the one signal that
        says "work is already running"."""
        return self._update_progress is not None or self._fw_up_progress is not None

    def _balloons_reach_user(self):
        """Whether ``show_balloon`` is seen at all. False on macOS unless we
        are running from a real .app bundle — see `gui/tray_notify`."""
        return QSystemTrayIcon.supportsMessages() and balloons_are_delivered()

    def show_balloon(self, title: str, message: str, msec: int = 8000):
        if not self._balloons_reach_user():
            # Still call showMessage (harmless, and correct the moment the
            # platform starts delivering), but leave a trace: a log bundle
            # otherwise has no way to show what the user was never told.
            self.log.debug("Balloon not delivered on this platform: %s — %s",
                           title, message)
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, msec)

    def _refresh_updates_marker(self):
        """Put the pending versions on the top-level ``Updates`` row.

        The rows that name a new version live one submenu deeper, which is
        where a user who was never shown a balloon will not look."""
        self.updates_menu.setTitle(updates_menu_title(
            getattr(self._pending_release, "version", None),
            getattr(self._pending_fw_release, "version", None)))
        self._refresh_tray_tooltip()

    def _refresh_tray_tooltip(self):
        """Decide the tray's resting tooltip and hand it to ``IconStateManager``.

        Three things want that one string: a font-pack flash (a live
        percentage, so it wins while it runs), a pending update, and the idle
        version line. ⚠️ It goes through ``set_base_tooltip`` rather than
        ``tray.setToolTip`` because ``IconStateManager`` restores its OWN
        stored tooltip when a warning expires — a direct write survives only
        until the next `set_warning`, after which the marker is gone for good
        (CodeRabbit, #257)."""
        self.icon_manager.set_base_tooltip(
            self._fontpack_tooltip
            or updates_tooltip(getattr(self._pending_release, "version", None),
                               getattr(self._pending_fw_release, "version", None))
            or self._idle_tooltip)

    # ------------------------------------------------------------------
    # Font-pack flash progress (auto on connect, or manual via polyctl)
    # ------------------------------------------------------------------

    def _on_fontpack_progress(self, result):
        """Surface a font-pack transfer in the tray. The keyboard can't service
        keys while flashing, so a quiet first-connect transfer would otherwise be
        invisible — announce it once, then keep a live percentage in the tooltip.

        The doom easter egg's game data / engine pack ride the same transport and
        events, so the wording comes from the payload's "kind"."""
        result = result or {}
        noun = flash_kind_label(result)
        if not self._fontpack_flashing:
            self._fontpack_flashing = True
            self.show_balloon("PolyKybd",
                              f"Updating keyboard {noun} — please wait, do not unplug…", 5000)
        pct = result.get("pct")
        if pct is not None:
            self._fontpack_tooltip = f"PolyKybd — updating {noun} ({pct}%)"
            self._refresh_tray_tooltip()

    def _on_fontpack_done(self, result):
        result = result or {}
        noun = flash_kind_label(result)
        self._fontpack_flashing = False
        self._fontpack_tooltip = ""
        self._refresh_tray_tooltip()
        if result.get("ok"):
            self.show_balloon("PolyKybd", f"Keyboard {noun} is up to date.", 4000)
        else:
            self.tray.showMessage("PolyKybd",
                                  f"{noun.capitalize()} update failed: {result.get('msg', '')}",
                                  QSystemTrayIcon.Warning, 6000)

    def _on_balloon_clicked(self):
        if self._update_installer is not None and self._update_installer.is_alive():
            return
        if self._pending_release is not None:
            self._fallback_prompt(self._prompt_and_install, self._pending_release)
        elif self._pending_fw_release is not None:
            self._fallback_prompt(self._prompt_and_flash, self._pending_fw_release)

    # ------------------------------------------------------------------
    # Firmware update
    # ------------------------------------------------------------------

    def _on_fw_up_available(self, release):
        self._pending_fw_release = release
        self.firmware_update_action.setText(f"Update firmware to v{release.version}…")
        self.firmware_update_action.setVisible(True)
        self._refresh_updates_marker()
        self.managed_connection_status()
        self.log.info("Firmware update available: %s", release.version)
        if self._await_manual_fw_prompt:
            self._await_manual_fw_prompt = False
            self._fallback_prompt(self._prompt_and_flash, release)
        elif self._balloons_reach_user():
            self.show_balloon(
                "PolyKybd Firmware Update",
                f"New firmware v{release.version} is available. "
                "Click the tray icon to update.",
            )
        elif self._auto_prompted_fw_version != release.version:
            self._auto_prompted_fw_version = release.version
            self._fallback_prompt(self._prompt_and_flash, release)

    def _on_fw_up_clicked(self):
        if self._fw_up_downloader is not None and self._fw_up_downloader.is_alive():
            return
        if self._pending_fw_release is not None:
            self._fallback_prompt(self._prompt_and_flash, self._pending_fw_release)
            return
        # No on_no_update here: the firmware result comes via _await_manual_fw_prompt
        # and the _fw_no_update closure in _start_update_check. Only flip the UI
        # if a run actually started (see _on_update_clicked).
        if self._start_update_check(force=True):
            self.firmware_update_action.setText("Checking for firmware update…")
            self.firmware_update_action.setEnabled(False)
            self._await_manual_fw_prompt = True

    def _on_manual_no_fw_update(self, blocked=None):
        self._await_manual_fw_prompt = False
        self.firmware_update_action.setText("Check for firmware update…")
        self.firmware_update_action.setEnabled(self._fw_actions_allowed())
        fw_version = self.kb_sw_version if self._fw_actions_allowed() else "unknown"
        if blocked is not None:
            # A newer release exists but its build never produced a .bin, so
            # there is nothing to flash. Saying "you are running the latest
            # firmware" here is simply false and hides a broken release.
            _msgbox(QMessageBox.Warning, "PolyKybd Firmware",
                    f"Firmware v{blocked.version} has been released, but it does not "
                    f"include a downloadable firmware file, so it cannot be installed "
                    f"yet.\n\nYour keyboard is on v{fw_version}. This usually means the "
                    f"release build failed — the release page will get its firmware "
                    f"once that is fixed."
                    + (f"\n\n{blocked.html_url}" if blocked.html_url else ""))
            return
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
        message = (f"Firmware {release.version} is available.\n{info}\n"
                   "Both halves update over HID and reboot automatically.")
        if not confirm_update("Update PolyKybd Firmware", message,
                              notes=getattr(release, "notes", ""),
                              html_url=getattr(release, "html_url", ""),
                              release_name=getattr(release, "name", ""),
                              question="Download and flash now?"):
            return
        self._run_fw_up_downloader(release)

    def _run_fw_up_downloader(self, release):
        if self._fw_up_downloader is not None and self._fw_up_downloader.is_alive():
            return

        self.firmware_update_action.setEnabled(False)
        self._fw_download_cancel = [False]
        self._fw_up_progress = _progress_dlg(
            f"Downloading firmware v{release.version}…", "Firmware Update",
            tray_icon=self.tray, on_cancel=self._on_fw_download_cancel)

        b = self.bridge
        self._fw_up_downloader = FwUpDownloader(
            release,
            on_progress=lambda pct, msg: b.job_done.emit("fw_download_progress", (pct, msg)),
            on_finished=lambda ok, err, path: b.job_done.emit("fw_download_done", (ok, err, path)),
            cancel_flag=self._fw_download_cancel,
        )
        self._fw_up_downloader.start()

    def _on_fw_download_cancel(self):
        """User pressed Cancel while the .bin was downloading from GitHub.

        Nothing has been sent to the keyboard at this stage, so cancelling is
        always safe. Flag the download thread — it aborts on the next chunk and
        fires fw_download_done, where _on_fw_download_done resets the UI."""
        if self._fw_download_cancel is not None:
            self._fw_download_cancel[0] = True
        if self._fw_up_progress is not None:
            self._fw_up_progress.setLabelText("Cancelling…")

    def _on_fw_download_progress(self, percent: int, message: str):
        if self._fw_up_progress is None:
            return
        # Don't overwrite the "Cancelling…" label with late download progress.
        if self._fw_download_cancel is not None and self._fw_download_cancel[0]:
            return
        self._fw_up_progress.setLabelText(message)
        self._fw_up_progress.setValue(percent)

    def _on_fw_download_done(self, ok: bool, error: str, bin_path: str):
        cancelled = bool(self._fw_download_cancel and self._fw_download_cancel[0])
        self._fw_download_cancel = None
        if self._fw_up_progress is not None:
            self._fw_up_progress.close()
            self._fw_up_progress = None

        if cancelled:
            # Discard any partial temp file (and its .sig) and return to the
            # pre-download state. Nothing reached the keyboard, so no device
            # cleanup is needed.
            discard_fw_download(bin_path)
            self.log.info("Firmware download cancelled by user.")
            if self._pending_fw_release is not None:
                self.firmware_update_action.setText(
                    f"Update firmware to v{self._pending_fw_release.version}…")
                self.firmware_update_action.setVisible(True)
                self.firmware_update_action.setEnabled(self._fw_actions_allowed())
            else:
                self._reset_fw_update_action()
            return

        if not ok:
            self.firmware_update_action.setEnabled(True)
            self.log.error("Firmware download failed: %s", error)
            _msgbox(QMessageBox.Warning, "Firmware Update Failed",
                    f"Could not download the firmware:\n\n{error}")
            return

        if self.client_mode:
            # The daemon owns the device — flash the downloaded .bin over the
            # fw.flash RPC with the same event-driven dialog as the manual
            # client-mode flash. flash_firmware() queues async on the daemon and
            # returns immediately, so the temp file must outlive this call: it is
            # cleaned up on the terminal fw_apply_done / failed fw_flash_done
            # event (see _on_flash_done), keyed off self._pending_fw_tmp_path.
            self._pending_fw_tmp_path = bin_path
            self._flash_dialog = HidFwUpDialog(
                None, bin_path, parent=None, apply_after=True,
                tray_icon=self.tray, external=True)
            self._flash_dialog.show()
            ok2, payload = self.core.flash_firmware(bin_path, apply=True)
            if not ok2:
                # The flash never queued on the daemon, so no terminal
                # fw_flash_done/fw_apply_done event will arrive to restore the
                # action — clean up and reset it inline so the manual "Check for
                # firmware update…" entry isn't lost.
                self._flash_dialog.feed_finished(False, str(payload))
                self._cleanup_fw_release_tmp()
                self._pending_fw_release = None
                self._reset_fw_update_action()
                return
            # Queued OK: hide the "Update firmware to vX…" prompt while the daemon
            # flashes; the terminal event restores the action (see _on_flash_done).
            self._pending_fw_release = None
            self._refresh_updates_marker()
            self.firmware_update_action.setVisible(False)
            self.managed_connection_status()
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
                discard_fw_download(bin_path)

        self._pending_fw_release = None
        self._reset_fw_update_action()
        self.managed_connection_status()

    def _reset_fw_update_action(self):
        """Return the firmware action to its idle 'Check for firmware update…'
        state (visible, enabled per _fw_actions_allowed) once a flash reaches a
        terminal outcome, so the manual check entry is never left hidden — in
        either in-process or client (daemon) mode."""
        self.firmware_update_action.setText("Check for firmware update…")
        self.firmware_update_action.setVisible(True)
        self.firmware_update_action.setEnabled(self._fw_actions_allowed())
        self._refresh_updates_marker()

    def _cleanup_fw_release_tmp(self):
        """Remove the temp .bin (and its .sig) downloaded for the client-mode
        GitHub update flow. No-op when there's nothing pending (the manual client
        flash uses the user's own file, so it never sets _pending_fw_tmp_path)."""
        path = self._pending_fw_tmp_path
        if not path:
            return
        self._pending_fw_tmp_path = None
        discard_fw_download(path)

    # ------------------------------------------------------------------
    # WinCompose install (Windows)
    # ------------------------------------------------------------------

    def _refresh_wincompose_action(self):
        """Show 'Install WinCompose…' exactly while WinCompose is NOT running.

        Runs on every tray-menu open (a user action, so the ~50 ms TASKLIST is
        fine and always current — no background polling). When WinCompose has
        appeared since the last look, re-push the unicode input mode: the core
        only sends it on connect, so a fresh install would otherwise not reach
        the keyboard until the next replug.

        ⚠️ The FIRST probe counts too. This used to skip it on the reasoning that
        "startup already pushed the mode on connect" — but the bug worth catching
        is precisely that that push was WRONG: at logon the core probes before
        WinCompose has started and pushes plain Windows. The first menu open is
        then the first chance to notice, and the old guard threw it away, so the
        keyboard stayed on Windows sequences (no emoji) for the whole session.
        Re-applying costs one HID command, and the firmware only touches EEPROM
        when the mode actually changes, so a redundant push is free.

        ⚠️ It fires in BOTH directions. refresh_unicode_mode's own docstring has
        always said it covers "installing (or quitting) WinCompose", but the
        guard here only ever fired on appear — so quitting WinCompose left the
        keyboard emitting WinCompose sequences, which produce nothing once the
        composer is gone. Same silent-until-you-need-it shape as the appear case,
        just less common."""
        if self.wincompose_action is None:
            return
        running = wincompose_running()
        self.wincompose_action.setVisible(not running)
        # Any change of state, including the first probe (was_running is None) —
        # see the two notes above.
        if self._wincompose_was_running != running:
            self.log.info("WinCompose is %srunning — re-applying the unicode input mode.",
                          "" if running else "no longer ")
            # ⚠️ OFF the Qt main thread. refresh_unicode_mode bottoms out in a
            # bounded run_sync (PolyCore.DEVICE_CALL_TIMEOUT, 5 s) — and in
            # client mode in an RPC to the daemon that does the same — so a
            # paused or mid-flash keyboard would freeze the tray for seconds
            # while the menu is trying to open. Nothing renders from the result,
            # so it only needs to be logged; RemoteCore takes its own _rpc_lock,
            # which is what makes calling it off-main-thread safe.
            threading.Thread(target=self._reapply_unicode_mode,
                             name="poly-unicode-refresh", daemon=True).start()
        self._wincompose_was_running = running

    def _reapply_unicode_mode(self):
        """Re-push the unicode input mode; runs on its own thread (see caller)."""
        try:
            ok, payload = self.core.refresh_unicode_mode()
        except Exception as e:  # noqa: BLE001 — no keyboard / daemon not up yet
            ok, payload = False, e
        if not ok:
            self.log.warning("Could not re-apply the unicode input mode: %s", payload)

    def _on_install_wincompose_clicked(self):
        """Explain what WinCompose is, then download + start its installer.

        Falls back to opening the releases page when no installer asset can be
        resolved (no release published yet, or a network/lookup failure), so the
        entry always leads somewhere useful."""
        if self._wincompose_downloader is not None and self._wincompose_downloader.is_alive():
            return
        if _msgbox(QMessageBox.Question, "Install WinCompose",
                   "WinCompose lets your PolyKybd type any unicode character on "
                   "Windows — emoji, accents and the language layers all go through "
                   "it. Without it the keyboard falls back to the far more limited "
                   "native Windows input.\n\n"
                   "PolyKybd's build of WinCompose will be downloaded from GitHub and "
                   "its installer started (Windows will ask you to confirm).",
                   buttons=QMessageBox.Yes | QMessageBox.Cancel,
                   default=QMessageBox.Yes) != QMessageBox.Yes:
            return

        self.wincompose_action.setEnabled(False)
        self._wincompose_cancel = [False]
        self._wincompose_progress = _progress_dlg(
            "Looking for the latest WinCompose release…", "Install WinCompose",
            tray_icon=self.tray, on_cancel=self._on_wincompose_cancel)

        # The release lookup makes two HTTP requests, so it runs on the download
        # thread too (info=None) — inline it would freeze the tray for up to two
        # request timeouts on a slow or unreachable network.
        b = self.bridge
        self._wincompose_downloader = wincompose_install.InstallerDownloader(
            on_progress=lambda pct, msg: b.job_done.emit("wincompose_download_progress",
                                                         (pct, msg)),
            on_finished=lambda ok, err, path: b.job_done.emit("wincompose_download_done",
                                                              (ok, err, path)),
            cancel_flag=self._wincompose_cancel,
        )
        self._wincompose_downloader.start()

    def _on_wincompose_cancel(self):
        """User pressed Cancel while the installer downloaded. Only a temp file
        has been written and nothing has been executed, so this is always safe."""
        if self._wincompose_cancel is not None:
            self._wincompose_cancel[0] = True
        if self._wincompose_progress is not None:
            self._wincompose_progress.setLabelText("Cancelling…")

    def _on_wincompose_download_progress(self, percent: int, message: str):
        if self._wincompose_progress is None:
            return
        # Don't overwrite "Cancelling…" with late progress from the download thread.
        if self._wincompose_cancel is not None and self._wincompose_cancel[0]:
            return
        self._wincompose_progress.setLabelText(message)
        self._wincompose_progress.setValue(percent)

    def _on_wincompose_download_done(self, ok: bool, error: str, path: str):
        cancelled = bool(self._wincompose_cancel and self._wincompose_cancel[0])
        self._wincompose_cancel = None
        if self._wincompose_progress is not None:
            self._wincompose_progress.close()
            self._wincompose_progress = None
        if self.wincompose_action is not None:
            self.wincompose_action.setEnabled(True)

        if error == wincompose_install.NO_INSTALLER:
            # No release published yet (or the lookup failed) — point the user at
            # the releases page rather than reporting a failure.
            self.log.info("No WinCompose installer asset found — opening the releases page.")
            _msgbox(QMessageBox.Information, "Install WinCompose",
                    "No ready-made installer was found for download.\n\n"
                    "The releases page will open in your browser — download and run "
                    "the setup from there.")
            wincompose_install.open_releases_page()
            return

        if cancelled or not ok:
            if not cancelled:
                _msgbox(QMessageBox.Warning, "Install WinCompose",
                        f"The download failed:\n\n{error}")
            return

        started, err = wincompose_install.launch_installer(path)
        if not started:
            _msgbox(QMessageBox.Warning, "Install WinCompose",
                    f"The installer could not be started:\n\n{err}\n\nIt was saved to:\n{path}")
            return
        # The installer runs detached (UAC), so we can't wait for it. The next
        # tray-menu open re-probes: the entry disappears and the unicode mode is
        # re-applied once WinCompose is actually running (_refresh_wincompose_action).
        self.show_balloon(
            "PolyKybd",
            "The WinCompose installer has started. Once it finishes and WinCompose "
            "is running, PolyKybd will switch to it automatically.", 8000)

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
        #
        # ⚠️ The guard is NOT defensive dressing, and it costs a raise TWO
        # things. An unhandled exception in a Qt slot goes to `sys.excepthook`
        # and then PyQt5's `qFatal()` ABORTS the process (`util/crash_log`), and
        # the re-arm below is skipped, so even surviving it would end window
        # tracking for the rest of the session with no further log line. The
        # core's own headless tick thread has carried this guard all along
        # (`PolyCore._tick_loop`); the GUI path -- the one macOS uses -- did not.
        #
        # It is reachable: on macOS `MacOSWindow.title` and `getHandle()` shell
        # out to `osascript` and `ast.literal_eval` its stdout, and the change
        # test in `_decide_active_window` reads them OUTSIDE its own try, so a
        # truncated or error reply raises straight through this slot.
        try:
            self.core.tick_window_tracking(UPDATE_CYCLE_MSEC,
                                           NEW_WINDOW_ACCEPT_TIME_MSEC)
        except Exception:  # noqa: BLE001 - one bad poll must not end polling
            self.log.exception("Window-tracking tick failed")
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
        elif name == "wincompose_download_progress":
            self._on_wincompose_download_progress(*result)
        elif name == "wincompose_download_done":
            self._on_wincompose_download_done(*result)
        elif name == "host_shutdown":
            # A control client (polyctl shutdown) asked the app to quit; the
            # request arrived on a server thread and was hopped here.
            self.quit_app()
        elif name == "crash_detected":
            self._on_crash_detected(result)
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
                self._update_fw_no_update(result)
        elif name == "update_check_error":
            if self._update_check_error is not None:
                self._update_check_error(result)
        elif name == "update_check_finished":
            self._on_update_check_finished()
        elif name == "update_progress":
            # Local UpdateInstaller emits a (pct, msg) tuple; the daemon's core
            # event (client mode) carries a {"pct","msg"} dict — accept both.
            if isinstance(result, dict):
                self._on_update_progress(result.get("pct", -1), result.get("msg", ""))
            else:
                self._on_update_progress(*result)
        elif name == "update_finished_ok":
            self._on_update_done()
        elif name == "update_relay_needed":
            path = result.get("relay_path") if isinstance(result, dict) else result
            self._on_relay_needed(path)
        elif name == "update_failed":
            msg = result.get("msg") if isinstance(result, dict) else result
            self._on_update_failed(msg)
        elif name == "fw_download_progress":
            self._on_fw_download_progress(*result)
        elif name == "fw_download_done":
            self._on_fw_download_done(*result)
