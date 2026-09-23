import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
import ipaddress
import socket
import sys
import time


from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QDialog,
    QMenu,
    QAction,
    QMessageBox,
    QProgressDialog)
from polyhost._version import __version__, __protocol__
from polyhost.services import problem_report
from polyhost.services.relay_health import RelayHealth
from polyhost.services import shortcut_relay
from polyhost.gui.get_icon import get_icon
from polyhost.services import log_bundle
from polyhost.gui import about_dialog
from polyhost.gui.dialog_util import bring_to_front, position_near_tray
from polyhost.gui.theme import apply_theme
from polyhost.services.os_theme import THEME_AUTO
from polyhost.settings import read_setting
from polyhost.gui.update_ui import UpdateProgressController
from polyhost.gui.icon_state_manager import IconStateManager
from polyhost.gui.qt_crash import install_qt_message_handler
from polyhost.gui.tray_wait import TrayVisibilityWaiter
from polyhost.gui.log_viewer import LogViewerDialog
from polyhost.handler.remote_window import TCP_PORT
from polyhost.handler.browser_url_source import BrowserUrlSource
from polyhost.handler.browser_url_source import SETTING_DEFAULTS as _URL_SETTINGS
from polyhost.handler.own_process import (
    describe_python_owner, is_python_runtime, own_app_name, window_pid)
from polyhost.handler.win_process import app_name_for


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


# The settings the forwarder actually acts on. It owns no keyboard, so the vast
# majority of settings.yaml (brightness, unicode mode, font pack, daemon mode)
# would be rows that silently do nothing on this machine — worse than no dialog
# at all. `ui_theme` is read at startup here; the browser-URL keys drive
# BrowserUrlSource, which the forwarder runs for the machine it sits on.
FORWARDER_SETTING_KEYS = ("ui_theme", "shortcut_icons_enabled") + tuple(_URL_SETTINGS)

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
        # ⚠️ Directly after it, because it is the COST of the line above: an
        # accessory app is never promoted to active by opening a window, so
        # without this every dialog the tray opens lands behind whatever the
        # user was in. One filter rather than a call at each `show()` -- there
        # are a dozen sites across the two apps and `.exec_()` modals among
        # them. See `gui.dialog_util.install_front_on_show`.
        from polyhost.gui.dialog_util import install_front_on_show
        install_front_on_show(self)
        self.host = host
        self.host_file = os.path.expanduser(host_file) if host_file else None

        # H4d: optionally push the active window over the authenticated network
        # window-report endpoint instead of the plaintext TCP relay. ⚠️ The RPC
        # transport is unit-tested but UNTESTED on hardware / cross-machine; the
        # default (report_rpc False) keeps the proven TCP path untouched.
        self._report_rpc = report_rpc
        self._report_port = report_port
        self._report_session = None
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
        install_qt_message_handler(self.log)
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
            from polyhost.server.window_report_client import WindowReportSession
            self._report_session = WindowReportSession(
                self._report_port, self._report_authkey)
            self.log.info("Forwarder using the authenticated window-report endpoint (H4d).")

        # Browser-URL feed for THIS machine. The extension is already willing to
        # report here — it POSTs to 127.0.0.1 on whatever machine it runs on —
        # but in forwarder mode nothing was listening, so its /ping failed and a
        # forwarded browser could only ever match on its window title.
        self._url_dirty = False
        self._url_source = BrowserUrlSource(
            self.log, on_change=self._on_browser_url_changed)
        if self._url_source.start():
            self.log.info("Browser-URL reporting enabled for forwarded windows.")

        # Create the tray
        self.tray = QSystemTrayIcon(parent=self)
        # prefix="f": the forwarder's mark spells an F where the tray app's
        # spells a P. Both are trays, and forwarding to your own keyboard
        # machine puts the two side by side in the same notification area.
        self.icon_manager = IconStateManager(
            self, False, self._tray_tooltip(), prefix="f")
        self._tray_waiter = TrayVisibilityWaiter(
            show=lambda: self.tray.setVisible(True),
            is_available=QSystemTrayIcon.isSystemTrayAvailable,
            log=self.log)
        self._tray_waiter.start()
        
        self.setQuitOnLastWindowClosed(False)
        self.win = None
        self.prev_win = None
        self.is_closing = False
        # Set when a self-update lands: main_app re-execs into the new version
        # *after* exec_() returns (from a clean, fully-unwound event loop),
        # mirroring how the headless daemon restarts — rather than calling
        # os.execv from inside a live Qt slot with the tray/timer still up.
        self.wants_restart = False
        self.title = None
        self.last_update_msec = 0
        # Whether the last report reached the keyboard machine. None = nothing
        # sent yet. The tray icon and the status row both read it, so a relay
        # that is quietly failing is visible without opening the log — the
        # forwarder used to declare itself connected at startup and never
        # revisit it, whatever the socket did afterwards.
        self.relay_ok = None
        # Should we attempt a report now, and is this failure worth a line?
        # ⚠️ Pure and in its own module because THIS file cannot be tested (it
        # imports pywinctl at module load), and the backoff/transition rules are
        # exactly the part worth testing. The transport records a reason here
        # and never logs it itself.
        self._relay = RelayHealth()
        self._send_error = None
        # app name -> what the local OS says it is. One lookup per app; see
        # _identity_for. Unbounded is fine here: the keys are app names from
        # THIS machine's own window manager, not remote input.
        self._identity_cache = {}
        # Python windows already explained in the log, by pid.
        self._told_python_owner = set()
        # The shortcuts THIS machine's accessibility tree exposes, per app --
        # same one-lookup-per-app contract as `_identity_cache` and the same
        # reason it is resolved here rather than on the keyboard machine: a
        # forwarded app's tree is only readable from the computer running it.
        #
        # ⚠️ The logic lives in a Qt-free module because THIS file cannot be
        # tested (it imports pywinctl at module load), and the three-state
        # answer, the in-flight guard and the privacy gate are exactly the parts
        # worth testing -- the same split as `RelayHealth` above.
        self._shortcuts = shortcut_relay.RelaySource(
            self.log, on_ready=self._shortcuts_ready)
        # Forwarding paused by the user. The window poll keeps running (so the
        # log still shows what is focused) but nothing leaves this machine —
        # this is the privacy switch, and it mirrors the tray app's Pause.
        self.paused = False

        self.heartbeat_msec = 0

        self._tray_waiter.start()
        self.set_style()

        # The menu follows the tray app's shape (docs/tray-ui.md): a status row
        # you can click, Pause, then the "get something newer" row, Settings and
        # one Help & About group holding the read-only corner. It used to be
        # seven flat rows in no particular order, so the same four support
        # entries sat in different places depending on which app you opened.
        self.menu = QMenu()

        self.status = QAction(get_icon("sync.svg"), "Starting…", parent=self)
        self.status.setToolTip("Press to pause forwarding")
        # noinspection PyUnresolvedReferences
        self.status.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.status)

        self.pause_action = QAction(get_icon("pause_circle.svg"), "Pause", parent=self)
        self.pause_action.setToolTip(
            "Stop sending this machine's active window to the keyboard machine.")
        # noinspection PyUnresolvedReferences
        self.pause_action.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.pause_action)

        self.menu.addSeparator()

        # The tray app groups this under "Updates" alongside the firmware and
        # font-pack rows. The forwarder owns no keyboard, so a submenu of one
        # would be a level of nesting over a single entry — it keeps the label
        # the tray app uses inside that submenu, in the slot the submenu holds.
        self.update_action = QAction(get_icon("browser_updated.svg"),
                                     "Check for host update\u2026", parent=self)
        # noinspection PyUnresolvedReferences
        self.update_action.triggered.connect(self._on_update_clicked)
        self.menu.addAction(self.update_action)

        self.settings_action = QAction(get_icon("settings.svg"), "Settings...", parent=self)
        # noinspection PyUnresolvedReferences
        self.settings_action.triggered.connect(self.open_settings)
        self.menu.addAction(self.settings_action)

        # --- Help & About: the read-only, always-available corner -------------
        # The forwarder runs on a DIFFERENT machine from the keyboard, so its
        # logs can never appear in a bundle collected host-side — and its
        # failure modes (which window backend this desktop selects, the report
        # transport, the authkey) are exactly the log-diagnosable kind. Every
        # entry here is worth as much as it is in the tray app.
        self.about = QAction(get_icon("info.svg"), "About", parent=self)
        # noinspection PyUnresolvedReferences
        self.about.triggered.connect(self.show_about_dialog)

        self.log_dialog = QAction(get_icon("log.svg"), "Log file...", parent=self)
        # noinspection PyUnresolvedReferences
        self.log_dialog.triggered.connect(self.open_log)
        self.log_viewer = None

        self.report_problem_action = QAction(get_icon("feedback.svg"),
                                             "Report a Problem...", parent=self)
        # noinspection PyUnresolvedReferences
        self.report_problem_action.triggered.connect(self.open_report_problem)
        self.report_problem_dialog = None

        self.collect_logs_action = QAction(get_icon("archive.svg"),
                                           "Collect logs...", parent=self)
        # noinspection PyUnresolvedReferences
        self.collect_logs_action.triggered.connect(self.open_log_bundle)
        self.log_bundle_dialog = None

        self.open_config_action = QAction(get_icon("file_open.svg"),
                                          "Open config folder", parent=self)
        # noinspection PyUnresolvedReferences
        self.open_config_action.triggered.connect(self._open_config_folder)

        self.help_menu = self.menu.addMenu(get_icon("help.svg"), "Help && About")
        self.help_menu.addAction(self.about)
        self.help_menu.addAction(self.report_problem_action)
        self.help_menu.addAction(self.log_dialog)
        self.help_menu.addAction(self.collect_logs_action)
        self.help_menu.addAction(self.open_config_action)

        self.exit = QAction(get_icon("power.svg"), "Quit", parent=self)
        # noinspection PyUnresolvedReferences
        self.exit.triggered.connect(self.quit_app)
        self.menu.addAction(self.exit)

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
        self._update_ui = UpdateProgressController(self.log)

        self.tray.setContextMenu(self.menu)
        self.refresh_status()

        QTimer.singleShot(1000, self.active_window_reporter)

    # ------------------------------------------------------------------
    # Status row, tray tooltip and the pause switch
    # ------------------------------------------------------------------
    def _target_text(self) -> str:
        """What this forwarder is aiming at, for a tooltip or a menu row."""
        host = self._resolve_host()
        if host:
            return host
        if self.host_file:
            return f"no host (waiting for {self.host_file})"
        return "no host configured"

    def _tray_tooltip(self) -> str:
        return f"PolyKybdHost {__version__} (forwarder) \u2192 {self._target_text()}"

    def _status_text(self) -> str:
        if self.paused:
            return "Forwarding paused"
        target = self._target_text()
        if self.relay_ok is None:
            return f"Forwarding to {target}\u2026"
        if self.relay_ok:
            return f"Forwarding to {target}"
        return f"Cannot reach {target}"

    def refresh_status(self):
        """Re-label the status row and repaint the tray icon from the current
        relay state.

        The colour mark means *reaching the keyboard machine*, not *the process
        is alive*: the forwarder used to call set_connected() once at startup
        and never touch it again, so a relay that had been refusing connections
        for hours still wore the connected icon."""
        self.status.setText(self._status_text())
        self.pause_action.setText("Resume" if self.paused else "Pause")
        self.pause_action.setIcon(get_icon(
            "play_circle.svg" if self.paused else "pause_circle.svg"))
        self.tray.setToolTip(self._tray_tooltip())
        if self.relay_ok and not self.paused:
            self.icon_manager.set_connected()
        else:
            self.icon_manager.set_disconnected()

    def toggle_pause(self):
        """Stop/resume sending the active window to the keyboard machine.

        The window poll keeps running either way — only send_to_host is skipped
        — so resuming pushes the current window on the next tick instead of
        waiting for the user to switch app."""
        self.paused = not self.paused
        self.log.info("Forwarding %s", "paused" if self.paused else "resumed")
        if self.paused:
            # Drop the RPC connection: a paused forwarder holding an open
            # authenticated session to the keyboard machine is exactly what
            # somebody pausing it would not expect.
            if self._report_session is not None:
                self._report_session.close()
        else:
            # Force the next tick to re-send rather than dedupe against the
            # window it was already showing when pause was pressed.
            self.win = None
            self.title = None
            self.relay_ok = None
            # ⚠️ And drop any backoff: pressing Resume must not sit out a 30 s
            # retry timer left over from before the pause.
            self._relay.reset()
        self.refresh_status()

    def set_style(self):
        """Fusion, dark or light per the OS — shared with PolyHost
        (gui/theme.py). Read once at startup: unlike the tray app this menu has
        no aboutToShow hook to re-follow from, and the forwarder's few dialogs
        are short-lived."""
        apply_theme(self, read_setting("ui_theme", THEME_AUTO))

    def _on_browser_url_changed(self):
        """A tab switch / SPA navigation changed the URL. The window-change test
        below is handle+title, which such a change does not move, so flag it and
        let the next 250 ms tick re-send instead of waiting for the heartbeat.

        Called from the receiver's HTTP thread, so it deliberately does nothing
        but set a bool — no Qt objects, no send from off the main thread."""
        self._url_dirty = True

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

    def _send_via_rpc(self, handle, title, name, url=None):
        """Push the active window over the authenticated window-report endpoint
        (H4d). `WindowReportSession` keeps the connection, reconnecting when it
        fails *or when the resolved host changes* — with `--host-file` the
        target can be rewritten between two reports."""
        host = self._resolve_host()
        if not host:
            # The host-file is gone, i.e. no active session. Drop the
            # connection: when the file returns it may name a different
            # machine, and a stale connection would keep serving the old one.
            if self._report_session is not None:
                self._report_session.close()
            return self._note_send_failure("no host to report to")
        ident = self._identity_for(name)
        try:
            result = self._report_session.report(
                host, handle, name, title, os=self._os_value, url=url,
                names=ident.get("names"), icon_key=ident.get("icon_key"))
            # ⚠️ The RECEIVER decides, and it is asked on every report. See
            # RemoteHandler._note_identity for why a sender-side "already sent"
            # flag cannot be trusted: its daemon restarts, --host-file repoints
            # us at a different machine, entries get evicted.
            asked = result or {}
            send_icon = bool(asked.get("want_icon") and ident.get("icon"))
            # ⚠️ `None` means "not harvested yet", `[]` means "harvested, this
            # app exposes nothing" -- and the difference is what stops the
            # receiver asking forever. So the emptiness test below is
            # `is not None`, never truthiness.
            shortcuts = (self._shortcuts.shortcuts_for(name)
                         if asked.get("want_shortcuts") else None)
            if send_icon or shortcuts is not None:
                # Follow up NOW rather than waiting for the next window change:
                # otherwise the mark appears only once the user switches away
                # and back, which reads as the feature not working.
                #
                # ⚠️ Guarded SEPARATELY, and the report above has already
                # landed. This second call carries nothing the keyboard needs to
                # track the window, so a rejected decoration must not be reported
                # as a failed window report -- that is the tray mark going red
                # and `send_to_host` retrying over a keycap decoration.
                try:
                    self._report_session.report(
                        host, handle, name, title, os=self._os_value, url=url,
                        names=ident.get("names"), icon_key=ident.get("icon_key"),
                        icon=ident["icon"] if send_icon else None,
                        shortcuts=shortcuts)
                except Exception as e:
                    # Drop it for this app rather than re-offering forever: the
                    # receiver asks on every report, so an icon it will not
                    # accept would otherwise be re-sent on every window change.
                    self.log.warning(
                        "Could not send the app icon/shortcuts for %r (%d B, %s"
                        " shortcut(s)) to %s: %s -- window reporting is"
                        " unaffected", name, len(ident.get("icon") or b""),
                        "-" if shortcuts is None else len(shortcuts), host, e)
                    # ⚠️ Only the half that was actually offered. Attributing a
                    # failure to the icon when this call carried no icon would
                    # throw away a good one over an unrelated refusal.
                    if send_icon:
                        ident.pop("icon", None)
                        ident.pop("icon_key", None)
            return True
        except Exception as e:
            return self._note_send_failure("RPC to %s: %s" % (host, e))

    def _identity_for(self, name):
        """What THIS machine's OS says the app is -- cached, one lookup per app.

        ⚠️ Resolved here because it cannot be resolved there. `app_identity`
        reads a `.desktop` entry / PE resources and the process behind the
        window, all of which exist only on the machine running the application;
        the keyboard machine may not even be the same OS.

        ⚠️ Cached because it does FILE I/O and this runs on the window tick. One
        lookup per application, not per report -- the same reason
        `AppIconFetcher` caches on the receiving side.

        Never raises: a cosmetic feature must not break window reporting.
        """
        key = str(name or "")
        if not key:
            return {}
        cached = self._identity_cache.get(key)
        if cached is not None:
            return cached
        ident = {}
        try:
            from polyhost.services import os_app_icon
            got = os_app_icon.app_identity(self._pid_for_window(), key)
            if got.names:
                ident["names"] = list(got.names)
            if got.icon:
                # ⚠️ SHRUNK before it goes anywhere near the wire. A stock VS
                # Code icon is 512x512 / ~220 KB, which the window-report
                # endpoint refuses outright (it bounds its one network-reachable
                # method on purpose) -- so the whole report failed and the mark
                # never arrived. The receiver reduces to a 38 px box regardless.
                from polyhost.services import icon_binarise
                icon = icon_binarise.shrink_for_transport(got.icon)
                ident["icon"] = icon
                # A content hash, so a theme change or an app update yields a
                # DIFFERENT key and the receiver re-fetches. A path would not.
                # Taken over the bytes we SEND, so the key names what the
                # receiver actually holds.
                ident["icon_key"] = hashlib.sha256(icon).hexdigest()[:16]
                self.log.info(
                    "App identity for %r: icon %s %d B (%d B on disk), key %s,"
                    " names=%s", key, got.icon_path or "<no path>", len(icon),
                    len(got.icon), ident["icon_key"],
                    ", ".join(got.names) or "<none>")
        except Exception as e:
            self.log.debug("No OS identity for %r: %s", key, e)
        if not ident.get("icon"):
            # ⚠️ Said out loud because the keyboard machine cannot say it. When
            # no icon travels, the daemon has only the names to work with and
            # its log reports a CATALOG miss -- which reads as "the catalog is
            # thin" when the real answer is that this machine never found an
            # icon to send.
            self.log.info("App identity for %r: no icon to send, names=%s",
                          key, ", ".join(ident.get("names") or ()) or "<none>")
        self._identity_cache[key] = ident
        return ident

    def _shortcuts_ready(self, name):
        """A harvest finished; make the next poll re-send so it goes out now.

        ⚠️ Nudges the heartbeat rather than waiting it out. The receiver only
        learns the answer on the next report, and plain waiting is up to
        HEARTBEAT_MSEC (15 s) of a focused app with no icons -- which reads as
        the feature not working. The poll may reset the counter first, in which
        case the real heartbeat still delivers, so this is an accelerator and
        never the only path.
        """
        self.heartbeat_msec = HEARTBEAT_MSEC

    def _pid_for_window(self):
        """The focused window's pid, or 0.

        ⚠️ `app_identity` uses it to read `/proc/<pid>/exe`, which is the ONLY
        rank that resolves an app whose desktop-entry stem does not reduce to its
        process name -- measured: GNOME Text Editor reports the comm
        `gnome-text-edit` (kernel-truncated at 15) and resolves through the exe
        alone.
        """
        try:
            return int(self.win._win.getPid()) if self.win is not None else 0
        except Exception:
            return 0

    def _note_send_failure(self, reason: str) -> bool:
        """Record WHY a report failed. Always returns False, and never logs.

        ⚠️ Deliberately silent. Every transport path used to log its own ERROR,
        which is correct once and wrong on the two-hundredth consecutive
        attempt; `RelayHealth` owns the up/down transition and so is the only
        thing that can tell those apart.
        """
        self._send_error = reason
        return False

    def send_to_host(self, handle, title, name, url=None):
        """Report one window, and record whether it landed.

        The status row and the tray mark read `relay_ok`, so every exit path of
        the transport below has to run through here — that is why the actual
        socket work sits in _send_to_host and this wrapper does nothing but
        remember the verdict.

        ⚠️ It also SKIPS the attempt while the relay is backing off. That is not
        only about the log: the attempt blocks the window poll for the whole
        socket timeout, so a dead daemon used to stall the tick by 3 s on every
        focus change. The cost is that a window change during the backoff is not
        reported — harmless, because the heartbeat re-sends the current window
        within HEARTBEAT_MSEC of the relay coming back.
        """
        now = time.monotonic()
        if not self._relay.should_attempt(now):
            self._say(self._relay.tick(now))
            return False
        ok = self._send_to_host(handle, title, name, url=url)
        self._say(self._relay.note(ok, now, self._send_error))
        if ok != self.relay_ok:
            self.relay_ok = ok
            self.refresh_status()
        return ok

    def _say(self, verdict) -> None:
        """Emit what RelayHealth decided is worth saying, naming the host."""
        if not verdict:
            return
        level, message = verdict
        getattr(self.log, level)(
            "Window %s (%s)", message, self._resolve_host() or "no host set")

    def _send_to_host(self, handle, title, name, url=None):
        # ⚠️ `url` rides the authenticated RPC path ONLY. The legacy relay's
        # framing is positional `handle;name;title;os` with the free-text field
        # in the middle, so a title containing ';' already truncates the title
        # and kills the os field — a fifth field would deepen a live bug on a
        # transport that is off by default.
        if self._report_rpc:
            return self._send_via_rpc(handle, title, name, url=url)
        host = self._resolve_host()
        if not host:
            return self._note_send_failure("no host to report to")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = socket.gethostbyname(host)
        except OSError as err:
            return self._note_send_failure("could not resolve %s: %s" % (host, err))
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
            return self._note_send_failure("connection timed out: %s" % err)
        except ConnectionRefusedError as err:
            return self._note_send_failure("connection refused: %s" % err)
        except ConnectionAbortedError as err:
            return self._note_send_failure("connection aborted: %s" % err)
        except ConnectionResetError as err:
            return self._note_send_failure("connection reset: %s" % err)
        except ConnectionError as err:
            return self._note_send_failure("connection error: %s" % err)

    def _diagnostics_text(self) -> str:
        """Diagnostics for a forwarder report.

        Composition lives in the Qt-free `problem_report` module: this file
        imports pywinctl at module load, so anything left here cannot be tested
        in the documented environment (the forwarder smoke mode skips without
        it). This method only supplies the state.
        """
        return problem_report.forwarder_diagnostics(
            __version__, host=self.host, host_file=self.host_file,
            report_rpc=self._report_rpc, report_port=self._report_port)

    def open_report_problem(self):
        """Guided problem report (retained instance — see PolyHost.open_report_problem)."""
        from polyhost.gui.report_problem_dialog import ReportProblemDialog
        if self.report_problem_dialog is None:
            self.report_problem_dialog = ReportProblemDialog(
                parent=None, diagnostics_cb=self._diagnostics_text)
        self.report_problem_dialog.show()
        bring_to_front(self.report_problem_dialog)

    def open_log_bundle(self):
        """Log-collection dialog (retained instance — see PolyHost.open_log_bundle)."""
        from polyhost.gui.log_bundle_dialog import LogBundleDialog
        if self.log_bundle_dialog is None:
            self.log_bundle_dialog = LogBundleDialog(
                parent=None, diagnostics_cb=self._diagnostics_text)
        self.log_bundle_dialog.show()
        bring_to_front(self.log_bundle_dialog)

    def open_log(self):
        # assignment is needed otherwise the dialog would go away immediately
        delta = time.perf_counter()
        # See host.py: one declaration in log_bundle.LOG_SOURCES feeds the
        # bundle, the clipboard text and both viewers' tabs.
        log_files = log_bundle.viewer_files(always=("forwarder",))
        self.log_viewer = LogViewerDialog(log_files, collect_cb=self.open_log_bundle)
        self.log_viewer.show()
        delta = time.perf_counter() - delta
        self.log.info("Opened log dialog in '%f' sec", delta)
        
    def _open_config_folder(self):
        """Open the config directory (settings.yaml) in the file manager.

        The forwarder reads the same settings.yaml as the tray app, out of the
        same platformdirs location nobody can guess — and on this machine it is
        the only PolyKybd process there is, so nothing else would open it."""
        import platformdirs
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        path = platformdirs.user_config_dir("PolyHost")
        self.log.info("Opening config folder %s", path)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.information(None, "Config folder", path)

    def open_settings(self):
        """Settings, narrowed to the keys that do something on this machine.

        ⚠️ The dialog renders whatever dict it is handed, so passing the whole
        of settings.yaml here would show brightness, unicode-mode and font-pack
        rows on a machine with no keyboard attached — every one of them a
        control that writes a value and changes nothing. FORWARDER_SETTING_KEYS
        is the allow-list; a value absent from the file falls back to the same
        default the reader uses.
        """
        from polyhost.gui.settings_dialog import SettingsDialog
        from polyhost.settings import PolySettings
        settings = PolySettings()
        current = dict(settings.get_all())
        shown = {k: current[k] for k in FORWARDER_SETTING_KEYS if k in current}
        dlg = SettingsDialog()
        dlg.setup(shown)
        if dlg.exec_() == QDialog.Accepted:
            updated = dlg.get_updated_settings()
            changed = {k: v for k, v in updated.items() if current.get(k) != v}
            if changed:
                # set_all over the FULL dict: the dialog only saw a slice, so
                # writing `updated` alone would drop every key it was not shown.
                current.update(changed)
                settings.set_all(current)
                self.log.info("Forwarder settings changed: %s",
                              ", ".join(sorted(changed)))
            # `ui_theme` may be among them — apply it now rather than at the
            # next restart.
            self.set_style()
        dlg.close()

    def _about_info_html(self):
        """The boxed block: what this forwarder is relaying, and how."""
        transport = (f"authenticated RPC (port {self._report_port})"
                     if self._report_rpc
                     else "legacy plaintext TCP relay")
        state = ("paused" if self.paused else
                 "reaching the keyboard machine" if self.relay_ok else
                 "not reaching the keyboard machine" if self.relay_ok is False
                 else "starting up")
        rows = [
            "<b>Mode:</b> forwarder — no keyboard attached to this machine",
            f"<b>Target:</b> {self._target_text()} "
            f"<span style='color:gray;'>({state})</span>",
            f"<b>Window reports:</b> {transport}",
        ]
        if self.host_file:
            rows.append(f"<b>Host file:</b> {self.host_file}")
        return about_dialog.rows_html(rows)

    def _about_env_html(self):
        import platformdirs
        return about_dialog.rows_html([
            f"<b>Config:</b> {platformdirs.user_config_dir('PolyHost')}",
            f"<b>Logs:</b> {os.getcwd()}",
        ], muted=True)

    def show_about_dialog(self):
        """The same About dialog the tray app shows, with forwarder content.

        It used to be a webbrowser.open() straight to ko-fi, which told a user
        on the forwarder machine nothing about the version, the relay target or
        the transport — the three things every forwarding problem turns out to
        be about. The Discord link that "Get Support" used to be is one of the
        project links in here."""
        import platform
        from PyQt5.QtCore import qVersion
        dlg = about_dialog.build_about_dialog(
            title="About PolyKybdHost (forwarder)",
            icon_name="fcolor.png",
            heading=about_dialog.heading_html(
                __version__,
                f" &nbsp;·&nbsp; HID protocol P{__protocol__}",
                f"Python {platform.python_version()} · Qt {qVersion()} · "
                f"{platform.system()} · forwarder"),
            description=(
                "Forwarder mode: this machine has no keyboard. It watches the "
                "active window here and relays it to the PolyKybdHost running "
                "on the machine the keyboard is plugged into."),
            boxed=self._about_info_html(),
            muted=self._about_env_html(),
            diagnostics_cb=self._diagnostics_text,
            clipboard=self.clipboard())
        QTimer.singleShot(0, lambda: position_near_tray(dlg, self.tray))
        dlg.exec_()


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
        from polyhost.gui.update_dialog import confirm_update
        self.update_action.setText("Check for updates...")
        message = f"Version {release.version} is available."
        if not confirm_update("Update PolyKybdHost", message,
                              notes=getattr(release, "notes", ""),
                              html_url=getattr(release, "html_url", ""),
                              release_name=getattr(release, "name", ""),
                              question="Download, install, and restart the forwarder now?"):
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
            f"Could not check for updates:\n\n{msg}\n\nRun with --dev 1 for details.")

    def _run_update_installer(self, release):
        from polyhost.services.updater import UpdateInstaller
        if self._update_installer is not None and self._update_installer.is_alive():
            return
        self.update_action.setEnabled(False)
        dlg = QProgressDialog(f"Downloading v{release.version}…", "", 0, 100)
        dlg.setWindowTitle("PolyKybdHost Update")
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.show()
        self._update_ui.attach(dlg)
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
        self._update_ui.on_progress(percent, message)

    def _on_update_done(self):
        self._update_ui.close()
        self.log.info("Update applied, restarting forwarder...")
        # Re-exec from a clean state after the event loop exits (see
        # `wants_restart` and main_app), not with os.execv from inside this
        # slot while the tray/timer are still live — exactly like the daemon.
        self.wants_restart = True
        self.quit_app()

    def _on_relay_needed(self, relay_path):
        """Windows: some files were locked; a relay script finishes the copy
        once we exit. Spawned through the shared controller so it gets the
        normalised (windowless) interpreter and updater.spawn_detached — this
        used to be a bare Popen on sys.executable, which left the restarted
        forwarder owning a console window and dying with any job object."""
        if not self._update_ui.stage_relay(relay_path):
            # Nothing will finish the locked-file copy if we exit now, and the
            # tree is already partially rewritten — surface it and stay up.
            self._on_update_failed(
                "Could not start the update relay; the update is incomplete. "
                "See the log for details.")
            return
        # Brief pause so the user sees the "Restarting" label before we vanish.
        QTimer.singleShot(1200, self.quit)

    def _on_update_failed(self, message):
        self._update_ui.close()
        self.update_action.setEnabled(True)
        self.log.error("Update failed: %s", message)
        QMessageBox.warning(
            None, "Update failed", f"Could not apply the update:\n\n{message}")

    def quit_app(self):
        self.icon_manager.set_disconnected()
        self.is_closing = True
        if self._report_session is not None:
            self._report_session.close()
        self._url_source.close()
        # Tear the tray icon down before the loop exits so a re-exec (update
        # restart) doesn't leave a stale icon behind / a doubled tray.
        try:
            self.tray.hide()
        except Exception:  # noqa: BLE001 — tray teardown must never block quit
            pass
        self.quit()

    def active_window_reporter(self):
        if self.paused:
            # Keep the timer alive but send nothing. The window state is
            # deliberately NOT tracked while paused: self.win/self.title stay
            # where they were, and toggle_pause clears them so resuming
            # re-sends immediately rather than deduping against a window the
            # keyboard machine never heard about.
            if not self.is_closing:
                QTimer.singleShot(UPDATE_CYCLE_MSEC, self.active_window_reporter)
            return
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
                    # PolyHost's own windows travel as `polyhost`, not as
                    # the interpreter, so the keyboard draws our mark for them.
                    # `activeWindow()` is Qt's own answer to "is one of OUR
                    # windows focused" and needs no pid.
                    pid = window_pid(win)
                    app_name = own_app_name(app_name_for(win), pid,
                                            self.activeWindow() is not None)
                    if is_python_runtime(app_name) and pid not in self._told_python_owner:
                        self._told_python_owner.add(pid)
                        self.log.info("Window '%s' belongs to a Python process"
                                      " that is not PolyHost (%s)", win.title,
                                      describe_python_owner(pid))
                    # None for every non-browser app, and for a browser whose
                    # extension report is stale/unfocused — so a URL can never
                    # linger onto the wrong window.
                    url = self._url_source.current_url(app_name)
                    changed = (
                        self.win is None
                        or win.getHandle() != self.win.getHandle()
                        or win.title != self.title
                        or self._url_dirty
                    )
                    if changed or self.heartbeat_msec >= HEARTBEAT_MSEC:
                        self.win = win
                        self.title = win.title
                        self._url_dirty = False
                        handle = win.getHandle()
                        self.send_to_host(handle, self.title, app_name, url=url)
                        if changed:
                            # ⚠️ %s, never %d -- the handle is a TUPLE on macOS
                            # (pywinctl `MacOSWindow.getHandle()`), and the
                            # TypeError lands in the `except` below, which
                            # reports it as "Exception in window reporter" and
                            # relays nothing. Same defect, and the same one-line
                            # fix, as `ActiveWindow.log_win`.
                            self.log.info("Active App: '%s' %s %s", self.title, app_name, handle)
                        else:
                            self.log.debug("Heartbeat: '%s' %s %s", self.title, app_name, handle)
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
