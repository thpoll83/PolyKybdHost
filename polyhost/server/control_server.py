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

Core events are fanned out to every connection that has sent
``events.subscribe``. The server subscribes to the core exactly once at
``start()`` and pushes :func:`protocol.make_event` notifications.
"""
import multiprocessing.connection as mpc
import queue
import threading

from polyhost.server import protocol as p


class RpcError(Exception):
    """Raised by a method handler to produce a JSON-RPC error response.

    ``code`` is one of the ``protocol.ERR_*`` constants; ``message`` is a
    human-readable string sent back to the client verbatim.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = str(message)


def _unwrap(result):
    """Normalize a PolyCore ``(ok, payload)`` return to a JSON-RPC result.

    ``ok`` falsy -> raise ``RpcError(ERR_DEVICE, str(payload))``.
    ``ok`` truthy -> the payload becomes the result.
    """
    ok, payload = result
    if not ok:
        raise RpcError(p.ERR_DEVICE, str(payload))
    return payload


class ControlServer:
    """Serve a :class:`PolyCore` over the local control socket."""

    def __init__(self, core, host_version, log, *,
                 on_shutdown=None, address=None, authkey=None):
        self.core = core
        self.host_version = host_version
        self.log = log
        self._on_shutdown = on_shutdown
        self.address = address or p.endpoint_address()
        self.authkey = authkey if authkey is not None else p.load_or_create_authkey()

        self._listener = None
        self._accept_thread = None
        self._running = False

        # Live connections and the subset that have subscribed to events.
        self._conns = set()              # conn -> write lock
        self._conn_locks = {}
        self._subscribed = set()
        self._lock = threading.Lock()    # guards the three structures above

        # Core events are handed off to this queue and sent by a dedicated
        # thread; the emitting core/worker thread must never do socket I/O (a
        # full socket buffer would stall the reconnect probe / device work —
        # see the threading-model notes in CLAUDE.md).
        self._event_q = queue.Queue()
        self._sender_thread = None

        # Set by host.shutdown; the teardown callback fires only after the
        # reply has been written (see _dispatch), so the client sees the ack.
        self._pending_shutdown = False

        self.registry = self._build_registry()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Bind the listener, tighten its permissions, and start accepting."""
        self._listener = mpc.Listener(self.address, authkey=self.authkey)
        p.secure_endpoint(self.address)
        self._running = True
        # Start the event sender before subscribing so no event is dropped.
        self._sender_thread = threading.Thread(
            target=self._event_sender_loop, name="control-events", daemon=True)
        self._sender_thread.start()
        # Subscribe to the core exactly once; fan-out filters by subscription.
        self.core.subscribe(self._on_core_event)
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="control-accept", daemon=True)
        self._accept_thread.start()

    def stop(self):
        """Stop accepting and close everything. Best-effort, never raises."""
        self._running = False
        # Wake the sender thread so it can exit its blocking queue.get().
        self._event_q.put(None)
        listener = self._listener
        # Unblock the blocking accept() by connecting a throwaway client, then
        # close the listener. Both wrapped — a half-torn-down listener on a
        # racing stop() must not raise.
        if listener is not None:
            try:
                throwaway = mpc.Client(self.address, authkey=self.authkey)
                try:
                    throwaway.close()
                except Exception:
                    pass
            except Exception:
                pass
            try:
                listener.close()
            except Exception:
                pass
        # Close every live connection.
        with self._lock:
            conns = list(self._conns)
            self._conns.clear()
            self._conn_locks.clear()
            self._subscribed.clear()
        for conn in conns:
            try:
                conn.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Accept loop + per-connection handler
    # ------------------------------------------------------------------

    def _accept_loop(self):
        while self._running:
            try:
                conn = self._listener.accept()
            except Exception:
                # Listener closed (normal stop()) or an auth/transport error on
                # a single client — keep serving unless we're shutting down.
                if not self._running:
                    break
                continue
            if not self._running:
                try:
                    conn.close()
                except Exception:
                    pass
                break
            lock = threading.Lock()
            with self._lock:
                self._conns.add(conn)
                self._conn_locks[conn] = lock
            t = threading.Thread(
                target=self._handle_connection, args=(conn, lock),
                name="control-conn", daemon=True)
            t.start()

    def _handle_connection(self, conn, lock):
        # The very first frame is the server's hello notification.
        try:
            with lock:
                p.send_message(conn, p.make_notification(
                    p.HELLO, p.hello_params(self.host_version)))
        except Exception:
            self._drop(conn)
            return

        try:
            while True:
                try:
                    msg = p.recv_message(conn)
                except (EOFError, OSError):
                    break
                except Exception:
                    self.log.exception("Control server: malformed frame")
                    break
                self._dispatch(conn, lock, msg)
        finally:
            self._drop(conn)

    def _dispatch(self, conn, lock, msg):
        req_id = msg.get("id") if isinstance(msg, dict) else None
        method = msg.get("method") if isinstance(msg, dict) else None
        params = (msg.get("params") if isinstance(msg, dict) else None) or {}

        if req_id is None:
            # A notification (no id) — we don't expect client->server
            # notifications today; ignore silently.
            return

        handler = self.registry.get(method)
        if handler is None:
            self._reply(conn, lock, p.make_error(
                req_id, p.ERR_METHOD_NOT_FOUND, f"unknown method '{method}'"))
            return

        try:
            result = handler(conn, params)
            reply = p.make_response(req_id, result)
        except RpcError as e:
            reply = p.make_error(req_id, e.code, e.message)
        except (KeyError, TypeError, ValueError) as e:
            reply = p.make_error(
                req_id, p.ERR_INVALID_PARAMS, f"{type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001 — last-resort guard
            self.log.exception("Control server: handler for %r failed", method)
            reply = p.make_error(
                req_id, p.ERR_INTERNAL, f"{type(e).__name__}: {e}")

        self._reply(conn, lock, reply)

        # host.shutdown defers teardown to here so the reply is on the wire
        # before quit_app() closes the connection (client would otherwise see
        # EOF instead of {"shutting_down": True}).
        if self._pending_shutdown:
            self._pending_shutdown = False
            if self._on_shutdown is not None:
                self._on_shutdown()

    def _reply(self, conn, lock, obj):
        try:
            with lock:
                p.send_message(conn, obj)
        except Exception:
            self._drop(conn)

    def _drop(self, conn):
        with self._lock:
            self._conns.discard(conn)
            self._conn_locks.pop(conn, None)
            self._subscribed.discard(conn)
        try:
            conn.close()
        except Exception:
            pass

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
                targets = [(c, self._conn_locks.get(c)) for c in self._subscribed]
            if not targets:
                continue
            event = p.make_event(name, payload)
            dead = []
            for conn, lock in targets:
                if lock is None:
                    continue
                try:
                    with lock:
                        p.send_message(conn, event)
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
            p.M_OVERLAY_SEND: lambda conn, params: {"queued": c.send_overlay_data(params["files"])},
            p.M_OVERLAY_ENABLE: lambda conn, params: _unwrap(c.enable_overlays()),
            p.M_OVERLAY_DISABLE: lambda conn, params: _unwrap(c.disable_overlays()),
            p.M_OVERLAY_RESET: lambda conn, params: _unwrap(c.reset_overlays()),
            p.M_KEYMAP_LAYER_COUNT: lambda conn, params: _unwrap(c.keymap_layer_count()),
            p.M_KEYMAP_DEFAULT_LAYER: lambda conn, params: _unwrap(c.keymap_default_layer()),
            p.M_KEYMAP_BUFFER: lambda conn, params: _unwrap(c.keymap_buffer()),
            p.M_KEYMAP_SET: lambda conn, params: _unwrap(c.keymap_set(
                params["layer"], params["row"], params["col"], params["keycode"])),
            p.M_COMMANDS_EXECUTE: self._cmd_commands_execute,
            p.M_FW_VERSION: lambda conn, params: c.get_fw_version(),
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
            p.M_FONTPACK_SYNC: lambda conn, params: _unwrap(c.sync_fontpack()),
            p.M_FONTPACK_BUNDLES: lambda conn, params: _unwrap(c.fontpack_bundle_status()),
            p.M_PAUSE_SET: self._cmd_pause_set,
            p.M_MRU_SAVE: self._cmd_mru_save,
            p.M_SETTINGS_GET: lambda conn, params: c.settings_get(params["key"]),
            p.M_SETTINGS_LIST: lambda conn, params: c.settings_list(),
            p.M_SETTINGS_SET: lambda conn, params: _unwrap(c.settings_set(
                params["key"], params["value"])),
            p.M_WINDOW_REPORT: lambda conn, params: _unwrap(c.report_window(
                params["handle"], params["name"], params.get("title", ""))),
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
