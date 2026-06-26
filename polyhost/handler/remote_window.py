import logging
import re
import socket
import threading

from polyhost.handler.common import Flags, find_matching_entry

TCP_PORT = 50162
BUFFER_SIZE = 1024


# Needs to be started as thread
def receive_from_forwarder(log, on_report, stop_event):
    """Accept ``handle;name;title[;os]`` reports from a forwarder and hand each to
    ``on_report(handle, name, title, os=...)`` — the same entry point the
    window.report RPC uses (RemoteHandler.report_window), so the TCP relay is now
    just a transport over the unified path rather than poking a separate store.
    The optional 4th ``os`` field (an OsType value int) is sent by forwarders that
    forward their OS; older forwarders omit it (back-compatible split)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind(("", TCP_PORT))
    except socket.error as message:
        log.warning(f"Failed to bind remote listener socket: {message}")
        sock.close()
        return

    sock.listen(5)
    sock.settimeout(10.0)
    log.info("Remote listener started on port %d", TCP_PORT)

    while not stop_event.is_set():
        try:
            conn, (addr, _) = sock.accept()
            try:
                data = conn.recv(BUFFER_SIZE)
                data = data.decode("utf-8")
                entries = [0, "", ""] if not data else data.split(";")
                if len(entries) > 2:
                    os = None
                    if len(entries) > 3 and entries[3] != "":
                        try:
                            os = int(entries[3])
                        except ValueError:
                            os = None
                    on_report(entries[0], entries[1], entries[2], os=os)
                    log.debug_detailed("Remote data from %s: handle=%s name=%s os=%s", addr, entries[0], entries[1], os)
            finally:
                conn.close()
        except socket.timeout:
            pass
        except OSError as e:
            if not stop_event.is_set():
                log.warning("Remote listener socket error: %s", e)
    sock.close()
    log.info("Remote listener stopped")


class RemoteHandler:
    def __init__(self, mapping):
        self.log = logging.getLogger("PolyHost")
        self.forwarder = None
        self.stop_event = threading.Event()

        self.handle = None
        self.title = None
        self.name = None
        self.current_entry = None
        self.last_entry = None
        self.connections = {}
        self.mapping = mapping
        # Latest OS reported by the forwarder (an OsType value int), or None when
        # the forwarder does not forward its OS. Read by PolyCore's window tick.
        self.forwarded_os = None
        self.listen_to_forwarder()

    def _has_remote_entries(self):
        return any("remote" in entry for entry in self.mapping.values())

    def listen_to_forwarder(self):
        if not self._has_remote_entries():
            return
        if self.forwarder and self.forwarder.is_alive():
            return
        self.forwarder = threading.Thread(
            target=receive_from_forwarder,
            name="PolyKybd Remote Handler",
            args=(self.log, self.report_window, self.stop_event),
        )
        self.forwarder.daemon = True
        self.forwarder.start()

    def report_window(self, handle, name, title, os=None):
        """Single entry point for an active-window report, from either source:
        the cross-machine TCP relay (`receive_from_forwarder`) or the
        ``window.report`` control-socket RPC / ``polyctl window report``.

        Stores the latest report; ``remote_changed`` reads it and runs the
        shared matcher (`common.find_matching_entry`). ``os`` (optional, an OsType
        value int) is the forwarder's OS — kept on ``forwarded_os`` for the window
        tick; left unchanged when None so a report without an OS never clears it."""
        self.connections["_report"] = {
            "handle": str(handle),
            "name": str(name),
            "title": str(title),
        }
        self.connections["_latest"] = "_report"
        if os is not None:
            self.forwarded_os = os
        self.log.debug_detailed(
            "report_window: handle=%s name=%s title=%s os=%s", handle, name, title, os)

    def _match_remote(self):
        """Match the current remote window's app/title against the mapping using
        the shared matcher, updating current/last_entry. Returns True on match."""
        if self.name not in self.mapping:
            return False
        try:
            matched = find_matching_entry(self.title, self.mapping[self.name])
        except re.error as e:
            self.log.warning(
                "Cannot match entry '%s': %s, because '%s'@%d with '%s'",
                self.name, self.mapping[self.name], e.msg, e.pos, e.pattern,
            )
            return False
        if matched is None:
            return False
        self.current_entry = matched
        self.last_entry = matched
        return True

    def remote_changed(self, remote_entry: dict):
        self.listen_to_forwarder()  # restart listener if it died (e.g. bind failed on first try)
        ip = self.connections.get("_latest")
        if not ip:
            self.log.debug_detailed("remote_changed: no TCP data received yet (no connection)")
            return False
        if not isinstance(self.connections.get(ip), dict):
            self.log.debug_detailed("remote_changed: connection data for %s is not a dict: %s", ip, self.connections.get(ip))
            return False

        data = self.connections[ip]

        if (
            data
            and len(data) > 2
            and (self.handle != data["handle"] or self.title != data["title"])
        ):
            self.handle = data["handle"]
            self.title = data["title"]
            self.name = data["name"].split(".")[0].lower()
            self.log.info(
                'Remote App Changed: "%s", Title: "%s"  Handle: %s',
                data["name"],
                self.title,
                self.handle,
            )

            if not self._match_remote() and self.current_entry:
                self.current_entry = None
            return True
        self.log.debug_detailed(
            "remote_changed: no change (ip=%s stored_handle=%s->%s stored_title=%s->%s)",
            ip, self.handle, data.get("handle"), self.title, data.get("title"),
        )
        return False

    def has_overlay(self):
        return (
            self.current_entry and self.current_entry["flags"][Flags.HAS_OVERLAY.value]
        )

    def get_overlay_data(self):
        return self.current_entry["overlay"]

    def reset_for_resend(self):
        """Clear cached remote window identity so the next remote_changed() call sees a delta."""
        self.handle = None
        self.title = None
        self.last_entry = None

    def close(self):
        self.stop_event.set()
        if self.forwarder and self.forwarder.is_alive():
            self.forwarder.join(timeout=15)
