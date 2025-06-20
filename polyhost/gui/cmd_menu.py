import logging

from PyQt5.QtWidgets import QAction, QFileDialog

from polyhost.device.poly_kybd import MaskFlag
from polyhost.gui.get_icon import get_icon


class CommandsSubMenu:
    def __init__(self, parent, keeb):
        self.parent = parent
        self.keeb = keeb
        self.log = logging.getLogger('PolyForwarder')

    def build_menu(self, parent_menu):
        cmd_menu = parent_menu.addMenu(get_icon("settings.svg"), "All PolyKybd Commands")

        action = QAction(get_icon("toggle_off.svg"), "Stop Idle", parent=self.parent)
        action.setData(False)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.change_idle)
        cmd_menu.addAction(action)

        action = QAction(get_icon("toggle_on.svg"), "Start Idle", parent=self.parent)
        action.setData(True)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.change_idle)
        cmd_menu.addAction(action)

        action = QAction(get_icon("delete.svg"), "Reset Overlays Buffers", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.reset_overlays)
        cmd_menu.addAction(action)

        action = QAction(get_icon("toggle_on.svg"), "Enable Shortcut Overlays", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.enable_overlays)
        cmd_menu.addAction(action)

        action = QAction(get_icon("toggle_off.svg"), "Disable Shortcut Overlays", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.disable_overlays)
        cmd_menu.addAction(action)

        action = QAction("Load command file...", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.load_commands)
        cmd_menu.addAction(action)

        # set_overlay_mask_menu = cmd_menu.addMenu("Set Overlay Masking")
        # action = QAction("Left Top", parent=self.parent)
        # action.setData(MaskFlag.LEFT_TOP)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.set_mask)
        # set_overlay_mask_menu.addAction(action)

        # action = QAction("Right Top", parent=self.parent)
        # action.setData(MaskFlag.RIGHT_TOP)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.set_mask)
        # set_overlay_mask_menu.addAction(action)

        # action = QAction("Left Bottom", parent=self.parent)
        # action.setData(MaskFlag.LEFT_BOTTOM)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.set_mask)
        # set_overlay_mask_menu.addAction(action)

        # action = QAction("Right Bottom", parent=self.parent)
        # action.setData(MaskFlag.RIGHT_BOTTOM)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.set_mask)
        # set_overlay_mask_menu.addAction(action)

        # set_overlay_mask_menu = cmd_menu.addMenu("Clear Overlay Masking")
        # action = QAction("Left Top", parent=self.parent)
        # action.setData(MaskFlag.LEFT_TOP)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.clear_mask)
        # set_overlay_mask_menu.addAction(action)

        # action = QAction("Right Top", parent=self.parent)
        # action.setData(MaskFlag.RIGHT_TOP)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.clear_mask)
        # set_overlay_mask_menu.addAction(action)

        # action = QAction("Left Bottom", parent=self.parent)
        # action.setData(MaskFlag.LEFT_BOTTOM)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.clear_mask)
        # set_overlay_mask_menu.addAction(action)

        # action = QAction("Right Bottom", parent=self.parent)
        # action.setData(MaskFlag.RIGHT_BOTTOM)
        # # noinspection PyUnresolvedReferences
        # action.triggered.connect(self.clear_mask)
        # set_overlay_mask_menu.addAction(action)

        bri_menu = cmd_menu.addMenu("Change Brightness")
        action = QAction(get_icon("backlight_high_off.svg"), "Off", parent=self.parent)
        action.setData(0)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.set_brightness)
        bri_menu.addAction(action)

        action = QAction(get_icon("backlight_low.svg"), "1%", parent=self.parent)
        action.setData(2)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.set_brightness)
        bri_menu.addAction(action)

        action = QAction(get_icon("backlight_high.svg"), "50%", parent=self.parent)
        action.setData(25)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.set_brightness)
        bri_menu.addAction(action)

        action = QAction(get_icon("backlight_high.svg"), "100%", parent=self.parent)
        action.setData(50)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.set_brightness)
        bri_menu.addAction(action)

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
        file_name = QFileDialog.getOpenFileName(None, 'Open file', '', "PolyKybd commands (*.poly.cmd)")
        if len(file_name) > 0:
            with open(file_name[0]) as f:
                self.keeb.execute_commands(f.readlines())
        else:
            self.log.info("No file selected. Operation canceled.")