import logging

from PyQt5.QtWidgets import (
    QAction, QFileDialog, QMessageBox, QAbstractItemView, QProxyStyle, QStyle,
)

from polyhost.device.keys import KeyCode, keycode_to_mapping_idx
from polyhost.device.hid_fw_up import get_fw_version, validate_rp2040_firmware, validate_polykybd_firmware, apply_staged_firmware
from polyhost.gui.get_icon import get_icon


class _RequireExplicitOpen(QProxyStyle):
    """Style proxy that stops the file list from accepting on a single click.

    Qt's file dialog honours the desktop's "single-click to open files and
    folders" setting (KDE Plasma's default), which makes a single click on a
    file activate -> accept the dialog immediately.  Forcing this one style
    hint to 0 makes a single click only *select* the file; the user must
    double-click it or press Open, regardless of the desktop setting.
    """
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.SH_ItemView_ActivateItemOnSingleClick:
            return 0
        return super().styleHint(hint, option, widget, returnData)


def _get_open_file_explicit(caption: str, name_filter: str) -> str:
    """Drop-in for QFileDialog.getOpenFileName that always requires an explicit
    Open (never accepts on a single click).  Returns the chosen path, or '' if
    cancelled.

    The platform's native dialog can't be overridden from the app, so this uses
    Qt's own dialog and disables single-click activation on its item views.
    """
    dlg = QFileDialog(None, caption, "", name_filter)
    dlg.setFileMode(QFileDialog.ExistingFile)
    dlg.setOption(QFileDialog.DontUseNativeDialog, True)
    proxy = _RequireExplicitOpen("Fusion")
    # Scope the override to the main file list / detail views only — those are
    # what accept on activation.  Leaving the sidebar (Places) untouched keeps
    # its single-click folder navigation working as the user expects.
    views = [dlg.findChild(QAbstractItemView, "listView"),
             dlg.findChild(QAbstractItemView, "treeView")]
    views = [v for v in views if v is not None]
    if not views:   # unexpected Qt layout — fall back to every item view
        views = dlg.findChildren(QAbstractItemView)
    for view in views:
        view.setStyle(proxy)
    dlg._require_explicit_open_style = proxy   # keep the proxy alive with the dialog
    if dlg.exec_() != QFileDialog.Accepted:
        return ""
    files = dlg.selectedFiles()
    return files[0] if files else ""


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

        action = QAction(get_icon("delete.svg"), "Reset Overlays Mapping", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.reset_overlay_mapping)
        cmd_menu.addAction(action)

        action = QAction(get_icon("toggle_off.svg"), "Clear Overlays Usage", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.reset_overlay_usage)
        cmd_menu.addAction(action)

        action = QAction(get_icon("toggle_on.svg"), "Set All Overlays Mapping", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.set_all_overlay_usage)
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

        cmd_menu.addSeparator()

        action = QAction(get_icon("keyboard_input.svg"), "Flash Firmware (.bin)…", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.open_hid_fw_up_dialog)
        cmd_menu.addAction(action)

        action = QAction(get_icon("keyboard_input.svg"), "Apply Staged Firmware (master)…", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.apply_staged_firmware_action)
        cmd_menu.addAction(action)

        action = QAction("Test mapping...", parent=self.parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(self.mapping_test)
        cmd_menu.addAction(action)

    def reset_dynamic_keymap(self):
        result, msg = self.keeb.reset_dynamic_keymap()
        self.parent.report_device_result("Error", f"Failed resetting dynamic keymap: {msg}", result)

    def reset_overlay_mapping(self):
        result, msg = self.keeb.reset_overlay_mapping()
        self.parent.report_device_result("Error", f"Failed clearing overlays: '{msg}'", result)

    def set_all_overlay_usage(self):
        result, msg = self.keeb.set_all_overlay_usage()
        self.parent.report_device_result("Error", f"Failed setting all overlay usage: '{msg}'", result)

    def reset_overlays_and_usage(self):
        result, msg = self.keeb.reset_overlays_and_usage()
        self.parent.report_device_result("Error", f"Failed clearing overlays and usage: '{msg}'", result)

    def reset_overlay_usage(self):
        result, msg = self.keeb.reset_overlay_usage()
        self.parent.report_device_result("Error", f"Failed clearing overlay usage: '{msg}'", result)

    def reset_overlays(self):
        result, msg = self.keeb.reset_overlays()
        self.parent.report_device_result("Error", f"Failed clearing overlays: '{msg}'", result)

    def enable_overlays(self):
        result, msg = self.keeb.enable_overlays()
        self.parent.report_device_result("Error", f"Failed enabling overlays: '{msg}'", result)

    def disable_overlays(self):
        result, msg = self.keeb.disable_overlays()
        self.parent.report_device_result("Error", f"Failed disabling overlays: '{msg}'", result)

    def set_brightness(self):
        result, msg = self.keeb.set_brightness(self.parent.sender().data())
        self.parent.report_device_result("Error", f"Failed disabling overlays: '{msg}'", result)

    def change_idle(self):
        result, msg = self.keeb.set_idle(self.parent.sender().data())
        self.parent.report_device_result("Error", f"Failed to change idle mode: '{msg}'", result)

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
        self.parent.report_device_result("Error", f"Failed to change idle mode: '{msg}'", result)

    def load_commands(self):
        file_name = _get_open_file_explicit('Open file', "PolyKybd commands (*.poly.cmd)")
        if file_name:
            with open(file_name) as f:
                self.keeb.execute_commands(f.readlines())
        else:
            self.log.info("No file selected. Operation canceled.")

    def open_hid_fw_up_dialog(self):
        from polyhost.gui.hid_fw_up_dialog import HidFwUpDialog

        if not self.keeb.hid or not self.keeb.hid.interface_acquired():
            QMessageBox.warning(None, "Not Connected",
                                "PolyKybd is not connected. Please connect the keyboard and try again.")
            return

        bin_path = _get_open_file_explicit("Select Firmware Binary", "Firmware binary (*.bin)")
        if not bin_path:
            self.log.info("FW_UP: no file selected, cancelled.")
            return

        # Read the full binary up front so both validation passes can run
        # before we show the confirmation dialog.
        try:
            with open(bin_path, 'rb') as fh:
                fw_bytes = fh.read()
        except OSError as exc:
            QMessageBox.critical(None, "File Error",
                                 f"Could not read firmware file:\n{exc}")
            return

        valid, reason = validate_rp2040_firmware(fw_bytes)
        if not valid:
            QMessageBox.critical(None, "Invalid Firmware File", reason)
            return

        valid, reason = validate_polykybd_firmware(fw_bytes)
        if not valid:
            QMessageBox.critical(None, "Wrong Keyboard", reason)
            return

        # Query current keyboard version for the confirmation dialog.
        ok, info = get_fw_version(self.keeb.hid)
        if ok:
            current = info.get('version', '?')
            size_kb = info.get('fw_size', 0) // 1024
            confirm_msg = (
                f"Current keyboard firmware: <b>{current}</b> ({size_kb} KB)<br><br>"
                f"Selected file:<br>{bin_path}<br><br>"
                "This will transfer and stage the new firmware on the keyboard, "
                "then verify it (CRC32). The image is stored but <b>not "
                "activated yet</b> — the keyboard keeps running its current "
                "firmware (activation will be a separate step).<br><br>"
                "Continue?"
            )
        else:
            confirm_msg = (
                f"Could not query current firmware version.<br><br>"
                f"Selected file:<br>{bin_path}<br><br>"
                "This will transfer and stage the new firmware on the keyboard, "
                "then verify it (CRC32). The image is stored but <b>not "
                "activated yet</b> — the keyboard keeps running its current "
                "firmware (activation will be a separate step).<br><br>"
                "Continue?"
            )

        reply = QMessageBox.question(
            None, "Flash Firmware", confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("FW_UP: user cancelled at confirmation.")
            return

        # Pause the host polling loop for the duration of the flash so the
        # HID lock is not contested by the 1 s reconnect timer.
        host = self.parent
        was_paused = getattr(host, 'paused', False)
        if hasattr(host, 'pause') and not was_paused:
            host.pause()

        try:
            dlg = HidFwUpDialog(self.keeb.hid, bin_path)
            dlg.exec_()
        finally:
            if hasattr(host, 'pause') and not was_paused:
                host.pause()   # toggle back to resume

    def apply_staged_firmware_action(self):
        """Trigger the keyboard to install a previously-staged firmware (FW_UP_APPLY).

        PHASE 2 (experimental): master-only self-apply. The master erases its own
        flash from offset 0, copies the staged image in, and reboots.
        """
        if not self.keeb.hid or not self.keeb.hid.interface_acquired():
            QMessageBox.warning(None, "Not Connected",
                                "PolyKybd is not connected. Please connect the keyboard and try again.")
            return

        confirm_msg = (
            "<b>Apply the staged firmware?</b><br><br>"
            "In-application self-apply is <b>currently disabled in the firmware</b> "
            "because it bricked the master half (it erases the live interrupt-vector "
            "table while rewriting flash from offset 0, then faults mid-copy).<br><br>"
            "Pressing OK will query the keyboard; it will safely report that apply is "
            "unavailable and <b>leave the staged image untouched</b> — it will NOT "
            "reboot or modify the active firmware.<br><br>"
            "A safe apply path (reboot into a minimal bootloader stage) is planned. "
            "Continue?"
        )
        reply = QMessageBox.warning(
            None, "Apply Staged Firmware", confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("FW_UP_APPLY: user cancelled at confirmation.")
            return

        # Pause the host polling loop so the 1 s reconnect timer doesn't contend for
        # the HID lock while the device reboots (same pattern as the flash dialog).
        host = self.parent
        was_paused = getattr(host, 'paused', False)
        if hasattr(host, 'pause') and not was_paused:
            host.pause()
        try:
            ok, msg = apply_staged_firmware(
                self.keeb.hid,
                progress_cb=lambda pct, m: self.log.info("FW_UP_APPLY %d%% — %s", pct, m))
        finally:
            if hasattr(host, 'pause') and not was_paused:
                host.pause()   # toggle back to resume

        if ok:
            QMessageBox.information(None, "Firmware Applied", msg)
        else:
            QMessageBox.warning(None, "Apply Failed", msg)
