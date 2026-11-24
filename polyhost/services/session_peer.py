"""The keyboard computer's address, read from the remote-desktop connection to this one.

A forwarder runs on the computer you reach through NoMachine or Remote Desktop (RDP). That
connection comes FROM the keyboard computer, so its peer address is where the forwarder
must report to. This module finds it, with no script and no file (the older way is
autorun_forwarder/remote_ip_poll.sh).

Qt-free. The system call runs off the GUI thread: `ClientAddressWatcher` asks every few
seconds and `address()` answers from memory.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import subprocess
import sys
import threading
import time

log = logging.getLogger(__name__)

#: NoMachine's port, and the RDP port (xrdp, or Windows' own RDP server).
DEFAULT_PORTS = (4000, 3389)
#: Seconds between two looks at the connections.
REFRESH_S = 5.0
#: Seconds one `ss` or `netstat` may run.
TOOL_TIMEOUT_S = 5.0

# Linux `ss -tn`: "0 0 10.0.0.5:3389 10.0.0.9:51234". A dual-stack listener shows an IPv4
# client as "[::ffff:10.0.0.9]:51234".
_SS_ROW = re.compile(r"^\s*\d+\s+\d+\s+\S+\s+(\S+)\s*", re.M)
# macOS/BSD `netstat -an -p tcp`: "tcp4 0 0 10.0.0.5.3389 10.0.0.9.51234 ESTABLISHED". The word
# is English there. (Windows' `netstat` translates it, "HERGESTELLT" in German, so Windows
# asks PowerShell for the connections: see _WINDOWS_COMMAND.)
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


def _ss_peer(value: str):
    """The IPv4 address in an `ss` peer column ("a.b.c.d:port", "[::ffff:a.b.c.d]:port"),
    or None for anything else (native IPv6)."""
    host = value.rsplit(":", 1)[0].strip("[]")
    if host.lower().startswith("::ffff:"):
        host = host[7:]
    return host if _usable(host) else None


def parse_ss(text: str):
    """Peer addresses of the rows of `ss -tn state established ( sport = :PORT )`, in
    order. The header row has no digits in its first columns and is skipped."""
    out = []
    for match in _SS_ROW.finditer(text):
        peer = _ss_peer(match.group(1))
        if peer:
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


def parse_connections_csv(text: str, ports):
    """Peer addresses from the CSV of `Get-NetTCPConnection` (Windows), in order, for
    the rows whose LocalPort is in `ports`. The column names are property names, so they
    are the same in every display language."""
    wanted = {int(p) for p in ports}
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            port = int(row.get("LocalPort") or 0)
        except ValueError:
            continue
        address = (row.get("RemoteAddress") or "").strip()
        if address.lower().startswith("::ffff:"):
            address = address[7:]
        if port in wanted and _usable(address):
            out.append(address)
    return out


def _windows_command(ports):
    """The PowerShell call for the established connections to `ports`. `Get-NetTCPConnection`
    takes the state as an enum, so it does not depend on the language of Windows."""
    numbers = ",".join(str(int(p)) for p in ports)
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue "
            f"| Where-Object {{ $_.LocalPort -in {numbers} }} "
            "| Select-Object LocalPort,RemoteAddress | ConvertTo-Csv -NoTypeInformation"]


def _run(argv):
    """The tool's text output, or None when it cannot run or fails."""
    kwargs = {"capture_output": True, "text": True, "timeout": TOOL_TIMEOUT_S,
              "check": False}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        # Audited: a fixed argv of the OS's own tool (ss or netstat) with numeric ports,
        # shell=False, no value from outside. No injection path.
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
        proc = subprocess.run(argv, **kwargs)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def detect_client_address(ports=DEFAULT_PORTS, platform=None, run=_run):
    """`(ok, address)`: the first IPv4 peer connected to one of `ports` on this computer.
    `ok` is False when the system tool could not be run: the caller keeps what it had
    then, and does not read the failure as "nobody is connected". The first port in
    `ports` wins when clients are on several."""
    platform = platform or sys.platform
    if platform.startswith("linux"):
        for port in ports:
            text = run(["ss", "-tn", "state", "established", f"( sport = :{int(port)} )"])
            if text is None:
                return False, None
            peers = parse_ss(text)
            if peers:
                return True, peers[0]
        return True, None
    if platform == "win32":
        text = run(_windows_command(ports))
        if text is None:
            return False, None
        for port in ports:
            peers = parse_connections_csv(text, [port])
            if peers:
                return True, peers[0]
        return True, None
    text = run(["netstat", "-an", "-p", "tcp"])
    if text is None:
        return False, None
    for port in ports:
        peers = parse_netstat(text, [port])
        if peers:
            return True, peers[0]
    return True, None


class ClientAddressWatcher:
    """Looks for the keyboard computer's address every `REFRESH_S` seconds on a thread
    of its own; `address()` answers at once from the last look.

    The thread starts with the first `address()` call. A look that fails (the tool is
    missing, or it timed out) keeps the previous answer.
    """

    def __init__(self, ports=DEFAULT_PORTS, detect=detect_client_address,
                 interval=REFRESH_S):
        self._ports = tuple(ports)
        self._detect = detect
        self._interval = interval
        self._address = None
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()

    def refresh(self):
        """One look now, on the caller's thread."""
        ok, address = self._detect(self._ports)
        if not ok:
            return
        with self._lock:
            if address != self._address:
                log.info("Keyboard computer from the remote-desktop connection: %s",
                         address or "none")
            self._address = address

    def address(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="PolyKybd client address")
            self._thread.start()
        with self._lock:
            return self._address

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.refresh()
            except Exception:  # noqa: BLE001 - a bad look must not end the watch
                log.exception("Looking for the remote-desktop client failed")
            self._stop.wait(self._interval)


def resolve_host(host, has_host_file, host_file_text, detect_enabled, watcher):
    """The address the forwarder reports to.

    `host` is `--host`. With a `--host-file` (`has_host_file`), the file takes priority
    over `--host`, as before: `host_file_text` is its text, None when the file is absent
    (no active session). With the detection on (`detect_enabled`) and nothing named,
    the address of the remote-desktop client is used. None: no host.
    """
    named = (host_file_text or "").strip() if has_host_file else host
    if named:
        return named
    if detect_enabled and watcher is not None:
        return watcher.address()
    return None
