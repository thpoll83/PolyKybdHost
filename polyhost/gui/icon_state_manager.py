

import os
import time
from polyhost.gui.get_icon import get_icon


class IconStateManager:
    """ Set the tray icon as needed """

    def __init__(self, parent, is_connected, tooltip):
        self.parent = parent
        parent.tray.setToolTip(tooltip)
        
        self.connected = get_icon("pcolor.png")
        self.disconnected = get_icon("pgray.png")
        self.wait = get_icon("pthink.png")
        self.warn = get_icon("pwarn.png")
        self._is_connected = is_connected
        self._is_thinking = False
        self.warning_timeout = 0
        self.warning_msg = ""
        self.updated = round(time.time() * 1000)
        self.tooltip = tooltip
        self.dirty_flag = True
        self.update()

    def set_connected(self):
        """ Set icon for connected state """
        if not self._is_connected:
            self._is_connected = True
            self.dirty_flag = True
        self.update()

    def set_disconnected(self):
        """ Set icon for disconnected state """
        if self._is_connected:
            self._is_connected = False
            self.dirty_flag = True
        self.update()

    def set_thinking(self):
        """ Set hour glass icon on top of the actual connection state """
        if not self._is_thinking:
            self._is_thinking = True
            self.dirty_flag = True
        self.update()

    def set_idle(self):
        """ Clear hour glass icon to the actual connection state """
        if self._is_thinking:
            self._is_thinking = False
            self.dirty_flag = True
        self.update()

    def set_warning(self, msg, timeout_msec=5000):
        """ Clear hour glass icon to the actual connection state """
        self.warning_timeout = timeout_msec
        if self.warning_msg=="":
            self.warning_msg = msg
        else:
            self.warning_msg += os.linesep + msg
        self.parent.tray.setToolTip(self.warning_msg)
        self.dirty_flag = True
        self.update()

    def update(self):
        """ Set the icon to the current state """
        now = round(time.time() * 1000)
        if self._is_thinking:
            if self.dirty_flag:
                self.parent.setWindowIcon(self.wait)
                self.parent.tray.setIcon(self.wait)
        else:
            if self.warning_timeout>0:
                self.parent.setWindowIcon(self.warn)
                self.parent.tray.setIcon(self.warn)
                self.warning_timeout -= (now - self.updated)
                if self.warning_timeout==0:
                    self.warning_timeout = -1
            elif self.warning_timeout<0:
                self.warning_timeout = 0
                self.warning_msg = ""
                self.parent.tray.setToolTip(self.tooltip)
                self.dirty_flag = True
            elif self.dirty_flag:
                if self._is_connected:
                    self.parent.setWindowIcon(self.connected)
                    self.parent.tray.setIcon(self.connected)
                else:
                    self.parent.setWindowIcon(self.disconnected)
                    self.parent.tray.setIcon(self.disconnected)
        self.updated = now
