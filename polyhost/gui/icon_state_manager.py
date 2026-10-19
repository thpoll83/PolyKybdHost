

import os
import time
from polyhost.gui.get_icon import get_icon


class IconStateManager:
    """ Set the tray icon as needed """

    def __init__(self, parent, is_connected, tooltip, prefix="p"):
        """`prefix` picks which brand mark the tray wears: "p" for the tray app,
        "f" for the forwarder, whose unlit keys spell an F instead of a P (see
        tools/gen_brand_icons.py). Both run as trays on the same desktop when
        somebody forwards to their own machine, so they must not look alike.

        The busy and warning states are NOT prefixed: they draw the ring only,
        with every inner key cleared, so there is no letter left in them to
        differ — a second, byte-identical copy under "f" would be exactly the
        kind of mirrored file this repo keeps getting caught by."""
        self.parent = parent
        parent.tray.setToolTip(tooltip)

        self.connected = get_icon(f"{prefix}color.png")
        # Connected over raw HID only (no bulk pipe): the same mark in violet.
        # Only the tray app has a keyboard, so only the P mark has the variant.
        self.connected_hid = get_icon("phid.png") if prefix == "p" else self.connected
        self._hid_only = False
        self.disconnected = get_icon(f"{prefix}gray.png")
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

    def set_base_tooltip(self, tooltip):
        """Replace the tray's RESTING tooltip — what it shows whenever no
        warning is up.

        This class owns the tray tooltip: it sets one at construction, swaps in
        the warning text in `set_warning`, and puts `self.tooltip` back when the
        warning expires. A caller that writes `tray.setToolTip` directly is
        therefore correct only until the next warning, whose expiry silently
        restores the STARTUP text over it — so anything with a lifetime (the
        pending-update marker, a flash percentage) has to come through here.
        """
        self.tooltip = tooltip
        if self.warning_timeout == 0 and not self.warning_msg:
            self.parent.tray.setToolTip(tooltip)

    def set_connected(self):
        """ Set icon for connected state """
        if not self._is_connected:
            self._is_connected = True
            self.dirty_flag = True
        self.update()

    def set_transport(self, transport):
        """Colour the connected mark by the channel in use: violet for "hid"
        (raw HID only), the blue sweep for "pipe". None keeps the blue, so a
        core that predates the transport field changes nothing."""
        hid_only = transport == "hid"
        if hid_only != self._hid_only:
            self._hid_only = hid_only
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
                    icon = self.connected_hid if self._hid_only else self.connected
                    self.parent.setWindowIcon(icon)
                    self.parent.tray.setIcon(icon)
                else:
                    self.parent.setWindowIcon(self.disconnected)
                    self.parent.tray.setIcon(self.disconnected)
        self.updated = now
