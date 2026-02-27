import logging

from PyQt5.QtWidgets import QAction, QFileDialog

from polyhost.device.keys import KeyCode, keycode_to_mapping_idx
from polyhost.gui.get_icon import get_icon


class CommandsSubMenu:
    def __init__(self, parent, keeb):
        self.parent = parent
        self.keeb = keeb
        self.log = logging.getLogger('PolyHost')

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

        action = QAction(get_icon("keyboard.svg"), "Reset Dynamic Keymap", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.reset_dynamic_keymap)
        cmd_menu.addAction(action)

        action = QAction(get_icon("delete.svg"), "Reset Overlays Buffers", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.reset_overlays)
        cmd_menu.addAction(action)

        action = QAction(get_icon("delete.svg"), "Reset Overlays Usage", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.reset_overlay_usage)
        cmd_menu.addAction(action)

        action = QAction(get_icon("delete.svg"), "Reset Overlays Mapping", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.reset_overlay_mapping)
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

        action = QAction("Test mapping...", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.mapping_test)
        cmd_menu.addAction(action)

    def reset_dynamic_keymap(self):
        result, msg = self.keeb.reset_dynamic_keymap()
        self.parent.show_mb("Error", f"Failed resetting dynamic keymap: {msg}", result)

    def reset_overlay_mapping(self):
        result, msg = self.keeb.reset_overlay_mapping()
        self.parent.show_mb("Error", f"Failed clearing overlays: {msg}", result)

    def reset_overlays_and_usage(self):
        result, msg = self.keeb.reset_overlays_and_usage()
        self.parent.show_mb("Error", f"Failed clearing overlays: {msg}", result)

    def reset_overlay_usage(self):
        result, msg = self.keeb.reset_overlay_usage()
        self.parent.show_mb("Error", f"Failed clearing overlays: {msg}", result)

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

    def mapping_test(self):
        from_to = {}
        from_key = keycode_to_mapping_idx(KeyCode.KC_Q)
        to_key = keycode_to_mapping_idx(KeyCode.KC_A)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_A)
        to_key = keycode_to_mapping_idx(KeyCode.KC_Q)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_S)
        to_key = keycode_to_mapping_idx(KeyCode.KC_W)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_W)
        to_key = keycode_to_mapping_idx(KeyCode.KC_S)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_E)
        to_key = keycode_to_mapping_idx(KeyCode.KC_D)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_D)
        to_key = keycode_to_mapping_idx(KeyCode.KC_E)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_U)
        to_key = keycode_to_mapping_idx(KeyCode.KC_J)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_J)
        to_key = keycode_to_mapping_idx(KeyCode.KC_U)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_I)
        to_key = keycode_to_mapping_idx(KeyCode.KC_K)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_K)
        to_key = keycode_to_mapping_idx(KeyCode.KC_I)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_O)
        to_key = keycode_to_mapping_idx(KeyCode.KC_L)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        from_key = keycode_to_mapping_idx(KeyCode.KC_L)
        to_key = keycode_to_mapping_idx(KeyCode.KC_O)
        from_to[from_key] = to_key
        from_to[to_key] = from_key
        
        result, msg = self.keeb.send_overlay_mapping(from_to)
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