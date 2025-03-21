import logging
from pathlib import Path
import re
import socket
import threading
import time
import ipaddress

from handler.HandlerCommon import Flags

TCP_PORT = 50162
BUFFER_SIZE = 1024


# Needs to be started as thread
def receiveFromForwarder(log, connections):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.bind(("", TCP_PORT))
    except socket.error as message:
        log.warning(f"Failed to bind socket: {message}")
        sock.close()
        return

    sock.listen(5)
    sock.settimeout(10.0)

    while len(connections) > 0:
        try:
            conn, (addr, _) = sock.accept()
            data = conn.recv(BUFFER_SIZE)
            data = data.decode("utf-8")
            entries = [0, "", ""] if not data else data.split(";")
            if len(entries) > 2:
                lookup = {}
                lookup["handle"] = entries[0]
                lookup["name"] = entries[1]
                lookup["title"] = entries[2]
                connections[addr] = lookup
        except socket.timeout:
            time.sleep(3)
    conn.close()
    sock.close()


class RemoteHandler:
    def __init__(self, mapping):
        self.log = logging.getLogger("PolyHost")
        self.forwarder = None

        self.handle = None
        self.title = None
        self.name = None
        self.currentMappingEntry = None

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
                        self.log.info(f"IP address {remote} used with {addr}")
                        resolved_remote = True
                        entry["ip"] = addr

                except ValueError:
                    try:
                        addr = str(socket.gethostbyname(remote))
                        if addr not in self.connections.keys():
                            self.connections[addr] = ""
                            self.log.info(f"Resolved {remote} to {addr}")
                            resolved_remote = True
                            entry["ip"] = addr
                    except:
                        self.log.warning(f"Could not resolve {remote}")
                except:
                    self.log.warning(f"Could not resolve {remote}")
        if resolved_remote:
            if not self.forwarder:
                self.forwarder = threading.Thread(
                    target=receiveFromForwarder,
                    name="PolyKybd Remote Handler",
                    args=(self.log, self.connections),
                )
                self.forwarder.start()
        else:
            self.forwarder = None

    def tryToMatchWindow(self, name, entry):
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
                titleElements = (
                    self.title.split() if has_starts_with or has_ends_with else []
                )
                if len(titleElements) > 0:
                    if (
                        has_starts_with
                        and titleElements[0] in entry["titles-startswith"].keys()
                    ):
                        found, cmd = self.tryToMatchWindow(
                            name, entry["titles-startswith"][titleElements[0]]
                        )
                        if found:
                            return True
                    if (
                        has_ends_with
                        and titleElements[-1] in entry["titles-endswith"].keys()
                    ):
                        found, cmd = self.tryToMatchWindow(
                            name, entry["titles-endswith"][titleElements[-1]]
                        )
                        if found:
                            return True
                    if has_contains:
                        contains = entry["titles-contains"]
                        for elem in titleElements:
                            if elem in contains.keys():
                                found, cmd = self.tryToMatchWindow(name, contains[elem])
                                if found:
                                    return True
                if self.title and has_title:
                    match = match and re.search(entry["title"], self.title)
        except re.error as e:
            self.log.warning(
                f"Cannot match entry '{name}': {entry}, because '{e.msg}'@{e.pos} with '{e.pattern}'"
            )
            return False

        if match:
            self.currentMappingEntry = entry
            self.lastMappingEntry = entry
            return True
        return False

    def remoteChanged(self, remote_entry: dict):
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
                f"Remote App Changed: \"{data['name']}\", Title: \"{self.title}\"  Handle: {self.handle}"
            )

            found = False
            if self.name in self.mapping.keys():
                found = self.tryToMatchWindow(self.name, self.mapping[self.name])
            if self.currentMappingEntry and not found:
                self.currentMappingEntry = None
            return True
        return False

    def hasOverlay(self):
        return (
            self.currentMappingEntry
            and self.currentMappingEntry["flags"][Flags.HAS_OVERLAY.value]
        )

    def getOverlayData(self):
        return self.currentMappingEntry["overlay"]

    def close(self):
        self.connections = {}
        if self.forwarder:
            self.forwarder.join()
