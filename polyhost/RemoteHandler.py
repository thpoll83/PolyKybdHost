import logging
import re
import socket
import threading
import time
import ipaddress


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
    
    while len(connections)>0:
        try:
            conn, (addr, _) = sock.accept()
            data = conn.recv(BUFFER_SIZE)
            data = data.decode("utf-8")
            entries = [0,"",""] if not data else data.split(";")
            if len(entries)>2:
                lookup = {}
                lookup["handle"] = entries[0]
                lookup["name"] = entries[1]
                lookup["title"] = entries[2]
                connections[addr] = lookup
        except socket.timeout:
            time.sleep(3)
    conn.close()
    sock.close()


class RemoteHandler():
    def __init__(self, mapping):
        self.log = logging.getLogger('PolyHost')
        self.forwarder = None
        
        self.handle = None
        self.title = None
        self.currentRemoteMappingEntry = None
        
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
                    if not addr in self.connections.keys():
                        self.connections[remote] = ""
                        self.log.info(f"IP address {remote} used with {addr}")
                        resolved_remote = True
                        entry["ip"] = addr
                        
                except ValueError:
                    try:
                        addr = str(socket.gethostbyname(remote))
                        if not addr in self.connections.keys():
                            self.connections[remote] = ""
                            self.log.info(f"Resolved {remote} to {addr}")
                            resolved_remote = True
                            entry["ip"] = addr
                    except:
                        self.log.warning(f"Could not resolve {remote}")
                except:
                    self.log.warning(f"Could not resolve {remote}")    
        if resolved_remote:
            if not self.forwarder:
                self.forwarder = threading.Thread(target = receiveFromForwarder, name = f"PolyKybd Remote Handler", args = (self.log, self.connections))
                self.forwarder.start()
        else:
            self.forwarder = None
    
    def tryToMatchWindow(self, name, entry):   
        overlayKey = "overlay" in entry.keys()
        appKey = "app" in entry.keys()
        titleKey = "title" in entry.keys()
        
        match = overlayKey and appKey or titleKey
        try:
            if self.name and match and appKey:
                match = match and re.search(entry["app"], self.name)
                if match:
                    if "titles" in entry.keys():
                        for subentryName, subentry in entry["titles"].items():
                            return self.tryToMatchWindow(subentryName, subentry)
            if self.title and match and titleKey:
                match = match and re.search(entry["title"], self.title)
        except re.error as e:
            self.log.warning(f"Cannot match entry '{name}': {entry}, because '{e.msg}'@{e.pos} with '{e.pattern}'")
            return False

        if match:
            self.currentMappingEntry = entry
            self.lastMappingEntry = entry
            return True
        return False
      
            
    def remoteChanged(self, remoteEntry):
        data = self.connections[remoteEntry["remote"]]
        
        if data and len(data)>2 and self.handle != data["handle"] and self.title != data["title"]:
            self.handle = data["handle"]
            self.title = data["title"]
            self.name = data["name"]
            self.log.info(f"Remote App Changed: \"{self.name}\", Title: \"{self.title}\"  Handle: {self.handle}")
                
            found = False
            for entryName, entry in self.mapping.items():
                found = self.tryToMatchWindow(entryName, entry)
                if found:
                    self.currentRemoteMappingEntry = entry
                    break
            if self.currentRemoteMappingEntry and not found:
                self.currentRemoteMappingEntry = None
            return True
        return False
    
    def hasOverlay(self):
        return self.currentRemoteMappingEntry and "overlay" in self.currentRemoteMappingEntry
    
    def getOverlayData(self):
        return self.currentRemoteMappingEntry["overlay"]
          
    def close(self):
        self.connections = {}
        if self.forwarder:
            self.forwarder.join()
