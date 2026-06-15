import logging
import time

from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
)

from polyhost.device.hid_fw_up import flash_firmware, apply_staged_firmware
from polyhost.gui.dialog_util import position_near_tray


class _HidFwUpWorker(QThread):
    progress = pyqtSignal(int, str)   # (percent, status_message)
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, hid, bin_path: str):
        super().__init__()
        self.hid      = hid
        self.bin_path = bin_path
        self._cancel  = [False]   # mutable flag checked between chunks

    def cancel(self):
        self._cancel[0] = True

    def run(self):
        ok, msg = flash_firmware(
            self.hid, self.bin_path,
            progress_cb=lambda pct, m: self.progress.emit(pct, m),
            cancel_flag=self._cancel,
        )
        self.finished.emit(ok, msg)


class _ApplyWorker(QThread):
    """Runs the apply/activate step (FW_UP_APPLY) on its own thread.

    Apply has no meaningful percentage — it sends one command then waits for the
    keyboard to reboot and re-enumerate — so the dialog shows a spinner and only
    surfaces the textual status messages this emits.
    """
    progress = pyqtSignal(int, str)   # (percent, status_message)
    finished = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, hid):
        super().__init__()
        self.hid = hid

    def run(self):
        ok, msg = apply_staged_firmware(
            self.hid,
            progress_cb=lambda pct, m: self.progress.emit(pct, m),
        )
        self.finished.emit(ok, msg)


class HidFwUpDialog(QDialog):
    """Modal progress dialog for HID firmware updates.

    Starts the update immediately on open; the Cancel button aborts between
    chunks and becomes Close once the update finishes.

    The reported progress is coarse and arrives in jumps (begin, every ~100
    chunks, commit), so instead of snapping the bar to each reported value it
    glides there smoothly at a constant speed — a larger jump simply takes
    proportionally longer to catch up.

    The very first phase (FW_UP_BEGIN: erasing the staging area on both halves)
    has no measurable progress and can take ~10 s, so the bar shows an
    indeterminate spinner there instead of sitting stuck near zero.  It switches
    to the determinate glide once the keyboard starts accepting chunks.

    When ``apply_after`` is set, a successful staging is immediately followed by
    the apply/activate step in the same dialog: the bar shows a spinner while the
    keyboard reboots and the final "applied" message lands in the dialog's status
    label, so no separate message box is needed.
    """

    # Bar animation: a timer interpolates the displayed value toward the latest
    # reported one.  Constant velocity (percent per second) means the glide time
    # is proportional to the size of the jump, so the speed feels consistent.
    _ANIM_TICK_MS = 5
    _GLIDE_SPEED  = 2.3    # %/s — a full-width jump glides in roughly one second

    # If a newer progress report arrives while the bar is still catching up to
    # the previous target, the bar has fallen behind the real transfer — glide
    # that stretch this much faster so it catches up, then drop back to normal.
    _CATCHUP_FACTOR = 3

    # The bar runs at 10x resolution (0..1000 instead of 0..100) so the glide
    # advances in 0.1% steps rather than visible whole-percent jumps, and the
    # displayed text carries one decimal place.
    _SCALE = 100

    # The backend reports pct < this while still in the begin/erase phase (0 =
    # sending BEGIN, 1 = erasing) and >= this once chunks start flowing.  Below
    # the threshold the real progress is unknown, so we show a busy spinner.
    _DETERMINATE_FROM = 2

    # On success there's nothing for the user to do — show the completed state
    # this long, then dismiss automatically (no Close button to mis-place).
    _SUCCESS_AUTOCLOSE_MS = 1500

    def __init__(self, hid, bin_path: str, parent=None, apply_after=False, tray_icon=None,
                 external=False, apply_only=False):
        super().__init__(parent)
        self.log         = logging.getLogger('PolyHost')
        self._hid        = hid
        self._apply_after = apply_after
        self._tray_icon  = tray_icon
        # external: the flash runs elsewhere (the daemon, over RPC) and progress
        # is pushed in via feed_*() — no local HID worker. apply_only: there's no
        # staging phase, the dialog opens straight into the apply spinner.
        self._external   = external
        self._apply_only = apply_only
        self._success    = False      # staging succeeded
        self._apply_ok   = None       # apply result, or None if not attempted

        # Smooth-progress animation state.
        self._target_pct    = 0      # latest reported percent (monotonic)
        self._display_pct   = 0.0    # currently shown value, animated toward target
        self._pending_finish = None  # (ok, msg) held until a successful glide reaches 100
        self._pending_apply  = False # start the apply step once the glide reaches 100
        self._busy           = False # True while the bar is an indeterminate spinner
        self._apply_worker   = None  # _ApplyWorker, created after staging succeeds
        self._determinate    = False # True once chunks start; spinner never returns after
        self._done           = False # True once finalized; late signals are ignored
        self._behind         = False # bar fell behind a fresh report; catch up faster

        # ETA tracking for the chunk-transfer phase (pct 2–98).
        self._transfer_start_time = None  # monotonic, set when chunks begin flowing
        self._last_reported_pct   = 0     # latest pct in [2, 98) — drives ETA calculation
        self._positioned          = False  # move-to-corner only on the first showEvent

        self.setWindowTitle("Firmware Update")
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        # Prevent accidental close during flash
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._file_label = QLabel(f"<b>File:</b> {bin_path}")
        self._file_label.setWordWrap(True)
        self._file_label.setVisible(bool(bin_path))
        layout.addWidget(self._file_label)

        self._status_label = QLabel("Applying staged firmware…" if apply_only else "Starting…")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100 * self._SCALE)
        self._progress_bar.setTextVisible(True)
        self._show_pct(0.0)
        layout.addWidget(self._progress_bar)

        self._eta_label = QLabel("")
        self._eta_label.setAlignment(Qt.AlignRight)
        self._eta_label.setStyleSheet("color: gray;")
        layout.addWidget(self._eta_label)

        # Drives the smooth catch-up of the bar toward the reported percent.
        # Started lazily on the first progress update and stopped once settled.
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(self._ANIM_TICK_MS)
        self._anim_timer.timeout.connect(self._animate_step)

        # Updates the "~N s remaining" estimate once per second during transfer.
        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(1000)
        self._eta_timer.timeout.connect(self._update_eta)

        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        if external:
            # Display-only: the daemon runs the flash and pushes progress via
            # feed_*(). No local HID worker, and Cancel can't reach a remote
            # flash, so hide it until _finalize repurposes it as Close.
            self._worker = None
            self._cancel_btn.setVisible(False)
            if apply_only:
                # No staging phase — open straight into the apply spinner.
                self._set_busy(True)
        else:
            self._worker = _HidFwUpWorker(hid, bin_path)
            self._worker.progress.connect(self._on_progress)
            self._worker.finished.connect(self._on_finished)
            self._worker.start()

    # ------------------------------------------------------------------
    # External (event-driven) feed: the daemon's fw_flash_*/fw_apply_* events
    # drive the same handlers the local worker's signals would.
    def feed_progress(self, pct, msg):
        self._on_progress(int(pct), str(msg))

    def feed_finished(self, ok, msg):
        self._on_finished(bool(ok), str(msg))

    def feed_apply_progress(self, pct, msg):
        self._on_apply_progress(int(pct), str(msg))

    def feed_apply_finished(self, ok, msg):
        self._on_apply_finished(bool(ok), str(msg))

    # ------------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        if not self._positioned:
            self._positioned = True
            # Defer one event-loop tick so the WM has finalised the frame size.
            QTimer.singleShot(0, self._position_near_tray)

    def _position_near_tray(self):
        """Move the dialog to the screen corner nearest the system-tray icon."""
        position_near_tray(self, self._tray_icon)

    # ------------------------------------------------------------------
    def _update_eta(self):
        """Recompute and display the estimated remaining transfer time."""
        if self._transfer_start_time is None or self._done:
            self._eta_label.setText("")
            return
        pct = self._last_reported_pct
        if pct >= 98 or pct < 2:
            self._eta_label.setText("")
            return
        elapsed       = time.monotonic() - self._transfer_start_time
        fraction_done = (pct - 2) / 96.0
        # Wait for at least 5 % chunk progress and 2 s elapsed before showing
        # an estimate — early values are noisy and misleadingly large.
        if fraction_done < 0.05 or elapsed < 2.0:
            return
        remaining = max(0.0, elapsed / fraction_done - elapsed)
        if remaining < 60:
            self._eta_label.setText(f"~{round(remaining)} s remaining")
        else:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            self._eta_label.setText(f"~{mins}m {secs:02d}s remaining")

    # ------------------------------------------------------------------
    def _on_progress(self, pct: int, msg: str):
        if self._done:
            # The dialog is logically complete; ignore any late signals so they
            # can't restart the animation or flip the bar back into busy mode.
            return
        self._status_label.setText(msg)
        self.log.info("FW_UP %d%% — %s", pct, msg)

        if pct < self._DETERMINATE_FROM and not self._determinate:
            # Begin/erase phase — no measurable progress yet; spin instead of
            # sitting stuck near zero.  Only valid before determinate progress
            # has begun; once chunks flow we never return to the spinner even if
            # a stray low value arrives.
            self._set_busy(True)
            return

        # Chunks are flowing: switch to the determinate bar and glide toward the
        # latest target.  Never move backwards if a stray lower value arrives.
        self._determinate = True
        self._set_busy(False)
        new_target = max(self._target_pct, pct)
        # A fresh report arrived before the bar reached the previous target — it
        # has fallen behind the real transfer, so speed up until it catches up.
        if new_target > self._target_pct and self._display_pct < self._target_pct:
            self._behind = True
        self._target_pct = new_target
        if not self._anim_timer.isActive():
            self._anim_timer.start()

        # ETA: record when chunk transfer started and keep the latest pct.
        self._last_reported_pct = max(self._last_reported_pct, pct)
        if self._transfer_start_time is None and pct < 98:
            self._transfer_start_time = time.monotonic()
            self._eta_timer.start()
        elif pct >= 98:
            self._eta_timer.stop()
            self._eta_label.setText("")

    def _show_pct(self, pct: float):
        """Render a percentage on the bar at 10x resolution with one decimal."""
        self._progress_bar.setValue(int(round(pct * self._SCALE)))
        self._progress_bar.setFormat(f"{pct:.2f}%")

    def _set_busy(self, busy: bool):
        """Toggle the bar between an indeterminate spinner and the normal 0–100
        scale.  Qt renders a QProgressBar with a zero-width range (0, 0) as a
        busy spinner."""
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            self._anim_timer.stop()
            self._progress_bar.setRange(0, 0)
            self._progress_bar.setFormat("")
        else:
            self._progress_bar.setRange(0, 100 * self._SCALE)
            self._show_pct(self._display_pct)

    def _animate_step(self):
        """Advance the displayed value toward the target at a constant speed."""
        if self._display_pct < self._target_pct:
            speed = self._GLIDE_SPEED
            if self._behind:
                speed *= self._CATCHUP_FACTOR
            step = speed * (self._ANIM_TICK_MS / 1000.0)
            self._display_pct = min(self._display_pct + step, float(self._target_pct))
            self._show_pct(self._display_pct)

        if self._display_pct >= self._target_pct:
            # Caught up — back to normal speed; nothing left to animate for now.
            self._behind = False
            self._anim_timer.stop()
            if self._pending_apply:
                self._pending_apply = False
                self._start_apply()
            elif self._pending_finish is not None:
                ok, msg = self._pending_finish
                self._pending_finish = None
                self._finalize(ok, msg)

    def _on_finished(self, ok: bool, msg: str):
        self._success = ok
        if ok:
            self.log.info("FW_UP finished: ok=%s — %s", ok, msg)
            # Let the bar glide all the way to 100 before moving on, so the user
            # sees staging complete rather than the bar snapping.
            self._set_busy(False)
            self._target_pct = 100
            if self._apply_after:
                # Chain the apply step in this same dialog once the bar reaches 100.
                self._pending_apply = True
            else:
                self._pending_finish = (ok, msg)
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        else:
            # On failure, leave the bar where it stopped and report immediately.
            self.log.warning("FW_UP finished: ok=%s — %s", ok, msg)
            self._anim_timer.stop()
            self._finalize(ok, msg)

    # -- Apply / activate phase (only when apply_after) ----------------
    def _start_apply(self):
        """Kick off the apply/activate step on its own worker, reusing this dialog.

        Apply has no real percentage (send command, wait for reboot/reconnect),
        so the bar shows a spinner and only the status messages update.
        """
        self.log.info("FW_UP: staging done, starting apply…")
        self._status_label.setText("Applying — activating the staged firmware…")
        self._set_busy(True)
        # Apply can't be interrupted; the button is meaningless until it returns.
        self._cancel_btn.setEnabled(False)

        if self._external:
            # Apply runs in the daemon; feed_apply_*() drive the rest.
            return

        self._apply_worker = _ApplyWorker(self._hid)
        self._apply_worker.progress.connect(self._on_apply_progress)
        self._apply_worker.finished.connect(self._on_apply_finished)
        self._apply_worker.start()

    def _on_apply_progress(self, pct: int, msg: str):
        # No determinate percentage during apply — keep the spinner, show the text.
        self._status_label.setText(msg)
        self.log.info("FW_UP_APPLY %d%% — %s", pct, msg)

    def _on_apply_finished(self, ok: bool, msg: str):
        self._apply_ok = ok
        if ok:
            self.log.info("FW_UP_APPLY finished: ok=%s — %s", ok, msg)
        else:
            self.log.warning("FW_UP_APPLY finished: ok=%s — %s", ok, msg)
        # _finalize re-enables the button (disabled for the uninterruptible apply).
        self._finalize(ok, msg)

    def _finalize(self, ok: bool, msg: str):
        """Finish: success dismisses itself; failure keeps a Close button."""
        self._done = True
        self._anim_timer.stop()
        self._eta_timer.stop()
        self._eta_label.setText("")
        # Leave any spinner behind so the bar shows a concrete value (a full bar
        # on success, or wherever it stalled on failure).
        self._set_busy(False)
        if ok:
            self._display_pct = 100.0
        self._show_pct(self._display_pct)
        self._status_label.setText(msg)

        if ok:
            # Nothing for the user to do — show the completed state briefly, then
            # close. No Close button (so none can land under the taskbar), and we
            # don't touch the window flags/size (the old re-show grew the frame).
            self._cancel_btn.setVisible(False)
            QTimer.singleShot(self._SUCCESS_AUTOCLOSE_MS, self.accept)
            return

        # Failure: keep a Close button so the error stays readable. Repurpose the
        # existing in-layout button instead of re-adding WindowCloseButtonHint +
        # re-showing (that re-decoration grew the frame and pushed the button
        # under the taskbar). Re-snap into the available area in case the final
        # message wrapped and grew the dialog.
        self._cancel_btn.setVisible(True)
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.setText("Close")
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.reject)
        self._positioned = False
        QTimer.singleShot(0, self._position_near_tray)

    def _on_cancel(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._status_label.setText("Cancelling — waiting for current chunk to finish…")
        else:
            self.reject()

    def closeEvent(self, event):
        worker_busy = self._worker is not None and self._worker.isRunning()
        apply_busy = self._apply_worker is not None and self._apply_worker.isRunning()
        # In external mode there is no local worker to poll, so block close until
        # the daemon-driven flash has finalized (feed_*_finished sets _done).
        if worker_busy or apply_busy or (self._external and not self._done):
            event.ignore()   # Block close while flashing
        else:
            self._anim_timer.stop()
            self._eta_timer.stop()
            event.accept()
