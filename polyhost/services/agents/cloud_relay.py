"""The host side of the agent keys for Claude Code cloud sessions.

A cloud session (claude.ai/code, also when the desktop app shows it) runs in a VM
that cannot reach this computer. Its hooks (cloud_hook.py, installed by the cloud
environment's setup script) send each change of the session's state to the relay
Worker (`agent-relay/`). This module is the other end:

- `create_channel()` makes a channel on the relay and keeps its secrets in
  `cloud_relay.json` in the config folder. The relay gets only the hashes of the
  two tokens. `setup_text()` is what the user copies into the cloud environment.
- `RelayClient` keeps a WebSocket open to the channel. The relay sends a snapshot
  of the channel's sessions, then each report. Every report is decrypted with the
  channel's key (cloud_hook.open_sealed) and goes into the agent registry as a
  Claude Code agent on the computer "cloud". A key press only focuses: the
  browser window showing the session, else the Claude desktop app
  (raiser.raise_cloud). The page address is kept for a later tab switch.

Standard library only (ssl, socket), with no Qt: it runs in PolyCore, also in
the headless daemon. Every request sends a User-Agent: Cloudflare answers
Python's default one with 403 "error code: 1010".
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import secrets
import socket
import ssl
import tempfile
import threading
import time
import urllib.parse
import urllib.request

from polyhost.services.agents import cloud_hook

DEFAULT_RELAY_URL = "https://polyhost-agent-relay.polykybd.workers.dev"
USER_AGENT = "polyhost-cloud-relay/1"
FILE_NAME = "cloud_relay.json"
FILE_FORMAT = 1

VENDOR = "claude-code"
MACHINE = "cloud"
SURFACE = "web"
# The only pages a key press opens: a claude.ai session page, as cloud_hook's
# session_url() builds it. The report is authenticated with the channel key, but
# a wrong URL must still not open another site, path or query.
URL_PREFIX = "https://claude.ai/code/"
_SESSION_URL = re.compile(r"https://claude\.ai/code/session_[A-Za-z0-9_-]{1,100}")


def is_session_url(url) -> bool:
    return isinstance(url, str) and _SESSION_URL.fullmatch(url) is not None

# The relay closes nothing on its side, but a router or proxy drops a TCP
# connection that is quiet for long. Each ping costs one relay request, so this
# is about 360 requests a day for each connected host.
PING_EVERY_S = 240
PONG_TIMEOUT_S = 30
RECONNECT_MIN_S = 5
RECONNECT_MAX_S = 300
HTTP_TIMEOUT_S = 15
MAX_MESSAGE_BYTES = 1 << 20     # a snapshot of 64 sessions is about 25 KB

log = logging.getLogger(__name__)


class RelayError(Exception):
    pass


# ---- the channel and its file ---------------------------------------------------

def load_channel(path: str) -> dict | None:
    """{url, channel, read_token, write_token, key} from the file, or None."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    try:
        if not isinstance(data, dict) or data.get("format") != FILE_FORMAT:
            return None
        key = base64.urlsafe_b64decode(data["key"] + "=" * (-len(data["key"]) % 4))
        out = {"url": str(data["url"]).rstrip("/"), "channel": data["channel"],
               "read_token": data["read_token"], "write_token": data["write_token"],
               "key": key}
        # The same checks as the configuration string the cloud side reads.
        cloud_hook.parse_config(setup_config(out))
        if not cloud_hook._is_hex(out["read_token"], 64):
            return None
        return out
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def save_channel(path: str, channel: dict) -> None:
    """Write the channel's secrets, readable by this user only."""
    data = {"format": FILE_FORMAT, "url": channel["url"], "channel": channel["channel"],
            "read_token": channel["read_token"], "write_token": channel["write_token"],
            "key": base64.urlsafe_b64encode(channel["key"]).decode().rstrip("=")}
    # A file of its own per write (mkstemp creates it with mode 0600), so two
    # writers never share a temporary file.
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp",
                               dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass    # already moved or never written
        raise


def remove_channel_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass    # already gone: the goal of this call


def setup_config(channel: dict) -> str:
    """The value of POLYKYBD_CLOUD_RELAY in the cloud environment."""
    return cloud_hook.format_config(channel["url"], channel["channel"],
                                    channel["write_token"], channel["key"])


# Where the setup script writes what the download and the install said: the
# `|| true` below hides a failure from the session, so this file is the one
# place a blocked host (a 403 from the proxy) or a failed install shows.
SETUP_LOG = "/var/log/polykybd-hook-install.log"


def setup_script(url: str) -> str:
    """The cloud environment's setup script.

    - `|| true`: a failing setup script stops the session from starting, and the
      agent keys are not worth that.
    - Download and install are one group with one log, so a blocked download
      leaves a trace too (SETUP_LOG).
    - `--install` adds to ~/.claude/settings.json: a script line that writes
      that file afterwards would remove the hooks, hence the first comment."""
    return ("# PolyKybd agent keys. Put this after anything that writes "
            "~/.claude/settings.json.\n"
            f"{{ curl -fsSL {url}/v1/hook.py -o {cloud_hook.INSTALL_PATH} \\\n"
            f"  && python3 {cloud_hook.INSTALL_PATH} --install; }} "
            f"> {SETUP_LOG} 2>&1 || true")


def setup_text(channel: dict) -> dict:
    """What the user enters in the claude.ai cloud environment's settings."""
    return {"variable": cloud_hook.CONFIG_ENV, "config": setup_config(channel),
            "host": urllib.parse.urlsplit(channel["url"]).hostname or "",
            "script": setup_script(channel["url"])}


# ---- HTTP ------------------------------------------------------------------------

def ssl_context() -> ssl.SSLContext:
    """The app's trust store: the platform's roots plus certifi's
    (polyhost.util.https). A python.org build on macOS has no system store."""
    from polyhost.util.https import ssl_context as shared
    ctx = shared()
    if ctx is None:
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def http_call(base_url: str, method: str, path: str, token: str | None = None,
              body: dict | None = None, timeout: float = HTTP_TIMEOUT_S):
    """(status, JSON answer or {}) of one request to the relay. Raises RelayError
    when the relay cannot be reached."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base_url + path, data=data, method=method, headers=headers)
    https = urllib.request.HTTPSHandler(context=ssl_context())
    try:
        with urllib.request.build_opener(https).open(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read(MAX_MESSAGE_BYTES)
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read(4096)
    except (OSError, ValueError) as e:
        raise RelayError(f"the relay cannot be reached: {e}") from e
    try:
        answer = json.loads(raw or b"{}")
    except ValueError:
        answer = {}
    return status, answer if isinstance(answer, dict) else {}


def create_channel(path: str, url: str = DEFAULT_RELAY_URL, http=None) -> dict:
    """A new channel on the relay, saved to `path`. Raises RelayError."""
    http = http or http_call
    channel = cloud_hook.new_channel()
    channel["url"] = url.rstrip("/")
    status, answer = http(channel["url"], "POST", "/v1/channels", body={
        "channel": channel["channel"],
        "read_hash": cloud_hook.token_hash(channel["read_token"]),
        "write_hash": cloud_hook.token_hash(channel["write_token"])})
    if status not in (200, 201):
        raise RelayError(f"the relay refused the new channel ({status}: "
                         f"{answer.get('error') or 'no reason given'})")
    save_channel(path, channel)
    return channel


def delete_session(channel: dict, k: str, http=None) -> bool:
    """Remove one cloud session from the relay, so a reconnect's snapshot does
    not bring it back (it stays there 24 h after its last report). True when the
    relay answered; a relay that cannot be reached removes it after 24 h."""
    http = http or http_call
    if not cloud_hook._is_hex(k, 32):
        return False
    try:
        status, _ = http(channel["url"], "DELETE", f"/v1/c/{channel['channel']}/e/{k}",
                         token=channel["read_token"])
    except RelayError as e:
        log.info("Cloud relay: session %s not removed on the relay: %s", k[:8], e)
        return False
    return status == 200


def delete_channel(path: str, channel: dict | None, http=None) -> str:
    """Delete the channel on the relay and the local file. The file goes even when
    the relay cannot be reached: its sessions expire there after 24 h. Returns
    what happened on the relay."""
    http = http or http_call
    result = "no channel"
    if channel is not None:
        try:
            status, _ = http(channel["url"], "DELETE", f"/v1/c/{channel['channel']}",
                             token=channel["read_token"])
            result = "deleted" if status in (200, 404) else f"relay answered {status}"
        except RelayError as e:
            result = str(e)
    remove_channel_file(path)
    return result


# ---- reports into the registry ----------------------------------------------------

def decode_report(key: bytes, blob: str) -> dict | None:
    """The fields of one sealed report, bounded, or None when it is not ours or
    malformed."""
    try:
        report = json.loads(cloud_hook.open_sealed(key, blob))
    except (ValueError, TypeError):
        return None
    if not isinstance(report, dict):
        return None
    state = report.get("state")
    if state not in ("working", "waiting", "done", "idle", "ended"):
        return None
    url = report.get("url")
    url = url if is_session_url(url) else ""
    ts = report.get("ts")
    return {"state": state, "url": url,
            "title": str(report.get("title") or "")[:cloud_hook.TITLE_MAX_CHARS],
            "cwd": str(report.get("cwd") or "")[:120],
            "ts": float(ts) if isinstance(ts, (int, float)) and not isinstance(ts, bool) else 0.0}


class RelaySink:
    """Applies relay entries to the registry. Separate from the connection so the
    tests drive it without a socket."""

    def __init__(self, registry, key: bytes, limits=None, wall=time.time):
        """`limits()`: (stale after s, forget after s), as the registry reads them."""
        self.registry = registry
        self.key = key
        self._limits = limits
        self._wall = wall
        self._applied: dict[str, str] = {}     # k -> the blob last applied

    def snapshot(self, entries) -> int:
        """The relay's full list for the channel. A cloud agent missing from it
        ended while this host was not listening. Returns how many were applied."""
        present = set()
        applied = 0
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, dict):
                continue
            k = entry.get("k")
            if isinstance(k, str) and cloud_hook._is_hex(k, 32):
                present.add(k)
                applied += self.event(k, entry.get("blob"), False)
        for agent in self.registry.agents():
            if agent.machine == MACHINE and agent.session_id not in present:
                self.registry.report(agent.vendor, agent.session_id, "ended", event="relay")
                self._applied.pop(agent.session_id, None)
        return applied

    def event(self, k, blob, ended) -> int:
        """One entry. 1 when it changed the registry's input, else 0."""
        if not isinstance(k, str) or not cloud_hook._is_hex(k, 32) or not isinstance(blob, str):
            return 0
        if ended and not blob:
            # The relay removed the session (a host's "Remove Agent"): it has no
            # key, so it sends no report. The worst a relay can do with this is
            # remove a key early, which it can do anyway by dropping reports.
            self._applied.pop(k, None)
            if any(a.session_id == k and a.machine == MACHINE for a in self.registry.agents()):
                self.registry.report(VENDOR, k, "ended", event="relay")
                return 1
            return 0
        if self._applied.get(k) == blob:
            return 0     # the same report again (a reconnect's snapshot)
        report = decode_report(self.key, blob)
        if report is None:
            log.info("Cloud relay: a report for %s could not be decrypted "
                     "(another key, or changed on the way)", k[:8])
            return 0
        self._applied[k] = blob
        if ended or report["state"] == "ended":
            self.registry.report(VENDOR, k, "ended", event="relay")
            self._applied.pop(k, None)
            return 1
        state = report["state"]
        age = self._wall() - report["ts"] if report["ts"] else 0.0
        stale_s, forget_s = self._limits() if self._limits else (0, 0)
        if forget_s and state in ("idle", "done") and age >= forget_s:
            return 0     # the registry would forget it at once
        if stale_s and state == "working" and age >= stale_s:
            state = "stale"
        self.registry.report(VENDOR, k, state, event="relay", headline=report["title"],
                             cwd=report["cwd"], surface=SURFACE, machine=MACHINE,
                             url=report["url"])
        return 1

    def forget_all(self) -> None:
        """The channel was disconnected: no cloud agent stays on a key."""
        for agent in self.registry.agents():
            if agent.machine == MACHINE:
                self.registry.forget(agent.vendor, agent.session_id)
        self._applied.clear()


# ---- the WebSocket --------------------------------------------------------------

def _proxy_for(host: str):
    """(host, port) of the HTTPS proxy for `host`, or None."""
    proxy = urllib.request.getproxies().get("https")
    if not proxy or urllib.request.proxy_bypass(host):
        return None
    parts = urllib.parse.urlsplit(proxy if "://" in proxy else "http://" + proxy)
    return (parts.hostname, parts.port or 8080) if parts.hostname else None


class WebSocket:
    """Enough of RFC 6455 for the relay: one TLS connection, text frames in, a
    masked text frame out ("ping"), control frames answered."""

    def __init__(self, sock):
        self.sock = sock
        self._buf = b""
        self._parts = []        # the frames of a message not yet complete

    @classmethod
    def connect(cls, url: str, path: str, token: str, timeout: float = HTTP_TIMEOUT_S):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not parts.hostname:
            raise RelayError("the relay address must use https")
        host, port = parts.hostname, parts.port or 443
        proxy = _proxy_for(host)
        try:
            if proxy:
                raw = socket.create_connection(proxy, timeout=timeout)
                raw.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                            f"User-Agent: {USER_AGENT}\r\n\r\n".encode())
                status, _ = cls._read_head(raw)
                if status != 200:
                    raw.close()
                    raise RelayError(f"the proxy refused the connection ({status})")
            else:
                raw = socket.create_connection((host, port), timeout=timeout)
            sock = ssl_context().wrap_socket(raw, server_hostname=host)
            key = base64.b64encode(secrets.token_bytes(16)).decode()
            sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                          "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                          f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                          f"User-Agent: {USER_AGENT}\r\n"
                          f"Authorization: Bearer {token}\r\n\r\n").encode())
            status, rest = cls._read_head(sock)
        except (OSError, ssl.SSLError) as e:
            raise RelayError(f"the relay cannot be reached: {e}") from e
        if status != 101:
            sock.close()
            raise RelayError(f"the relay refused the connection ({status})")
        ws = cls(sock)
        ws._buf = rest
        return ws

    @staticmethod
    def _read_head(sock):
        """(status, bytes after the header) of an HTTP response head."""
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(1024)
            if not chunk:
                raise RelayError("the connection closed during the handshake")
            head += chunk
            if len(head) > 16384:
                raise RelayError("the handshake answer is too long")
        head, rest = head.split(b"\r\n\r\n", 1)
        try:
            status = int(head.split(b" ", 2)[1])
        except (IndexError, ValueError):
            raise RelayError("not an HTTP answer") from None
        return status, rest

    def _parse_frame(self):
        """(fin, opcode, payload) of the first frame in the buffer, consumed, or
        None while it has not arrived in full. Nothing is consumed before then,
        so a timeout in the middle of a frame loses no bytes."""
        buf = self._buf
        if len(buf) < 2:
            return None
        b0, b1 = buf[0], buf[1]
        length, pos = b1 & 0x7F, 2
        if length == 126:
            if len(buf) < 4:
                return None
            length, pos = int.from_bytes(buf[2:4], "big"), 4
        elif length == 127:
            if len(buf) < 10:
                return None
            length, pos = int.from_bytes(buf[2:10], "big"), 10
        if length > MAX_MESSAGE_BYTES:
            raise ConnectionError("a message from the relay is too large")
        mask = None
        if b1 & 0x80:
            if len(buf) < pos + 4:
                return None
            mask, pos = buf[pos:pos + 4], pos + 4
        if len(buf) < pos + length:
            return None
        payload = buf[pos:pos + length]
        self._buf = buf[pos + length:]
        if mask:
            payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        return bool(b0 & 0x80), b0 & 0x0F, payload

    def _frame(self):
        """The next whole frame, reading from the socket as needed."""
        while True:
            frame = self._parse_frame()
            if frame is not None:
                return frame
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("the relay closed the connection")
            self._buf += chunk

    def recv(self, timeout: float):
        """The next text message, or None when `timeout` passed without one.
        Raises ConnectionError when the connection ends. A message that has
        only partly arrived stays buffered for the next call."""
        self.sock.settimeout(timeout)
        try:
            while True:
                fin, op, payload = self._frame()
                if op == 0x8:
                    raise ConnectionError("the relay closed the connection")
                if op == 0x9:
                    self._send(0xA, payload)
                    continue
                if op == 0xA:
                    continue
                if op in (0x1, 0x0):
                    self._parts.append(payload)
                    if sum(len(p) for p in self._parts) > MAX_MESSAGE_BYTES:
                        raise ConnectionError("a message from the relay is too large")
                    if fin:
                        text = b"".join(self._parts).decode("utf-8", errors="replace")
                        self._parts = []
                        return text
                # Binary frames are not part of the relay's protocol: skipped.
        except (socket.timeout, TimeoutError):
            return None
        except (OSError, ssl.SSLError) as e:
            raise ConnectionError(str(e)) from e

    def send_text(self, text: str) -> None:
        self._send(0x1, text.encode())

    def _send(self, op: int, payload: bytes) -> None:
        mask = secrets.token_bytes(4)
        head = bytes([0x80 | op])
        n = len(payload)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 1 << 16:
            head += bytes([0x80 | 126]) + n.to_bytes(2, "big")
        else:
            head += bytes([0x80 | 127]) + n.to_bytes(8, "big")
        body = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
        try:
            self.sock.sendall(head + mask + body)
        except (OSError, ssl.SSLError) as e:
            raise ConnectionError(str(e)) from e

    def close(self) -> None:
        try:
            self._send(0x8, (1000).to_bytes(2, "big"))
        except ConnectionError:
            pass    # already gone
        try:
            self.sock.close()
        except OSError:
            pass    # already closed


# ---- the connection thread -------------------------------------------------------

class RelayClient:
    """Keeps the WebSocket to one channel open and applies what arrives. start()
    and stop() may be called from any thread; stop() waits at most `join_s`."""

    def __init__(self, channel: dict, registry, limits=None, connect=WebSocket.connect,
                 log_=None):
        self.channel = channel
        self.sink = RelaySink(registry, channel["key"], limits=limits)
        self._connect = connect
        self._log = log_ or log
        self._stop = threading.Event()
        self._thread = None
        self._ws = None
        self._lock = threading.Lock()
        self.state = "stopped"      # stopped, connecting, connected, retrying
        self.last_error = ""
        self.connected_since = 0.0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="cloud-relay", daemon=True)
            self._thread.start()

    def stop(self, join_s: float = 2.0) -> None:
        self._stop.set()
        with self._lock:
            ws, thread = self._ws, self._thread
            self._thread = None
        if ws is not None:
            ws.close()     # wakes the reader
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=join_s)
        self.state = "stopped"

    def status(self) -> dict:
        return {"state": self.state, "error": self.last_error,
                "connected_since": self.connected_since}

    def _run(self) -> None:
        delay = RECONNECT_MIN_S
        while not self._stop.is_set():
            self.state = "connecting"
            started = time.monotonic()
            try:
                self._session()
            except (RelayError, ConnectionError, OSError, ValueError) as e:
                self.last_error = str(e)
            if self._stop.is_set():
                break
            # A connection that held for a while starts the backoff again.
            if time.monotonic() - started > 2 * RECONNECT_MAX_S:
                delay = RECONNECT_MIN_S
            self.state = "retrying"
            self._log.info("Cloud relay: disconnected (%s); next try in %d s",
                           self.last_error or "closed", delay)
            if self._stop.wait(delay):
                break
            delay = min(RECONNECT_MAX_S, delay * 2)
        self.state = "stopped"

    def _session(self) -> None:
        ch = self.channel
        ws = self._connect(ch["url"], f"/v1/c/{ch['channel']}/ws", ch["read_token"])
        with self._lock:
            if self._stop.is_set():
                ws.close()
                return
            self._ws = ws
        try:
            self.state = "connected"
            self.connected_since = time.time()
            self.last_error = ""
            self._log.info("Cloud relay: connected")
            last_ping = time.monotonic()
            ping_sent = 0.0
            while not self._stop.is_set():
                text = ws.recv(timeout=10)
                now = time.monotonic()
                if text is None:
                    if ping_sent and now - ping_sent > PONG_TIMEOUT_S:
                        raise ConnectionError("no answer to a ping")
                    if not ping_sent and now - last_ping >= PING_EVERY_S:
                        ws.send_text("ping")
                        ping_sent = last_ping = now
                    continue
                if text == "pong":
                    ping_sent = 0.0
                    continue
                self._message(text)
        finally:
            with self._lock:
                self._ws = None
            ws.close()

    def _message(self, text: str) -> None:
        try:
            msg = json.loads(text)
        except ValueError:
            return
        if not isinstance(msg, dict):
            return
        if msg.get("type") == "snapshot":
            entries = msg.get("entries")
            self.sink.snapshot(entries)
            self._log.info("Cloud relay: %d cloud session(s) on the channel",
                           len(entries) if isinstance(entries, list) else 0)
        elif msg.get("type") == "event":
            self.sink.event(msg.get("k"), msg.get("blob"), msg.get("ended") is True)
