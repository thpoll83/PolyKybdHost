"""Control server for the PolyKybd headless core (headless-core plan H2).

A small JSON-RPC-shaped server that exposes :class:`polyhost.core.poly_core.PolyCore`
over the stdlib ``multiprocessing.connection`` transport defined in
:mod:`polyhost.server.protocol`. The GUI client and the CLI both talk to it;
the core itself stays Qt-free and is the single source of truth.

Threading model:
  - one daemon **accept-loop** thread owns the ``Listener``;
  - each accepted connection gets one daemon **handler** thread that reads
    requests and dispatches them through the method ``REGISTRY``;
  - writes on a connection are serialized through a per-connection lock so the
    handler thread and the core-event fan-out never interleave a frame.

The first two of those, plus the opening ``hello`` frame, the JSON-RPC error
mapping and the non-deadlocking ``stop()``, are shared with
:class:`polyhost.server.window_report_server.WindowReportServer` through
:class:`polyhost.server.mpc_listener.MpcListenerServer`. What is genuinely local
to this server — and stays here — is the **method registry** (the whole
device-control surface, which is precisely what the network endpoint must not
have), the per-connection write locks, and the event fan-out.

Core events are fanned out to every connection that has sent
``events.subscribe``. The server subscribes to the core exactly once at
``start()`` and pushes :func:`protocol.make_event` notifications.
"""
import queue
import threading

from polyhost.server import protocol as p
from polyhost.server.mpc_listener import MpcListenerServer, RpcError


def _unwrap(result):
    """Normalize a PolyCore ``(ok, payload)`` return to a JSON-RPC result.

    ``ok`` falsy -> raise ``RpcError(ERR_DEVICE, str(payload))``.
    ``ok`` truthy -> the payload becomes the result.
    """
    ok, payload = result
    if not ok:
        raise RpcError(p.ERR_DEVICE, str(payload))
    return payload


class ControlServer(MpcListenerServer):
    """Serve a :class:`PolyCore` over the local control socket."""

    def __init__(self, core, host_version, log, *,
                 on_shutdown=None, address=None, authkey=None):
        super().__init__(
            address=address or p.endpoint_address(),
            authkey=authkey if authkey is not None else p.load_or_create_authkey(),
            host_version=host_version,
            log=log,
            thread_prefix="control")
        self.core = core
        self._on_shutdown = on_shutdown

        # Per-connection write locks and the subset subscribed to events. The
        # live-connection set itself is the base's; these ride alongside it via
        # the on_connection_added / _dropped hooks.
        self._conn_locks = {}
        self._subscribed = set()

        # Core events are handed off to this queue and sent by a dedicated
        # thread; the emitting core/worker thread must never do socket I/O (a
        # full socket buffer would stall the reconnect probe / device work —
        # see the threading-model notes in CLAUDE.md).
        self._event_q = queue.Queue()
        self._sender_thread = None

        # Set by host.shutdown; the teardown callback fires only after the
        # reply has been written (see after_dispatch), so the client sees the ack.
        self._pending_shutdown = False

        self.registry = self._build_registry()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def secure_listener(self):
        """Tighten the endpoint's permissions right after bind (0600 UDS)."""
        p.secure_endpoint(self.address)

    def start(self):
        """Bind the listener, tighten its permissions, and start accepting."""
        # Start the event sender before subscribing so no event is dropped.
        self._sender_thread = threading.Thread(
            target=self._event_sender_loop, name="control-events", daemon=True)
        self._sender_thread.start()
        # Subscribe to the core exactly once; fan-out filters by subscription.
        self.core.subscribe(self._on_core_event)
        super().start()

    def stop(self):
        """Stop accepting and close everything. Best-effort, never raises."""
        # Wake the sender thread so it can exit its blocking queue.get().
        self._event_q.put(None)
        super().stop()
        self._conn_locks.clear()
        self._subscribed.clear()

    # ------------------------------------------------------------------
    # Per-connection state + serialized writes
    # ------------------------------------------------------------------

    def on_connection_added(self, conn):
        with self._lock:
            self._conn_locks[conn] = threading.Lock()

    def on_connection_dropped(self, conn):
        with self._lock:
            self._conn_locks.pop(conn, None)
            self._subscribed.discard(conn)

    def send(self, conn, obj):
        """Serialize writes per connection so the handler thread and the event
        fan-out can never interleave halves of two frames on one socket.

        The lock table IS this server's liveness registry — a lock is created in
        ``on_connection_added`` before the reader thread starts, and removed in
        ``on_connection_dropped`` under the same mutex that discards the
        subscription. So "no lock" means the connection is already dropped (and
        closed), and the write is skipped rather than issued unsynchronised: the
        event fan-out snapshots ``_subscribed`` and then sends *outside* the
        mutex, so a teardown landing in that window would otherwise write to a
        closing connection with no serialization at all.
        """
        lock = self._conn_locks.get(conn)
        if lock is None:
            return
        with lock:
            p.send_message(conn, obj)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(self, conn, req_id, method, params):
        handler = self.registry.get(method)
        if handler is None:
            return p.make_error(
                req_id, p.ERR_METHOD_NOT_FOUND, f"unknown method '{method}'")
        return p.make_response(req_id, handler(conn, params))

    def after_dispatch(self, conn, method):
        # host.shutdown defers teardown to here so the reply is on the wire
        # before quit_app() closes the connection (the client would otherwise
        # see EOF instead of {"shutting_down": True}).
        if self._pending_shutdown:
            self._pending_shutdown = False
            if self._on_shutdown is not None:
                self._on_shutdown()

    # ------------------------------------------------------------------
    # Core event fan-out
    # ------------------------------------------------------------------

    def _on_core_event(self, name, payload):
        """Called on core/worker threads — hand off without blocking.

        Only enqueues; the dedicated sender thread does the socket I/O so a
        slow/stopped subscriber can never stall the emitting thread."""
        self._event_q.put((name, payload))

    def _event_sender_loop(self):
        """Drain queued core events and push them to subscribers (own thread)."""
        while True:
            item = self._event_q.get()
            if item is None:        # sentinel from stop()
                break
            name, payload = item
            with self._lock:
                targets = list(self._subscribed)
            if not targets:
                continue
            event = p.make_event(name, payload)
            dead = []
            for conn in targets:
                try:
                    self.send(conn, event)   # per-connection write lock
                except Exception:   # noqa: BLE001 — subscriber went away
                    dead.append(conn)
            for conn in dead:
                self._drop(conn)

    # ------------------------------------------------------------------
    # Method registry
    # ------------------------------------------------------------------

    def _build_registry(self):
        c = self.core
        return {
            p.M_STATUS_GET: lambda conn, params: c.get_status(),
            p.M_LANG_LIST: lambda conn, params: c.list_languages(),
            p.M_LANG_SET: lambda conn, params: _unwrap(c.set_language(params["lang"])),
            p.M_BRIGHTNESS_SET: lambda conn, params: _unwrap(c.set_brightness(params["value"])),
            p.M_IDLE_SET: lambda conn, params: _unwrap(c.set_idle(params["idle"])),
            p.M_IDLE_STYLE_SET: lambda conn, params: _unwrap(c.set_idle_style(params["value"])),
            p.M_IDLE_STYLE_GET: lambda conn, params: _unwrap(c.get_idle_style()),
            p.M_GLYPH_SCRIPT_SET: lambda conn, params: _unwrap(c.set_glyph_script(params["value"])),
            p.M_GLYPH_SCRIPT_GET: lambda conn, params: _unwrap(c.get_glyph_script()),
            p.M_GLYPH_SIZE_SET: lambda conn, params: _unwrap(c.set_glyph_size(params["value"])),
            p.M_GLYPH_SIZE_GET: lambda conn, params: _unwrap(c.get_glyph_size()),
            p.M_REPLAY_ANIM: lambda conn, params: _unwrap(c.replay_startup_anim()),
            p.M_UNICODE_MODE_REFRESH: lambda conn, params: _unwrap(c.refresh_unicode_mode()),
            p.M_DAYLIGHT_REFRESH: lambda conn, params: _unwrap(c.refresh_daylight_brightness()),
            p.M_OVERLAY_SEND: lambda conn, params: {"queued": c.send_overlay_data(params["files"])},
            p.M_OVERLAY_ENABLE: lambda conn, params: _unwrap(c.enable_overlays()),
            p.M_OVERLAY_DISABLE: lambda conn, params: _unwrap(c.disable_overlays()),
            p.M_OVERLAY_RESET: lambda conn, params: _unwrap(c.reset_overlays()),
            p.M_KEYMAP_LAYER_COUNT: lambda conn, params: _unwrap(c.keymap_layer_count()),
            p.M_KEYMAP_DEFAULT_LAYER: lambda conn, params: _unwrap(c.keymap_default_layer()),
            p.M_KEYMAP_BUFFER: lambda conn, params: _unwrap(c.keymap_buffer()),
            p.M_KEYMAP_SET: lambda conn, params: _unwrap(c.keymap_set(
                params["layer"], params["row"], params["col"], params["keycode"])),
            p.M_MACRO_LIST: lambda conn, params: _unwrap(c.macro_list()),
            p.M_MACRO_SET: lambda conn, params: _unwrap(c.macro_set(
                params["id"], text=params.get("text"), steps=params.get("steps"),
                label=params.get("label"))),
            p.M_MACRO_CLEAR: lambda conn, params: _unwrap(c.macro_clear(params["id"])),
            p.M_COMMANDS_EXECUTE: self._cmd_commands_execute,
            p.M_FW_VERSION: lambda conn, params: _unwrap(c.get_fw_version()),
            p.M_FW_FLASH: lambda conn, params: _unwrap(c.flash_firmware(
                params["path"], params.get("apply", False))),
            p.M_UPDATE_CHECK: lambda conn, params: _unwrap(c.check_update()),
            p.M_UPDATE_INSTALL: lambda conn, params: _unwrap(c.install_update()),
            p.M_RESET_DYNAMIC_KEYMAP: lambda conn, params: _unwrap(c.reset_dynamic_keymap()),
            p.M_OVERLAY_RESET_BUFFERS: lambda conn, params: _unwrap(c.reset_overlay_buffers()),
            p.M_OVERLAY_RESET_MAPPING: lambda conn, params: _unwrap(c.reset_overlay_mapping()),
            p.M_OVERLAY_RESET_USAGE: lambda conn, params: _unwrap(c.reset_overlay_usage()),
            p.M_OVERLAY_SET_ALL_USAGE: lambda conn, params: _unwrap(c.set_all_overlay_usage()),
            p.M_OVERLAY_MAPPING_SEND: lambda conn, params: _unwrap(c.send_overlay_mapping(params["mapping"])),
            p.M_ACTIVATE_BOOTLOADER: lambda conn, params: _unwrap(c.activate_bootloader()),
            p.M_SET_HANDEDNESS: lambda conn, params: _unwrap(c.set_handedness(params["master_is_left"])),
            p.M_FW_APPLY_STAGED: lambda conn, params: _unwrap(c.apply_staged_firmware()),
            p.M_FONTPACK_FLASH: lambda conn, params: _unwrap(
                c.flash_fontpack_bundle(params["bundle"]) if "bundle" in params
                else c.flash_fontpack(params["path"], params.get("bundle_id", 0))),
            p.M_FONTPACK_STATUS: lambda conn, params: _unwrap(c.get_fontpack_status()),
            p.M_FONTPACK_SYNC: lambda conn, params: _unwrap(
                c.sync_fontpack(force=bool(params.get("force", False)))),
            p.M_FONTPACK_WIPE: lambda conn, params: _unwrap(c.wipe_fontpack()),
            p.M_FONTPACK_BUNDLES: lambda conn, params: _unwrap(c.fontpack_bundle_status()),
            p.M_DOOM_INSTALL: lambda conn, params: _unwrap(c.install_doomwad(params["path"])),
            p.M_DOOM_INSTALL_PACK: lambda conn, params: _unwrap(c.install_doompack(params["path"])),
            p.M_PAUSE_SET: self._cmd_pause_set,
            p.M_SET_NEWER_FW_POLICY: lambda conn, params: _unwrap(
                c.set_newer_firmware_policy(params["choice"])),
            p.M_MRU_SAVE: self._cmd_mru_save,
            p.M_SETTINGS_GET: lambda conn, params: c.settings_get(params["key"]),
            p.M_SETTINGS_LIST: lambda conn, params: c.settings_list(),
            p.M_SETTINGS_SET: lambda conn, params: _unwrap(c.settings_set(
                params["key"], params["value"])),
            p.M_TELEMETRY_STATUS: lambda conn, params: c.telemetry_status(),
            p.M_TELEMETRY_PREVIEW: lambda conn, params: c.telemetry_preview(),
            p.M_TELEMETRY_SET: lambda conn, params: _unwrap(
                c.telemetry_set_enabled(params["enabled"])),
            p.M_TELEMETRY_SEND: lambda conn, params: _unwrap(c.telemetry_send_now()),
            p.M_WINDOW_REPORT: lambda conn, params: _unwrap(c.report_window(
                params["handle"], params["name"], params.get("title", ""),
                os=params.get("os"), url=params.get("url"))),
            p.M_HOST_SHUTDOWN: self._cmd_host_shutdown,
            p.EVENTS_SUBSCRIBE: self._cmd_events_subscribe,
        }

    def _cmd_commands_execute(self, conn, params):
        self.core.execute_commands(params["lines"])
        return {"queued": True}

    def _cmd_pause_set(self, conn, params):
        self.core.set_paused(bool(params["paused"]))
        return {"paused": self.core.paused}

    def _cmd_mru_save(self, conn, params):
        self.core.save_mru()
        return {"queued": True}

    def _cmd_host_shutdown(self, conn, params):
        # Defer the actual teardown until _dispatch has written this reply.
        self._pending_shutdown = True
        return {"shutting_down": True}

    def _cmd_events_subscribe(self, conn, params):
        with self._lock:
            self._subscribed.add(conn)
        return {"subscribed": True}
