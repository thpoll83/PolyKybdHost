import logging
from contextlib import contextmanager

from PyQt5.QtWidgets import (
    QAction, QFileDialog, QMessageBox, QAbstractItemView, QProxyStyle, QStyle,
)

from polyhost.device.hid_fw_up import (get_fw_version, validate_rp2040_firmware,
                                       validate_polykybd_firmware, apply_staged_firmware,
                                       check_signature_file)
from polyhost.gui import file_dialogs
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

    The native-vs-Qt choice follows the shared per-desktop policy in
    ``file_dialogs`` (native on Windows/macOS/KDE, Qt's own dialog on other
    Linux desktops).  Only the non-native Qt widget dialog needs the
    single-click-activation fix below — the native KDE/portal dialog handles
    single-click on its own — so it is applied only in that branch.
    """
    if file_dialogs.use_native():
        path, _ = QFileDialog.getOpenFileName(None, caption, "", name_filter)
        return path

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
    """Builds the device-command menus and owns their handlers.

    Since the tray restructure these live in TWO places instead of one flat "All
    PolyKybd Commands" list: the small set a normal user legitimately needs goes
    into the top-level **Maintenance** menu, and the diagnostic/bulk rest goes
    under **Developer** (only built in developer mode). The handlers are shared,
    so this class builds both.

    Enabling is driven off explicit action lists rather than by walking a menu:
    the two menus have different parents and mixed gating (protocol-dependent
    actions follow `connected`, firmware/flash actions follow `fw_enabled` so a
    protocol-mismatched keyboard can still be updated).
    """

    def __init__(self, parent):
        self.parent = parent
        self.log = logging.getLogger('PolyHost')
        # Actions that need a protocol-compatible connection, and actions that
        # ride the protocol-independent staging transport (see update_enabled).
        self._device_actions = []
        self._fw_actions = []
        # Menu action of the Maintenance root, gated as a whole in update_enabled.
        self._maintenance_action = None
        self._auto_brightness_action = None

    @property
    def _core(self):
        return self.parent.core

    def _report(self, result, err_msg_fn):
        """Report a core command's (ok, payload) outcome. The core methods run
        synchronously (a worker run_sync in-process, an RPC in client mode) and
        normalize failures to (False, msg), so a brief main-thread block on a
        deliberate menu click is fine. ``err_msg_fn(msg)`` builds the per-command
        failure wording (only logged on failure)."""
        ok, msg = result
        self.parent.report_device_result("Error", err_msg_fn(msg), ok)

    def _act(self, icon, text, slot, data=None, device=False, firmware=False):
        """Create an action, wire it, and register it for enable-gating."""
        action = QAction(get_icon(icon), text, parent=self.parent)
        if data is not None:
            action.setData(data)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(slot)
        if device:
            self._device_actions.append(action)
        if firmware:
            self._fw_actions.append(action)
        return action

    def build_brightness_menu(self, parent_menu):
        """Keycap brightness presets - top level, it is the most-used control.

        Deliberately no "auto" RADIO: the keyboard owns that decision (its own
        light sensor and the host's daylight periodic drive it). These presets
        are manual overrides; the trailing entry is the way back out of one.
        """
        menu = parent_menu.addMenu(get_icon("settings_brightness.svg"), "Brightness")
        for icon, label, value in (("backlight_high_off.svg", "Off", 0),
                                   ("backlight_low.svg", "1%", 2),
                                   ("backlight_high.svg", "50%", 25),
                                   ("backlight_high_fill.svg", "100%", 50)):
            menu.addAction(self._act(icon, label, self.set_brightness, data=value, device=True))
        menu.addSeparator()
        # The firmware drops auto mode on ANY manual set and never re-engages by
        # itself, so without this the presets above are a one-way door until a
        # replug. Wording/tooltip are set on open from the live setting.
        self._auto_brightness_action = self._act(
            "brightness_auto.svg", "Back to automatic", self.back_to_automatic_brightness, device=True)
        menu.addAction(self._auto_brightness_action)
        # noinspection PyUnresolvedReferences
        menu.aboutToShow.connect(self._refresh_auto_brightness_action)
        self._device_actions.append(menu.menuAction())
        return menu

    def _refresh_auto_brightness_action(self):
        """Explain what "automatic" will actually do, from the live setting.

        With daylight-dependent brightness ON this re-engages auto mode (the
        host's daylight value, and the keyboard's own light sensor resumes with
        it). With it OFF the host tells the keyboard to leave auto mode, which
        just restores its stored manual level — still the way to clear a preset,
        but not "automatic", so don't claim it is.
        """
        action = self._auto_brightness_action
        try:
            daylight = bool(self._core.settings_get("brightness_set_daylight_dependent"))
        except Exception as exc:   # noqa: BLE001 — a tooltip must never break the menu
            self.log.debug("Could not read the daylight setting: %s", exc)
            action.setToolTip("Re-apply the host's automatic brightness.")
            return
        if daylight:
            action.setText("Back to automatic")
            action.setToolTip("Re-engage automatic (daylight) brightness — the manual "
                              "preset above is dropped.")
        else:
            action.setText("Clear manual override")
            action.setToolTip("Daylight-dependent brightness is off in Settings, so this "
                              "only returns the keyboard to its own stored brightness.")

    def back_to_automatic_brightness(self):
        self._report(self._core.refresh_daylight_brightness(),
                     lambda m: f"Failed to re-apply automatic brightness: '{m}'")

    def build_maintenance_menu(self, parent_menu):
        """Rare but legitimate user-facing repair actions.

        What earns a place here: fixing a keyboard that is in a wrong state
        (handedness, stale overlays, a keymap edited into a corner) plus the
        manual firmware paths. Everything diagnostic or bulk lives under
        Developer instead.
        """
        menu = parent_menu.addMenu(get_icon("build.svg"), "Maintenance")
        self._maintenance_action = menu.menuAction()

        hand_menu = menu.addMenu(get_icon("flip.svg"), "Fix Left/Right Side")
        hand_menu.addAction(self._act("splitscreen_left.svg",
                                      "Connected half is LEFT (other is RIGHT)",
                                      self.set_handedness, data=True, device=True))
        hand_menu.addAction(self._act("splitscreen_right.svg",
                                      "Connected half is RIGHT (other is LEFT)",
                                      self.set_handedness, data=False, device=True))
        self._device_actions.append(hand_menu.menuAction())

        menu.addAction(self._act("layers_clear.svg", "Reset overlays",
                                 self.reset_overlays, device=True))
        menu.addAction(self._act("device_reset.svg", "Reset keymap to default\u2026",
                                 self.reset_dynamic_keymap_confirmed, device=True))

        menu.addSeparator()
        # Firmware: protocol-independent staging transport, so these follow
        # fw_enabled and stay usable on a protocol mismatch.
        menu.addAction(self._act("deployed_code_update.svg", "Flash firmware file (.bin)\u2026",
                                 lambda: self.open_hid_fw_up_dialog(apply_after=True),
                                 firmware=True))
        menu.addAction(self._act("usb.svg", "Activate bootloader\u2026",
                                 self.activate_bootloader, firmware=True))
        return menu

    def build_developer_menus(self, dev_menu):
        """The diagnostic / bulk half, under the Developer submenu."""
        ov_menu = dev_menu.addMenu(get_icon("overlays.svg"), "Overlays")
        ov_menu.addAction(self._act("toggle_on.svg", "Enable shortcut overlays",
                                    self.enable_overlays, device=True))
        ov_menu.addAction(self._act("toggle_off.svg", "Disable shortcut overlays",
                                    self.disable_overlays, device=True))
        ov_menu.addSeparator()
        ov_menu.addAction(self._act("layers_clear.svg", "Reset overlay buffers",
                                    self.reset_overlays, device=True))
        ov_menu.addAction(self._act("link_off.svg", "Reset overlay mapping",
                                    self.reset_overlay_mapping, device=True))
        ov_menu.addAction(self._act("deselect.svg", "Clear overlay usage",
                                    self.reset_overlay_usage, device=True))
        ov_menu.addAction(self._act("select_all.svg", "Set all overlay mapping",
                                    self.set_all_overlay_usage, device=True))
        self._device_actions.append(ov_menu.menuAction())

        idle_menu = dev_menu.addMenu(get_icon("bedtime.svg"), "Idle")
        idle_menu.addAction(self._act("bedtime.svg", "Start idle now",
                                      self.change_idle, data=True, device=True))
        idle_menu.addAction(self._act("bedtime_off.svg", "Stop idle",
                                      self.change_idle, data=False, device=True))
        self._device_actions.append(idle_menu.menuAction())

        km_menu = dev_menu.addMenu(get_icon("keyboard.svg"), "Keymap")
        km_menu.addAction(self._act("list_alt.svg", "Layer count",
                                    self.show_layer_count, device=True))
        km_menu.addAction(self._act("list_alt.svg", "Default layer",
                                    self.show_default_layer, device=True))
        km_menu.addAction(self._act("file_open.svg", "Dump keymap buffer to the log",
                                    self.dump_keymap_buffer, device=True))
        self._device_actions.append(km_menu.menuAction())

        fp_menu = dev_menu.addMenu(get_icon("font_download.svg"), "Font Pack")
        fp_menu.addAction(self._act("list_alt.svg", "Per-bundle status…",
                                    self.show_fontpack_status, firmware=True))
        fp_menu.addAction(self._act("sync_alt.svg", "Sync (flash missing/updated bundles)",
                                    self.sync_fontpack, firmware=True))
        fp_menu.addAction(self._act("sync_alt.svg", "Re-flash ALL bundles (force)…",
                                    self.force_sync_fontpack, firmware=True))
        fp_menu.addAction(self._act("delete.svg", "Wipe (empty all bundles)",
                                    self.wipe_fontpack, firmware=True))
        # The submenu's own action must be in _fw_actions too, else it stays grey
        # when only the firmware half is enabled and its items are unreachable.
        self._fw_actions.append(fp_menu.menuAction())

        fw_menu = dev_menu.addMenu(get_icon("memory.svg"), "Firmware")
        fw_menu.addAction(self._act("deployed_code.svg", "Flash only (.bin, stage)\u2026",
                                    lambda: self.open_hid_fw_up_dialog(apply_after=False),
                                    firmware=True))
        fw_menu.addAction(self._act("arrow_circle_down.svg", "Apply staged firmware\u2026",
                                    self.apply_staged_firmware_action, firmware=True))
        self._fw_actions.append(fw_menu.menuAction())

        dev_menu.addSeparator()
        dev_menu.addAction(self._act("file_open.svg", "Run command file (.poly.cmd)\u2026",
                                     self.load_commands, device=True))

    def update_enabled(self, connected, fw_enabled):
        """Protocol-dependent commands follow ``connected``; the firmware
        flash/apply/bootloader actions follow ``fw_enabled`` so a keyboard with a
        mismatched protocol can still be updated (see PolyHost._fw_actions_allowed).

        A parent menu action must be enabled for its items to be reachable, so
        Maintenance opens whenever EITHER half is live.
        """
        for action in self._device_actions:
            action.setEnabled(connected)
        for action in self._fw_actions:
            action.setEnabled(fw_enabled)
        if self._maintenance_action is not None:
            self._maintenance_action.setEnabled(connected or fw_enabled)

    def activate_bootloader(self):
        self._report(self._core.activate_bootloader(),
                     lambda m: f"Failed to activate bootloader: '{m}'")

    def set_handedness(self):
        master_is_left = self.parent.sender().data()
        connected = "LEFT" if master_is_left else "RIGHT"
        other = "RIGHT" if master_is_left else "LEFT"
        confirm_msg = (
            f"<b>Set the half the USB cable is plugged into as the {connected} side?</b>"
            f"<br><br>The other half becomes the {other} side. Both halves save the "
            f"new handedness and reboot onto it (about 10 s, no replug needed).<br><br>"
            f"Make sure the USB cable is plugged into the half you want to be the "
            f"<b>{connected}</b> side, then continue."
        )
        reply = QMessageBox.question(
            None, "Fix Left/Right Side", confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("Set handedness: user cancelled at confirmation.")
            return
        self._report(self._core.set_handedness(master_is_left),
                     lambda m: f"Failed to set handedness: '{m}'")

    def reset_dynamic_keymap(self):
        self._report(self._core.reset_dynamic_keymap(),
                     lambda m: f"Failed resetting dynamic keymap: {m}")

    def reset_dynamic_keymap_confirmed(self):
        """Maintenance entry point: same reset, but it asks first.

        In the old flat command list this sat among a dozen sibling resets and
        fired straight away; on the top-level Maintenance menu it is one slip
        away from every user's remapped keymap, so it confirms.
        """
        confirm_msg = (
            "<b>Reset the keyboard's keymap to its firmware default?</b><br><br>"
            "Every key you remapped goes back to the layout the "
            "firmware ships with. This cannot be undone.<br><br>Continue?"
        )
        reply = QMessageBox.question(
            None, "Reset Keymap", confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("Reset dynamic keymap: user cancelled at confirmation.")
            return
        self.reset_dynamic_keymap()

    def reset_overlay_mapping(self):
        self._report(self._core.reset_overlay_mapping(),
                     lambda m: f"Failed clearing overlays: '{m}'")

    def set_all_overlay_usage(self):
        self._report(self._core.set_all_overlay_usage(),
                     lambda m: f"Failed setting all overlay usage: '{m}'")

    def reset_overlay_usage(self):
        self._report(self._core.reset_overlay_usage(),
                     lambda m: f"Failed clearing overlay usage: '{m}'")

    def reset_overlays(self):
        self._report(self._core.reset_overlay_buffers(),
                     lambda m: f"Failed clearing overlays: '{m}'")

    def enable_overlays(self):
        self._report(self._core.enable_overlays(),
                     lambda m: f"Failed enabling overlays: '{m}'")

    def disable_overlays(self):
        self._report(self._core.disable_overlays(),
                     lambda m: f"Failed disabling overlays: '{m}'")

    def set_brightness(self):
        value = self.parent.sender().data()
        self._report(self._core.set_brightness(value),
                     lambda m: f"Failed setting brightness: '{m}'")

    def change_idle(self):
        idle = self.parent.sender().data()
        self._report(self._core.set_idle(idle),
                     lambda m: f"Failed to change idle mode: '{m}'")

    def sync_fontpack(self):
        """Flash any font-pack bundles the keyboard is missing/behind on (the same
        comparison as the on-connect auto-flash). Progress shows in the tray."""
        self._report(self._core.sync_fontpack(),
                     lambda m: f"Failed to sync font pack: '{m}'")

    def force_sync_fontpack(self):
        """Re-flash every shipped bundle, ignoring the version comparison.

        The version-based Sync cannot fix a bundle the keyboard reports as current but
        renders wrong (a lost COMMIT acknowledgement leaves exactly that state), so this
        is the way back. Confirmed because it re-sends the whole pack (~0.5 MB, ~1 min)."""
        reply = QMessageBox.question(
            None, "Re-flash Font Pack",
            "<b>Re-flash every font-pack bundle?</b><br><br>"
            "Every shipped bundle is sent again even if the keyboard already reports it as "
            "up to date — use this when a glyph renders wrong or a previous flash was "
            "reported as failed. Takes about a minute; typing keeps working throughout."
            "<br><br>Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("Font pack force re-flash: user cancelled at confirmation.")
            return
        self._report(self._core.sync_fontpack(force=True),
                     lambda m: f"Failed to re-flash the font pack: '{m}'")

    def wipe_fontpack(self):
        """Empty every font-pack slot (resident-only fonts until re-flashed). The next
        connect re-flashes the shipped bundles automatically."""
        confirm_msg = (
            "<b>Wipe the external-flash font pack?</b><br><br>"
            "Every font-pack bundle slot is emptied — the keyboard renders only its "
            "built-in (resident) fonts until the pack is flashed again. The bundles "
            "shipped with this host are re-flashed automatically on the next connect "
            "(or via Font Pack → Sync).<br><br>Continue?"
        )
        reply = QMessageBox.question(
            None, "Wipe Font Pack", confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("Font pack wipe: user cancelled at confirmation.")
            return
        self._report(self._core.wipe_fontpack(),
                     lambda m: f"Failed to wipe font pack: '{m}'")

    def show_layer_count(self):
        ok, value = self._core.keymap_layer_count()
        self._info("Keymap", f"Layers: {value}" if ok else f"Could not read the layer count: {value}")

    def show_default_layer(self):
        ok, value = self._core.keymap_default_layer()
        self._info("Keymap", f"Default layer: {value}" if ok
                   else f"Could not read the default layer: {value}")

    def dump_keymap_buffer(self):
        """Write the raw keymap buffer to the host log — it is far too big for a
        dialog, and the log is what gets attached to a bug report anyway."""
        ok, buf = self._core.keymap_buffer()
        if not ok:
            self._info("Keymap", f"Could not read the keymap buffer: {buf}")
            return
        data = bytes(buf) if not isinstance(buf, str) else buf.encode()
        self.log.info("Keymap buffer (%d bytes):\n%s", len(data), data.hex(" ", 2))
        self._info("Keymap", f"Keymap buffer ({len(data)} bytes) written to the log.")

    def show_fontpack_status(self):
        """Per-bundle device-vs-shipped versions (what Sync would actually do)."""
        ok, info = self._core.fontpack_bundle_status()
        if not ok:
            self._info("Font Pack", f"Could not read the font-pack status: {info}")
            return
        if not info.get("shipped"):
            self._info("Font Pack", "This host ships no font-pack bundles.")
            return
        # NB: `state=` is deliberately a DIFFERENT name from the payload's own
        # `stale` key — passing both an explicit stale= and **b (which carries
        # stale) is a TypeError, which crashed this dialog on every open.
        rows = "".join(
            "<tr><td>{id}</td><td align=right>{device_version}</td>"
            "<td align=right>{shipped_version}</td><td>{state}</td></tr>".format(
                state="stale" if b["stale"] else "ok", **b)
            for b in info["bundles"])
        self._info("Font Pack",
                   "<table cellpadding=4><tr><th align=left>bundle</th><th>device</th>"
                   f"<th>shipped</th><th></th></tr>{rows}</table>")

    def _info(self, title, text):
        QMessageBox.information(None, title, text)

    def load_commands(self):
        file_name = _get_open_file_explicit('Open file', "PolyKybd commands (*.poly.cmd)")
        if file_name:
            with open(file_name) as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            # Queued on the worker (in-process) / RPC (client) — runs async so a
            # long script with `wait`s never blocks the GUI.
            self._core.execute_commands(lines)
        else:
            self.log.info("No file selected. Operation canceled.")

    @contextmanager
    def _paused_polling(self):
        """Hold the HID worker off for a critical HID operation (firmware flash /
        apply) so its periodic reconnect probe doesn't contend for the device
        while the keyboard reboots and re-enumerates.  exclusive() cancels the
        in-flight job, waits for it to finish, suspends periodics, and resumes on
        exit (even if the body raises)."""
        with self.parent.worker.exclusive():
            yield

    def open_hid_fw_up_dialog(self, apply_after=False):
        # Client mode: no local HID — flash a (daemon-readable) .bin over RPC,
        # with the event-driven progress dialog.
        if self.parent.client_mode:
            self.parent._client_flash_firmware(apply=apply_after)
            return

        from polyhost.gui.hid_fw_up_dialog import HidFwUpDialog

        if not self.parent.keeb.hid or not self.parent.keeb.hid.interface_acquired():
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

        # FW-2 advisory, at SELECTION time — before a 446 KB transfer and before
        # the keyboard goes modal asking for a physical confirmation the user was
        # never told to expect. Informational only: the host cannot decide what the
        # keyboard accepts (and is exactly the thing signing does not trust), so
        # this never blocks the flash.
        signed, advisory = check_signature_file(bin_path)
        if not signed:
            QMessageBox.information(None, "Unsigned Firmware", advisory)

        # The confirmation text + title depend on whether we also activate the
        # image right after staging (single-step "flash + apply").
        if apply_after:
            dlg_title = "Flash + Apply Firmware"
            confirm_body = (
                "This will transfer the new firmware to the keyboard, verify it "
                "(CRC32), then <b>activate it</b> — both halves reboot onto the "
                "new firmware automatically (no replug needed)."
            )
        else:
            dlg_title = "Flash Firmware"
            confirm_body = (
                "This will transfer and stage the new firmware on the keyboard, "
                "then verify it (CRC32). The image is stored but "
                "<b>not activated yet</b> — the keyboard keeps running its "
                "current firmware until you apply it separately."
            )

        # Query current keyboard version for the confirmation dialog. The worker
        # is still live here (exclusive() is entered later), so route the read
        # through run_sync to avoid interleaving with a queued device job.
        try:
            ok, info = self.parent.worker.run_sync(
                "get_fw_version", lambda c: get_fw_version(self.parent.keeb.hid), timeout=5)
        except Exception as exc:
            self.log.warning("FW version query failed: %s", exc)
            ok, info = False, {}
        if ok:
            current = info.get('version', '?')
            size_kb = info.get('fw_size', 0) // 1024
            head = (f"Current keyboard firmware: <b>{current}</b> ({size_kb} KB)<br><br>"
                    f"Selected file:<br>{bin_path}<br><br>")
        else:
            head = (f"Could not query current firmware version.<br><br>"
                    f"Selected file:<br>{bin_path}<br><br>")
        confirm_msg = head + confirm_body + "<br><br>Continue?"

        reply = QMessageBox.question(
            None, dlg_title, confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("FW_UP: user cancelled at confirmation.")
            return

        # Pause the host polling loop for the duration of the flash (and the apply,
        # if requested) so the HID lock is not contested by the 1 s reconnect timer.
        # The dialog itself chains the apply step when apply_after is set, so the
        # staging progress and the apply outcome both surface in the same window.
        with self._paused_polling():
            dlg = HidFwUpDialog(self.parent.keeb.hid, bin_path, apply_after=apply_after,
                                tray_icon=getattr(self.parent, 'tray', None))
            dlg.exec_()

    def apply_staged_firmware_action(self):
        """Trigger the keyboard to install a previously-staged firmware (FW_UP_APPLY).

        Both halves install the staged image and reboot onto it: the master tells
        the slave to apply + reboot, then applies itself, so both come up on the
        new firmware (no replug). Requires a firmware build with in-app apply
        enabled; otherwise the keyboard safely reports apply unavailable and leaves
        the staged image untouched.
        """
        confirm_msg = (
            "<b>Apply the staged firmware?</b><br><br>"
            "Both keyboard halves will install the previously-staged image and "
            "reboot onto the new firmware automatically (no replug needed).<br><br>"
            "If this firmware was not built with in-app apply enabled, the keyboard "
            "safely reports apply unavailable and leaves the staged image "
            "untouched.<br><br>"
            "Continue?"
        )
        reply = QMessageBox.question(
            None, "Apply Staged Firmware", confirm_msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            self.log.info("FW_UP_APPLY: user cancelled at confirmation.")
            return

        # Client mode: the daemon owns the device — apply over RPC with the
        # event-driven progress dialog.
        if self.parent.client_mode:
            self.parent._client_apply_staged()
            return

        if not self.parent.keeb.hid or not self.parent.keeb.hid.interface_acquired():
            QMessageBox.warning(None, "Not Connected",
                                "PolyKybd is not connected. Please connect the keyboard and try again.")
            return

        # Pause the host polling loop so the 1 s reconnect timer doesn't contend for
        # the HID lock while the device reboots (same pattern as the flash dialog).
        with self._paused_polling():
            ok, msg = apply_staged_firmware(
                self.parent.keeb.hid,
                progress_cb=lambda pct, m: self.log.info("FW_UP_APPLY %d%% — %s", pct, m))

        if ok:
            QMessageBox.information(None, "Firmware Applied", msg)
        else:
            QMessageBox.warning(None, "Apply Failed", msg)
