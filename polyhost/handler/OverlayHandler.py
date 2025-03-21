import logging
import os
import platform
import re

import handler.RemoteHandler as RemoteHandler
from handler.HandlerCommon import OverlayCommand, Flags

IS_PLASMA = os.getenv("XDG_CURRENT_DESKTOP") == "KDE"

if not IS_PLASMA:
    import pywinctl as pwc

TITLE_SW = "titles-startswith"
TITLE_EW = "titles-endswith"
TITLE_CNTS = "titles-contains"
TITLE = "title"
INDEX = "index"
FLAGS = "flags"
OVERLAY = "overlay"
REMOTE = "remote"

class OverlayHandler:
    def __init__(self, mapping):
        self.log = logging.getLogger("PolyHost")
        self.last_update_msec = 0
        self.prev_win = None
        self.win = None
        self.set_win()
        self.currentMappingEntry = None
        self.lastMappingEntry = None
        self.mapping = mapping
        self.annotate(self.mapping.items())
        self.remote_handler = RemoteHandler.RemoteHandler(self.mapping)

    def annotate(self, entries):
        for _, entry in entries:
            has_overlay = OVERLAY in entry.keys()
            has_remote = REMOTE in entry.keys()
            has_title = TITLE in entry.keys()
            has_starts_with = TITLE_SW in entry.keys() and entry[TITLE_SW]
            has_ends_with = TITLE_EW in entry.keys() and entry[TITLE_EW]
            has_contains = TITLE_CNTS in entry.keys() and entry[TITLE_CNTS]

            entry[FLAGS] = [
                has_overlay,
                has_remote,
                has_title,
                has_starts_with,
                has_ends_with,
                has_contains,
            ]
            if has_starts_with:
                self.annotate(entry[TITLE_SW].items())
            if has_ends_with:
                self.annotate(entry[TITLE_EW].items())
            if has_contains:
                self.annotate(entry[TITLE_CNTS].items())

    def set_win(self, win=None, title=None, handle=None):
        """Set the active window"""
        self.win = win
        self.title = title
        self.handle = handle

    def tryToMatchWindow(self, name, entry):
        (
            has_overlay,
            has_remote,
            has_title,
            has_starts_with,
            has_ends_with,
            has_contains,
        ) = entry[FLAGS]
        match = has_overlay or has_remote
        try:
            if match:
                elem = self.title.split() if has_starts_with or has_ends_with else []
                elem_count = len(elem)
                if elem_count > 0:
                    if (
                        has_starts_with
                        and elem[0] in entry[TITLE_SW].keys()
                    ):
                        found, cmd = self.tryToMatchWindow(
                            name, entry[TITLE_SW][elem[0]]
                        )
                        if found:
                            return True, cmd
                    if (
                        has_ends_with
                        and elem[-1] in entry[TITLE_EW].keys()
                    ):
                        found, cmd = self.tryToMatchWindow(
                            name, entry[TITLE_EW][elem[-1]]
                        )
                        if found:
                            return True, cmd
                    if has_contains:
                        contains = entry[TITLE_CNTS]
                        for elem in elem:
                            if elem in contains.keys():
                                found, cmd = self.tryToMatchWindow(name, contains[elem])
                                if found:
                                    return True, cmd
                if self.title and has_title:
                    match = match and re.search(entry[TITLE], self.title)
        except re.error as e:
            self.log.warning(
                f"Cannot match entry '{name}': {entry}, because '{e.msg}'@{e.pos} with '{e.pattern}'"
            )
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
        if platform.system() == "Windows":
            self.log.info(
                f"Active App Changed: \"{name}\", Title: \"{self.win.title.encode('utf-8')}\"  Handle: {self.win.getHandle()}"
            )
        else:
            self.log.info(
                f"Active App Changed: \"{name}\", Title: \"{self.win.title.encode('utf-8')}\"  Handle: {self.win.getHandle()} Parent: {self.win.getParent()}"
            )

    def handleActiveWindow(self, update_cycle_time_msec, accept_time_msec):
        self.last_update_msec = self.last_update_msec + update_cycle_time_msec
        win = pwc.getActiveWindow()
        if win:
            if self.prev_win != win:
                self.prev_win = win
                self.last_update_msec = 0
            if self.last_update_msec > accept_time_msec:
                self.last_update_msec = accept_time_msec  * 2 #just to limit that
                local_win_changed = (
                    self.win is None
                    or win.getHandle() != self.handle
                    or win.title != self.title
                )

                if local_win_changed:
                    # remember active window
                    self.set_win(win, win.title, win.getHandle())
                    if win.title == "PolyHost":
                        return None, OverlayCommand.NONE
                    try:
                        self.log_win()
                        if self.mapping:
                            found = False
                            appName = self.win.getAppName().split(".")[0].lower()
                            if appName in self.mapping.keys():
                                found, cmd = self.tryToMatchWindow(
                                    appName, self.mapping[appName]
                                )
                                if found:
                                    self.log.info(f"Changing to {appName}")
                                    return self.getOverlayData(), cmd
                            if self.currentMappingEntry and not found:
                                self.currentMappingEntry = None
                                self.log.info("Nothing active")
                                return None, OverlayCommand.DISABLE
                    except Exception as e:
                        self.log.warning(f"Failed retrieving active window: {e}")
                        self.log.warning("".join(traceback.format_exception(e)))
                    self.log.info("No match")
                    return None, OverlayCommand.DISABLE
                elif self.isRemoteMappingEntry() and self.remote_handler.remoteChanged(
                    self.currentMappingEntry
                ):
                    self.log.info("Remote")
                    if self.remote_handler.hasOverlay():
                        return self.getOverlayData(), OverlayCommand.OFF_ON
                    else:
                        return None, OverlayCommand.DISABLE
        else:
            if self.win:
                self.log.info("No active window")
                self.set_win()
                if self.currentMappingEntry:
                    self.currentMappingEntry = None
                    return None, OverlayCommand.DISABLE

        # self.log.info(f"Nothing at all")
        return None, OverlayCommand.NONE

    def isRemoteMappingEntry(self):
        return (
            self.currentMappingEntry
            and self.currentMappingEntry[FLAGS][Flags.HAS_REMOTE.value]
        )  # 0 for remote

    def getOverlayData(self):
        if (
            self.currentMappingEntry
            and self.currentMappingEntry[FLAGS][Flags.HAS_OVERLAY.value]
        ):  # 0 for overlay
            return self.currentMappingEntry[OVERLAY]
        elif self.remote_handler.hasOverlay():
            return self.remote_handler.getOverlayData()
        return None

    def close(self):
        self.remote_handler.close()
