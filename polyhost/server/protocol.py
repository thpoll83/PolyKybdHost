"""Wire protocol + transport for the PolyKybd control socket (headless-core H2).

Transport is stdlib ``multiprocessing.connection`` (Unix domain socket on
POSIX, a real Windows named pipe on win32) with HMAC ``authkey``
authentication and length-prefixed framing — zero third-party deps. We
deliberately use **only** ``send_bytes``/``recv_bytes`` carrying UTF-8 JSON
(never the pickling ``send``/``recv``), so the protocol stays language-
agnostic and safe.

Message shape is JSON-RPC 2.0-flavoured:
  request:      {"jsonrpc":"2.0","id":N,"method":str,"params":{...}}
  response:     {"jsonrpc":"2.0","id":N,"result":...}
  error:        {"jsonrpc":"2.0","id":N,"error":{"code":int,"message":str}}
  notification: {"jsonrpc":"2.0","method":str,"params":{...}}   (no id)

Server-push events are notifications sent after the client calls
``events.subscribe`` (their ``method`` is ``"event"`` and params carry the
core event ``name``/``payload`` — names defined in ``polyhost.core.events``).

The first exchange must be ``hello`` carrying the control-protocol version +
host version; a client refuses on major mismatch (mirrors the firmware
protocol gate).
"""
import json
import os
import secrets
import sys

from platformdirs import user_config_dir, user_runtime_dir

APP_NAME = "PolyHost"

# Bump on any breaking change to the framing or method/notification shapes.
CONTROL_PROTOCOL_VERSION = 1

# Reserved JSON-RPC-ish error codes (negative, like JSON-RPC).
ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602
ERR_INTERNAL = -32603
ERR_DEVICE = -32000          # device command returned failure
ERR_UNAVAILABLE = -32001     # worker suspended / device busy
ERR_VERSION_MISMATCH = -32002

HELLO = "hello"
EVENTS_SUBSCRIBE = "events.subscribe"
EVENT_NOTIFICATION = "event"

# Canonical method names — the server registry and the CLI both reference
# these so the wire names can never drift. Each maps to a PolyCore call;
# the (params -> result) contract is in the comment.
M_STATUS_GET = "status.get"            # {} -> status dict (PolyCore.get_status)
M_LANG_LIST = "lang.list"              # {} -> [code, ...]
M_LANG_SET = "lang.set"                # {"lang": "deDE"} -> (ok, payload)
M_BRIGHTNESS_SET = "brightness.set"    # {"value": 0..50} -> (ok, payload)
M_IDLE_SET = "idle.set"                # {"idle": bool} -> (ok, payload)
M_OVERLAY_SEND = "overlay.send"        # {"files": [name, ...]} -> {"queued": bool}
M_OVERLAY_ENABLE = "overlay.enable"    # {} -> (ok, payload)
M_OVERLAY_DISABLE = "overlay.disable"  # {} -> (ok, payload)
M_OVERLAY_RESET = "overlay.reset"      # {} -> (ok, payload)
M_KEYMAP_LAYER_COUNT = "keymap.layer_count"      # {} -> (ok, count)
M_KEYMAP_DEFAULT_LAYER = "keymap.default_layer"  # {} -> (ok, layer)
M_KEYMAP_BUFFER = "keymap.buffer"      # {} -> (ok, [int, ...])
M_KEYMAP_SET = "keymap.set"            # {"layer","row","col","keycode"} -> (ok, payload)
M_COMMANDS_EXECUTE = "commands.execute"  # {"lines": [str, ...]} -> {"queued": True}
M_FW_VERSION = "fw.version"            # {} -> version str
M_FW_FLASH = "fw.flash"                # {"path": str, "apply": bool} -> {"queued": bool} (streams fw_flash_* events)
M_UPDATE_CHECK = "update.check"        # {} -> {"available": bool, "version": str, "url": str}
M_UPDATE_INSTALL = "update.install"    # {} -> {"queued": bool, "version": str} (streams update_* events)
M_PAUSE_SET = "pause.set"              # {"paused": bool} -> {"paused": bool}
M_MRU_SAVE = "mru.save"                # {} -> {"queued": True}
M_SETTINGS_GET = "settings.get"        # {"key": str} -> value
M_SETTINGS_LIST = "settings.list"      # {} -> {key: value, ...} (all settings)
M_SETTINGS_SET = "settings.set"        # {"key","value"} -> (ok, payload)
M_HOST_SHUTDOWN = "host.shutdown"      # {} -> {"shutting_down": True}

# ---------------------------------------------------------------------------
# Endpoint location + authkey (filesystem-permission gated, local only)
# ---------------------------------------------------------------------------

def _config_dir() -> str:
    d = user_config_dir(APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def endpoint_address() -> str:
    """Listener/Client address. UDS path on POSIX (mode 0600 after bind),
    a per-user named pipe on Windows."""
    if sys.platform == "win32":
        return r"\\.\pipe\polykybd-" + os.environ.get("USERNAME", "user")
    # Prefer the runtime dir (tmpfs, auto-cleaned); fall back to config dir.
    try:
        base = user_runtime_dir(APP_NAME)
        os.makedirs(base, exist_ok=True)
    except Exception:
        base = _config_dir()
    return os.path.join(base, "polykybd.sock")


def authkey_path() -> str:
    return os.path.join(_config_dir(), "polykybd.authkey")


def load_or_create_authkey() -> bytes:
    """Return the shared HMAC secret, creating a 0600 file on first use.

    On POSIX the 0600 file is defense-in-depth (the socket is already perm-
    gated); on Windows it is the primary gate for the named pipe."""
    path = authkey_path()
    # Create atomically with O_EXCL so two near-simultaneous first launches
    # can't each generate a different key and have the later writer overwrite
    # the key the earlier server already bound with (which would then fail
    # every probe_existing/polyctl auth until restart). The loser of the race
    # gets FileExistsError and rereads the winner's key.
    for _ in range(5):
        try:
            with open(path, "rb") as f:
                key = f.read().strip()
            if key:
                return key
        except OSError:
            pass
        new_key = secrets.token_hex(32).encode("ascii")
        try:
            # 0600 best effort on Windows, which ignores the mode bits.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # Another launch created it first; loop to reread its key. A
            # zero-byte file (crash mid-write under the old code) is corrupt —
            # drop it and retry rather than spin forever.
            try:
                if not os.path.getsize(path):
                    os.unlink(path)
            except OSError:
                pass
            continue
        try:
            os.write(fd, new_key)
        finally:
            os.close(fd)
        return new_key
    # Last resort after repeated races: use whatever is on disk.
    with open(path, "rb") as f:
        return f.read().strip()


def secure_endpoint(address: str) -> None:
    """Tighten the UDS file mode to 0600 after the Listener binds it.
    No-op on Windows (named pipe ACLs are separate)."""
    if sys.platform != "win32":
        try:
            os.chmod(address, 0o600)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Framing — UTF-8 JSON over send_bytes/recv_bytes (never pickle send/recv)
# ---------------------------------------------------------------------------

def send_message(conn, obj) -> None:
    conn.send_bytes(json.dumps(obj).encode("utf-8"))


def recv_message(conn):
    """Read one framed JSON message. Raises EOFError when the peer closes."""
    return json.loads(conn.recv_bytes().decode("utf-8"))


# ---------------------------------------------------------------------------
# JSON-RPC message builders
# ---------------------------------------------------------------------------

def make_request(req_id, method, params=None):
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}


def make_response(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def make_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def make_notification(method, params=None):
    return {"jsonrpc": "2.0", "method": method, "params": params or {}}


def make_event(name, payload):
    """A core event pushed to a subscribed client as a notification."""
    return make_notification(EVENT_NOTIFICATION, {"name": name, "payload": payload})


def hello_params(host_version: str) -> dict:
    return {"control_protocol": CONTROL_PROTOCOL_VERSION, "host_version": host_version}


def check_hello(params: dict) -> tuple[bool, str]:
    """Client-side: verify the server's hello. Major version must match."""
    got = (params or {}).get("control_protocol")
    if got != CONTROL_PROTOCOL_VERSION:
        return False, (f"control protocol mismatch: client v{CONTROL_PROTOCOL_VERSION}, "
                       f"server v{got} — restart so versions match")
    return True, ""
