import logging
import os
from pathlib import Path
import platform
import re

import handler.RemoteHandler as RemoteHandler
from handler.HandlerCommon import OverlayCommand, Flags

IS_PLASMA = os.getenv('XDG_CURRENT_DESKTOP')=="KDE"

if not IS_PLASMA:
    import pywinctl as pwc
    
class OverlayHandler():
    def __init__(self, mapping):
        self.log = logging.getLogger('PolyHost')

        self.setWin()
        self.currentMappingEntry = None
        self.lastMappingEntry = None
        self.mapping = mapping
        self.annotate(self.mapping.items())
        self.remote_handler = RemoteHandler.RemoteHandler(self.mapping)
    
    def annotate(self, entries):
        for _, entry in entries:
            has_overlay = "overlay" in entry.keys()
            has_remote = "remote" in entry.keys()
            has_title = "title" in entry.keys()
            has_starts_with = "titles-startswith" in entry.keys()
            has_ends_with = "titles-endswith" in entry.keys()
            has_contains = "titles-contains" in entry.keys()
            
            entry["flags"] = [has_overlay, has_remote, has_title, has_starts_with, has_ends_with, has_contains] 
            if has_starts_with:
                self.annotate(entry["titles-startswith"].items())
            if has_ends_with:
                self.annotate(entry["titles-endswith"].items())
            if has_contains:
                self.annotate(entry["titles-contains"].items())
    
    def setWin(self, win = None, title = None, handle = None):
        self.win = win
        self.title = title
        self.handle = handle
        
    def tryToMatchWindow(self, name, entry):
        has_overlay, has_remote, has_title, has_starts_with, has_ends_with, has_contains = entry["flags"]
        match = (has_overlay or has_remote)
        try:
            if match:
                titleElements = self.title.split() if has_starts_with or has_ends_with else []
                if len(titleElements)>0:
                    if has_starts_with and titleElements[0] in entry["titles-startswith"].keys():
                        found, cmd = self.tryToMatchWindow(name, entry["titles-startswith"][titleElements[0]])
                        if found:
                            return True, cmd
                    if has_ends_with and titleElements[-1] in entry["titles-endswith"].keys():
                        found, cmd = self.tryToMatchWindow(name, entry["titles-endswith"][titleElements[-1]])
                        if found:
                            return True, cmd
                    if has_contains:
                        contains = entry["titles-contains"]
                        for elem in titleElements:
                            if elem in contains.keys():
                                found, cmd = self.tryToMatchWindow(name, contains[elem])
                                if found:
                                    return True, cmd
                if self.title and has_title:
                    match = match and re.search(entry["title"], self.title)
        except re.error as e:
            self.log.warning(f"Cannot match entry '{name}': {entry}, because '{e.msg}'@{e.pos} with '{e.pattern}'")
            return False, OverlayCommand.NONE

        if match:
            if self.lastMappingEntry == entry:
                self.currentMappingEntry = entry
                return True, OverlayCommand.ENABLE
            self.currentMappingEntry = entry
            self.lastMappingEntry = entry
            return True, OverlayCommand.OFF_ON
        return False, OverlayCommand.NONE
    
    def log_win(self):
        name = self.win.getAppName()
        if platform.system() == 'Windows':
            self.log.info(
                f"Active App Changed: \"{name}\", Title: \"{self.win.title.encode('utf-8')}\"  Handle: {self.win.getHandle()}")
        else:
            self.log.info(
                f"Active App Changed: \"{name}\", Title: \"{self.win.title.encode('utf-8')}\"  Handle: {self.win.getHandle()} Parent: {self.win.getParent()}")
            
    def handleActiveWindow(self):
        win = pwc.getActiveWindow()
        if win:
            local_win_changed = self.win is None or win.getHandle() != self.handle or win.title != self.title
            
            if local_win_changed:
                #remember active window
                self.setWin(win, win.title, win.getHandle())
                if win.title == "PolyHost":
                    return None, OverlayCommand.NONE
                try:
                    self.log_win()
                    if self.mapping:
                        found = False
                        appName = self.win.getAppName().split(".")[0].lower()
                        if appName in self.mapping.keys():
                            found, cmd = self.tryToMatchWindow(appName, self.mapping[appName])
                            if found:
                                self.log.info(f"Changing to {appName}")
                                return self.getOverlayData(), cmd
                        if self.currentMappingEntry and not found:
                            self.currentMappingEntry = None
                            self.log.info(f"Nothing active")
                            return None, OverlayCommand.DISABLE
                except Exception as e:
                    self.log.warning(f"Failed retrieving active window: {e}")
                self.log.info(f"No match")
                return None, OverlayCommand.DISABLE
            elif self.isRemoteMappingEntry() and self.remote_handler.remoteChanged(self.currentMappingEntry):
                self.log.info(f"Remote")
                if self.remote_handler.hasOverlay():
                    return self.getOverlayData(), OverlayCommand.OFF_ON
                else:
                    return None, OverlayCommand.DISABLE
                    
        else:
            if self.win:
                self.log.info("No active window")
                self.setWin()
                if self.currentMappingEntry:
                    self.currentMappingEntry = None
                    return None, OverlayCommand.DISABLE
        
       # self.log.info(f"Nothing at all")
        return None, OverlayCommand.NONE

    def isRemoteMappingEntry(self):
        return self.currentMappingEntry and self.currentMappingEntry["flags"][Flags.HAS_REMOTE.value] #0 for remote
    
    def getOverlayData(self):
        if self.currentMappingEntry and self.currentMappingEntry["flags"][Flags.HAS_OVERLAY.value]: #0 for overlay
            return self.currentMappingEntry["overlay"]
        elif self.remote_handler.hasOverlay():
            return self.remote_handler.getOverlayData()
        return None
    
    def close(self):
        self.remote_handler.close()