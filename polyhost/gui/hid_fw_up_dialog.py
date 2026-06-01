import logging

from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
)

from polyhost.device.hid_fw_up import flash_firmware, apply_staged_firmware


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
    _GLIDE_SPEED  = 2.5    # %/s — a full-width jump glides in roughly one second

    # If a newer progress report arrives while the bar is still catching up to
    # the previous target, the bar has fallen behind the real transfer — glide
    # that stretch this much faster so it catches up, then drop back to normal.
    _CATCHUP_FACTOR = 10

    # The bar runs at 10x resolution (0..1000 instead of 0..100) so the glide
    # advances in 0.1% steps rather than visible whole-percent jumps, and the
    # displayed text carries one decimal place.
    _SCALE = 100

    # The backend reports pct < this while still in the begin/erase phase (0 =
    # sending BEGIN, 1 = erasing) and >= this once chunks start flowing.  Below
    # the threshold the real progress is unknown, so we show a busy spinner.
    _DETERMINATE_FROM = 2

    def __init__(self, hid, bin_path: str, parent=None, apply_after=False):
        super().__init__(parent)
        self.log         = logging.getLogger('PolyHost')
        self._hid        = hid
        self._apply_after = apply_after
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

        self.setWindowTitle("Firmware Update")
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        # Prevent accidental close during flash
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._file_label = QLabel(f"<b>File:</b> {bin_path}")
        self._file_label.setWordWrap(True)
        layout.addWidget(self._file_label)

        self._status_label = QLabel("Starting…")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100 * self._SCALE)
        self._progress_bar.setTextVisible(True)
        self._show_pct(0.0)
        layout.addWidget(self._progress_bar)

        # Drives the smooth catch-up of the bar toward the reported percent.
        # Started lazily on the first progress update and stopped once settled.
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(self._ANIM_TICK_MS)
        self._anim_timer.timeout.connect(self._animate_step)

        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._worker = _HidFwUpWorker(hid, bin_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

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
        """Swap the dialog into its finished state (button, close flag, result)."""
        self._done = True
        self._anim_timer.stop()
        # Leave any spinner behind so the bar shows a concrete value (a full bar
        # on success, or wherever it stalled on failure).
        self._set_busy(False)
        if ok:
            self._display_pct = 100.0
        self._show_pct(self._display_pct)
        self._status_label.setText(msg)

        # Re-enable the button: it may have been disabled by a cancel request or
        # during the uninterruptible apply phase.  Now repurpose it as Close.
        self._cancel_btn.setEnabled(True)
        self._cancel_btn.setText("Close")
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.accept)

        # Re-enable the close button now that it's safe
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()

    def _on_cancel(self):
        if self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._status_label.setText("Cancelling — waiting for current chunk to finish…")
        else:
            self.reject()

    def closeEvent(self, event):
        if self._worker.isRunning() or (self._apply_worker is not None and self._apply_worker.isRunning()):
            event.ignore()   # Block close while flashing
        else:
            event.accept()
