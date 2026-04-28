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

    try:
        sock.bind(("", TCP_PORT))
    except socket.error as message:
        log.warning(f"Failed to bind socket: {message}")
        sock.close()
        return

    sock.listen(5)
    sock.settimeout(10.0)

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
            finally:
                conn.close()
        except socket.timeout:
            pass
    sock.close()


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
        if self._has_remote_entries() and not self.forwarder:
            self.forwarder = threading.Thread(
                target=receive_from_forwarder,
                name="PolyKybd Remote Handler",
                args=(self.log, self.connections, self.stop_event),
            )
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
        ip = self.connections.get("_latest")
        if not ip:
            return False
        if not isinstance(self.connections.get(ip), dict):
            return False

        data = self.connections[ip]

        if (
            data
            and len(data) > 2
            and self.handle != data["handle"]
            and self.title != data["title"]
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
        return False

    def has_overlay(self):
        return (
            self.current_entry and self.current_entry["flags"][Flags.HAS_OVERLAY.value]
        )

    def get_overlay_data(self):
        return self.current_entry["overlay"]

    def close(self):
        self.stop_event.set()
        if self.forwarder:
            self.forwarder.join()
