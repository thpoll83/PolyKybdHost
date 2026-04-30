import logging
import re
import socket
import threading

from polyhost.handler.common import Flags

TCP_PORT = 50162
BUFFER_SIZE = 1024


# Needs to be started as thread
def receive_from_forwarder(log, connections, stop_event):
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
                    connections[addr] = {
                        "handle": entries[0],
                        "name": entries[1],
                        "title": entries[2],
                    }
                    connections["_latest"] = addr
                    log.debug("Remote data from %s: handle=%s name=%s", addr, entries[0], entries[1])
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
            args=(self.log, self.connections, self.stop_event),
        )
        self.forwarder.daemon = True
        self.forwarder.start()

    def try_to_match_window_remote(self, name, entry):
        (
            has_overlay,
            has_remote,
            has_title,
            has_starts_with,
            has_ends_with,
            has_contains,
        ) = entry["flags"]
        match = has_overlay or has_remote
        try:
            if match:
                title_elements = (
                    self.title.split() if has_starts_with or has_ends_with else []
                )
                if len(title_elements) > 0:
                    if (
                        has_starts_with
                        and title_elements[0] in entry["titles-startswith"].keys()
                    ):
                        found = self.try_to_match_window_remote(
                            name, entry["titles-startswith"][title_elements[0]]
                        )
                        if found:
                            return True
                    if (
                        has_ends_with
                        and title_elements[-1] in entry["titles-endswith"].keys()
                    ):
                        found = self.try_to_match_window_remote(
                            name, entry["titles-endswith"][title_elements[-1]]
                        )
                        if found:
                            return True
                    if has_contains:
                        contains = entry["titles-contains"]
                        for elem in title_elements:
                            if elem in contains.keys():
                                found = self.try_to_match_window_remote(
                                    name, contains[elem]
                                )
                                if found:
                                    return True
                if self.title and has_title:
                    match = match and re.search(entry["title"], self.title)
        except re.error as e:
            self.log.warning(
                "Cannot match entry '%s': %s, because '%s'@%d with '%s'",
                name,
                entry,
                e.msg,
                e.pos,
                e.pattern,
            )
            return False

        if match:
            self.current_entry = entry
            self.last_entry = entry
            return True
        return False

    def remote_changed(self, remote_entry: dict):
        self.listen_to_forwarder()  # restart listener if it died (e.g. bind failed on first try)
        ip = self.connections.get("_latest")
        if not ip:
            self.log.debug("remote_changed: no TCP data received yet (no connection)")
            return False
        if not isinstance(self.connections.get(ip), dict):
            self.log.debug("remote_changed: connection data for %s is not a dict: %s", ip, self.connections.get(ip))
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

            found = False
            if self.name in self.mapping.keys():
                found = self.try_to_match_window_remote(self.name, self.mapping[self.name])
            if self.current_entry and not found:
                self.current_entry = None
            return True
        self.log.debug(
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

    def close(self):
        self.stop_event.set()
        if self.forwarder and self.forwarder.is_alive():
            self.forwarder.join(timeout=15)
