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
import threading

from polyhost._version import __version__, __protocol__
from polyhost.core.decisions import decide_probe_publish, decide_reconnect_apply
from polyhost.device.device_manager import DeviceManager
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.hid_worker import HidWorker
from polyhost.device.poly_kybd import PolyKybd
from polyhost.device.poly_kybd_mock import PolyKybdMock
from polyhost.handler.common import OverlayCommand
from polyhost.services.sleep_listener import install_sleep_listener
from polyhost.services.sunlight_helper import Sunlight
from polyhost.settings import PolySettings

RECONNECT_CYCLE_MSEC = 1000
UPDATE_CYCLE_MSEC = 250
PERIODIC_10MIN_CYCLE_MSEC = 1000 * 60 * 10
NEW_WINDOW_ACCEPT_TIME_MSEC = 1000

_RES_DIR = pathlib.Path(__file__).parent.parent.resolve() / "res"


def get_overlay_path(filepath):
    """Absolute path of a shipped overlay template (polyhost/res/overlays)."""
    return os.path.join(_RES_DIR, "overlays", filepath)


class PolyCore:
    """Operational facade: commands in, events out. No Qt, no widgets."""

    def __init__(self, log, ignore_version=False, start_worker=True):
        self.log = log
        self.ignore_version = ignore_version

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
        # Firmware version (parsed) of the connected keyboard, for update checks.
        self.kb_sw_version = None
        # Set on a fresh connect; consumed by the first applied snapshot after
        # it so the overlay state on the keyboard is cleared exactly once.
        self.needs_overlay_reset = False

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

    def shutdown(self):
        """Orderly stop: persist MRU, stop listeners/threads. Never raises.

        Persist the keyboard's MRU recents on a clean shutdown (the firmware
        only writes if they changed). USB suspend covers the sleep case; this
        covers a clean quit/logout where USB suspend may not fire. Run it
        synchronously (short bounded wait) BEFORE stopping the worker, but
        never let it block shutdown."""
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
        elif self.poly_settings.get("dev_run_window_detection_if_not_connected_to_poly_kybd"):
            handler.handle_active_window(update_cycle_msec, new_window_accept_msec)

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

    def _overlay_cmd_job(self, cmd, cancel):
        """Worker-thread enable/disable of overlays on every device entry."""
        for entry in self.device_mgr.all_entries:
            if cancel.is_set():
                return
            if cmd == OverlayCommand.DISABLE:
                entry.device.disable_overlays()
            elif cmd == OverlayCommand.ENABLE:
                entry.device.enable_overlays()

    # ------------------------------------------------------------------
    # Worker periodics: reconnect probe, console/serial reads, brightness
    # ------------------------------------------------------------------

    def _reconnect_periodic(self, cancel):
        """Worker periodic (1 s): probe the device, publish the snapshot to
        observers. Skipped automatically while suspended."""
        snapshot = self._reconnect_probe(cancel)
        if snapshot is not None:
            self.emit("reconnect", snapshot)

    def _reconnect_probe(self, cancel):
        """Runs on the WORKER thread. Performs all device I/O for a reconnect
        and returns a plain dict snapshot (or None to publish nothing) — no
        UI access.

        Only re-queries version/lang info when the probed connectivity differs
        from the last applied state (read atomically under the GIL)."""
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
                self.device_mgr.reset_all_caches()
                if self.overlay_handler is not None:
                    self.overlay_handler.force_resend()
                self.needs_overlay_reset = True
                self.log.info("Connected: active window resend queued.")

        # The applying client owns the applied-connection state the worker reads.
        self.last_applied_connected = self.connected

        if not connected_now:
            self.log.warning("Reconnect failed: '%s'",
                             snapshot["lang"] if snapshot["lang"] else "NO RESPONSE")

        if self.connected:
            if snapshot["state_changed"] and self.needs_overlay_reset:
                self.needs_overlay_reset = False
                applied["do_overlay_reset"] = True
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

    def _brightness_periodic(self, cancel):
        """Worker periodic (10 min): daylight-dependent brightness incl. the
        network lookups — kept entirely off any client thread."""
        if self.poly_settings.get("brightness_set_daylight_dependent"):
            min_val = self.poly_settings.get("irradiance_min")
            max_val = self.poly_settings.get("irradiance_max")
            prescaler = self.poly_settings.get("irradiance_prescaler")
            brightness = self.sunlight.get_brightness_now(min_val, max_val, prescaler)
            self.keeb.set_brightness(2 + brightness * 48)
