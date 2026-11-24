"""The keyboard computer's address, read from the remote-desktop connection to this one.

A forwarder runs on the computer you reach through NoMachine or Remote Desktop (RDP). That
connection comes FROM the keyboard computer, so its peer address is where the forwarder
must report to. This module finds it, with no script and no file (the older way is
autorun_forwarder/remote_ip_poll.sh).

The connection table is read in Python, with no child process: `/proc/net/tcp` on Linux
and `GetExtendedTcpTable` (ctypes) on Windows. Both are free of the display language.
Only macOS runs `netstat`, whose state word is English there.

Qt-free. `ClientAddressWatcher` looks on a thread of its own, and only while window
changes show that someone uses this computer: `address()` answers from memory.
"""
from __future__ import annotations

import logging
import re
import socket
import struct
import subprocess
import sys
import threading
import time

log = logging.getLogger(__name__)

#: NoMachine's port, and the RDP port (xrdp, or Windows' own RDP server).
DEFAULT_PORTS = (4000, 3389)
#: Fewest seconds between two looks.
MIN_GAP_S = 5.0
#: Seconds between looks while an address is found and the computer is in use.
IDLE_INTERVAL_S = 60.0
#: Seconds without a window change after which the watcher stops looking at all.
ACTIVE_FOR_S = 600.0
#: Failed looks in a row before the watcher logs a warning.
WARN_AFTER_FAILURES = 3
#: Seconds `netstat` (macOS) may run.
TOOL_TIMEOUT_S = 5.0

_TCP_ESTABLISHED_PROC = "01"       # /proc/net/tcp state column
_TCP_ESTABLISHED_WIN = 5           # MIB_TCP_STATE_ESTAB
_TCP_TABLE_BASIC_ALL = 2           # MIB_TCPTABLE, rows of five DWORDs
_ERROR_INSUFFICIENT_BUFFER = 122

# macOS/BSD `netstat -an -p tcp`: "tcp4 0 0 10.0.0.5.3389 10.0.0.9.51234 ESTABLISHED".
_NETSTAT_BSD = re.compile(
    r"^\s*tcp\S*\s+\d+\s+\d+\s+(\d{1,3}(?:\.\d{1,3}){3})\.(\d+)\s+"
    r"(\d{1,3}(?:\.\d{1,3}){3})\.\d+\s+ESTABLISHED\b", re.M | re.I)


def _usable(address: str) -> bool:
    """An IPv4 address the forwarder can report to: not loopback, not unspecified.
    Only IPv4: the forwarder's report endpoint and its relay are AF_INET sockets."""
    parts = address.split(".")
    if len(parts) != 4 or not all(p.isdigit() and int(p) <= 255 for p in parts):
        return False
    return parts[0] not in ("127", "0")


def _proc_address(hex_text: str):
    """The IPv4 address in a /proc/net/tcp (8 hex digits) or tcp6 (32 hex digits) column,
    or None for a native IPv6 address. The kernel prints each 32-bit word in the byte
    order of the CPU, so the bytes are read back in that order."""
    try:
        if len(hex_text) == 8:
            return socket.inet_ntoa(struct.pack("=I", int(hex_text, 16)))
        if len(hex_text) == 32:
            raw = b"".join(struct.pack("=I", int(hex_text[i:i + 8], 16))
                           for i in range(0, 32, 8))
            if raw[:12] == b"\0" * 10 + b"\xff\xff":       # ::ffff:a.b.c.d
                return socket.inet_ntoa(raw[12:])
    except (ValueError, struct.error, OSError):
        return None             # not a hex address: the row is skipped
    return None


def parse_proc_tcp(text: str, ports):
    """Peer addresses of the established connections TO one of `ports` on this
    computer, from the text of /proc/net/tcp or /proc/net/tcp6, in order."""
    wanted = {int(p) for p in ports}
    out = []
    for line in text.splitlines()[1:]:            # the first line is the header
        cols = line.split()
        if len(cols) < 4 or cols[3] != _TCP_ESTABLISHED_PROC:
            continue
        try:
            local_port = int(cols[1].rsplit(":", 1)[1], 16)
        except (IndexError, ValueError):
            continue
        if local_port not in wanted:
            continue
        peer = _proc_address(cols[2].rsplit(":", 1)[0])
        if peer and _usable(peer):
            out.append(peer)
    return out


def parse_windows_table(data: bytes, ports):
    """Peer addresses from the bytes of a MIB_TCPTABLE (`GetExtendedTcpTable`), in
    order: a count, then rows of five DWORDs (state, local address, local port, remote
    address, remote port). Ports hold the network byte order in their low 16 bits."""
    wanted = {int(p) for p in ports}
    if len(data) < 4:
        return []
    (count,) = struct.unpack_from("<I", data, 0)
    out = []
    for i in range(min(count, (len(data) - 4) // 20)):
        state, _local, local_port, remote, _remote_port = struct.unpack_from(
            "<5I", data, 4 + 20 * i)
        port = ((local_port & 0xFF) << 8) | ((local_port >> 8) & 0xFF)
        if state != _TCP_ESTABLISHED_WIN or port not in wanted:
            continue
        peer = socket.inet_ntoa(struct.pack("<I", remote))
        if _usable(peer):
            out.append(peer)
    return out


def parse_netstat(text: str, ports):
    """Peer addresses of the established connections TO one of `ports` on this
    computer, from the macOS `netstat -an -p tcp` output, in order."""
    wanted = {str(p) for p in ports}
    out = []
    for match in _NETSTAT_BSD.finditer(text):
        if match.group(2) in wanted and _usable(match.group(3)):
            out.append(match.group(3))
    return out


def _windows_table():
    """The bytes of the IPv4 TCP table, or None when Windows refuses."""
    import ctypes
    import ctypes.wintypes
    iphlpapi = ctypes.windll.iphlpapi
    size = ctypes.wintypes.DWORD(0)
    buf = None
    for _ in range(4):                 # the table can grow between the two calls
        result = iphlpapi.GetExtendedTcpTable(
            buf, ctypes.byref(size), False, socket.AF_INET, _TCP_TABLE_BASIC_ALL, 0)
        if result == 0:
            return buf.raw[:size.value]
        if result != _ERROR_INSUFFICIENT_BUFFER:
            return None
        buf = ctypes.create_string_buffer(size.value)
    return None


def _read(kind: str):
    """The raw connection data for `kind` ("tcp", "tcp6", "win", "netstat"), or None
    when it cannot be read."""
    try:
        if kind in ("tcp", "tcp6"):
            try:
                with open("/proc/net/" + kind, encoding="ascii", errors="replace") as f:
                    return f.read()
            except FileNotFoundError:
                # No tcp6 file: IPv6 is off, so there is nothing to list. (A missing
                # /proc/net/tcp means no /proc: a failure.)
                return "" if kind == "tcp6" else None
        if kind == "win":
            return _windows_table()
        kwargs = {"capture_output": True, "text": True, "timeout": TOOL_TIMEOUT_S,
                  "check": False}
        # Audited: a fixed argv of the OS's own `netstat`, shell=False, no value from
        # outside. No injection path.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        proc = subprocess.run(["netstat", "-an", "-p", "tcp"], **kwargs)
        return proc.stdout if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, AttributeError):
        return None


def detect_client_address(ports=DEFAULT_PORTS, platform=None, read=_read):
    """`(ok, address)`: the first IPv4 peer connected to one of `ports` on this computer.
    `ok` is False when the connection table could not be read: the caller keeps what it
    had then, and does not read the failure as "nobody is connected". The first port in
    `ports` wins when clients are on several."""
    platform = platform or sys.platform
    if platform.startswith("linux"):
        tcp = read("tcp")
        if tcp is None:
            return False, None
        tcp6 = read("tcp6")                # "" when IPv6 is off, None when unreadable
        if tcp6 is None:
            return False, None
        for port in ports:
            peers = parse_proc_tcp(tcp, [port]) + parse_proc_tcp(tcp6, [port])
            if peers:
                return True, peers[0]
        return True, None
    if platform == "win32":
        table = read("win")
        if table is None:
            return False, None
        for port in ports:
            peers = parse_windows_table(table, [port])
            if peers:
                return True, peers[0]
        return True, None
    text = read("netstat")
    if text is None:
        return False, None
    for port in ports:
        peers = parse_netstat(text, [port])
        if peers:
            return True, peers[0]
    return True, None


class ClientAddressWatcher:
    """Looks for the keyboard computer's address, only while this computer is in use.

    `touch()` is called on every window change. It asks for a look, and a look happens
    at most once per `min_gap` seconds. With an address found, the watcher looks again
    every `idle_interval` seconds, to notice a dropped connection or another client.
    After `active_for` seconds without a `touch()` it stops, and an idle computer (a
    weekend) runs no look. The next `touch()` starts it again. `address()` answers from
    the last look and starts nothing.

    A look that fails (the table cannot be read) keeps the previous answer.
    """

    def __init__(self, ports=DEFAULT_PORTS, detect=detect_client_address,
                 min_gap=MIN_GAP_S, idle_interval=IDLE_INTERVAL_S,
                 active_for=ACTIVE_FOR_S, clock=time.monotonic):
        self._ports = tuple(ports)
        self._detect = detect
        self._min_gap = min_gap
        self._idle_interval = idle_interval
        self._active_for = active_for
        self._clock = clock
        self._address = None
        self._last_look = None
        self._last_touch = None
        self._failures = 0
        self._lock = threading.Lock()
        self._thread = None
        self._wake = threading.Event()
        self._stop = threading.Event()

    def address(self):
        with self._lock:
            return self._address

    def touch(self):
        """A window changed: this computer is in use. Ask for a look."""
        with self._lock:
            self._last_touch = self._clock()
        self.request_look()

    def request_look(self):
        """Ask for a look soon (a report to the found address failed). Ignored while the
        computer is idle (no window change for `active_for` seconds): a relay that stays
        down must not keep the watcher looking."""
        with self._lock:
            if (self._last_touch is None
                    or self._clock() - self._last_touch >= self._active_for):
                return
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="PolyKybd client address")
            self._thread.start()
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def refresh(self):
        """One look now, on the caller's thread."""
        ok, address = self._detect(self._ports)
        with self._lock:
            self._last_look = self._clock()
            if not ok:
                self._failures += 1
                if self._failures == WARN_AFTER_FAILURES:
                    log.warning("The connection table cannot be read (%d looks in a "
                                "row): the keyboard computer's address is not found "
                                "automatically", self._failures)
                return
            self._failures = 0
            if address != self._address:
                log.info("Keyboard computer from the remote-desktop connection: %s",
                         address or "none")
            self._address = address

    def _timeout(self):
        """Seconds the thread sleeps before it looks without being asked: None (until
        the next request) when no address is found, or the computer is idle."""
        with self._lock:
            if self._address is None or self._last_touch is None:
                return None
            now = self._clock()
            if now - self._last_touch >= self._active_for:
                return None
            return max(0.0, self._idle_interval - (now - (self._last_look or now)))

    def _loop(self):
        while not self._stop.is_set():
            self._wake.wait(self._timeout())
            if self._stop.is_set():
                break
            self._wake.clear()
            with self._lock:
                wait = (self._min_gap - (self._clock() - self._last_look)
                        if self._last_look is not None else 0.0)
            if wait > 0:
                self._stop.wait(wait)      # requests made meanwhile are one look
                self._wake.clear()
                if self._stop.is_set():
                    break
            try:
                self.refresh()
            except Exception:  # noqa: BLE001 - a bad look must not end the watch
                log.exception("Looking for the remote-desktop client failed")


def named_host(host, has_host_file, host_file_text):
    """The host `--host` or `--host-file` names, or "". The file takes priority over
    `--host`: `host_file_text` is its text, None when the file is absent."""
    return ((host_file_text or "").strip() if has_host_file else host) or ""


def resolve_host(host, has_host_file, host_file_text, detect_enabled, watcher,
                 authenticated=True):
    """The address the forwarder reports to.

    `host` is `--host`. With a `--host-file` (`has_host_file`), the file takes priority
    over `--host`, as before: `host_file_text` is its text, None when the file is absent
    (no active session). With the detection on (`detect_enabled`) and nothing named,
    the address of the remote-desktop client is used, but only when `authenticated`: a
    computer that can reach port 3389 or 4000 gets a TCP connection before it logs in,
    and the plaintext relay would send it the window titles. None: no host.
    """
    named = named_host(host, has_host_file, host_file_text)
    if named:
        return named
    if detect_enabled and authenticated and watcher is not None:
        return watcher.address()
    return None
