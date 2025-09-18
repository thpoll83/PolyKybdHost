

from polyhost.gui.get_icon import get_icon


class IconStateManager():
    """ Set the tray icon as needed """

    def __init__(self, parent, is_connected):
        self.parent = parent
        self.connected = get_icon("pcolor.png")
        self.disconnected = get_icon("pgray.png")
        self.wait = get_icon("pthink.png")
        self._is_connected = is_connected
        self._is_thinking = False

    def set_connected(self):
        """ Set icon for connected state """
        if not self._is_connected:
            self._is_connected = True
            self.update()

    def set_disconnected(self):
        """ Set icon for disconnected state """
        if self._is_connected:
            self._is_connected = False
            self.update()

    def set_thinking(self):
        """ Set hour glass icon on top of the actual connection state """
        if not self._is_thinking:
            self._is_thinking = True
            self.update()

    def set_idle(self):
        """ Clear hour glass icon to the actual connection state """
        if self._is_thinking:
            self._is_thinking = False
            self.update()

    def update(self):
        """ Set the icon to the current state """
        if self._is_thinking:
            self.parent.setWindowIcon(self.wait)
            self.parent.tray.setIcon(self.wait)
        else:
            if self._is_connected:
                self.parent.setWindowIcon(self.connected)
                self.parent.tray.setIcon(self.connected)
            else:
                self.parent.setWindowIcon(self.disconnected)
                self.parent.tray.setIcon(self.disconnected)
