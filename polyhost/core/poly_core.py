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
from polyhost.core import events
from polyhost.core.decisions import decide_probe_publish, decide_reconnect_apply
from polyhost.device.poly_kybd import MIN_SUPPORTED_PROTOCOL, protocol_supports
from polyhost.device.device_manager import DeviceManager
from polyhost.device.device_settings import DeviceSettings
from polyhost.device import hid_fw_up
from polyhost.device import hid_fontpack
from polyhost.device.hid_worker import HidWorker
from polyhost.device.poly_kybd import PolyKybd
from polyhost.handler.common import OverlayCommand
from polyhost.services import telemetry as telemetry_svc
from polyhost.services.sleep_listener import install_sleep_listener
from polyhost.services.sunlight_helper import Sunlight
from polyhost.settings import PolySettings
from polyhost.services.crash_report import CrashScanner
from polyhost.util.observable import Observable

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


def flash_progress_relay(emit, cancel, kind):
    """Build the ``(progress_cb, cancel_flag)`` pair every font-pack-transport
    flash hands to its engine.

    ``cancel_flag`` is a one-element **list** because the flash engines poll it
    by reference between chunks — a plain bool could never reach them — and the
    only thing that ever raises it is a progress callback noticing the worker's
    cancel Event (a supersede or a ``suspend()``). Getting that wiring wrong
    fails silently: the flash simply becomes uncancellable, which is why it
    lives in one place rather than being re-typed at each of the five call
    sites. Takes ``emit`` rather than a core so it stays a plain function.
    """
    cancel_flag = [False]

    def _progress(pct, m):
        if cancel.is_set():
            cancel_flag[0] = True      # relay supersede/suspend to the engine
        emit("fontpack_flash_progress", {"pct": pct, "msg": m, "kind": kind})

    return _progress, cancel_flag


class PolyCore(Observable):
    """Operational facade: commands in, events out. No Qt, no widgets."""

    def __init__(self, log, ignore_version=False, start_worker=True,
                 apply_reconnect_in_core=False, allow_key_injection=False,
                 telemetry_mode="in-process"):
        self.log = log
        self.ignore_version = ignore_version
        # SECURITY: the `press`/`release` script commands inject real keystrokes
        # on the keyboard (firmware HID cmd 14 -> the keyboard types into the
        # host's focused app). That is a demo/dev capability, so it is honoured
        # only when the owning process runs in developer mode (--dev, or the
        # persisted developer_mode setting). The
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
        # Newer-firmware policy (session-only, like ignore_version): when the
        # keyboard's protocol is NEWER than this host, the user chooses in a dialog
        # whether to connect fully ("ignore") or run restricted ("safe"). None =
        # undecided (defaults to safe + prompts). Remembered for the session, keyed
        # to the protocol it was chosen for so a re-flash re-asks.
        self.safe_mode = False
        self._newer_fw_policy = None
        self._newer_fw_policy_proto = None
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
        # The generic overlay set -- the app's own mark on ESC plus a shortcut
        # icon on every key its accessibility tree named. Two fetch queues, each
        # built on first use so a headless run that never tracks a window never
        # starts either thread, and a signature of what is currently on the
        # device, which dedupes the per-tick send.
        self._app_icons = None
        self._shortcut_icons = None
        self._generic_on_device = None
        # Apps already told they get no shortcut icons because they are
        # forwarded -- one line each, not one per window change.
        self._told_no_remote_shortcuts = set()
        # Last unicode input method pushed to the keyboard (an InputMethod, or
        # None). The WinCompose settle watcher re-probes after a connect and pushes
        # only on a real change; see _start_wincompose_settle.
        self._last_pushed_unicode_mode = None
        # The mode of a push that is queued but whose device result is not in yet.
        # Separate from _last_pushed_unicode_mode so a FAILED push does not stay
        # deduped: only a confirmed one suppresses a retry.
        self._queued_unicode_mode = None
        # Whether the last confirmed / in-flight push was RAM-only. A volatile
        # push has to be re-asserted persistently once the logon window closes,
        # so "same mode" alone cannot decide whether a push is a duplicate.
        self._last_push_was_volatile = False
        self._queued_push_is_volatile = False
        self._wincompose_shutting_down = False
        self._wincompose_stop = threading.Event()
        self._wincompose_thread = None
        self._wincompose_fast_until = 0.0
        self._wincompose_lock = threading.Lock()
        # When THIS PROCESS started, which is what the logon race is measured
        # against — not when the keyboard connected. See _unicode_mode_is_ambiguous.
        self._started_at = time.monotonic()
        # Re-entrancy guard for the font-pack auto-flash: True only while a flash
        # is actually running, so a connection flap mid-flash can't start a second
        # one — but it is cleared on completion, so each fresh connect (e.g. a
        # physical reconnect after a wipe) re-checks and flashes any stale bundles.
        # decide_stale_bundles keeps it self-terminating: once the device is
        # current, a reconnect finds nothing to do.
        self._fontpack_flash_in_progress = False
        # Bundles whose last flash attempt genuinely failed: {slot index: message}.
        # Re-flashed on the next pass regardless of the version comparison, because a
        # bundle can report a failure and still read as current (see
        # _fontpack_flash_bundles_job). In-memory only — a daemon restart re-reads the
        # device versions anyway, and a persisted failure could outlive its cause.
        self._fontpack_failed = {}

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
        # fast and exception-safe from the caller's perspective; Observable
        # isolates one raising observer from the rest and from this thread.
        Observable.__init__(self, log)

        # Overlay mapping + active-window handler. pywinctl hard-fails at
        # import without a display, so the handler is created lazily and
        # window tracking degrades to "off" (plan §5.4) — explicit overlay
        # sends still work.
        self.mapping = {}
        self.overlay_handler = None
        # Which window-tracking backend active_window selected, for the
        # telemetry census. "" while the handler has not been created, and
        # STAYS "" when its import fails (headless, or no display) — which is
        # the state worth seeing, since such a daemon does no window tracking
        # at all and nothing else reports that.
        self.window_backend = ""
        # Focused-browser active-tab URL, so overlays can key off the website
        # (browser web-apps defeat window-title matching). Fed by the browser
        # extension via the loopback report server below, and/or the macOS
        # AppleScript fallback consulted inside current_url.
        from polyhost.handler.browser_url_source import BrowserUrlSource
        # Shared with the forwarder, which needs the same receiver+provider pair
        # to put the URL on the wire — one implementation, so the two roles
        # cannot drift. `on_change` re-drives an SPA route change (no title
        # change, so the window tick would otherwise see nothing).
        self.browser_url_source = BrowserUrlSource(
            self.log, settings_get=self.poly_settings.get,
            on_change=self._on_browser_url_changed)
        self.load_overlay_mapping(str(_RES_DIR / "overlay-mapping.poly.yaml"))
        self._create_overlay_handler()
        self.browser_url_source.start()

        self.sunlight = Sunlight(
            self.poly_settings.get("brightness_allow_online_location_lookup"),
            self.poly_settings.get("brightness_allow_online_irradiance_request"))

        self.worker = HidWorker(log=self.log)
        self.worker.add_periodic("reconnect", RECONNECT_CYCLE_MSEC / 1000.0,
                                 self._reconnect_periodic)
        self._crash_scanner = CrashScanner()   # firmware crash lines in the console stream
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

        # Anonymous usage census. Created unconditionally (so `polyctl telemetry
        # status/preview` answers even when it is off) but only *started* by
        # start_telemetry(), which the owning host calls alongside worker.start()
        # — so the many short-lived PolyCore instances in the test suite never
        # spawn a thread.
        self.telemetry = self._create_telemetry(telemetry_mode)
        self.telemetry.note("sessions")
        self._log_telemetry_notice()
        if start_worker:
            self.worker.start()
            self.start_telemetry()

    # ------------------------------------------------------------------
    # Observer plumbing
    # ------------------------------------------------------------------

    # subscribe() / emit() come from Observable (polyhost/util/observable.py) —
    # the same seam RemoteCore exposes, so PolyHost can consume either.

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

    def set_newer_firmware_policy(self, choice):
        """Record the session choice for a keyboard whose firmware protocol is
        NEWER than this host: "ignore" (connect fully) or "safe" (restricted).

        Thread-agnostic (no Qt / no device I/O) — called in-process on the Qt main
        thread or, in daemon mode, on a control-server thread over RPC. Forces a
        prompt re-apply by dropping ``last_applied_connected`` so the next ~1 s
        reconnect probe re-runs the decision tree with the new policy (a bool write,
        atomic under the GIL; mirrors set_paused)."""
        if choice not in ("ignore", "safe"):
            return False, f"Unknown newer-firmware policy: {choice!r}"
        self._newer_fw_policy = choice
        self._newer_fw_policy_proto = self.keeb.get_protocol_version()
        self.last_applied_connected = False
        self.log.info("Newer-firmware policy set to '%s'.", choice)
        return True, {"choice": choice}

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
        # Never started unless a window was tracked; stop() is idempotent and
        # never raises, and a daemon thread must still be told to stand down
        # so it cannot resolve an app into a stopped worker.
        if self._app_icons is not None:
            self._app_icons.stop()
        if self._shortcut_icons is not None:
            self._shortcut_icons.stop()
        # Under the same lock as _start_wincompose_settle, and with a one-way
        # flag: otherwise a reconnect landing here concurrently would clear the
        # stop Event and start a fresh watcher AFTER shutdown, which would then
        # hold the core and submit to a stopped worker for up to 15 minutes.
        with self._wincompose_lock:
            self._wincompose_shutting_down = True
            self._wincompose_stop.set()
            wincompose_thread = self._wincompose_thread
            self._wincompose_thread = None
        if wincompose_thread is not None:
            wincompose_thread.join(timeout=1)
        try:
            self.worker.run_sync("save_mru", lambda c: self.keeb.save_mru(), timeout=2)
        except Exception as e:  # never let a save attempt break shutdown
            self.log.debug("MRU save request failed: %s: %s", type(e).__name__, e)
        if self._sleep_listener is not None:
            self._sleep_listener.close()
        self.telemetry.stop()
        self.worker.stop()
        self.browser_url_source.close()
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
            from polyhost.handler.active_window import _BACKEND_NAME, OverlayHandler
            # url_provider lets the matcher key overlays off the focused
            # browser's website; None-safe (returns None for non-browsers / when
            # no reporter is present, so matching is unchanged without it).
            url_lookup = (self.browser_url_source.current_url
                          if self.browser_url_source.enabled else None)
            self.overlay_handler = OverlayHandler(
                self.mapping, url_provider=url_lookup,
                enable_legacy_relay=bool(self.settings_get("dev_legacy_plaintext_relay")),
                rpc_relay_enabled=bool(self.settings_get("window_report_network_enabled")))
            self.window_backend = _BACKEND_NAME
        except Exception as e:
            # Headless / no display: pywinctl cannot load. Window-driven
            # overlay switching stays off; explicit sends still work.
            self.overlay_handler = None
            self.log.warning("Window tracking unavailable (%s: %s) — "
                             "active-window overlay switching disabled.",
                             type(e).__name__, e)

    def _on_browser_url_changed(self):
        """A real URL change arrived: nudge window tracking so an SPA route
        change (which moves no window title) still swaps overlays."""
        if self.overlay_handler is not None:
            self.overlay_handler.invalidate_window_cache()

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
                           on_done=self.emit)
        return True

    @staticmethod
    def _template_files(handler) -> tuple:
        """The template overlay paths covering the focused window, right now.

        ⚠️ From `get_overlay_data()`, the same source `covered_by_template()`
        reads, and NEVER from what `handle_active_window` returned -- that is
        non-None only on the tick the window changes, while the gap fill runs on
        the tick the shortcuts resolve, several later. A list taken from `data`
        would therefore be empty exactly when it is needed, the fill would send
        the synthetic sources alone, and `send_overlays_mru`'s reset would blank
        every hand-made keycap. That is the 2026-09-18 field bug, reachable
        again through a different door.
        """
        data = handler.get_overlay_data()
        if not data:
            return ()
        names = [data] if isinstance(data, str) else list(data)
        return tuple(get_overlay_path(name) for name in names)

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
        # safe_mode (newer firmware, user chose restricted): connected but no
        # operational overlay/OS traffic — only firmware-update + debugging.
        if self.connected and not self.safe_mode:
            data, cmd = handler.handle_active_window(update_cycle_msec, new_window_accept_msec)
            if cmd in (OverlayCommand.DISABLE, OverlayCommand.ENABLE):
                self.submit_overlay_cmd(cmd)
            if data and cmd == OverlayCommand.OFF_ON:
                self.send_overlay_data(data)
                # A template send re-programs the whole pool, so whatever
                # generic overlays were on the device are gone with it.
                self._generic_on_device = None
            elif not self.poly_settings.get("generic_overlays_enabled"):
                pass                      # the whole generic path is switched off
            elif handler.covered_by_template():
                # ⚠️ A TEMPLATE COVERS THIS WINDOW, and asking the HANDLER is the
                # only way to know, because `handle_active_window` returns the
                # template filenames ONLY on the tick the window changes. Reading
                # "a template is active" off `data` therefore saw it once and
                # then believed there was none, so the very next tick sent the
                # generic set, `send_overlays_mru` reset the mapping the template
                # had just committed, and every hand-made keycap went blank about
                # a second after it appeared (field, 2026-09-18).
                #
                # The same trap decides where the FILL gets its file list from:
                # `get_overlay_data()`, never `data`, for exactly that reason.
                if self.poly_settings.get("generic_overlays_fill_gaps"):
                    self._maybe_send_generic_overlays(
                        handler, template_files=self._template_files(handler))
                else:
                    self.log.debug_detailed(
                        "Generic overlays stood down: a template covers this window")
            else:
                # ⚠️ Every tick, not only on a change. `overlay_for` is a dict
                # lookup by contract precisely so this is cheap, and it is what
                # makes a SLOW lookup land: the first sighting returns nothing
                # and queues the fetch, and the tick after it resolves picks the
                # mask up. No completion callback has to race the focus.
                self._maybe_send_generic_overlays(handler)
            self._track_active_os(handler)
        elif self.poly_settings.get("dev_run_window_detection_if_not_connected_to_poly_kybd"):
            handler.handle_active_window(update_cycle_msec, new_window_accept_msec)

    def _maybe_send_generic_overlays(self, handler, template_files=()):
        """Draw the focused app's OWN icon on ESC, and an icon per shortcut key.

        The generic fall-back, in two halves that ship as ONE send: the
        application's own mark on ESC plus whatever its accessibility tree could
        tell us about its keyboard shortcuts.

        ⚠️ **`template_files` is what makes the TEMPLATE win, and it wins per
        KEY rather than per window.** Passed non-empty (the `fill_gaps` branch),
        the hand-made overlays ride the same send ahead of the synthetic
        sources, and `send_overlays_mru` skips a synthetic source on any
        (modifier, keycode) a real one already drew -- so a template keeps every
        key it draws and the generic icons reach only the ones it leaves blank.
        Empty (no template covers this window) is the original behaviour.

        ⚠️ **ONE send, not two, and that is forced rather than tidy.**
        `send_overlays_mru` calls `prepare_for_mru_send()`, which RESETS the
        firmware's whole display->pool mapping, and then commits the mapping it
        built from the filenames it was given. So a second call does not add to
        the first -- it replaces it. Sending the mark and then the shortcut icons
        would leave only the shortcut icons, with the mark's upload wasted.

        ⚠️ Nothing here does I/O. Both `overlay_for` and `overlays_for` are dict
        lookups and a queue append; the lookups themselves (a file read, an HTTP
        GET at a 15 s timeout, and for shortcuts a tree walk over another
        process) happen on the fetchers' own threads. This runs on the GUI main
        thread in the tray and on the core tick thread headless, and neither may
        block.
        """
        if self._app_icons is None:
            from polyhost.services.app_icon_fetcher import AppIconFetcher
            self._app_icons = AppIconFetcher(on_ready=lambda slug: None)
        if self._shortcut_icons is None:
            from polyhost.services.shortcut_fetcher import ShortcutIconFetcher
            # ⚠️ No completion callback on either fetcher, deliberately. The tick
            # re-asks every cycle, so the pass after a resolution picks the
            # answer up on its own -- and a callback would have to race the focus
            # to be correct, since the app it resolved may no longer be the one
            # in front of the user.
            self._shortcut_icons = ShortcutIconFetcher(on_ready=lambda app: None)
        name, identity = handler.focused_app()
        if not name:
            # ⚠️ Silent until 2026-09-17, and that cost a hardware round: with
            # no line here and none from the fetcher (which only speaks once it
            # has RESOLVED something), "no mark appeared" and "this code never
            # ran" look identical in the log. debug_detailed because the tick
            # runs continuously.
            self.log.debug_detailed(
                "No generic overlays: the handler names no focused app "
                "(remote=%s)", handler.is_remote_mapping_entry())
            return
        # `identity` is set only for a FORWARDED window, where the other machine
        # already resolved it — see AppAwareHandler.focused_app.
        mask, slug = self._app_icons.overlay_for(name, identity=identity)
        if mask is None or not slug:
            slug = None
        # ⚠️ **A FORWARDED window's shortcuts CANNOT be harvested here, and
        # asking anyway is worse than not asking.** The harvest reads the
        # application's accessibility tree through a LOCAL backend -- AT-SPI on
        # Linux, UI Automation on Windows -- and a forwarded app is running on
        # the OTHER machine. So the lookup walks this machine's tree, never
        # finds the app, and reports "the app exposes no accelerators", which is
        # indistinguishable from an app that genuinely has none.
        #
        # Measured from a real log (2026-09-18): a Windows daemon with a Linux
        # forwarder drew `mark 'si:gnometerminal' on ESC, 0 shortcut icon(s)`
        # for a gnome-terminal whose own machine exposes SIXTEEN, every one
        # displayable.
        #
        # So the harvest is RELAYED, exactly as the program mark's identity is:
        # the forwarder harvests its own machine and sends the shortcuts as text
        # (`services.shortcut_relay`), and everything after the harvest still
        # happens here, because only this machine knows the icon catalog, the
        # keycap height and the corner.
        #
        # {source_name: {(modifier_value, keycode): mask}} -- one entry per
        # CONCEPT, shared across every key that concept lands on and across
        # applications, which is what makes Save cost one pool slot board-wide.
        if handler.is_remote_mapping_entry():
            remote = getattr(handler, "remote_handler", None)
            relayed = (remote.forwarded_shortcuts(name)
                       if remote is not None else None)
            if relayed is None:
                # ⚠️ NOT `overlays_for(name, harvested=())`. An empty result is
                # cached, so feeding in "has not answered yet" as "found
                # nothing" would pin that answer for the life of the process and
                # the relay would arrive to a cache that no longer asks.
                self._say_no_remote_shortcuts(name)
                shortcuts = {}
            else:
                shortcuts = self._shortcut_icons.overlays_for(
                    name, harvested=relayed)
        else:
            shortcuts = self._shortcut_icons.overlays_for(name)
        signature = self._generic_signature(slug, shortcuts, template_files)
        if signature is None:
            # Both halves are normal on the first sighting (the fetches were
            # just queued) and both fetchers report a real miss themselves, so
            # this stays at the detailed level -- it exists to prove the path RAN.
            self.log.debug_detailed(
                "No generic overlays for '%s' yet: mask=%s slug=%s shortcuts=%d "
                "forwarded_identity=%s", name, mask is not None, slug,
                len(shortcuts), identity is not None)
            return
        if signature == self._generic_on_device:
            return
        self._send_generic_overlays(name, signature, slug, mask, shortcuts,
                                    template_files)

    def _say_no_remote_shortcuts(self, name):
        """Say it once per app, at INFO, because it is not a failure to debug.

        The same level and shape as `ShortcutIconFetcher._say`: this feature
        decides on its own what to draw on ~20 keycaps, so "it drew nothing"
        needs a reason a user can read without developer mode. Bounded by how
        many forwarded applications get focused, not by how long the session
        runs.
        """
        if name in self._told_no_remote_shortcuts:
            return
        self._told_no_remote_shortcuts.add(name)
        self.log.info(
            "No shortcut icons for '%s' yet: it runs on the FORWARDER, so its "
            "shortcuts have to be harvested there and relayed. Either the "
            "answer is still in flight (it arrives on a later report) or that "
            "forwarder predates the relay and will never send them -- the "
            "program mark is unaffected either way.", name)

    @staticmethod
    def _generic_signature(slug, shortcuts, template_files=()):
        """What a send would put on the device, or None when that is nothing.

        ⚠️ `template_files` is part of it because the gap fill sends them, so
        two apps whose generic halves resolve identically -- same mark, same
        shortcuts on the same keys -- but whose templates differ would otherwise
        share a signature, and the second would be reported as already on the
        device while its template was never sent.

        ⚠️ The shortcut half must carry its KEYS and not just its source names.
        Two applications routinely resolve the same concepts -- Save, Copy, Paste
        -- while binding them to different chords, so a name-only signature would
        report the second app as already on the device and its icons would land
        on the first app's keys, or nowhere. The names alone are what the MRU
        cache keys on, and that is correct there for exactly the opposite reason:
        the PIXELS do not depend on the key.
        """
        if not shortcuts:
            # ⚠️ NO SHORTCUTS MEANS NO SEND -- **including the mark**, which is
            # the one case where "what we could resolve" and "what is worth
            # drawing" come apart.
            #
            # The mark alone says only "this app was recognised", and the person
            # reading the board takes it for "this app has icons": it is the
            # confirmation that the rest of the keycaps mean something. Drawn
            # over a board that gained nothing else, it promises what the next
            # glance disproves -- so it is worse than blank, which at least says
            # nothing.
            #
            # ⚠️ The consequence is deliberate and it is LARGE: where the
            # harvest can never answer, the feature is silent. That is all of
            # macOS (no backend built) and every Linux app whose menus live in a
            # hamburger rather than a menu bar. Those are exactly the cases
            # where the mark was standing in for a promise nothing could keep.
            #
            # ⚠️ Also correct for the first tick of an app that DOES have
            # shortcuts: the harvest is asynchronous, so this is "not yet"
            # rather than "never", and the tick that resolves them sends both
            # together. A mark that appears alone and is joined a second later
            # by its icons would read as the board changing its mind.
            return None
        return (slug, tuple(sorted(
            (source, tuple(sorted(keys))) for source, keys in shortcuts.items())),
            tuple(template_files))

    def _send_generic_overlays(self, app, signature, slug, mask, shortcuts,
                               template_files=()):
        """Queue the mark and the shortcut icons for every attached device.

        ⚠️ The converters are built HERE, on the caller's thread, and one PER
        DEVICE. `OverlayData` derives its message counts from that device's
        `DeviceSettings`, so a single instance shared between two keyboards
        would report the wrong transfer cost for at least one of them — and
        `send_overlays_mru` runs on the HID worker, which must not be the thread
        that builds them.

        ⚠️ The mark goes FIRST among the SYNTHETIC sources, so it keeps ESC.
        Both are synthetic and `send_overlays_mru` gives an earlier synthetic
        source the key: the mark is the "which application is this" anchor and
        the one keycap that means the same thing in every app, so a shortcut
        concept that happened to land on Escape must not displace it. The loser
        is logged as deferred, like a template deferral.

        ⚠️ And the TEMPLATES go ahead of both, because the precedence in
        `send_overlays_mru` is positional: it is a real source, so it claims its
        (modifier, keycode) pairs into `covered` unconditionally, and every
        synthetic source after it skips them. Put them last and a template with
        a baked `program_icon:` would lose ESC to the mark -- the opposite of
        "the hand-made design always wins".
        """
        from polyhost.device.keys import KeyCode
        from polyhost.device.synthetic_overlay import (
            program_converter, program_name, shortcut_converter)
        built = []
        for entry in self.device_mgr.all_entries:
            sources = []
            if slug:
                converter = program_converter(entry.device.device_settings,
                                              KeyCode.KC_ESCAPE.value, mask)
                if converter is not None:
                    sources.append((program_name(slug), converter))
            for source, keys in sorted(shortcuts.items()):
                converter = shortcut_converter(entry.device.device_settings, keys)
                if converter is not None:
                    sources.append((source, converter))
            if sources:
                built.append((entry, sources))
        if not built:
            return
        drawn = sum(len(keys) for keys in shortcuts.values())
        # ⚠️ Say which mode this was. The two differ in what the keycaps end up
        # showing AND in what the send costs, and a log that reads the same for
        # both makes "the template lost a key" and "the fill never ran"
        # indistinguishable -- the failure this whole branch is most likely to
        # produce. The per-key verdicts are `send_overlays_mru`'s `deferred`.
        self.log.info(
            "Generic overlays for '%s': %s, %d shortcut icon(s) on %d key(s) "
            "(%s).",
            app, f"mark '{slug}' on ESC" if slug else "no mark",
            len(shortcuts), drawn,
            f"filling the gaps in {len(template_files)} template file(s)"
            if template_files else "no template overlay")
        # Recorded BEFORE the send so a tick landing mid-flight does not queue a
        # second copy of the same set; a failed send clears it again.
        self._generic_on_device = signature
        self.emit("overlay_activity", {"state": "thinking"})
        self.worker.submit(
            "overlay",
            lambda cancel: self._generic_overlay_job(built, cancel, template_files),
            coalesce_key="overlay",
            on_done=self.emit)

    def _generic_overlay_job(self, built, cancel, template_files=()):
        """Worker-thread send of the generic set. Mirrors _overlay_send_job.

        ONE `send_overlays_mru` per device carrying the templates and the
        synthetic sources together -- never two calls. `prepare_for_mru_send()`
        resets the firmware's whole display->pool mapping, so a second call
        replaces the first rather than adding to it, and the template's images
        would be uploaded and then unmapped.
        """
        try:
            for entry, sources in built:
                if cancel.is_set():
                    # Superseded by a real overlay set or another app: forget
                    # what we claimed to have sent, or the set can never be
                    # re-sent for this app.
                    self._generic_on_device = None
                    return
                filenames = list(template_files) + [name for name, _ in sources]
                entry.device.send_overlays_mru(
                    filenames, entry.cache, cancel,
                    synthetic=dict(sources))
        except Exception as e:
            self._generic_on_device = None
            msg = f"Failed to send the generic overlays: {e}"
            self.log.warning(msg)
            self.emit("overlay_warning", msg)
        self.keeb.set_idle(False)

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

    # ------------------------------------------------------------------
    # Unicode input method
    # ------------------------------------------------------------------

    # WinCompose's start time at logon is unknown and machine-dependent
    # ("sometimes it needs a while", field), so rather than guess a cut-off the
    # watch simply never ends: 10 s probes for the first 10 minutes after a
    # connect, then one a minute for as long as the core lives. A TASKLIST spawn
    # is ~50 ms on a background thread, so the steady state is well under a
    # tenth of a percent of one core.
    WINCOMPOSE_FAST_SECONDS = 600   # the boot window, at the short interval
    WINCOMPOSE_FAST_INTERVAL = 10
    WINCOMPOSE_SLOW_INTERVAL = 60

    def _push_unicode_mode(self, mode, persist=True):
        """Submit a unicode-input-method push (HID cmd 20), deduped.

        Device I/O, so it goes on the worker — which means ``submit`` only
        QUEUES it and the result arrives later.

        ``persist=False`` applies the mode in RAM only (firmware protocol 17+),
        for a reading the host is not yet sure of — see
        ``_unicode_mode_is_ambiguous``.

        ⚠️ The mode is recorded as pushed in ``on_done``, only when the keyboard
        reports success. Recording it here would dedupe a push the device never
        took (paused, mid-flash, unplugged), and the settle watcher would then
        skip the retry and exit as soon as it saw WinCompose — leaving the
        keyboard on the wrong mode for the session, which is the very bug this
        watcher exists to fix. ``_queued_unicode_mode`` suppresses a duplicate
        submission while one is in flight and is cleared either way.

        ⚠️ The dedupe is over (mode, persist), not the mode alone: re-asserting
        the SAME mode to make a volatile one stick is the whole point of the
        window closing, and a mode-only dedupe would swallow it."""
        if ((mode, persist) in ((self._last_pushed_unicode_mode,
                                 not self._last_push_was_volatile),
                                (self._queued_unicode_mode,
                                 not self._queued_push_is_volatile))):
            return False
        self._queued_unicode_mode = mode
        self._queued_push_is_volatile = not persist
        self.log.info("Pushing unicode input mode %s to keyboard (%s).", mode.name,
                      "persist" if persist else "volatile")
        self.worker.submit(
            "set_unicode_mode",
            lambda c, m=mode, p=persist: self.keeb.set_unicode_mode(m, persist=p),
            on_done=lambda _name, result, m=mode, p=persist:
                self._unicode_mode_pushed(m, result, p))
        return True

    def _unicode_mode_pushed(self, mode, result, persist=True):
        """HID-worker callback: record the push only if the device took it.

        ``result`` is the job's return value — the device layer's ``(ok, msg)``
        — or the exception the job raised, which the worker catches and stores
        rather than re-raising."""
        if self._queued_unicode_mode == mode:
            self._queued_unicode_mode = None
            self._queued_push_is_volatile = False
        ok = isinstance(result, tuple) and len(result) == 2 and bool(result[0])
        if ok:
            self._last_pushed_unicode_mode = mode
            self._last_push_was_volatile = not persist
        else:
            self.log.warning(
                "Unicode input mode %s was not applied (%r); it will be retried "
                "while the settle watcher is running.", mode.name, result)

    def _unicode_mode_is_ambiguous(self, mode):
        """True while a plain-``Windows`` reading cannot yet be believed.

        Every other reading is a positive observation — wincompose.exe is
        running, or the platform is not Windows at all. A plain ``Windows`` is
        the one that is an ABSENCE, and just after logon "no wincompose.exe" is
        equally consistent with "WinCompose has not finished starting", which is
        the race this whole watcher exists for. Pushing it anyway costs every
        WinCompose user a wrong mode plus a keycap flicker on every single
        logon, and two EEPROM writes, to correct a state the keyboard was
        already in. Waiting costs a keyboard whose stored mode is stale (moved
        machines, or WinCompose uninstalled) up to one window — ONCE, since the
        push at the end of the window persists.

        ⚠️ Measured from the PROCESS start, not from the connect. WinCompose
        races the logon; it does not race a replug three hours later, and
        treating a reconnect as ambiguous would delay the re-assert that exists
        to catch a different keyboard being plugged in."""
        from polyhost.input.unicode_input import InputMethod
        return (sys.platform == "win32" and mode is InputMethod.Windows
                and time.monotonic() - self._started_at < self.WINCOMPOSE_FAST_SECONDS)

    def _apply_unicode_mode(self, mode):
        """Push ``mode``, letting the ambiguity rule decide whether it is STORED.

        Three outcomes, and the middle one is why the volatile flag exists:

        * unambiguous -> push and persist, as always;
        * ambiguous, firmware protocol 17+ -> push VOLATILE. While WinCompose is
          not running, plain ``Windows`` is genuinely how the keyboard should
          type, so applying it is correct; what would be wrong is *storing* a
          reading that may just mean "WinCompose has not started yet". The
          re-assert once the window closes then persists it, and if WinCompose
          turns up first the keyboard's stored mode was never disturbed
          (``eeprom_update_byte`` skips a write when the value is unchanged, so
          re-asserting the mode it already had costs nothing);
        * ambiguous, older firmware -> HOLD it. There is no way to apply without
          storing, so the choice is between a wrong stored value and a delay,
          and the delay is recoverable.

        Reads the CACHED protocol (``protocol_supports``) rather than
        ``keeb.supports()``, which lazily does device I/O — this runs on the
        settle watcher's own thread, which must never touch the device."""
        if not self._unicode_mode_is_ambiguous(mode):
            return self._push_unicode_mode(mode, persist=True)
        if protocol_supports(self.keeb.protocol_version, "unicode_mode_volatile"):
            return self._push_unicode_mode(mode, persist=False)
        self.log.debug("Holding back the %s unicode mode: the reading is ambiguous "
                       "and this firmware cannot apply one without storing it.",
                       mode.name)
        return False

    def _start_wincompose_settle(self):
        """Re-probe the unicode input method for a bounded window after a connect.

        The mode is otherwise detected exactly once, in the post-connect flow —
        and at logon that lands in a race the host usually loses: autostart brings
        PolyKybdHost up before WinCompose, so ``get_input_method()`` sees no
        wincompose.exe and reports plain ``Windows``. The keyboard is then told to
        type Windows-style Alt+numpad sequences for the rest of the session, which
        cannot produce an emoji. The only existing correction is the tray's
        menu-open probe, which needs the user to open the menu; a headless daemon
        has none at all.

        Windows-only: everywhere else ``get_input_method()`` is a constant
        function of ``sys.platform`` and cannot change under us. Runs on its own
        thread because the probe shells out to TASKLIST (~50 ms), which must not
        sit on the HID worker between the reconnect probe and the console read.
        Runs for the life of the core once started; a later connect only re-opens
        the fast-probe window (see _wincompose_settle_loop)."""
        if sys.platform != "win32":
            return
        with self._wincompose_lock:
            if self._wincompose_shutting_down:
                return   # shutdown() already set the stop Event — see below
            # A reconnect re-opens the boot window: it may be a replug on a
            # machine that has just come up, and the probes are cheap.
            self._wincompose_fast_until = (
                time.monotonic() + self.WINCOMPOSE_FAST_SECONDS)
            if self._wincompose_thread is not None and self._wincompose_thread.is_alive():
                return   # already watching; the deadline above extends it
            self._wincompose_stop.clear()
            self._wincompose_thread = threading.Thread(
                target=self._wincompose_settle_loop, name="poly-wincompose-settle",
                daemon=True)
            self._wincompose_thread.start()

    def _wincompose_settle_loop(self):
        """Watch the unicode input method for the life of the core.

        ⚠️ It deliberately does NOT stop once WinCompose is seen, and has no
        deadline. Stopping there would make the watch one-directional — it would
        catch WinCompose starting late and never notice it being QUIT, which
        leaves the keyboard emitting compose sequences that produce nothing.
        Only the tray's menu-open probe covers that today, and a headless daemon
        has no tray. A deadline would just be another guess at how slow a logon
        can be."""
        from polyhost.input.unicode_input import get_input_method
        while True:
            # Re-read the phase each pass: a reconnect re-opens the boot window.
            interval = (self.WINCOMPOSE_FAST_INTERVAL
                        if time.monotonic() < self._wincompose_fast_until
                        else self.WINCOMPOSE_SLOW_INTERVAL)
            if self._wincompose_stop.wait(interval):
                return
            if not self.poly_settings.get("unicode_send_composition_mode"):
                continue   # re-check: the setting can be turned back on
            if not self.connected:
                # Nothing to push to, and the post-connect flow re-asserts the
                # mode anyway — so a disconnected keyboard is not a reason to
                # log a failed push once a minute.
                continue
            try:
                mode = get_input_method()
            except Exception:
                self.log.debug("WinCompose probe failed", exc_info=True)
                continue
            # Deduped inside _push_unicode_mode over (mode, persist), so a
            # steady state is silent AND the volatile push made during the logon
            # window is re-asserted persistently on the first pass after it closes.
            self._apply_unicode_mode(mode)

    def report_window(self, handle, name, title, os=None, url=None,
                      names=(), icon_key=None, icon=None, shortcuts=None):
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
        ⚠️ This is the ONE sink both RPC entry points reach -- the network
        ``WindowReportServer`` and the control socket -- so a parameter missing
        here is missing from both. ``url`` was accepted and silently dropped
        until 2026-09-17; ``names``/``icon_key``/``icon`` raised TypeError at
        the forwarder, which is the louder half of the same omission.

        ``shortcuts`` is the forwarded app's harvested accelerators, decoded by
        `services.shortcut_relay`. Like ``names``/``icon`` it is resolved on the
        forwarder because it cannot be resolved here -- the application's
        accessibility tree lives on the machine running it.

        Returns the uniform ``(ok, payload)`` the RPC layer unwraps."""
        handler = self.overlay_handler
        if handler is None or getattr(handler, "remote_handler", None) is None:
            return False, "window tracking unavailable"
        ret = handler.remote_handler.report_window(
            handle, name, title, os=os, url=url,
            names=names, icon_key=icon_key, icon=icon, shortcuts=shortcuts)
        payload = {"reported": True}
        # The handler answers "send me the icon" here and nowhere else, so
        # dropping this makes the forwarder's follow-up unreachable and the app
        # mark never appears -- the failure looks like a dead feature, not a
        # lost field.
        if isinstance(ret, dict):
            payload.update(ret)
        return True, payload

    def submit_overlay_cmd(self, cmd):
        """Queue an enable/disable of overlays (coalesces with sends)."""
        self.worker.submit("overlay", lambda c, cmd=cmd: self._overlay_cmd_job(cmd, c),
                           coalesce_key="overlay")

    def _overlay_send_job(self, files, cancel):
        """Worker-thread overlay send. Reset/enable that accompany a send stay
        inside this job so ordering is preserved, and the cancel event is
        forwarded through."""
        try:
            # MRU is the only overlay path. The old direct path never programmed
            # overlay_map[] — it relied on the firmware's identity mapping, which
            # now covers only the first NUM_OVERLAY_SLOTS (600) of the 810 flat
            # (slot, variant) indices, so the high modifier variants would all
            # fold onto pool slot 0. Mapping is therefore mandatory, and the
            # per-device toggles that used to select between the two are gone.
            for entry in self.device_mgr.all_entries:
                if cancel.is_set():
                    return
                entry.device.send_overlays_mru(files, entry.cache, cancel)
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
        """Worker-thread enable/disable of overlays on every device entry.

        On a confirmed device-call FAILURE, re-arm the window handler (revert
        its optimistic overlays_enabled) so the next poll re-issues the command
        instead of the handler's redundant-command guard suppressing the retry —
        a failed DISABLE must not leave the keyboard showing overlays while the
        host believes they are off (and vice-versa). Success advances the state
        the handler already set, so nothing to do."""
        ok = True
        for entry in self.device_mgr.all_entries:
            if cancel.is_set():
                return
            # A device call can RAISE (e.g. an HID write on a disconnected
            # handle), not just return (False, …). Treat a raise as a failed
            # result and keep going so every entry is attempted and the re-arm
            # below still runs — otherwise the exception would escape the job
            # before note_overlay_state() and the retry would be suppressed.
            try:
                if cmd == OverlayCommand.DISABLE:
                    res = entry.device.disable_overlays()
                elif cmd == OverlayCommand.ENABLE:
                    res = entry.device.enable_overlays()
                else:
                    continue
                if not (res is None or res[0]):
                    ok = False
            except Exception as e:
                self.log.warning("Overlay %s failed: %s", cmd, e)
                ok = False
        if not ok and self.overlay_handler is not None:
            # Revert to the pre-command state (failed DISABLE -> "enabled",
            # failed ENABLE -> "disabled") so the next tick retries.
            self.overlay_handler.note_overlay_state(cmd == OverlayCommand.DISABLE)
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
        # ⚠️ A FRESH BOOT must re-read the version block even when connectivity
        # never appeared to change. A firmware apply reboots the keyboard INSIDE
        # the flash's own suspend/long-job window, so the probe never observes a
        # disconnect: connected before, connected after, state_changed False.
        # Returning here left `keeb.protocol_version` at its PRE-FLASH value, so
        # everything computed from it -- per-feature capabilities, the
        # newer-firmware decision, the editor's feature gates -- kept describing
        # the firmware that had just been replaced, until the app was restarted.
        # The marker is popped once per keyboard boot, so this costs one extra
        # version+lang query per reboot and nothing in steady state.
        if not snapshot["state_changed"] and not snapshot["fresh_boot"]:
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
        caches_reset = False

        # `fresh_boot` joins `state_changed` here for the reboot-with-no-observed-
        # disconnect case above. Note the block below already MEANT to cover it --
        # its first comment says "e.g. after a firmware flash" -- but sat behind a
        # guard a firmware flash cannot satisfy, and read `kb_proto` which the
        # probe only fills in when it gets this far.
        if snapshot["state_changed"] or snapshot["fresh_boot"]:
            # Forget a remembered newer-firmware choice if the device's protocol
            # changed (e.g. after a firmware flash) so the user is asked again for
            # the new firmware rather than silently reusing the old decision.
            if (self._newer_fw_policy_proto is not None
                    and snapshot.get("kb_proto") != self._newer_fw_policy_proto):
                self._newer_fw_policy = None
                self._newer_fw_policy_proto = None
            decision = decide_reconnect_apply(
                snapshot, __protocol__, __version__, self.ignore_version,
                min_supported=MIN_SUPPORTED_PROTOCOL,
                newer_fw_policy=self._newer_fw_policy)
            applied["decision"] = decision
            self.safe_mode = decision.get("safe_mode", False)

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
            # Census counters: a fresh connect vs losing one already-connected
            # keyboard. The flap count is the one number that would actually
            # tell us a tester's link is unhealthy without asking them.
            if connected_now:
                self.telemetry.note("connects")
            else:
                self.telemetry.note("reconnect_flaps")
            if snapshot["version_ok"] or self.ignore_version:
                self.kb_sw_version = snapshot["kb_sw_version"]

            if decision["do_post_connect"]:
                if connected_now and self.poly_settings.get("unicode_send_composition_mode"):
                    from polyhost.input.unicode_input import get_input_method
                    # Force the push (last_pushed reset) so a reconnect always
                    # re-asserts — this may be a different keyboard, or one whose
                    # EEPROM was reset since. Same idiom as _push_os below.
                    self._last_pushed_unicode_mode = None
                    self._queued_unicode_mode = None
                    # Armed FIRST: at logon this detection races WinCompose's own
                    # autostart and usually loses, and the watcher is what corrects it.
                    self._start_wincompose_settle()
                    self._apply_unicode_mode(get_input_method())
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
                caches_reset = True
                # ⚠️ The MRU cache is now empty and the keyboard's pool is about
                # to be cleared, so whatever generic overlays we believed were on
                # the device are NOT. Without this the dedupe kept claiming they
                # were and the tick never re-sent them: the mark and every
                # shortcut icon stayed missing until the user switched
                # application. Latent since the mark shipped.
                self._generic_on_device = None
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
                # Gated on the font-pack capability (v6+ reports bundle versions in
                # GET_ID): older firmware can't tell us what it has, so we must not
                # blindly mass-flash it now that we connect across protocols.
                if self.keeb.supports("fontpack"):
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
            # disconnect) still must invalidate the host-side MRU cache. Post-connect
            # already does it on the paths where it runs, so this is the fallback for
            # the ones where it does not (a reboot into firmware this host refuses,
            # or into safe mode) -- not a second reset on top of it.
            if snapshot.get("fresh_boot"):
                if not caches_reset:
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
            # Carry the device protocol + per-feature capabilities so a --connect
            # client can gate feature menus the same way the in-process app does
            # (the steady-state event, unlike status.get, otherwise omits them).
            "protocol": self.keeb.get_protocol_version(),
            "capabilities": self._reported_capabilities(),
            # Newer-firmware safe mode + whether the user still needs to be
            # prompted (drives the client's newer-firmware dialog off the status
            # seam — no separate event needed, and a late-attaching client sees it).
            "safe_mode": self.safe_mode,
            "newer_fw_pending": bool(
                (applied["decision"] or {}).get("newer_fw_pending")),
        })
        return applied

    def _reported_capabilities(self):
        """Per-feature capabilities as reported to clients. In safe mode every
        gated feature reads False so the UI (feature submenus, glyph-reset button,
        `polyctl status`) disables them with no extra mode-specific code."""
        caps = self.keeb.capabilities()
        if self.safe_mode:
            return {k: False for k in caps}
        return caps

    def _console_periodic(self, cancel):
        """Worker periodic (250 ms): read serial + console; publish."""
        kb_serial = self.keeb.read_serial()
        kb_log = self.keeb.get_console_output()
        if kb_serial or kb_log:
            self.emit("console", (kb_serial, kb_log))
        if kb_log:
            self._scan_console_for_crashes(kb_log)

    def _scan_console_for_crashes(self, chunk):
        """Watch the console stream for the firmware's crash line and alert once.

        The keyboard prints `crash: side=… kind=…` with its boot banner when the
        previous run ended in a fault or a watchdog timeout (and again, as
        `side=slave`, for the other half). Reading the log by hand is how it would
        otherwise be found — so it is surfaced as an event the tray turns into a
        dialog and `polyctl watch` prints. The scanner reassembles report-sized
        fragments into lines and dedupes the banner's own re-emits."""
        try:
            records = self._crash_scanner.feed(chunk)
        except Exception:  # noqa: BLE001 — a scanner bug must not kill the console read
            self.log.warning("Crash-record scan failed", exc_info=True)
            return
        for rec in records:
            self.log.warning("Keyboard firmware crash record: %s", rec.line)
            self.emit("crash_detected", rec.to_dict())

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
        # Skip while disconnected: there is no keyboard to set, and the compute
        # step does live network lookups (irradiance/location) that would run
        # for nothing on the 10-min tick.
        if not self.connected:
            return
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
        # (ok, payload) like every other command-API method, so the control
        # socket and the in-process caller see the same shape. It is a submit,
        # not a run_sync, so "queued" is all there is to report.
        return True, "queued"

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
            "capabilities": self._reported_capabilities(),
            "safe_mode": self.safe_mode,
            # Undecided newer-firmware state: safe mode with no policy chosen yet.
            # Lets a late-attaching client (status.get) still raise the dialog.
            "newer_fw_pending": self.safe_mode and self._newer_fw_policy is None,
            "hw_version": self.keeb.get_hw_version(),
            "current_lang": self.keeb.get_current_lang(),
            "host_version": __version__,
            "window_backend": self.window_backend,
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

    def set_idle_timeout(self, value):
        try:
            v = int(value)
        except (TypeError, ValueError):
            return False, f"Invalid idle timeout: {value!r}"
        return self._device_call(
            "idle_timeout_set", lambda c, v=v: self.keeb.set_idle_timeout(v))

    def get_idle_timeout(self):
        """(ok, (preset index, seconds)). The seconds are the KEYBOARD's, so a
        preset this host does not know still renders as a duration."""
        return self._device_call(
            "idle_timeout_get", lambda c: self.keeb.get_idle_timeout())

    def refresh_unicode_mode(self):
        """Re-detect the host's unicode input method and push it to the keyboard.

        The mode is otherwise pushed only in the post-connect flow, but it can
        change mid-session — installing (or quitting) WinCompose on Windows flips
        it between ``WinCompose`` and ``Windows``. Without this the keyboard keeps
        emitting the previous mode's sequences until the next replug, so the tray
        calls it when it notices WinCompose appear. Honours the
        ``unicode_send_composition_mode`` setting, like the connect path does."""
        if not self.poly_settings.get("unicode_send_composition_mode"):
            return False, "Sending the unicode composition mode is disabled in the settings."
        from polyhost.input.unicode_input import get_input_method
        mode = get_input_method()
        self.log.info("Re-applying unicode mode %s", mode)
        ok, payload = self._device_call(
            "set_unicode_mode", lambda c, m=mode: self.keeb.set_unicode_mode(m))
        if not ok:
            # Don't record a push the keyboard never took, or the settle watcher
            # (and the next explicit refresh) would dedupe against a mode that
            # never landed.
            return False, payload
        # Unconditional, unlike _push_unicode_mode: an explicit refresh is a user
        # asking for the mode to be re-asserted, so it always reaches the device.
        # Recording it keeps the watcher's dedupe honest.
        self._last_pushed_unicode_mode = mode
        # An explicit refresh always persists, so it also clears a volatile push
        # the watcher would otherwise still be waiting to make stick.
        self._last_push_was_volatile = False
        return True, {"mode": mode.name}

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

    def set_glyph_size(self, value):
        try:
            v = int(value)
        except (TypeError, ValueError):
            return False, f"Invalid glyph size: {value!r}"
        return self._device_call(
            "glyph_size_set", lambda c, v=v: self.keeb.set_glyph_size(v))

    def get_glyph_size(self):
        return self._device_call(
            "glyph_size_get", lambda c: self.keeb.get_glyph_size())

    # --- firmware crash records ----------------------------------------------
    def get_crash_record(self, which=0):
        """The archived crash record of one half (0 master, 1 slave), or None."""
        try:
            w = int(which)
        except (TypeError, ValueError):
            return False, f"Invalid half: {which!r}"
        if w not in (0, 1):
            return False, f"Invalid half: {which!r} (0 = master, 1 = slave)"
        return self._device_call(
            "crash_get", lambda c, w=w: self.keeb.get_crash_record(w))

    def clear_crash_record(self):
        """Erase the keyboard's crash archive; a cleared record can be reported again."""
        ok, payload = self._device_call(
            "crash_clear", lambda c: self.keeb.clear_crash_record())
        if ok:
            self._crash_scanner.forget()
        return ok, payload

    # --- dynamic macros ---------------------------------------------------
    #
    # Deliberately whole-buffer rather than per-macro: the bodies share one NUL
    # delimited buffer, so writing macro 3 means rewriting everything after it. Reading
    # it, editing in memory and writing it back is the only shape that cannot corrupt a
    # neighbour, and at ~2 KB it is a handful of reports either way.

    def macro_list(self):
        """Every macro: label, decoded steps, and the plain text when it is text.

        One call, because an editor needs all of it to draw a list and the alternative
        is sixteen round trips through the worker for something that is two reads.
        """
        from polyhost.services import macro_body

        ok, info = self._device_call("macro_info", lambda c: self.keeb.get_macro_info())
        if not ok:
            return False, info
        ok, buf = self._device_call(
            "macro_read", lambda c, n=info["capacity"]: self.keeb.read_macro_buffer(n))
        if not ok:
            return False, buf
        bodies = macro_body.split_buffer(buf, info["count"])
        macros = []
        for i, body in enumerate(bodies):
            ok_l, look = self._device_call(
                "macro_look_get", lambda c, i=i: self.keeb.get_macro_look(i))
            if not ok_l or not isinstance(look, dict):
                look = {"label": "", "style": 0, "icon": 0}
            steps = macro_body.decode(body)
            macros.append({
                "id": i,
                "label": look.get("label", ""),
                "style": look.get("style", 0),
                "icon": look.get("icon", 0),
                "bytes": len(body),
                "text": macro_body.to_text(steps),
                "steps": [{"kind": s.kind, "code": s.code, "ms": s.ms} for s in steps],
            })
        return True, {**info, "macros": macros}

    def macro_set(self, macro_id, *, text=None, steps=None, label=None,
                  style=None, icon=None):
        """Replace one macro's body and/or its keycap look.

        `text` and `steps` are alternatives; passing neither leaves the body alone,
        which is how a look-only edit avoids re-streaming the whole buffer.

        The look is caption + style + icon and travels as ONE write, so it can never be
        half-applied. Passing only some of the three therefore has to read the current
        look first and carry the rest forward, rather than defaulting the omitted
        fields -- otherwise setting a caption would silently reset the style.
        """
        from polyhost.services import macro_body

        try:
            macro_id = int(macro_id)
        except (TypeError, ValueError):
            return False, f"Invalid macro id: {macro_id!r}"

        if text is not None or steps is not None:
            ok, info = self._device_call("macro_info", lambda c: self.keeb.get_macro_info())
            if not ok:
                return False, info
            if not 0 <= macro_id < info["count"]:
                return False, f"macro {macro_id} out of range (0..{info['count'] - 1})"
            ok, buf = self._device_call(
                "macro_read", lambda c, n=info["capacity"]: self.keeb.read_macro_buffer(n))
            if not ok:
                return False, buf
            bodies = macro_body.split_buffer(buf, info["count"])
            try:
                if steps is not None:
                    bodies[macro_id] = macro_body.encode_steps(
                        [macro_body.Step(**s) for s in steps])
                else:
                    bodies[macro_id] = macro_body.encode_text(text)
                packed = macro_body.join_buffer(bodies, info["capacity"])
            except (macro_body.MacroError, TypeError) as e:
                return False, str(e)
            ok, msg = self._device_call(
                "macro_write", lambda c, d=packed: self.keeb.write_macro_buffer(d))
            if not ok:
                return False, msg

        if label is not None or style is not None or icon is not None:
            cur = {"label": "", "style": 0, "icon": 0}
            if label is None or style is None or icon is None:
                ok, got = self._device_call(
                    "macro_look_get", lambda c, i=macro_id: self.keeb.get_macro_look(i))
                if not ok:
                    return False, got
                if isinstance(got, dict):
                    cur = got
            new_label = cur.get("label", "") if label is None else label
            new_style = cur.get("style", 0) if style is None else int(style)
            new_icon = cur.get("icon", 0) if icon is None else int(icon)
            ok, msg = self._device_call(
                "macro_look_set",
                lambda c, i=macro_id, t=new_label, st=new_style, ic=new_icon:
                    self.keeb.set_macro_look(i, t, st, ic))
            if not ok:
                return False, msg
        return True, "ok"

    def macro_clear(self, macro_id):
        """Empty one macro's body and its whole keycap look."""
        return self.macro_set(macro_id, text="", label="", style=0, icon=0)

    def replay_startup_anim(self):
        return self._device_call(
            "replay_startup_anim", lambda c: self.keeb.replay_startup_anim())

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

    def keymap_layer_names(self):
        """Names for the host-remappable layers, straight from the keyboard (v14+).

        Empty list on firmware too old to answer; the layout editor then falls back
        to the shipped LAYER_TAGS fallback."""
        return self._device_call(
            "keymap_layer_names", lambda c: self.keeb.get_layer_names())

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
        """Firmware version read LIVE from the keyboard (HID cmd 0x43).

        ⚠️ This deliberately does device I/O rather than returning the cached
        ``keeb.get_sw_version()`` string parsed at the last GET_ID. The whole
        reason to ask is to find out what is *running right now* — typically
        straight after a flash — and a cache cannot answer that: the reconnect
        probe is suspended for the duration of a flash (``worker.exclusive()``),
        so the cached value is pinned to the state before it. It reported the
        pre-flash version after a firmware update had demonstrably installed, and
        was believed (field, 2026-08-05).

        Failing loudly is part of the fix: while the worker is suspended
        ``_device_call`` returns the "suspended" error instead of a stale string,
        which is the honest answer to "what is on the keyboard" mid-flash.
        """
        ok, payload = self._device_call(
            "fw_version", lambda c: hid_fw_up.get_fw_version(self.keeb.hid))
        if not ok:
            return False, payload
        if not payload:
            return False, "The keyboard did not answer the firmware-version query."
        return True, payload

    def execute_commands(self, lines):
        """Queue a (cancel-aware) command script across every device entry.

        Unless key injection is allowed (host in developer mode), the
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
                    "not running in developer mode (--dev).", dropped)

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
        self.note_settings_changed([key])
        return True, key

    def note_settings_changed(self, keys=None):
        """Apply the side effects a settings change has on the live device.

        ⚠️ Both writers land here, and there are exactly two: ``settings_set``
        (polyctl and the client-mode dialog) and the in-process settings dialog,
        which writes the file directly and then calls this. A side effect added
        to only one of them is a setting that behaves differently depending on
        whether the GUI happens to be a daemon client — which is how enabling
        ``unicode_send_composition_mode`` mid-session came to do nothing at all
        until the next reconnect.

        ``keys`` None means "anything in the dialog may have changed", which is
        all the in-process dialog knows."""
        if keys is None or self._BRIGHTNESS_SETTING_KEYS.intersection(keys):
            # Takes effect now instead of on the next 10-min cycle.
            self.refresh_daylight_brightness()
        if keys is None or "unicode_send_composition_mode" in keys:
            self._refresh_unicode_watch()
        if keys is None or self._GENERIC_ICON_SETTING_KEYS.intersection(keys):
            self._forget_generic_overlays()

    _GENERIC_ICON_SETTING_KEYS = frozenset({
        # ⚠️ The two outer switches belong here as much as the inner ones, and
        # for the SAME reason rather than for tidiness: turning `fill_gaps` on
        # mid-session changes what a templated app should be showing, and the
        # tick would otherwise read the cached signature and report it as
        # already on the device. `_forget_generic_overlays` clears exactly that.
        "generic_overlays_enabled", "generic_overlays_fill_gaps",
        "shortcut_icons_enabled", "shortcut_icon_auto_fetch",
        "shortcut_icon_height", "shortcut_icon_placement",
    })

    def _forget_generic_overlays(self):
        """Re-harvest and re-render after a settings change.

        ⚠️ Both caches AND the device signature, because each one alone leaves
        the change invisible. A plan built while auto-fetch was off carries no
        icons and nothing would ever ask again; and a height or corner change
        alters the PIXELS while the source names the signature is built from may
        be unchanged, so the tick would report the new masks as already on the
        device. (`shortcut_overlays.source_name` puts the height and corner in
        the MRU key for the same reason, one layer down.)
        """
        if self._app_icons is not None:
            # ⚠️ `forget_misses`, NOT `forget` -- which does not exist on this
            # fetcher and raised AttributeError here, BEFORE the two lines
            # below, so no generic-icon setting took effect at all mid-session
            # (Greptile, #240). The suite missed it because the fixture is a
            # bare MagicMock, which answers any attribute; the tests now pass
            # `spec=` so a nonexistent method fails there too.
            self._app_icons.forget_misses()
        if self._shortcut_icons is not None:
            self._shortcut_icons.forget()
        self._generic_on_device = None
        # ⚠️ And make the BOARD follow, not just the host's caches. Turning a
        # switch OFF means no generic send will happen, so whatever is already
        # mapped on the keycaps stays there until the next app switch -- a
        # setting that visibly does nothing, which is the failure this repo
        # keeps recording. `force_resend` makes the next tick re-evaluate the
        # window as if it had changed, so a templated app re-sends its template
        # (which re-programs the pool) and an untemplated one disables overlays.
        #
        # Unconditional rather than only-on-OFF: whether anything generic will
        # be drawn under the new settings is the tick's job to work out, not
        # this hook's. The cost is one overlay send per Settings-dialog OK.
        if self.overlay_handler is not None:
            self.overlay_handler.force_resend()

    def _refresh_unicode_watch(self):
        """Start the settle watcher and re-assert the mode after the setting was
        turned on mid-session.

        The watcher is otherwise armed only in the post-connect flow, and only
        when the setting was already on — so a user who connects with it off and
        enables it later had no watcher, and the keyboard kept whatever unicode
        mode it was last told, indefinitely. Turning it OFF stops nothing on
        purpose: the watcher re-reads the setting every pass (it can be turned
        back on) and pushes nothing while it is off."""
        if not self.poly_settings.get("unicode_send_composition_mode"):
            return
        self._start_wincompose_settle()
        if not self.connected:
            return   # the post-connect flow will assert it
        from polyhost.input.unicode_input import get_input_method
        self._apply_unicode_mode(get_input_method())

    # ------------------------------------------------------------------
    # Telemetry (anonymous usage census)
    # ------------------------------------------------------------------

    def _create_telemetry(self, mode):
        """Build the reporter, minting + persisting the install id on first use.

        The id is generated here rather than at first ping so that
        `polyctl telemetry status` can show the user exactly what identifies
        their install before anything is ever sent."""
        install_id = self.poly_settings.get("telemetry_install_id")
        if not install_id:
            install_id = telemetry_svc.new_install_id()
            try:
                self.settings_set("telemetry_install_id", install_id)
            except Exception:  # a read-only config must not break startup
                self.log.debug("Could not persist telemetry install id",
                               exc_info=True)
        return telemetry_svc.TelemetryReporter(
            self.log, install_id,
            snapshot_fn=self._telemetry_snapshot,
            enabled_fn=lambda: bool(self.poly_settings.get("telemetry_enabled")),
            endpoint_fn=lambda: self.poly_settings.get("telemetry_endpoint") or "",
            mode=mode)

    def _telemetry_snapshot(self):
        """(status, fontpack versions) — both read from cache, no device I/O,
        so the reporter thread can call this without touching the worker."""
        # getattr, matching fontpack_bundle_status and _fontpack_autocheck_job.
        # PolyKybd always defines the attribute, so this is consistency rather
        # than a live bug — but the callers swallow exceptions, so if a device
        # object ever lacked it the whole device block would vanish from the
        # ping with no trace, and all three reads should fail the same way.
        return (self.get_status(),
                dict(getattr(self.keeb, "fontpack_bundle_versions", None) or {}))

    def _log_telemetry_notice(self):
        """One INFO line per start saying what the telemetry state is.

        ⚠️ This line is part of the DISCLOSURE, not debug output — since the
        first-run dialog was removed there is no in-app consent step, so this and
        the release notes are how a user learns telemetry is on. Do not gate it
        on an "already told them" flag, downgrade it to debug, or drop it in a
        logging cleanup: repeating it every start is the point, and it is the
        only disclosure a headless daemon can make. See docs/telemetry.md."""
        if self.poly_settings.get("telemetry_enabled") and \
                self.poly_settings.get("telemetry_endpoint"):
            self.log.info(
                "Telemetry: ON — one anonymous ping/day (host+firmware version, "
                "OS, event counts; no window titles, app names or location). "
                "Turn off in Settings or `polyctl telemetry disable`; see what "
                "would be sent with `polyctl telemetry preview`.")
        else:
            self.log.info("Telemetry: off.")

    def start_telemetry(self):
        """Start the census thread. Call it wherever ``worker.start()`` is
        called (the hosts construct the core with ``start_worker=False`` and
        start it themselves once their own wiring is in place)."""
        self.telemetry.start()

    def telemetry_status(self):
        return self.telemetry.status()

    def telemetry_preview(self):
        return self.telemetry.preview()

    def telemetry_set_enabled(self, enabled):
        return self.settings_set("telemetry_enabled", bool(enabled))

    def telemetry_send_now(self):
        """Force a ping now (ignores the daily throttle). Used by
        `polyctl telemetry send` to verify an endpoint works."""
        ok, msg = self.telemetry.maybe_send(force=True)
        return bool(ok), msg

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
        # Counts the ATTEMPT, not the outcome — whether it worked is already
        # visible in the next ping's fw_version, and an attempt that never
        # produces a new version is exactly the case worth seeing.
        self.telemetry.note("fw_flashes")

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

    def _flash_resource(self, path, *, job_name, noun, validate, run, kind,
                        telemetry_counter=None):
        """Shared body of every resource flash that rides the font-pack transport.

        The font-pack bundle, the doom game data (``.whx``) and the doom engine
        pack (``.plyx``) all take the same route to the keyboard and differ in
        only four things — the "cannot read" noun, the validator, how the flash
        engine is invoked, and the ``kind`` tag on the events. Everything else is
        identical and lives here: the firmware-action gate, fail-fast reading +
        validation returning the uniform ``(ok, payload)`` contract, the
        **uncoalesced** worker job, the cancel relay into the flash engine, and
        the ``fontpack_flash_progress`` / ``fontpack_flash_done`` event pair that
        ``polyctl`` and the tray render their wording from (via ``kind``).

        ``run(data, progress_cb, cancel_flag)`` performs the actual upload and
        returns the engines' ``(ok, msg, commit_status)``; it is a closure rather
        than a set of flags because the engines genuinely disagree on their
        argument (``flash_fontpack`` re-opens the path, the doom flashers take the
        read bytes). The ``commit_status`` is discarded here on purpose: only the
        multi-bundle pass (``_fontpack_flash_bundles_job``) acts on it, to tell a
        lost COMMIT acknowledgement apart from a real refusal and decide whether to
        queue a retry. A single explicit flash has nothing to retry into — its
        caller asked for exactly this one upload and gets the plain verdict."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot flash."
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            return False, f"Cannot read {noun}: {e}"
        ok, msg = validate(data)
        if not ok:
            return False, msg
        if telemetry_counter is not None:
            self.telemetry.note(telemetry_counter)

        def _job(cancel):
            progress, cancel_flag = flash_progress_relay(self.emit, cancel, kind)
            fok, fmsg, _status = run(data, progress, cancel_flag)
            self.emit("fontpack_flash_done",
                      {"ok": bool(fok), "msg": fmsg, "kind": kind})

        # No coalesce_key: a flash must never be superseded by a later job.
        self.worker.submit(job_name, _job)
        return True, {"queued": True}

    def flash_fontpack(self, path, bundle_id=0):
        """Flash an external-flash ``.plyf`` font-pack bundle as a worker job.

        ``bundle_id`` selects the fixed flash slot (the bundle's index in
        res/fontpack/bundles.json); 0 by default. Same shape as
        :meth:`flash_firmware` minus the apply step — the firmware re-loads fonts
        in place on COMMIT (no reboot). Gating + header validation happen
        synchronously (uniform ``(ok, payload)``); the upload then streams
        ``fontpack_flash_progress`` events with a terminal ``fontpack_flash_done``."""
        return self._flash_resource(
            path,
            job_name="fontpack_flash",
            noun="font-pack file",
            validate=hid_fontpack.validate_fontpack,
            # The bundle flasher re-opens the path itself (it streams the file).
            run=lambda data, progress, flag: hid_fontpack.flash_fontpack(
                self.keeb.hid, path, progress_cb=progress, cancel_flag=flag,
                bundle_id=bundle_id),
            kind=events.FLASH_KIND_FONTPACK,
            # Counts the ATTEMPT, not the outcome — see flash_firmware.
            telemetry_counter="fontpack_flashes")

    def install_doomwad(self, path):
        """Install the doom easter egg's WHX game data (both halves) as a worker job.

        Rides the font-pack transport with the DOOMWAD pseudo bundle — the firmware
        routes it to the WHX slot at the top of the resource region and bridges the
        slave's copy in the same pass. Same event stream as a font-pack flash
        (``fontpack_flash_progress``/``fontpack_flash_done``), so ``polyctl`` and the
        tray progress surfaces work unchanged. Old firmware without the DOOMWAD
        target NACKs the BEGIN — reported as a plain error, nothing bricks."""
        return self._flash_resource(
            path,
            job_name="doomwad_install",
            noun="game-data file",
            validate=hid_fontpack.validate_doomwad,
            run=lambda data, progress, flag: hid_fontpack.flash_doomwad(
                self.keeb.hid, data, progress_cb=progress, cancel_flag=flag),
            kind=events.FLASH_KIND_DOOMWAD)

    def install_doompack(self, path):
        """Install the doom easter egg's executable engine pack (.plyx, both
        halves — the slave's lockstep drone runs the same engine) as a worker
        job. The DoomPack half of the shipping-shape split (qmk repo,
        doom/PACK_DESIGN.md): same transport, events and error model as
        :meth:`install_doomwad`, with the DOOMPACK pseudo bundle routing it
        to the engine-pack slot. Old firmware without the target NACKs the
        BEGIN — plain error, nothing bricks."""
        return self._flash_resource(
            path,
            job_name="doompack_install",
            noun="engine-pack file",
            validate=hid_fontpack.validate_doompack,
            run=lambda data, progress, flag: hid_fontpack.flash_doompack(
                self.keeb.hid, data, progress_cb=progress, cancel_flag=flag),
            kind=events.FLASH_KIND_DOOMPACK)

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

    def sync_fontpack(self, force=False):
        """Flash font-pack bundles manually.

        Default: the same targets the on-connect auto-check picks — stale bundles plus
        anything a previous attempt failed on. ``force=True`` re-flashes EVERY shipped
        bundle regardless of version, which is the only way to recover a bundle the
        keyboard reports as current but renders wrong (a version comparison cannot see
        that, so without a force there was no route back at all)."""
        if not self._fw_actions_allowed():
            return False, "No PolyKybd present (or paused) — cannot flash."
        self.worker.submit(
            "fontpack_sync",
            lambda cancel: self._fontpack_flash_bundles_job(cancel, force_all=bool(force)))
        return True, {"queued": True, "force": bool(force)}

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
        _progress, cancel_flag = flash_progress_relay(
            self.emit, cancel, events.FLASH_KIND_FONTPACK)

        fd, path = tempfile.mkstemp(suffix=".plyf", prefix="polykybd_wipe_")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(hid_fontpack.build_empty_pack())
            n = len(slots)
            wiped, failed = [], []
            for i, b in enumerate(slots):
                self.log.info("Font pack wipe: bundle %s (slot %d) — wiping (%d/%d).",
                              b["id"], b["index"], i + 1, n)
                fok, fmsg, _status = hid_fontpack.flash_fontpack(
                    self.keeb.hid, path, progress_cb=_progress,
                    cancel_flag=cancel_flag, bundle_id=b["index"])
                # Carry on through a failure, like the flash pass: one slot refusing
                # says nothing about the rest, and stopping leaves a half-wiped pack
                # with no report of which slots were reached.
                (wiped if fok else failed).append(b["id"])
                if not fok:
                    self.log.warning("Font pack wipe failed for slot %s: %s", b["id"], fmsg)
                if cancel_flag[0]:
                    break
            msg = f"Wiped {len(wiped)} font-pack slot(s)."
            if failed:
                msg += f" Failed: {', '.join(failed)}."
            self.emit("fontpack_flash_done",
                      {"ok": not failed, "msg": msg,
                       "kind": events.FLASH_KIND_FONTPACK})
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
        # "retry" is separate from "stale" on purpose: a bundle whose flash failed can
        # still read as current, so a UI that only looks at `stale` shows "up to date"
        # over a bundle that needs another attempt.
        bundles = [{"id": b["id"], "index": b["index"],
                    "device_version": dev.get(b["index"], 0),
                    "shipped_version": b["content_version"],
                    "stale": b["content_version"] > dev.get(b["index"], 0),
                    "retry": b["index"] in self._fontpack_failed,
                    "last_error": self._fontpack_failed.get(b["index"], "")}
                   for b in manifest["bundles"]]
        return True, {"shipped": True, "bundles": bundles,
                      "failed": [b["id"] for b in bundles if b["retry"]]}

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
        """Flash any font-pack bundles the keyboard is missing, behind on, or that
        failed a previous attempt.

        Compares the device's per-bundle versions (the GET_ID version block,
        captured by the reconnect probe into keeb.fontpack_bundle_versions)
        against the shipped bundles.json. ⚠️ That comparison alone is NOT enough to
        decide what to flash: a flash that streamed fine and only lost its COMMIT
        acknowledgement leaves the slot valid and current, so the version check
        reports it as up to date and it is never retried (field 2026-08-17 — the
        `symbol` bundle reported a failure and was then skipped on every later
        connect and manual sync). Anything a previous attempt genuinely failed is
        therefore remembered and re-flashed regardless of its version."""
        self._fontpack_flash_bundles_job(cancel, auto=True)

    def _fontpack_flash_bundles_job(self, cancel, auto=False, force_all=False):
        """The shared bundle-flash pass: pick the targets, flash them all, report once.

        Targets are the stale bundles ∪ the ones a previous pass failed on, or every
        shipped bundle when ``force_all``."""
        from polyhost.services import fontpack_bundle
        manifest = fontpack_bundle.load_bundle_manifest()
        if manifest is None:
            return   # no bundles shipped with this host — feature inert
        if self._fontpack_flash_in_progress:
            return   # a flash is already running (connection flapped) — don't double-flash
        device_versions = dict(getattr(self.keeb, "fontpack_bundle_versions", {}) or {})
        if force_all:
            targets = list(manifest["bundles"])
        else:
            stale = hid_fontpack.decide_stale_bundles(device_versions, manifest["bundles"])
            stale_idx = {b["index"] for b in stale}
            # Re-add anything a previous pass failed on even though its version now
            # reads current — see the docstring above.
            retry = [b for b in manifest["bundles"]
                     if b["index"] in self._fontpack_failed and b["index"] not in stale_idx]
            targets = sorted(stale + retry, key=lambda b: b["index"])
        if not targets:
            self.log.info("Font pack auto-check: all %d bundle(s) up to date.",
                          len(manifest["bundles"]))
            return

        self._fontpack_flash_in_progress = True
        _progress, cancel_flag = flash_progress_relay(
            self.emit, cancel, events.FLASH_KIND_FONTPACK)

        try:
            n = len(targets)
            done, failed, caveats = [], [], []
            for i, b in enumerate(targets):
                dev = device_versions.get(b["index"], 0)
                self.log.info("Font pack flash: bundle %s (slot %d) device v%d -> v%d "
                              "(%d/%d).", b["id"], b["index"], dev, b["content_version"],
                              i + 1, n)
                fok, fmsg, fstatus = hid_fontpack.flash_fontpack(
                    self.keeb.hid, b["path"], progress_cb=_progress,
                    cancel_flag=cancel_flag, bundle_id=b["index"])
                if fok:
                    done.append(b["id"])
                    self._fontpack_failed.pop(b["index"], None)
                else:
                    landed, note = self._verify_flashed_bundle(b, fstatus, fmsg)
                    if landed:
                        done.append(b["id"])
                        caveats.append(note)
                        if fstatus == hid_fontpack.COMMIT_NO_SLAVE:
                            # Verified on the MASTER only — and the firmware cannot tell
                            # us whether the slave lost its ACK or explicitly refused its
                            # own finalize (both surface as SYNC_CRC32_ERR over the
                            # bridge). So keep it queued: a re-flash on the next pass is
                            # one bundle's worth of traffic, whereas trusting it leaves
                            # the halves silently rendering different glyph sets.
                            self._fontpack_failed[b["index"]] = fmsg
                        else:
                            self._fontpack_failed.pop(b["index"], None)
                    else:
                        failed.append(b["id"])
                        self._fontpack_failed[b["index"]] = fmsg
                        # Keep going: one bundle's failure says nothing about the
                        # next one's, and aborting here cost six perfectly good
                        # bundles a re-flash on the next connect (field 2026-08-17).
                        self.log.warning("Font pack flash failed for bundle %s (%s): %s",
                                         b["id"], fstatus, fmsg)
                if cancel_flag[0]:
                    self.log.info("Font pack flash cancelled after bundle %s.", b["id"])
                    break
            self._emit_fontpack_summary(done, failed, caveats, auto)
        finally:
            self._fontpack_flash_in_progress = False

    def _verify_flashed_bundle(self, bundle, status, msg):
        """After a failed COMMIT, ask the keyboard whether the bundle landed anyway.

        Re-reads the GET_ID version block (the same cheap query the reconnect probe
        uses) and reports ``(landed, note)``. This is what stops a lost
        acknowledgement being reported as a failed flash — and, just as important,
        stops it being silently forgotten, since ``landed`` also clears the retry
        entry. Two things it deliberately does NOT do:

        * A ``rejected`` status is never verified. The keyboard told us it refused
          the data, so re-reading a version could only mislead.
        * The version block reflects the MASTER's slots only, so it cannot prove the
          slave got the bundle. On a ``slave-unconfirmed`` status the note says so
          rather than claiming success outright.

        Safe to run next to the reconnect probe: this is the worker thread (the flash
        job owns it), and ``query_id`` only ever *sets* the firmware's one-shot
        fresh-boot flag — only ``pop_fresh_boot`` clears it — so if this query is the
        one that happens to see the ``*`` marker, the next probe still pops it."""
        if status == hid_fontpack.COMMIT_REJECTED:
            return False, ""
        try:
            ok, _ = self.keeb.query_id()
        except Exception as exc:                      # noqa: BLE001 — a probe must not mask the flash error
            self.log.debug("Post-flash verification query failed: %s", exc)
            return False, ""
        if not ok:
            return False, ""
        dev = dict(getattr(self.keeb, "fontpack_bundle_versions", {}) or {}).get(bundle["index"], 0)
        if dev < bundle["content_version"]:
            return False, ""
        if status == hid_fontpack.COMMIT_NO_SLAVE:
            note = (f"{bundle['id']}: stored (v{dev}), but the other half never confirmed — "
                    f"it should pick the glyphs up at the next reboot")
        else:
            note = f"{bundle['id']}: stored (v{dev}); only the confirmation was lost"
        self.log.warning("Font pack bundle %s reported a failed COMMIT (%s) but the keyboard "
                         "now reports v%d — treating it as stored. %s", bundle["id"], status,
                         dev, msg)
        return True, note

    def _emit_fontpack_summary(self, done, failed, caveats, auto):
        """One terminal ``fontpack_flash_done`` for the whole pass, naming every
        bundle that failed — a per-bundle abort used to hide the rest."""
        parts = []
        if done:
            parts.append(f"Flashed {len(done)} font-pack bundle(s): {', '.join(done)}.")
        if caveats:
            parts.append("Unconfirmed: " + "; ".join(caveats) + ".")
        if failed:
            parts.append(f"Failed: {', '.join(failed)} — retried automatically on the "
                         f"next connect, or from Updates → Retry keyboard fonts.")
        msg = " ".join(parts) or "Nothing to flash."
        if failed:
            self.log.warning("Font pack flash finished with failures: %s", msg)
        else:
            self.log.info("Font pack flash complete: %s", msg)
        self.emit("fontpack_flash_done",
                  {"ok": not failed, "msg": msg, "auto": auto,
                   "kind": events.FLASH_KIND_FONTPACK})

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
        return True, {"available": True, "version": rel.version, "url": rel.html_url,
                      "name": getattr(rel, "name", ""), "notes": getattr(rel, "notes", "")}

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
        self.telemetry.note("update_installs")
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
