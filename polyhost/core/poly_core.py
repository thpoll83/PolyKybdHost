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
from polyhost.device.poly_kybd import MIN_SUPPORTED_PROTOCOL
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
            from polyhost.handler.active_window import OverlayHandler
            # url_provider lets the matcher key overlays off the focused
            # browser's website; None-safe (returns None for non-browsers / when
            # no reporter is present, so matching is unchanged without it).
            url_lookup = (self.browser_url_source.current_url
                          if self.browser_url_source.enabled else None)
            self.overlay_handler = OverlayHandler(
                self.mapping, url_provider=url_lookup,
                enable_legacy_relay=bool(self.settings_get("dev_legacy_plaintext_relay")),
                rpc_relay_enabled=bool(self.settings_get("window_report_network_enabled")))
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
        # safe_mode (newer firmware, user chose restricted): connected but no
        # operational overlay/OS traffic — only firmware-update + debugging.
        if self.connected and not self.safe_mode:
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

    def report_window(self, handle, name, title, os=None, url=None):
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
                caches_reset = True
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
            return False, payload
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
            ok_l, label = self._device_call(
                "macro_label_get", lambda c, i=i: self.keeb.get_macro_label(i))
            steps = macro_body.decode(body)
            macros.append({
                "id": i,
                "label": label if ok_l else "",
                "bytes": len(body),
                "text": macro_body.to_text(steps),
                "steps": [{"kind": s.kind, "code": s.code, "ms": s.ms} for s in steps],
            })
        return True, {**info, "macros": macros}

    def macro_set(self, macro_id, *, text=None, steps=None, label=None):
        """Replace one macro's body and/or label.

        `text` and `steps` are alternatives; passing neither leaves the body alone,
        which is how a label-only edit avoids re-streaming the whole buffer.
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

        if label is not None:
            ok, msg = self._device_call(
                "macro_label_set",
                lambda c, i=macro_id, s=label: self.keeb.set_macro_label(i, s))
            if not ok:
                return False, msg
        return True, "ok"

    def macro_clear(self, macro_id):
        """Empty one macro's body and label."""
        return self.macro_set(macro_id, text="", label="")

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
        to the shipped res/layer_names.yaml."""
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
        # A brightness/daylight setting change takes effect immediately instead
        # of on the next 10-min cycle (covers polyctl + the client-mode dialog).
        if key in self._BRIGHTNESS_SETTING_KEYS:
            self.refresh_daylight_brightness()
        return True, key

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
