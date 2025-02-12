import yaml
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QFileDialog

from PolyKybd import MaskFlag


class CommandsSubMenu():
    def __init__(self, parent, keeb):
        self.parent = parent
        self.keeb = keeb

    def buildMenu(self, parentMenu):
        cmdMenu = parentMenu.addMenu(QIcon("polyhost/icons/settings.svg"), "All PolyKybd Commands")

        action = QAction(QIcon("polyhost/icons/toggle_off.svg"), "Stop Idle", parent=self.parent)
        action.setData(False)
        action.triggered.connect(self.change_idle)
        cmdMenu.addAction(action)

        action = QAction(QIcon("polyhost/icons/toggle_on.svg"), "Start Idle", parent=self.parent)
        action.setData(True)
        action.triggered.connect(self.change_idle)
        cmdMenu.addAction(action)

        action = QAction(QIcon("polyhost/icons/delete.svg"), "Reset Overlays Buffers", parent=self.parent)
        action.triggered.connect(self.reset_overlays)
        cmdMenu.addAction(action)

        action = QAction(QIcon("polyhost/icons/toggle_on.svg"), "Enable Shortcut Overlays", parent=self.parent)
        action.triggered.connect(self.enable_overlays)
        cmdMenu.addAction(action)

        action = QAction(QIcon("polyhost/icons/toggle_off.svg"), "Disable Shortcut Overlays", parent=self.parent)
        action.triggered.connect(self.disable_overlays)
        cmdMenu.addAction(action)

        action = QAction("Load command file...", parent=self.parent)
        action.triggered.connect(self.load_commands)
        cmdMenu.addAction(action)

        setOverlayMaskMenu = cmdMenu.addMenu("Set Overlay Masking")
        action = QAction("Left Top", parent=self.parent)
        action.setData(MaskFlag.LEFT_TOP)
        action.triggered.connect(self.set_mask)
        setOverlayMaskMenu.addAction(action)

        action = QAction("Right Top", parent=self.parent)
        action.setData(MaskFlag.RIGHT_TOP)
        action.triggered.connect(self.set_mask)
        setOverlayMaskMenu.addAction(action)

        action = QAction("Left Bottom", parent=self.parent)
        action.setData(MaskFlag.LEFT_BOTTOM)
        action.triggered.connect(self.set_mask)
        setOverlayMaskMenu.addAction(action)

        action = QAction("Right Bottom", parent=self.parent)
        action.setData(MaskFlag.RIGHT_BOTTOM)
        action.triggered.connect(self.set_mask)
        setOverlayMaskMenu.addAction(action)

        setOverlayMaskMenu = cmdMenu.addMenu("Clear Overlay Masking")
        action = QAction("Left Top", parent=self.parent)
        action.setData(MaskFlag.LEFT_TOP)
        action.triggered.connect(self.clear_mask)
        setOverlayMaskMenu.addAction(action)

        action = QAction("Right Top", parent=self.parent)
        action.setData(MaskFlag.RIGHT_TOP)
        action.triggered.connect(self.clear_mask)
        setOverlayMaskMenu.addAction(action)

        action = QAction("Left Bottom", parent=self.parent)
        action.setData(MaskFlag.LEFT_BOTTOM)
        action.triggered.connect(self.clear_mask)
        setOverlayMaskMenu.addAction(action)

        action = QAction("Right Bottom", parent=self.parent)
        action.setData(MaskFlag.RIGHT_BOTTOM)
        action.triggered.connect(self.clear_mask)
        setOverlayMaskMenu.addAction(action)

        briMenu = cmdMenu.addMenu("Change Brightness")
        action = QAction(QIcon("polyhost/icons/backlight_high_off.svg"), "Off", parent=self.parent)
        action.setData(0)
        action.triggered.connect(self.set_brightness)
        briMenu.addAction(action)

        action = QAction(QIcon("polyhost/icons/backlight_low.svg"), "1%", parent=self.parent)
        action.setData(2)
        action.triggered.connect(self.set_brightness)
        briMenu.addAction(action)

        action = QAction(QIcon("polyhost/icons/backlight_high.svg"), "50%", parent=self.parent)
        action.setData(25)
        action.triggered.connect(self.set_brightness)
        briMenu.addAction(action)

        action = QAction(QIcon("polyhost/icons/backlight_high.svg"), "100%", parent=self.parent)
        action.setData(50)
        action.triggered.connect(self.set_brightness)
        briMenu.addAction(action)

    def reset_overlays(self):
        result, msg = self.keeb.reset_overlays()
        self.parent.show_mb("Error", f"Failed clearing overlays: {msg}", result)

    def enable_overlays(self):
        result, msg = self.keeb.enable_overlays()
        self.parent.show_mb("Error", f"Failed enabling overlays: {msg}", result)

    def disable_overlays(self):
        result, msg = self.keeb.disable_overlays()
        self.parent.show_mb("Error", f"Failed disabling overlays: {msg}", result)

    def set_brightness(self):
        result, msg = self.keeb.set_brightness(self.parent.sender().data())
        self.parent.show_mb("Error", f"Failed disabling overlays: {msg}", result)

    def change_idle(self):
        result, msg = self.keeb.set_idle(self.parent.sender().data())
        self.parent.show_mb("Error", f"Failed to change idle mode: {msg}", result)

    def set_mask(self):
        result, msg = self.keeb.set_overlay_masking(self.parent.sender().data(), True)
        self.parent.show_mb("Error", f"Failed to change idle mode: {msg}", result)

    def clear_mask(self):
        result, msg = self.keeb.set_overlay_masking(self.parent.sender().data(), False)
        self.parent.show_mb("Error", f"Failed to change idle mode: {msg}", result)

    def load_commands(self):
        fname = QFileDialog.getOpenFileName(None, 'Open file', '', "PolyKybd commands (*.poly.cmd)")
        if len(fname) > 0:
            with open(fname[0], 'r') as f:
                self.keeb.execute_commands(f.readlines())
        else:
            self.log.info("No file selected. Operation canceled.")