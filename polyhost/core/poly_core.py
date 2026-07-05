"""Qt-free operational core of PolyKybdHost (headless-core plan, H1).

``PolyCore`` owns the device stack and all operational background work:
the :class:`HidWorker` thread and its periodics (reconnect probe, console
reads, daylight brightness), the overlay send/command jobs, the overlay
mapping + handler, the sunlight model, MRU persistence and the sleep
listener. It communicates results exclusively through observer callbacks —
``emit(name, payload)`` with JSON-serializable payloads (contracts in
:mod:`polyhost.core.events`).

Threading contract: observer callbacks fire on core/worker threads.
Clients marshal to their own loop — the Qt client forwards every event
verbatim into ``WorkerBridge.job_done`` (a queued signal), which is why
the event names match the GUI's existing dispatch.

This module (and everything it imports) must stay importable without
PyQt5 and without a display: window tracking (pywinctl) is imported
lazily and degrades to "off" with a warning (plan §5.4).
"""
import os
import pathlib
import sys
import threading
import time

from polyhost._version import __version__, __protocol__
# Imported for its side effect: installs Logger.debug_detailed (used by the
# device code, e.g. poly_kybd). The Qt GUI gets this via host.py's log_util
# import; the headless process and bare tests would otherwise hit
# 'Logger' object has no attribute 'debug_detailed'. log_util is Qt-free.
import polyhost.util.log_util  # noqa: F401
from polyhost.core.decisions import decide_probe_publish, decide_reconnect_apply
from polyhost.device.device_manager import DeviceManager
from polyhost.device.device_settings import DeviceSettings
from polyhost.device import hid_fw_up
from polyhost.device import hid_fontpack
from polyhost.device.hid_worker import HidWorker
from polyhost.device.poly_kybd import PolyKybd
from polyhost.handler.common import OverlayCommand
from polyhost.services.sleep_listener import install_sleep_listener
from polyhost.services.sunlight_helper import Sunlight
from polyhost.settings import PolySettings

RECONNECT_CYCLE_MSEC = 1000
# After an overlay/MRU send the keyboard goes deaf for a few hundred ms while it
# bridges the images/mapping to the slave half over UART, so a probe landing in
# that window gets an EMPTY REPLY (harmless — the debounce absorbs it, but it's
# log noise and a wasted query). Skip the probe for one cycle's worth of time
# after the last overlay activity; a genuine disconnect is still caught once the
# window lapses (sends stop, so the timestamp goes stale within this window).
OVERLAY_PROBE_COOLDOWN_S = 1.0
UPDATE_CYCLE_MSEC = 250
PERIODIC_10MIN_CYCLE_MSEC = 1000 * 60 * 10
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000

_RES_DIR = pathlib.Path(__file__).parent.parent.resolve() / "res"


def get_overlay_path(filepath):
    """Absolute path of a shipped overlay template (polyhost/res/overlays)."""
    return os.path.join(_RES_DIR, "overlays", filepath)


def strip_key_injection(lines):
    """Drop the ``press``/``release`` key-injection commands from a script.

    Returns ``(kept_lines, dropped_count)``. Used to enforce that a non-debug
    host never drives arbitrary keystrokes on the keyboard via a command file
    or the ``commands.execute`` control RPC (see ``PolyCore.execute_commands``).
    """
    kept = [ln for ln in lines
            if ln.strip().split(" ", 1)[0] not in ("press", "release")]
    return kept, len(lines) - len(kept)


class PolyCore:
    """Operational facade: commands in, events out. No Qt, no widgets."""

    def __init__(self, log, ignore_version=False, start_worker=True,
                 apply_reconnect_in_core=False, allow_key_injection=False):
        self.log = log
        self.ignore_version = ignore_version
        # SECURITY: the `press`/`release` script commands inject real keystrokes
        # on the keyboard (firmware HID cmd 14 -> the keyboard types into the
        # host's focused app). That is a demo/dev capability, so it is honoured
        # only when the owning process was started in debug mode (--debug). The
        # firmware also NACKs cmd 14 unless DB_TOGG is on; this is the host half.
        self.allow_key_injection = allow_key_injection
        # When True (headless, no GUI to render), the reconnect periodic
        # applies its own snapshot (state + post-connect + status_changed).
        # The Qt client leaves this False and applies in _apply_reconnect_result.
        self.apply_reconnect_in_core = apply_reconnect_in_core

        # Connection state. `connected` means present AND protocol/version
        # compatible (only the reconnect decision tree may set it).
        # `device_present` means a device answers protocol-independent
        # queries (GET_ID) — firmware flash/apply keys off this so a
        # mismatched keyboard can always be updated.
        self.connected = False
        self.device_present = False
        self.paused = False
        # Worker-side reconnect bookkeeping. `last_applied_connected` is the
        # host's last APPLIED state: the worker reads it, the applying client
        # writes it (a bool read/write is atomic under the GIL).
        self.last_applied_connected = False
        self._probe_fail_streak = 0
        # monotonic timestamp of the last overlay/MRU send or enable/disable, so
        # the reconnect probe can skip the keyboard's post-send deaf window.
        self._last_overlay_activity = 0.0
        # Firmware version (parsed) of the connected keyboard, for update checks.
        self.kb_sw_version = None
        # Set on a fresh connect; consumed by the first applied snapshot after
        # it so the overlay state on the keyboard is cleared exactly once.
        self.needs_overlay_reset = False
        # Last OS value pushed to the keyboard (an OsType.value int, or None). The
        # window-tracking tick re-asserts the local OS when local windows drive the
        # display and the forwarder's OS when a remote-forwarded window is active,
        # deduped against this so set_os only fires on an actual change.
        self._last_pushed_os = None
        # Re-entrancy guard for the font-pack auto-flash: True only while a flash
        # is actually running, so a connection flap mid-flash can't start a second
        # one — but it is cleared on completion, so each fresh connect (e.g. a
        # physical reconnect after a wipe) re-checks and flashes any stale bundles.
        # decide_stale_bundles keeps it self-terminating: once the device is
        # current, a reconnect finds nothing to do.
        self._fontpack_flash_in_progress = False

        self.poly_settings = PolySettings()
        self.device_settings = DeviceSettings()
        self.keeb = PolyKybd(self.device_settings, self.poly_settings)

        self.device_mgr = DeviceManager(self.device_settings)
        self.device_mgr.add(self.keeb, "PolyKybd", is_primary=True)
        if self.poly_settings.get("dev_mock_enabled"):
            # Imported here, not at module top: the mock pulls in overlay_sim ->
            # numpy, which is otherwise dead weight on the daemon's startup import
            # path (the mock is only used when dev_mock_enabled is set).
            from polyhost.device.poly_kybd_mock import PolyKybdMock
            mock = PolyKybdMock(self.device_settings, f"{__version__}")
            self.device_mgr.add(mock, "PolyKybdMock", is_primary=False)
            self.log.info("Mock device added as secondary.")

        connected = self.keeb.connect()
        self.device_present = connected
        self.device_mgr.connect_secondaries()
        self.device_mgr.reset_all_caches()
        if connected:
            self.log.info("Connected to PolyKybd.")
        else:
            self.log.info("Not yet connected to PolyKybd...")

        # Observers: each is a callable(name, payload). Callbacks must be
        # fast and exception-safe from the caller's perspective.
        self._observers = []
        self._observers_lock = threading.Lock()

        # Overlay mapping + active-window handler. pywinctl hard-fails at
        # import without a display, so the handler is created lazily and
        # window tracking degrades to "off" (plan §5.4) — explicit overlay
        # sends still work.
        self.mapping = {}
        self.overlay_handler = None
        self.load_overlay_mapping(str(_RES_DIR / "overlay-mapping.poly.yaml"))
        self._create_overlay_handler()

        self.sunlight = Sunlight(
            self.poly_settings.get("brightness_allow_online_location_lookup"),
            self.poly_settings.get("brightness_allow_online_irradiance_request"))

        self.worker = HidWorker(log=self.log)
        self.worker.add_periodic("reconnect", RECONNECT_CYCLE_MSEC / 1000.0,
                                 self._reconnect_periodic)
        self.worker.add_periodic("console", UPDATE_CYCLE_MSEC / 1000.0,
                                 self._console_periodic)
        self.worker.add_periodic("brightness", PERIODIC_10MIN_CYCLE_MSEC / 1000.0,
                                 self._brightness_periodic)

        # Persist the keyboard MRU just before the system sleeps (Linux/logind).
        # The callback fires on the listener's daemon thread; save_mru only
        # logs and enqueues a worker job, so that is safe. Installed after the
        # worker exists so the callback always has a queue to submit to.
        self._sleep_listener = install_sleep_listener(self.save_mru, self.log)

        # Optional core-owned window-tracking tick (headless mode, H3). The Qt
        # client drives tick_window_tracking() from its main-thread QTimer
        # instead (pywinctl/macOS), so it never starts this.
        self._tick_thread = None
        self._tick_stop = threading.Event()
        self._tick_lock = threading.Lock()

        if start_worker:
            self.worker.start()

    # ------------------------------------------------------------------
    # Observer plumbing
    # ------------------------------------------------------------------

    def subscribe(self, callback):
        """Register callable(name, payload); fired on core/worker threads."""
        with self._observers_lock:
            self._observers.append(callback)

    def emit(self, name, payload):
        with self._observers_lock:
            observers = list(self._observers)
        for cb in observers:
            try:
                cb(name, payload)
            except Exception:  # one broken client must not break the core
                self.log.exception("Core event observer failed for %r", name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def set_paused(self, paused):
        """Pause/resume all device traffic. Pausing drops the connection
        state so the next resume goes through a full fresh-connect apply."""
        self.paused = paused
        if paused:
            self.connected = False
            self.last_applied_connected = False
            # suspend() is idempotent, so toggling pause while already
            # suspended (e.g. a flash holds exclusive()) is safe.
            self.worker.suspend()
        else:
            self.worker.resume()

    def start_window_tracking(self, interval_s=UPDATE_CYCLE_MSEC / 1000.0):
        """Run the active-window tick on a core-owned daemon thread.

        For headless mode (H3): there is no Qt main-thread QTimer to drive
        ``tick_window_tracking``. No-op when there is no window handler (no
        display) — explicit overlay sends via the API still work. The Qt
        client must NOT call this (it drives the tick from the main thread to
        satisfy the pywinctl/macOS constraint)."""
        if self.overlay_handler is None:
            self.log.info("No window handler — core window tracking stays off.")
            return

        def _loop():
            # pywinctl talks COM on Windows; a freshly-spawned thread must
            # initialize COM or getActiveWindow() fails with "Invalid syntax"
            # (0x80040E14). The Qt GUI gets this free on its main thread, but
            # this core-owned tick thread (headless / H3) does not.
            com_inited = False
            if sys.platform == "win32":
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                    com_inited = True
                except Exception:
                    self.log.warning("COM init for window tracking failed", exc_info=True)
            try:
                while not self._tick_stop.is_set():
                    try:
                        self.tick_window_tracking()
                    except Exception:
                        self.log.exception("Window-tracking tick failed")
                    self._tick_stop.wait(interval_s)
            finally:
                if com_inited:
                    try:
                        import pythoncom
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass

        # Guard the check-and-create so two callers can't start two threads.
        with self._tick_lock:
            if self._tick_thread is not None:
                return
            self._tick_stop.clear()
            self._tick_thread = threading.Thread(
                target=_loop, name="poly-window-tick", daemon=True)
            self._tick_thread.start()
        self.log.info("Core-owned window tracking started.")

    def shutdown(self):
        """Orderly stop: persist MRU, stop listeners/threads. Never raises.

        Persist the keyboard's MRU recents on a clean shutdown (the firmware
        only writes if they changed). USB suspend covers the sleep case; this
        covers a clean quit/logout where USB suspend may not fire. Run it
        synchronously (short bounded wait) BEFORE stopping the worker, but
        never let it block shutdown."""
        self._tick_stop.set()
        if self._tick_thread is not None:
            self._tick_thread.join(timeout=1)
            self._tick_thread = None
        try:
            self.worker.run_sync("save_mru", lambda c: self.keeb.save_mru(), timeout=2)
        except Exception as e:  # never let a save attempt break shutdown
            self.log.debug("MRU save request failed: %s: %s", type(e).__name__, e)
        if self._sleep_listener is not None:
            self._sleep_listener.close()
        self.worker.stop()
        if self.overlay_handler is not None:
            self.overlay_handler.close()

    def save_mru(self):
        """Best-effort request to persist the keyboard's emoji/language MRU.

        Safe to call when disconnected — the HID layer just reports failure
        and we swallow any error so shutdown/sleep is never blocked.
        Submitted as a normal worker job (device I/O stays on the worker)."""
        try:
            if self.keeb:
                self.worker.submit("save_mru", lambda c: self.keeb.save_mru())
        except Exception as e:  # never let a save attempt break shutdown/sleep
            self.log.debug("MRU save request failed: %s: %s", type(e).__name__, e)

    # ------------------------------------------------------------------
    # Overlay mapping / active-window handler
    # ------------------------------------------------------------------

    def load_overlay_mapping(self, path):
        import yaml
        try:
            with open(path, encoding="utf-8") as f:
                # safe_load: the mapping file is plain title→overlay-name data;
                # never instantiate arbitrary Python objects from it.
                loaded = yaml.safe_load(f) or {}
            if not isinstance(loaded, dict):
                self.log.warning("Overlay mapping %s is not a mapping; ignoring.", path)
                loaded = {}
            self.mapping = loaded
        except (OSError, yaml.YAMLError) as e:
            self.log.warning("Could not read overlay mapping %s: %s", path, e)
            self.mapping = {}

    def save_overlay_mapping(self, path):
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            f.write(yaml.dump(self.mapping))

    def _create_overlay_handler(self):
        try:
            from polyhost.handler.active_window import OverlayHandler
            self.overlay_handler = OverlayHandler(self.mapping)
        except Exception as e:
            # Headless / no display: pywinctl cannot load. Window-driven
            # overlay switching stays off; explicit sends still work.
            self.overlay_handler = None
            self.log.warning("Window tracking unavailable (%s: %s) — "
                             "active-window overlay switching disabled.",
                             type(e).__name__, e)

    # ------------------------------------------------------------------
    # Overlay jobs (HID worker)
    # ------------------------------------------------------------------

    def send_overlay_data(self, data):
        """Queue a (coalesced) overlay send for one or more template names."""
        files = []
        if isinstance(data, str):
            files.append(get_overlay_path(data))
        else:
            for overlay in data:
                files.append(get_overlay_path(overlay))

        if len(files) == 0:
            return False
        # Device I/O runs on the worker; coalesce_key="overlay" supersedes a
        # pending/in-flight send so rapid alt-tabbing doesn't replay transfers.
        # A client renders "thinking" off this event and clears it on the
        # "overlay" completion event.
        self.emit("overlay_activity", {"state": "thinking"})
        self.worker.submit("overlay", lambda cancel: self._overlay_send_job(files, cancel),
                           coalesce_key="overlay",
                           on_done=lambda name, result: self.emit(name, result))
        return True

    def tick_window_tracking(self, update_cycle_msec=UPDATE_CYCLE_MSEC,
                             new_window_accept_msec=NEW_WINDOW_ACCEPT_TIME_MSEC):
        """One active-window poll: switch overlays for the focused app.

        NO direct device I/O — pushes go through the worker. The active-window
        query (pywinctl) runs on the CALLER's thread: the GUI calls this from
        its main-thread QTimer (pywinctl/macOS must stay main-thread, per the
        worker refactor); headless mode calls it from the core's own tick
        thread (H3). When there is no window handler (no display) this is a
        no-op — explicit overlay sends via the API still work."""
        handler = self.overlay_handler
        if handler is None:
            return
        if self.connected:
            data, cmd = handler.handle_active_window(update_cycle_msec, new_window_accept_msec)
            if cmd in (OverlayCommand.DISABLE, OverlayCommand.ENABLE):
                self.submit_overlay_cmd(cmd)
            if data and cmd == OverlayCommand.OFF_ON:
                self.send_overlay_data(data)
            self._track_active_os(handler)
        elif self.poly_settings.get("dev_run_window_detection_if_not_connected_to_poly_kybd"):
            handler.handle_active_window(update_cycle_msec, new_window_accept_msec)

    def _track_active_os(self, handler):
        """Keep the keyboard's OS in sync with the machine currently driving the
        display: the forwarder's OS while a remote-forwarded window is active, else
        the local OS. This is what makes the OS feature follow a forwarded session
        (the keyboard reflects whichever computer you're working on), and revert to
        the local OS when local window tracking takes back over. Deduped via
        ``_push_os`` so set_os only fires on an actual change."""
        from polyhost.input.unicode_input import get_host_os
        from polyhost.device.command_ids import OsType
        forwarded = None
        rh = getattr(handler, "remote_handler", None)
        if rh is not None and handler.is_remote_mapping_entry():
            forwarded = getattr(rh, "forwarded_os", None)
        # A forwarded UNKNOWN(0)/None means the forwarder didn't report an OS — keep
        # the local OS rather than blanking the keyboard back to auto/unknown.
        desired = get_host_os()
        if isinstance(forwarded, int) and forwarded:
            try:
                desired = OsType(forwarded)
            except ValueError:
                pass  # unknown wire value — fall back to the local OS
        self._push_os(desired)

    def _push_os(self, os):
        """Submit a host-auto OS push to the keyboard, deduped against the last one.

        Accepts an OsType (or int); a no-op when it matches what was last pushed.
        set_os self-gates on protocol v7+, so this is harmless on older firmware."""
        from polyhost.device.command_ids import OsType as _OsType
        value = os.value if isinstance(os, _OsType) else int(os)
        if value == self._last_pushed_os:
            return
        self._last_pushed_os = value
        self.log.info("Pushing OS %s to keyboard.", _OsType(value))
        self.worker.submit("set_os", lambda c, v=value: self.keeb.set_os(v))

    def report_window(self, handle, name, title, os=None):
        """Inject an external active-window report into remote window tracking
        (the ``window.report`` RPC / ``polyctl window report``).

        ``os`` (optional, an OsType value int) is the forwarder's host OS, stored
        on the remote handler so the window-tracking tick can push it to the
        keyboard while the forwarded window is the active overlay driver.

        Mirrors what the cross-machine TCP relay does, but over the control
        socket — a local client (or a future unified transport) can feed the
        daemon's remote window matching without the bespoke TCP. No device I/O
        and no worker needed: it just stores the report; the next
        window-tracking tick applies it if a remote-mapping entry is active.
        Returns the uniform ``(ok, payload)`` the RPC layer unwraps."""
        handler = self.overlay_handler
        if handler is None or getattr(handler, "remote_handler", None) is None:
            return False, "window tracking unavailable"
        handler.remote_handler.report_window(handle, name, title, os=os)
        return True, {"reported": True}

    def submit_overlay_cmd(self, cmd):
        """Queue an enable/disable of overlays (coalesces with sends)."""
        self.worker.submit("overlay", lambda c, cmd=cmd: self._overlay_cmd_job(cmd, c),
                           coalesce_key="overlay")

    def _overlay_send_job(self, files, cancel):
        """Worker-thread overlay send. Reset/enable that accompany a send stay
        inside this job so ordering is preserved, and the cancel event is
        forwarded through."""
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
            # Runs on the worker thread — clients marshal this to their own
            # loop (the Qt client shows a tray warning).
            self.emit("overlay_warning", msg)

        self.keeb.set_idle(False)
        # The send + enable just bridged data to the slave; mark the deaf window
        # so the next reconnect probe skips it (avoids the EMPTY REPLY).
        self._last_overlay_activity = time.monotonic()

    def _overlay_cmd_job(self, cmd, cancel):
        """Worker-thread enable/disable of overlays on every device entry."""
        for entry in self.device_mgr.all_entries:
            if cancel.is_set():
                return
            if cmd == OverlayCommand.DISABLE:
                entry.device.disable_overlays()
            elif cmd == OverlayCommand.ENABLE:
                entry.device.enable_overlays()
        # enable/disable force-syncs state to the slave too — same deaf window.
        self._last_overlay_activity = time.monotonic()

    # ------------------------------------------------------------------
    # Worker periodics: reconnect probe, console/serial reads, brightness
    # ------------------------------------------------------------------

    def _reconnect_periodic(self, cancel):
        """Worker periodic (1 s): probe the device, publish the snapshot to
        observers. Skipped automatically while suspended."""
        snapshot = self._reconnect_probe(cancel)
        if snapshot is not None:
            # Headless: no GUI calls apply_reconnect, so the core applies its
            # own snapshot (settles state + runs post-connect, emits
            # status_changed). The Qt client applies it itself and leaves the
            # flag False, so this never double-applies.
            if self.apply_reconnect_in_core:
                try:
                    self.apply_reconnect(snapshot)
                except Exception:
                    # Never let an apply failure swallow the reconnect event —
                    # subscribers (e.g. ControlServer's fan-out to polyctl
                    # watch) must still see it.
                    self.log.exception("apply_reconnect failed in core periodic")
            self.emit("reconnect", snapshot)

    def _reconnect_probe(self, cancel):
        """Runs on the WORKER thread. Performs all device I/O for a reconnect
        and returns a plain dict snapshot (or None to publish nothing) — no
        UI access.

        Only re-queries version/lang info when the probed connectivity differs
        from the last applied state (read atomically under the GIL)."""
        # Skip the probe inside the post-send deaf window: while we still think
        # we're connected and an overlay/MRU send just bridged to the slave, the
        # GET_ID would get an EMPTY REPLY. Publishing nothing leaves state and
        # the fail-streak untouched; the next cycle (window lapsed) probes for
        # real, and a genuine disconnect is caught then since sends have stopped.
        if (self.last_applied_connected
                and time.monotonic() - self._last_overlay_activity
                < OVERLAY_PROBE_COOLDOWN_S):
            return None
        connected_now = False
        present_now = False
        response = ""
        if self.keeb.hid is not None:
            # Flush replies that arrived after their command gave up waiting
            # (the keyboard answers late while it syncs a large overlay
            # transfer to the slave half) — otherwise they get misread as the
            # replies to this probe's queries.
            self.keeb.hid.drain_replies(timeout_ms=2)
        if self.keeb.connect():
            # connect() succeeding (GET_ID answered / interface re-opened)
            # already proves a flashable device is present, even if the
            # GET_LANG probe below fails on a busy keyboard.
            present_now = True
            connected_now, response = self.keeb.query_current_lang()

        # Debounce: a busy keyboard misses probes without being disconnected.
        publish, self._probe_fail_streak = decide_probe_publish(
            connected_now, self.last_applied_connected, self._probe_fail_streak)
        if not publish:
            return None

        snapshot = {
            "connected_now": connected_now,
            "device_present": present_now,
            "lang": response,
            "state_changed": connected_now != self.last_applied_connected,
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
        if version_ok or self.ignore_version:
            enum_ok, _ = self.keeb.enumerate_lang()
            snapshot["lang_list"] = self.keeb.get_lang_list() if enum_ok else None
            snapshot["current_lang"] = self.keeb.get_current_lang() if enum_ok else None
        else:
            snapshot["lang_list"] = None
            snapshot["current_lang"] = None
        return snapshot

    def apply_reconnect(self, snapshot):
        """Apply a probe snapshot: the OPERATIONAL half of the reconnect.

        Updates core connection state, runs the version/protocol decision
        tree, and on a fresh compatible connect performs the post-connect
        work (unicode mode push, cache resets, window-handler resend).
        Returns an ``applied`` dict the calling client renders from (status
        text/icon, menu rebuild, OS-language switch); the same data is
        emitted as a ``status_changed`` event for passive observers.

        Thread-agnostic: no UI access; device work goes through worker jobs.
        """
        if self.paused:
            return None
        connected_now = snapshot["connected_now"]
        # Presence (= flashable) comes from the probe's connect()/GET_ID, not
        # from the GET_LANG result: a keyboard that answers GET_ID but misses
        # the language probe (busy syncing the slave half) and one that fails
        # the protocol/version check below must both keep firmware actions
        # available. Fall back to connected_now for snapshots without the key.
        self.device_present = snapshot.get("device_present", connected_now)

        applied = {
            "state_changed": snapshot["state_changed"],
            "connected_now": connected_now,
            "lang": snapshot["lang"],
            "decision": None,
            "do_overlay_reset": False,
            "fresh_boot": False,
        }

        if snapshot["state_changed"]:
            decision = decide_reconnect_apply(
                snapshot, __protocol__, __version__, self.ignore_version)
            applied["decision"] = decision

            # Mirror the original warning logs.
            if not snapshot["version_ok"] and self.ignore_version:
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
            if snapshot["version_ok"] or self.ignore_version:
                self.kb_sw_version = snapshot["kb_sw_version"]

            if decision["do_post_connect"]:
                if connected_now and self.poly_settings.get("unicode_send_composition_mode"):
                    from polyhost.input.unicode_input import get_input_method
                    mode = get_input_method()
                    self.log.info("Setting unicode mode to str %s", mode)
                    # set_unicode_mode is device I/O -> worker job.
                    self.worker.submit("set_unicode_mode",
                                       lambda c, m=mode: self.keeb.set_unicode_mode(m))
                if connected_now:
                    # Push the host OS (independent of the unicode mode). The keyboard
                    # applies it only in auto mode (a manual pin / Android wins), and
                    # set_os self-gates on protocol v7+, so this is a no-op on older
                    # firmware. Re-asserted on every connect — host wins when present.
                    # Force the push (last_pushed reset) so a reconnect always re-syncs.
                    from polyhost.input.unicode_input import get_host_os
                    self._last_pushed_os = None
                    self._push_os(get_host_os())
                self.device_mgr.reset_all_caches()
                if self.overlay_handler is not None:
                    self.overlay_handler.force_resend()
                self.needs_overlay_reset = True
                self.log.info("Connected: active window resend queued.")
                # Re-assert the host's brightness mode on the freshly-connected
                # keyboard (its auto mode is RAM-only and defaults off on boot):
                # engage daylight-auto + push the current value, or send AUTO_OFF
                # so it uses its stored manual brightness. Queued on the worker.
                self.refresh_daylight_brightness()
                # Auto-flash the bundled font pack if the keyboard's is missing
                # or older (queued on the worker; self-terminating — see below).
                self._maybe_auto_flash_fontpack()

        # The applying client owns the applied-connection state the worker reads.
        self.last_applied_connected = self.connected

        if not connected_now:
            self.log.warning("Reconnect failed: '%s'",
                             snapshot["lang"] if snapshot["lang"] else "NO RESPONSE")

        if self.connected:
            if snapshot["state_changed"] and self.needs_overlay_reset:
                self.needs_overlay_reset = False
                applied["do_overlay_reset"] = True
                # We just reset our OWN MRU cache (reset_all_caches above) to
                # empty, but the keyboard kept whatever pool it had — a fresh
                # host process (or daemon restart) connects to a keyboard that
                # never rebooted, so its overlay pool is still populated. Unless
                # we clear it, the empty host cache and the stale keyboard pool
                # are desynced and a later cache-hit ("0 upload") send maps
                # display positions onto slots the new session never wrote —
                # icons from a previous app/session bleed through.
                #
                # The GUI consumes do_overlay_reset and calls core.reset_overlays()
                # itself. Headless (apply_reconnect_in_core) ignores the returned
                # `applied`, so nothing cleared the keyboard there. Do it now —
                # we're on the worker thread, so call the device directly
                # (reset_overlays() would worker.run_sync and deadlock the worker
                # on itself).
                if self.apply_reconnect_in_core:
                    try:
                        self.keeb.reset_overlays_and_usage()
                        self.log.info("Connected: keyboard overlay state cleared.")
                    except Exception as e:
                        self.log.warning("Connect-time overlay reset failed: %s", e)
            # Independent of state_changed: a fast reboot (no observed
            # disconnect) still must invalidate the host-side MRU cache.
            if snapshot.get("fresh_boot"):
                self.device_mgr.reset_all_caches()
                self.log.info("Firmware restart detected — overlay MRU cache reset.")
                applied["fresh_boot"] = True

        self.emit("status_changed", {
            "connected": self.connected,
            "device_present": self.device_present,
            "paused": self.paused,
            "state_changed": snapshot["state_changed"],
            "text": (applied["decision"] or {}).get("text"),
            "icon": (applied["decision"] or {}).get("icon"),
            "lang": snapshot["lang"],
        })
        return applied

    def _console_periodic(self, cancel):
        """Worker periodic (250 ms): read serial + console; publish."""
        kb_serial = self.keeb.read_serial()
        kb_log = self.keeb.get_console_output()
        if kb_serial or kb_log:
            self.emit("console", (kb_serial, kb_log))

    # HID SET_BRIGHTNESS flag bits — mirror firmware base/com.h (protocol >= 5).
    # On older firmware the flags byte is ignored (plain persisted set), so we
    # only send flags when the device advertises support.
    _BR_FLAG_VOLATILE = 1 << 0   # daylight value: applied only in auto mode, never persisted
    _BR_FLAG_AUTO_ON  = 1 << 1   # engage host-driven (auto) brightness
    _BR_FLAG_AUTO_OFF = 1 << 2   # leave auto mode, revert to the keyboard's stored manual level
    _BRIGHTNESS_FLAGS_PROTOCOL = 5

    def _brightness_flags_supported(self):
        return (self.keeb.get_protocol_version() or 0) >= self._BRIGHTNESS_FLAGS_PROTOCOL

    def _compute_daylight_value(self):
        """Map the current daylight irradiance to a device value (2..50),
        applying the perceptual gamma. The keycap OLEDs are driven near the
        bottom of their contrast range (firmware caps at 49/50 for current/
        burn-in), where perceived brightness ~ luminance^(1/3), so a linear
        value feels uneven; gamma>1 evens out the perceived steps (1.0 = the
        old linear behaviour). Endpoints (0->2, 1->50) are preserved."""
        min_val = self.poly_settings.get("irradiance_min")
        max_val = self.poly_settings.get("irradiance_max")
        prescaler = self.poly_settings.get("irradiance_prescaler")
        brightness = self.sunlight.get_brightness_now(min_val, max_val, prescaler)
        gamma = self.poly_settings.get("brightness_gamma")
        if gamma and gamma > 0:
            brightness = brightness ** gamma
        return 2 + brightness * 48

    def _brightness_periodic(self, cancel):
        """Worker periodic (10 min): daylight-dependent brightness incl. the
        network lookups — kept entirely off any client thread. Sends a VOLATILE
        update only (never AUTO_ON): if the user has taken manual control on the
        keyboard the firmware ignores it, so a background tick can't override a
        deliberate choice. Engaging auto is a deliberate act (see _engage)."""
        if self.poly_settings.get("brightness_set_daylight_dependent"):
            val = self._compute_daylight_value()
            flags = self._BR_FLAG_VOLATILE if self._brightness_flags_supported() else 0
            self.keeb.set_brightness(val, flags)

    def _engage_brightness(self, cancel):
        """Deliberate (re-)assert of the host's brightness mode — runs on a
        settings change or on connect. Daylight on -> engage auto mode and push
        the current value (VOLATILE|AUTO_ON); daylight off -> tell the keyboard
        to leave auto mode and fall back to its stored manual brightness
        (AUTO_OFF). Both clear any prior keyboard manual override, which is the
        intended 'the host re-takes control' semantics."""
        supported = self._brightness_flags_supported()
        if self.poly_settings.get("brightness_set_daylight_dependent"):
            val = self._compute_daylight_value()
            flags = (self._BR_FLAG_VOLATILE | self._BR_FLAG_AUTO_ON) if supported else 0
            self.keeb.set_brightness(val, flags)
        elif supported:
            # Daylight disabled: leave auto mode; the keyboard restores its own
            # persisted manual brightness (level byte ignored on AUTO_OFF). On
            # pre-v5 firmware there is no auto mode, so there is nothing to do.
            self.keeb.set_brightness(0, self._BR_FLAG_AUTO_OFF)

    # Settings whose change should immediately recompute + retransmit the
    # daylight brightness rather than waiting for the next 10-min periodic.
    _BRIGHTNESS_SETTING_KEYS = frozenset({
        "brightness_set_daylight_dependent",
        "irradiance_min", "irradiance_max", "irradiance_prescaler",
        "brightness_gamma",
        "brightness_allow_online_irradiance_request",
        "brightness_allow_online_location_lookup",
    })

    def refresh_daylight_brightness(self):
        """(Re-)assert the host brightness mode on the device now, instead of
        waiting for the next 10-min periodic — used on a settings change and on
        connect. Runs on the worker so it never blocks the caller; coalesces so
        a burst of setting changes results in a single push."""
        # Keep the Sunlight lookup permissions in sync with the live settings,
        # so toggling the online-lookup options takes effect immediately too.
        self.sunlight.allow_online_lookup(
            bool(self.poly_settings.get("brightness_allow_online_irradiance_request")))
        self.sunlight.allow_location_lookup(
            bool(self.poly_settings.get("brightness_allow_online_location_lookup")))
        self.worker.submit("brightness_now", self._engage_brightness,
                           coalesce_key="brightness_now")

    # ------------------------------------------------------------------
    # Command API — the surface clients (CLI / RPC / GUI) drive (H2).
    #
    # Each device-touching call goes through the worker: short
    # request/response commands use run_sync (bounded block, raises while
    # suspended); long/coalescing ones (overlay send, command scripts) use
    # submit. Return shapes are plain JSON-serializable values/dicts so the
    # in-process observer and the socket transport are identical.
    # ------------------------------------------------------------------

    DEVICE_CALL_TIMEOUT = 5  # seconds for a bounded run_sync device command

    def _device_call(self, name, fn):
        """run_sync wrapper returning a uniform (ok, payload) result.

        Normalizes the two operational failure modes into a clean error
        instead of an exception: worker suspended (paused / firmware flash
        holds exclusive()) and timeout."""
        try:
            result = self.worker.run_sync(name, fn, timeout=self.DEVICE_CALL_TIMEOUT)
        except RuntimeError as e:       # suspended / stopping
            return False, str(e)
        except TimeoutError as e:
            return False, str(e)
        except Exception as e:          # device exception re-raised by run_sync
            self.log.debug("Device call %s failed: %s", name, e)
            return False, f"{type(e).__name__}: {e}"
        if isinstance(result, tuple) and len(result) == 2:
            ok, payload = result
            return bool(ok), payload
        return True, result

    def get_status(self):
        """Snapshot of connection state — no device I/O (reads cached state)."""
        return {
            "connected": self.connected,
            "device_present": self.device_present,
            "paused": self.paused,
            "name": self.keeb.get_name(),
            "fw_version": self.keeb.get_sw_version(),
            "protocol": self.keeb.get_protocol_version(),
            "hw_version": self.keeb.get_hw_version(),
            "current_lang": self.keeb.get_current_lang(),
            "host_version": __version__,
        }

    def list_languages(self):
        """Cached language list from the last enumeration (no device I/O)."""
        return list(self.keeb.get_lang_list() or [])

    def set_language(self, lang):
        """Change the keyboard language; emits ``lang_changed`` on success."""
        ok, payload = self._device_call(
            "lang_set", lambda c, l=lang: self.keeb.change_language(l))
        if ok:
            self.emit("lang_changed", {"lang": lang})
        return ok, payload

    def set_brightness(self, value):
        # Validate before _device_call so a bad value returns the uniform
        # (False, msg) contract instead of raising past it (the lambda default
        # was evaluated at call-construction time, outside _device_call's guard).
        try:
            v = int(value)
        except (TypeError, ValueError):
            return False, f"Invalid brightness value: {value!r}"
        return self._device_call(
            "brightness_set", lambda c, v=v: self.keeb.set_brightness(v))

    def set_idle(self, idle):
        # Reject non-bool input rather than bool()-coercing it: bool("false")
        # is True, which would silently invert the caller's intent over RPC.
        if not isinstance(idle, bool):
            return False, f"Invalid idle flag: {idle!r}"
        return self._device_call(
            "idle_set", lambda c, i=idle: self.keeb.set_idle(i))

    def set_idle_style(self, value):
        try:
            v = int(value)
        except (TypeError, ValueError):
            return False, f"Invalid idle style: {value!r}"
        return self._device_call(
            "idle_style_set", lambda c, v=v: self.keeb.set_idle_style(v))

    def get_idle_style(self):
        return self._device_call(
            "idle_style_get", lambda c: self.keeb.get_idle_style())

    def set_glyph_script(self, value):
        try:
            v = int(value)
        except (TypeError, ValueError):
            return False, f"Invalid glyph script: {value!r}"
        return self._device_call(
            "glyph_script_set", lambda c, v=v: self.keeb.set_glyph_script(v))

    def get_glyph_script(self):
        return self._device_call(
            "glyph_script_get", lambda c: self.keeb.get_glyph_script())

    def enable_overlays(self):
        return self._device_call("enable_overlays", lambda c: self.keeb.enable_overlays())

    def disable_overlays(self):
        return self._device_call("disable_overlays", lambda c: self.keeb.disable_overlays())

    def reset_overlays(self):
        return self._device_call(
            "reset_overlays_and_usage", lambda c: self.keeb.reset_overlays_and_usage())

    def keymap_layer_count(self):
        return self._device_call(
            "keymap_layer_count", lambda c: self.keeb.get_dynamic_layer_count())

    def keymap_default_layer(self):
        return self._device_call(
            "keymap_default_layer", lambda c: self.keeb.get_default_layer())

    def keymap_buffer(self):
        return self._device_call(
            "keymap_buffer", lambda c: self.keeb.get_dynamic_buffer())

    def keymap_set(self, layer, row, col, keycode):
        return self._device_call(
            "keymap_set",
            lambda c: self.keeb.set_dynamic_keycode(int(layer), int(row), int(col), int(keycode)))

    def get_fw_version(self):
        """Parsed firmware version string (cached; no device I/O)."""
        return self.keeb.get_sw_version()

    def execute_commands(self, lines):
        """Queue a (cancel-aware) command script across every device entry.

        Unless key injection is allowed (host started in debug mode), the
        ``press``/``release`` commands are stripped here so a command file (or
        the ``commands.execute`` control RPC) can never drive arbitrary
        keystrokes on a production host.
        """
        lines = list(lines)
        if not self.allow_key_injection:
            lines, dropped = strip_key_injection(lines)
            if dropped:
                self.log.warning(
                    "Ignoring %d key-injection command(s) (press/release): host "
                    "not started in debug mode (--debug).", dropped)

        def _job(cancel):
            for entry in self.device_mgr.all_entries:
                if cancel.is_set():
                    return
                entry.device.execute_commands(list(lines), cancel)
        self.worker.submit("execute_commands", _job)
        return True

    def settings_get(self, key):
        return self.poly_settings.get(key)

    def settings_list(self):
        """All settings as a plain dict (for the client's settings dialog)."""
        return dict(self.poly_settings.get_all())

    def settings_set(self, key, value):
        """Set one known setting and persist. Returns (ok, msg)."""
        alls = self.poly_settings.get_all()
        if key not in alls:
            return False, f"Unknown setting '{key}'"
        alls[key] = value
        self.poly_settings.set_all(alls)
        # A brightness/daylight setting change takes effect immediately instead
        # of on the next 10-min cycle (covers polyctl + the client-mode dialog).
        if key in self._BRIGHTNESS_SETTING_KEYS:
            self.refresh_daylight_brightness()
        return True, key

    # ------------------------------------------------------------------
    # Firmware flash + host self-update (headless / polyctl)
    # ------------------------------------------------------------------

    def _fw_actions_allowed(self):
        """Firmware flash/apply gate: a present device (even on a mismatched
        protocol) that isn't paused. Mirrors PolyHost._fw_actions_allowed —
        do NOT gate on self.connected (a protocol-mismatched keyboard must
        still be flashable)."""
        return (self.connected or self.device_present) and not self.paused

    def flash_firmware(self, path, apply=False):
        """Flash a firmware ``.bin`` (optionally apply it) as a worker job.

        Gating + file validation happen synchronously and return the uniform
        ``(ok, payload)`` contract — a bad file / absent device fails fast.
        Once accepted the upload runs on the HID worker (its single thread
        naturally blocks the reconnect probe for the duration, so no
        ``exclusive()`` is needed) and streams progress as
        ``fw_flash_progress`` / ``fw_apply_progress`` events with a terminal
        ``fw_flash_done`` / ``fw_apply_done``."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot flash."
        try:
            with open(path, "rb") as f:
                fw_bytes = f.read()
        except OSError as e:
            return False, f"Cannot read firmware file: {e}"
        ok, msg = hid_fw_up.validate_rp2040_firmware(fw_bytes)
        if not ok:
            return False, f"Not a valid RP2040 image: {msg}"
        ok, msg = hid_fw_up.validate_polykybd_firmware(fw_bytes)
        if not ok:
            return False, f"Not a PolyKybd firmware: {msg}"

        def _job(cancel):
            cancel_flag = [False]

            def _flash_progress(pct, m):
                if cancel.is_set():
                    cancel_flag[0] = True      # relay supersede/suspend to hid_fw_up
                self.emit("fw_flash_progress", {"pct": pct, "msg": m})

            fok, fmsg = hid_fw_up.flash_firmware(
                self.keeb.hid, path, progress_cb=_flash_progress, cancel_flag=cancel_flag)
            self.emit("fw_flash_done", {"ok": bool(fok), "msg": fmsg})
            if fok and apply:
                aok, amsg = hid_fw_up.apply_staged_firmware(
                    self.keeb.hid,
                    progress_cb=lambda pct, m: self.emit(
                        "fw_apply_progress", {"pct": pct, "msg": m}))
                self.emit("fw_apply_done", {"ok": bool(aok), "msg": amsg})

        # No coalesce_key: a flash must never be superseded by a later job.
        self.worker.submit("fw_flash", _job)
        return True, {"queued": True, "apply": bool(apply)}

    def flash_fontpack(self, path, bundle_id=0):
        """Flash an external-flash ``.plyf`` font-pack bundle as a worker job.

        ``bundle_id`` selects the fixed flash slot (the bundle's index in
        res/fontpack/bundles.json); 0 by default. Same shape as
        :meth:`flash_firmware` minus the apply step — the firmware re-loads fonts
        in place on COMMIT (no reboot). Gating + header validation happen
        synchronously (uniform ``(ok, payload)``); the upload then streams
        ``fontpack_flash_progress`` events with a terminal ``fontpack_flash_done``."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot flash."
        try:
            with open(path, "rb") as f:
                pack_bytes = f.read()
        except OSError as e:
            return False, f"Cannot read font-pack file: {e}"
        ok, msg = hid_fontpack.validate_fontpack(pack_bytes)
        if not ok:
            return False, msg

        def _job(cancel):
            cancel_flag = [False]

            def _progress(pct, m):
                if cancel.is_set():
                    cancel_flag[0] = True      # relay supersede/suspend to hid_fontpack
                self.emit("fontpack_flash_progress", {"pct": pct, "msg": m})

            fok, fmsg = hid_fontpack.flash_fontpack(
                self.keeb.hid, path, progress_cb=_progress, cancel_flag=cancel_flag,
                bundle_id=bundle_id)
            self.emit("fontpack_flash_done", {"ok": bool(fok), "msg": fmsg})

        # No coalesce_key: a flash must never be superseded by a later job.
        self.worker.submit("fontpack_flash", _job)
        return True, {"queued": True}

    def install_doomwad(self, path):
        """Install the doom easter egg's WHX game data (both halves) as a worker job.

        Rides the font-pack transport with the DOOMWAD pseudo bundle — the firmware
        routes it to the WHX slot at the top of the resource region and bridges the
        slave's copy in the same pass. Same event stream as a font-pack flash
        (``fontpack_flash_progress``/``fontpack_flash_done``), so ``polyctl`` and the
        tray progress surfaces work unchanged. Old firmware without the DOOMWAD
        target NACKs the BEGIN — reported as a plain error, nothing bricks."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot flash."
        try:
            with open(path, "rb") as f:
                whx_bytes = f.read()
        except OSError as e:
            return False, f"Cannot read game-data file: {e}"
        ok, msg = hid_fontpack.validate_doomwad(whx_bytes)
        if not ok:
            return False, msg

        def _job(cancel):
            cancel_flag = [False]

            def _progress(pct, m):
                if cancel.is_set():
                    cancel_flag[0] = True
                self.emit("fontpack_flash_progress", {"pct": pct, "msg": m})

            fok, fmsg = hid_fontpack.flash_doomwad(
                self.keeb.hid, path, progress_cb=_progress, cancel_flag=cancel_flag)
            self.emit("fontpack_flash_done", {"ok": bool(fok), "msg": fmsg})

        # No coalesce_key: a flash must never be superseded by a later job.
        self.worker.submit("doomwad_install", _job)
        return True, {"queued": True}

    def install_doompack(self, path):
        """Install the doom easter egg's executable engine pack (.plyd, both
        halves — the slave's lockstep drone runs the same engine) as a worker
        job. The DoomPack half of the shipping-shape split (qmk repo,
        doom/PACK_DESIGN.md): same transport, events and error model as
        :meth:`install_doomwad`, with the DOOMPACK pseudo bundle routing it
        to the engine-pack slot. Old firmware without the target NACKs the
        BEGIN — plain error, nothing bricks."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot flash."
        try:
            with open(path, "rb") as f:
                pack_bytes = f.read()
        except OSError as e:
            return False, f"Cannot read engine-pack file: {e}"
        ok, msg = hid_fontpack.validate_doompack(pack_bytes)
        if not ok:
            return False, msg

        def _job(cancel):
            cancel_flag = [False]

            def _progress(pct, m):
                if cancel.is_set():
                    cancel_flag[0] = True
                self.emit("fontpack_flash_progress", {"pct": pct, "msg": m})

            fok, fmsg = hid_fontpack.flash_doompack(
                self.keeb.hid, path, progress_cb=_progress, cancel_flag=cancel_flag)
            self.emit("fontpack_flash_done", {"ok": bool(fok), "msg": fmsg})

        # No coalesce_key: a flash must never be superseded by a later job.
        self.worker.submit("doompack_install", _job)
        return True, {"queued": True}

    def flash_fontpack_bundle(self, bundle):
        """Flash one shipped bundle (by id, e.g. ``"emoji"``, or its slot index) to
        its slot — forced, even if the keyboard is already up to date. Resolves the
        bundle to its res/fontpack/<id>.plyf and delegates to :meth:`flash_fontpack`."""
        from polyhost.services import fontpack_bundle
        manifest = fontpack_bundle.load_bundle_manifest()
        if manifest is None:
            return False, "No font-pack bundles shipped with this host."
        b = self._find_bundle(manifest, bundle)
        if b is None:
            ids = ", ".join(str(x["id"]) for x in manifest["bundles"])
            return False, f"Unknown bundle {bundle!r}. Available: {ids}."
        return self.flash_fontpack(b["path"], bundle_id=b["index"])

    @staticmethod
    def _find_bundle(manifest, bundle):
        key = str(bundle)
        for b in manifest["bundles"]:
            if b["id"] == key or str(b["index"]) == key:
                return b
        return None

    def sync_fontpack(self):
        """Flash every font-pack bundle the keyboard is missing/behind on — the
        same comparison as the on-connect auto-flash, triggered manually."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot flash."
        self.worker.submit("fontpack_sync", self._fontpack_autocheck_job)
        return True, {"queued": True}

    def wipe_fontpack(self):
        """Wipe every font-pack slot — flash the empty-pack sentinel to each shipped
        bundle's slot, so the keyboard renders resident-only fonts again. Streams the
        same ``fontpack_flash_progress``/``fontpack_flash_done`` events as a flash, so
        the tray surfaces it. The next connect re-flashes the bundles (auto-check sees
        device version 0 < shipped), which is the intended "reset to ship state" flow."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot wipe."
        self.worker.submit("fontpack_wipe", self._fontpack_wipe_job)
        return True, {"queued": True}

    def _fontpack_wipe_job(self, cancel):
        """Flash the empty-pack sentinel to every shipped bundle slot (sequential),
        clearing the external-flash font pack. Mirrors `_fontpack_autocheck_job`'s
        progress/guard handling."""
        import os, tempfile
        from polyhost.services import fontpack_bundle
        manifest = fontpack_bundle.load_bundle_manifest()
        # With no shipped manifest, fall back to wiping the current 6 fixed slots.
        slots = (manifest["bundles"] if manifest
                 else [{"id": str(i), "index": i} for i in range(6)])
        if self._fontpack_flash_in_progress:
            return
        self._fontpack_flash_in_progress = True
        cancel_flag = [False]

        def _progress(pct, m):
            if cancel.is_set():
                cancel_flag[0] = True
            self.emit("fontpack_flash_progress", {"pct": pct, "msg": m})

        fd, path = tempfile.mkstemp(suffix=".plyf", prefix="polykybd_wipe_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(hid_fontpack.build_empty_pack())
            n = len(slots)
            for i, b in enumerate(slots):
                self.log.info("Font pack wipe: bundle %s (slot %d) — wiping (%d/%d).",
                              b["id"], b["index"], i + 1, n)
                fok, fmsg = hid_fontpack.flash_fontpack(
                    self.keeb.hid, path, progress_cb=_progress,
                    cancel_flag=cancel_flag, bundle_id=b["index"])
                if not fok:
                    self.emit("fontpack_flash_done",
                              {"ok": False, "msg": f"Wipe bundle {b['id']}: {fmsg}"})
                    return
                if cancel_flag[0]:
                    return
            self.emit("fontpack_flash_done",
                      {"ok": True, "msg": f"Wiped {n} font-pack slot(s)."})
        finally:
            self._fontpack_flash_in_progress = False
            try:
                os.unlink(path)
            except OSError:
                pass

    def fontpack_bundle_status(self):
        """Per-bundle status: device version (from the GET_ID block) vs the shipped
        version, and whether each is stale. ``shipped`` is False with no bundles."""
        from polyhost.services import fontpack_bundle
        manifest = fontpack_bundle.load_bundle_manifest()
        if manifest is None:
            return True, {"shipped": False, "bundles": []}
        dev = dict(getattr(self.keeb, "fontpack_bundle_versions", {}) or {})
        bundles = [{"id": b["id"], "index": b["index"],
                    "device_version": dev.get(b["index"], 0),
                    "shipped_version": b["content_version"],
                    "stale": b["content_version"] > dev.get(b["index"], 0)}
                   for b in manifest["bundles"]]
        return True, {"shipped": True, "bundles": bundles}

    def get_fontpack_status(self):
        """Query the keyboard's currently-loaded font pack (present / abi /
        content_version / font_count). Bounded device read on the worker."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused)."
        try:
            ok, info = self.worker.run_sync(
                "fontpack_status",
                lambda c: hid_fontpack.get_fontpack_status(self.keeb.hid),
                timeout=self.DEVICE_CALL_TIMEOUT)
        except (RuntimeError, TimeoutError) as e:
            return False, f"Font-pack status query failed: {e}"
        if not ok:
            return False, "Keyboard did not report font-pack status (firmware too old?)."
        return True, info

    def _maybe_auto_flash_fontpack(self):
        """Queue the font-pack auto-check on a fresh connect (if enabled).

        Self-terminating: the check only flashes when the keyboard's pack is
        missing or strictly older than the bundled one, and a successful flash
        makes the versions equal — so it never loops. The actual decision +
        flash run on the worker (`_fontpack_autocheck_job`) so they don't block
        the caller (apply_reconnect may be on the Qt thread)."""
        if not self.poly_settings.get("fontpack_auto_flash"):
            return
        self.worker.submit("fontpack_autocheck", self._fontpack_autocheck_job)

    def _fontpack_autocheck_job(self, cancel):
        """Flash any font-pack bundles the keyboard is missing or behind on.

        Compares the device's per-bundle versions (the GET_ID version block,
        captured by the reconnect probe into keeb.fontpack_bundle_versions)
        against the shipped bundles.json, and flashes only the stale ones to
        their fixed slots. Self-terminating: a successful flash makes the
        versions equal, so the next connect finds nothing to do."""
        from polyhost.services import fontpack_bundle
        manifest = fontpack_bundle.load_bundle_manifest()
        if manifest is None:
            return   # no bundles shipped with this host — feature inert
        if self._fontpack_flash_in_progress:
            return   # a flash is already running (connection flapped) — don't double-flash
        device_versions = dict(getattr(self.keeb, "fontpack_bundle_versions", {}) or {})
        stale = hid_fontpack.decide_stale_bundles(device_versions, manifest["bundles"])
        if not stale:
            self.log.info("Font pack auto-check: all %d bundle(s) up to date.",
                          len(manifest["bundles"]))
            return

        self._fontpack_flash_in_progress = True
        cancel_flag = [False]

        def _progress(pct, m):
            if cancel.is_set():
                cancel_flag[0] = True
            self.emit("fontpack_flash_progress", {"pct": pct, "msg": m})

        try:
            n = len(stale)
            for i, b in enumerate(stale):
                dev = device_versions.get(b["index"], 0)
                self.log.info("Font pack auto-flash: bundle %s (slot %d) device v%d < v%d "
                              "— flashing (%d/%d).", b["id"], b["index"], dev,
                              b["content_version"], i + 1, n)
                fok, fmsg = hid_fontpack.flash_fontpack(
                    self.keeb.hid, b["path"], progress_cb=_progress,
                    cancel_flag=cancel_flag, bundle_id=b["index"])
                if not fok:
                    self.log.warning("Font pack auto-flash failed for bundle %s: %s", b["id"], fmsg)
                    self.emit("fontpack_flash_done",
                              {"ok": False, "msg": f"Bundle {b['id']}: {fmsg}", "auto": True})
                    return
                if cancel_flag[0]:
                    self.log.info("Font pack auto-flash cancelled after bundle %s.", b["id"])
                    return
            msg = f"Flashed {n} font-pack bundle(s): {', '.join(b['id'] for b in stale)}."
            self.log.info("Font pack auto-flash complete: %s", msg)
            self.emit("fontpack_flash_done", {"ok": True, "msg": msg, "auto": True})
        finally:
            self._fontpack_flash_in_progress = False

    def check_update(self):
        """Check GitHub for a newer host release (synchronous HTTP — runs on
        the caller's control-server thread, never the worker). Returns
        ``(ok, payload)``: ``(True, {"available", "version", "url"})`` or
        ``(False, msg)`` on an API/network error."""
        from polyhost.services import updater
        try:
            rel = updater.check_latest()
        except updater.UpdateCheckError as e:
            return False, str(e)
        except Exception as e:                      # network/parse failure
            return False, f"{type(e).__name__}: {e}"
        if rel is None:
            return True, {"available": False, "version": __version__}
        return True, {"available": True, "version": rel.version, "url": rel.html_url}

    def install_update(self):
        """Find the latest host release and apply it in the background.

        Streams ``update_progress`` and a terminal ``update_finished_ok`` /
        ``update_relay_needed`` / ``update_failed`` (JSON payloads). The core
        never restarts the process itself — the owning host (HeadlessHost /
        PolyHost) reacts to the terminal event. Returns ``(ok, payload)``:
        ``(False, msg)`` when already up to date or the check failed; else
        ``(True, {"queued", "version"})``."""
        from polyhost.services import updater
        try:
            rel = updater.check_latest()
        except updater.UpdateCheckError as e:
            return False, f"Update check failed: {e}"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
        if rel is None:
            return False, "Already up to date."
        inst = updater.UpdateInstaller(
            rel,
            on_progress=lambda pct, m: self.emit("update_progress", {"pct": pct, "msg": m}),
            on_finished_ok=lambda: self.emit("update_finished_ok", {"version": rel.version}),
            on_relay_needed=lambda p: self.emit("update_relay_needed", {"relay_path": p}),
            on_failed=lambda m: self.emit("update_failed", {"msg": m}))
        inst.start()
        return True, {"queued": True, "version": rel.version}

    # ------------------------------------------------------------------
    # Advanced device commands (the GUI "All PolyKybd Commands" submenu)
    # ------------------------------------------------------------------

    def reset_dynamic_keymap(self):
        return self._device_call("reset_dynamic_keymap",
                                 lambda c: self.keeb.reset_dynamic_keymap())

    def reset_overlay_buffers(self):
        return self._device_call("reset_overlays",
                                 lambda c: self.keeb.reset_overlays())

    def reset_overlay_mapping(self):
        return self._device_call("reset_overlay_mapping",
                                 lambda c: self.keeb.reset_overlay_mapping())

    def reset_overlay_usage(self):
        return self._device_call("reset_overlay_usage",
                                 lambda c: self.keeb.reset_overlay_usage())

    def set_all_overlay_usage(self):
        return self._device_call("set_all_overlay_usage",
                                 lambda c: self.keeb.set_all_overlay_usage())

    def send_overlay_mapping(self, mapping):
        # Over JSON-RPC the dict keys arrive as strings; coerce back to int so
        # the in-process and client paths behave identically.
        m = {int(k): int(v) for k, v in dict(mapping).items()}
        return self._device_call("send_overlay_mapping",
                                  lambda c: self.keeb.send_overlay_mapping(m))

    def activate_bootloader(self):
        """Send-only (the device resets without replying)."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused)."
        self.worker.submit("activate_bootloader", lambda c: self.keeb.activate_bootloader())
        return True, {"queued": True}

    def set_handedness(self, master_is_left):
        """Send-only (both halves reboot onto the new handedness)."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused)."
        self.worker.submit("set_handedness",
                           lambda c, m=bool(master_is_left): self.keeb.set_handedness(m))
        return True, {"queued": True}

    def apply_staged_firmware(self):
        """Apply a previously-staged firmware on the worker; streams
        fw_apply_progress / fw_apply_done (same events as flash_firmware's apply
        step). Returns (ok, payload): (False, msg) if unavailable; else
        (True, {"queued": True})."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot apply firmware."

        def _job(cancel):
            aok, amsg = hid_fw_up.apply_staged_firmware(
                self.keeb.hid,
                progress_cb=lambda pct, m: self.emit("fw_apply_progress", {"pct": pct, "msg": m}))
            self.emit("fw_apply_done", {"ok": bool(aok), "msg": amsg})

        self.worker.submit("apply_staged_firmware", _job)
        return True, {"queued": True}
