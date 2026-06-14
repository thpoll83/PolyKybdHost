"""Client-side ``PolyCore`` stand-in backed by the control socket (H4a).

``RemoteCore`` mirrors the subset of the :class:`~polyhost.core.poly_core.PolyCore`
API the Qt GUI consumes, turning each call into a JSON-RPC request over
:mod:`polyhost.server.protocol` and fanning server-pushed events to the same
observer seam ``PolyCore`` uses (``subscribe`` / ``emit``). It lets
``python -m polyhost --connect`` run the tray GUI as a **pure client** of a core
living in another process (a headless daemon, or another GUI's embedded
server) — no in-process device ownership.

Qt-free by construction: it speaks only the stdlib protocol + threads, exactly
like ``polyctl``. Connection model: **two** sockets — one for request/response
(``_rpc``) and one dedicated to the event subscription (``_evt``) — so the
event-pump thread and method calls never read the same connection concurrently.

State (``connected`` / ``device_present`` / …) is cached from the initial
``status.get`` and kept fresh by ``status_changed`` events; the property getters
read that cache. Quitting the client closes its sockets and leaves the daemon
running (it owns the device).
"""
import threading

from polyhost.cli.polyctl import RpcError
from polyhost.server import protocol as p


class RemoteCore:
    """RPC-backed proxy for the GUI's ``self.core`` (see docs/headless-h4-plan.md)."""

    def __init__(self, rpc_client, event_client, log):
        self.log = log
        self._rpc = rpc_client
        self._evt = event_client
        self._rpc_lock = threading.Lock()      # GUI dialogs may call off-main-thread
        self._observers = []
        self._observers_lock = threading.Lock()
        self._status = {}
        self._status_lock = threading.Lock()
        self._stop = threading.Event()

        # Seed cached state, then start the event pump on the second connection.
        try:
            self._status = self._rpc.call(p.M_STATUS_GET) or {}
        except (RpcError, OSError, EOFError) as e:
            self.log.warning("RemoteCore: initial status.get failed: %s", e)
            self._status = {}
        self._evt.subscribe_events()
        self._thread = threading.Thread(
            target=self._pump, name="remote-core-events", daemon=True)
        self._thread.start()

    @classmethod
    def connect(cls, log, address=None, authkey=None):
        """Open the two control-socket connections and return a RemoteCore.

        Raises the same errors as :func:`polyhost.cli.polyctl.connect`
        (``RpcError`` on a version mismatch, ``OSError``/``EOFError`` when no
        host is serving the socket) so the caller can report cleanly."""
        from polyhost.cli import polyctl
        rpc = polyctl.connect(address, authkey)
        evt = polyctl.connect(address, authkey)
        return cls(rpc, evt, log)

    # ------------------------------------------------------------------
    # Observer plumbing (mirrors PolyCore)
    # ------------------------------------------------------------------

    def subscribe(self, callback):
        with self._observers_lock:
            self._observers.append(callback)

    def emit(self, name, payload):
        with self._observers_lock:
            observers = list(self._observers)
        for cb in observers:
            try:
                cb(name, payload)
            except Exception:
                self.log.exception("RemoteCore observer failed for %r", name)

    def _pump(self):
        """Drain server-pushed events on the dedicated connection, keep the
        status cache fresh, and re-emit to local observers. On EOF (daemon
        gone) synthesize a disconnect so the GUI greys out instead of hanging."""
        for name, payload in self._evt.events():
            if self._stop.is_set():
                return
            if name == "status_changed" and isinstance(payload, dict):
                with self._status_lock:
                    self._status.update(payload)
            self.emit(name, payload)
        if not self._stop.is_set():
            with self._status_lock:
                self._status["connected"] = False
                self._status["device_present"] = False
            self.emit("status_changed", {
                "connected": False, "device_present": False, "state_changed": True,
                "text": "Lost connection to the PolyKybdHost core.",
                "icon": "sync_disabled.svg", "lang": None})

    # ------------------------------------------------------------------
    # Cached state (read from status events; writes update the local cache
    # only — the daemon is the source of truth and pushes status_changed)
    # ------------------------------------------------------------------

    def _get(self, key, default=None):
        with self._status_lock:
            return self._status.get(key, default)

    @property
    def connected(self):
        return bool(self._get("connected", False))

    @connected.setter
    def connected(self, value):
        with self._status_lock:
            self._status["connected"] = bool(value)

    @property
    def device_present(self):
        return bool(self._get("device_present", False))

    @device_present.setter
    def device_present(self, value):
        with self._status_lock:
            self._status["device_present"] = bool(value)

    @property
    def paused(self):
        return bool(self._get("paused", False))

    @property
    def last_applied_connected(self):
        return bool(self._get("connected", False))

    @last_applied_connected.setter
    def last_applied_connected(self, value):
        pass  # the daemon owns reconnect application

    @property
    def kb_sw_version(self):
        return self._get("fw_version")

    @property
    def mapping(self):
        # Window matching runs in the daemon; the client doesn't need the map.
        return {}

    # ------------------------------------------------------------------
    # RPC-backed command surface
    # ------------------------------------------------------------------

    def _rpc_call(self, method, params=None):
        with self._rpc_lock:
            return self._rpc.call(method, params)

    def _device(self, method, params=None):
        """RPC for a ``(ok, payload)``-contract device call: map RpcError back
        to the (False, msg) the GUI expects from the in-process PolyCore."""
        try:
            return True, self._rpc_call(method, params)
        except RpcError as e:
            return False, e.message

    # -- status / languages -------------------------------------------------
    def get_status(self):
        try:
            st = self._rpc_call(p.M_STATUS_GET) or {}
        except RpcError:
            return dict(self._status)
        with self._status_lock:
            self._status.update(st)
        return st

    def list_languages(self):
        try:
            return self._rpc_call(p.M_LANG_LIST) or []
        except RpcError:
            return []

    def set_language(self, lang):
        return self._device(p.M_LANG_SET, {"lang": lang})

    # -- brightness / idle --------------------------------------------------
    def set_brightness(self, value):
        return self._device(p.M_BRIGHTNESS_SET, {"value": value})

    def set_idle(self, idle):
        return self._device(p.M_IDLE_SET, {"idle": idle})

    # -- overlays -----------------------------------------------------------
    def send_overlay_data(self, files):
        try:
            res = self._rpc_call(p.M_OVERLAY_SEND, {"files": list(files)})
            return bool((res or {}).get("queued"))
        except RpcError:
            return False

    def enable_overlays(self):
        return self._device(p.M_OVERLAY_ENABLE)

    def disable_overlays(self):
        return self._device(p.M_OVERLAY_DISABLE)

    def reset_overlays(self):
        return self._device(p.M_OVERLAY_RESET)

    # -- keymap -------------------------------------------------------------
    def keymap_layer_count(self):
        return self._device(p.M_KEYMAP_LAYER_COUNT)

    def keymap_default_layer(self):
        return self._device(p.M_KEYMAP_DEFAULT_LAYER)

    def keymap_buffer(self):
        return self._device(p.M_KEYMAP_BUFFER)

    def keymap_set(self, layer, row, col, keycode):
        return self._device(p.M_KEYMAP_SET, {
            "layer": layer, "row": row, "col": col, "keycode": keycode})

    # -- commands / firmware / update --------------------------------------
    def execute_commands(self, lines):
        try:
            self._rpc_call(p.M_COMMANDS_EXECUTE, {"lines": list(lines)})
            return True
        except RpcError:
            return False

    def get_fw_version(self):
        try:
            return self._rpc_call(p.M_FW_VERSION)
        except RpcError:
            return self.kb_sw_version

    def flash_firmware(self, path, apply=False):
        return self._device(p.M_FW_FLASH, {"path": path, "apply": bool(apply)})

    def check_update(self):
        return self._device(p.M_UPDATE_CHECK)

    def install_update(self):
        return self._device(p.M_UPDATE_INSTALL)

    # -- lifecycle / settings ----------------------------------------------
    def set_paused(self, paused):
        try:
            res = self._rpc_call(p.M_PAUSE_SET, {"paused": bool(paused)})
            with self._status_lock:
                self._status["paused"] = bool((res or {}).get("paused", paused))
        except RpcError as e:
            self.log.warning("RemoteCore: pause.set failed: %s", e)

    def save_mru(self):
        try:
            self._rpc_call(p.M_MRU_SAVE)
        except RpcError as e:
            self.log.warning("RemoteCore: mru.save failed: %s", e)

    def settings_get(self, key):
        try:
            return self._rpc_call(p.M_SETTINGS_GET, {"key": key})
        except RpcError:
            return None

    def settings_list(self):
        try:
            return self._rpc_call(p.M_SETTINGS_LIST) or {}
        except RpcError:
            return {}

    def settings_set(self, key, value):
        return self._device(p.M_SETTINGS_SET, {"key": key, "value": value})

    # -- no-ops / client-local ---------------------------------------------
    def tick_window_tracking(self, *args, **kwargs):
        # The daemon polls the active window where the display is; the client
        # never ticks. (H4b/H4c wire window reporting for remote displays.)
        return None

    def shutdown(self):
        """Close the client sockets; leave the daemon running (it owns the
        device). Quitting the GUI must NOT shut the core down."""
        self._stop.set()
        for c in (self._evt, self._rpc):
            try:
                c.close()
            except Exception:
                pass

    def request_host_shutdown(self):
        """Explicitly ask the daemon to exit (distinct from closing the client)."""
        try:
            return self._rpc_call(p.M_HOST_SHUTDOWN)
        except RpcError as e:
            return {"error": e.message}
