import logging
import re
import socket
import threading
import time
import ipaddress

from polyhost.handler.common import Flags

TCP_PORT = 50162
BUFFER_SIZE = 1024


# Needs to be started as thread
def receive_from_forwarder(log, connections):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.bind(("", TCP_PORT))
    except socket.error as message:
        log.warning(f"Failed to bind socket: {message}")
        sock.close()
        return

    sock.listen(5)
    sock.settimeout(10.0)

    conn = None
    while len(connections) > 0:
        try:
            conn, (addr, _) = sock.accept()
            data = conn.recv(BUFFER_SIZE)
            data = data.decode("utf-8")
            entries = [0, "", ""] if not data else data.split(";")
            if len(entries) > 2:
                connections[addr] = {
                    "handle": entries[0],
                    "name": entries[1],
                    "title": entries[2],
                }
        except socket.timeout:
            time.sleep(3)
    if conn:
        conn.close()
    sock.close()


class RemoteHandler:
    def __init__(self, mapping):
        self.log = logging.getLogger("PolyHost")
        self.forwarder = None

        self.handle = None
        self.title = None
        self.name = None
        self.current_entry = None
        self.last_entry = None
        self.connections = {}
        self.mapping = mapping
        self.listen_to_forwarder()

    def listen_to_forwarder(self):
        resolved_remote = False
        for _, entry in self.mapping.items():
            if "remote" in entry.keys():
                remote = entry["remote"]
                try:
                    addr = str(ipaddress.ip_address(remote))
                    if addr not in self.connections.keys():
                        self.connections[addr] = ""
                        self.log.info("IP address '%s' used with %s", remote, addr)
                        resolved_remote = True
                        entry["ip"] = addr

                except ValueError:
                    try:
                        addr = str(socket.gethostbyname(remote))
                        if addr not in self.connections.keys():
                            self.connections[addr] = ""
                            self.log.info("Resolved '%s' to %s", remote, addr)
                            resolved_remote = True
                            entry["ip"] = addr
                    except Exception as e:
                        self.log.warning(
                            "Could not resolve hostname '%s': %s", remote, e
                        )
                except Exception as e:
                    self.log.warning("Could not resolve '%s': %s", remote, e)
        if resolved_remote:
            if not self.forwarder:
                self.forwarder = threading.Thread(
                    target=receive_from_forwarder,
                    name="PolyKybd Remote Handler",
                    args=(self.log, self.connections),
                )
                self.forwarder.start()
        else:
            self.forwarder = None

    def try_to_match_window(self, name, entry):
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
                        found, cmd = self.try_to_match_window(
                            name, entry["titles-startswith"][title_elements[0]]
                        )
                        if found:
                            return True
                    if (
                        has_ends_with
                        and title_elements[-1] in entry["titles-endswith"].keys()
                    ):
                        found, cmd = self.try_to_match_window(
                            name, entry["titles-endswith"][title_elements[-1]]
                        )
                        if found:
                            return True
                    if has_contains:
                        contains = entry["titles-contains"]
                        for elem in title_elements:
                            if elem in contains.keys():
                                found, cmd = self.try_to_match_window(
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
        if "ip" not in remote_entry.keys():
            self.listen_to_forwarder()
            return False
        if not remote_entry["ip"] in self.connections:
            return False

        data = self.connections[remote_entry["ip"]]

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
                found = self.try_to_match_window(self.name, self.mapping[self.name])
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
        self.connections = {}
        if self.forwarder:
            self.forwarder.join()
