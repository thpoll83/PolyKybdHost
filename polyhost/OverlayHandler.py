

from enum import Enum
import logging
import os
import platform
import re

import RemoteHandler

IS_PLASMA = os.getenv('XDG_CURRENT_DESKTOP')=="KDE"

if not IS_PLASMA:
    import pywinctl as pwc
    

class OverlayCommand(Enum):
    NONE = 0
    OFF_ON = 1
    DISABLE = 2
    ENABLE = 3
    
class OverlayHandler():
    def __init__(self, mapping):
        self.log = logging.getLogger('PolyHost')

        self.setWin()
        self.currentMappingEntry = None
        self.lastMappingEntry = None
        self.mapping = mapping
        self.remote_handler = RemoteHandler.RemoteHandler(mapping)
    
    def setWin(self, win = None, title = None, handle = None):
        self.win = win
        self.title = title
        self.handle = handle
        
    def tryToMatchWindow(self, name, entry):
        appName = self.win.getAppName()
    
        overlayOrRemote = "overlay" in entry.keys() or "remote" in entry.keys()
        appKey = "app" in entry.keys()
        titleKey = "title" in entry.keys()
        
        match = overlayOrRemote and appKey or titleKey
        try:
            if appName and match and appKey:
                match = match and re.search(entry["app"], appName)
                if match:
                    if "titles" in entry.keys():
                        for subentryName, subentry in entry["titles"].items():
                            found, cmd = self.tryToMatchWindow(subentryName, subentry)
                            if found:
                                return True, cmd
            if self.title and match and titleKey:
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

                try:
                    self.log_win()
                    if self.mapping:
                        found = False
                        for entryName, entry in self.mapping.items():
                            found, cmd = self.tryToMatchWindow(entryName, entry)
                            if found:
                                return self.getOverlayData(), cmd
                        if self.currentMappingEntry and not found:
                            self.currentMappingEntry = None
                            return None, OverlayCommand.DISABLE
                except Exception as e:
                    self.log.warning(f"Failed retrieving active window: {e}")
            elif self.isRemoteMappingEntry() and self.remote_handler.remoteChanged(self.currentMappingEntry):
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
                
        return None, OverlayCommand.NONE

    def isRemoteMappingEntry(self):
        return self.currentMappingEntry and "remote" in self.currentMappingEntry.keys()
    
    def getOverlayData(self):
        if self.currentMappingEntry and "overlay" in self.currentMappingEntry:
            return self.currentMappingEntry["overlay"]
        elif self.remote_handler.hasOverlay():
            return self.remote_handler.getOverlayData()
        return None
    
    def close(self):
        self.remote_handler.close()