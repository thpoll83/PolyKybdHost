import logging

from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QMessageBox,
)

from polyhost.device.hid_fw_up import flash_firmware


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


class HidFwUpDialog(QDialog):
    """Modal progress dialog for HID firmware updates.

    Starts the update immediately on open; the Cancel button aborts between
    chunks and becomes Close once the update finishes.

    The reported progress is coarse and arrives in jumps (begin, every ~100
    chunks, commit), so instead of snapping the bar to each reported value it
    glides there smoothly at a constant speed — a larger jump simply takes
    proportionally longer to catch up.
    """

    # Bar animation: a timer interpolates the displayed value toward the latest
    # reported one.  Constant velocity (percent per second) means the glide time
    # is proportional to the size of the jump, so the speed feels consistent.
    _ANIM_TICK_MS = 16      # ~60 FPS
    _GLIDE_SPEED  = 90.0    # %/s — a full-width jump glides in roughly one second

    def __init__(self, hid, bin_path: str, parent=None):
        super().__init__(parent)
        self.log      = logging.getLogger('PolyHost')
        self._success = False

        # Smooth-progress animation state.
        self._target_pct    = 0      # latest reported percent (monotonic)
        self._display_pct   = 0.0    # currently shown value, animated toward target
        self._pending_finish = None  # (ok, msg) held until a successful glide reaches 100

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
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
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
        # Record the latest target and let the timer glide the bar there; never
        # move backwards if a stray lower value arrives.
        self._target_pct = max(self._target_pct, pct)
        self._status_label.setText(msg)
        self.log.info("FW_UP %d%% — %s", pct, msg)
        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def _animate_step(self):
        """Advance the displayed value toward the target at a constant speed."""
        if self._display_pct < self._target_pct:
            step = self._GLIDE_SPEED * (self._ANIM_TICK_MS / 1000.0)
            self._display_pct = min(self._display_pct + step, float(self._target_pct))
            self._progress_bar.setValue(int(round(self._display_pct)))

        if self._display_pct >= self._target_pct:
            # Caught up — nothing left to animate for now.
            self._anim_timer.stop()
            if self._pending_finish is not None:
                ok, msg = self._pending_finish
                self._pending_finish = None
                self._finalize(ok, msg)

    def _on_finished(self, ok: bool, msg: str):
        self._success = ok
        if ok:
            self.log.info("FW_UP finished: ok=%s — %s", ok, msg)
            # Let the bar glide all the way to 100 before showing the result, so
            # the user sees it complete rather than snapping shut.
            self._target_pct = 100
            self._pending_finish = (ok, msg)
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        else:
            # On failure, leave the bar where it stopped and report immediately.
            self.log.warning("FW_UP finished: ok=%s — %s", ok, msg)
            self._anim_timer.stop()
            self._finalize(ok, msg)

    def _finalize(self, ok: bool, msg: str):
        """Swap the dialog into its finished state (button, close flag, result)."""
        self._progress_bar.setValue(100 if ok else self._progress_bar.value())
        self._status_label.setText(msg)

        self._cancel_btn.setText("Close")
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.accept)

        # Re-enable the close button now that it's safe
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()

        if not ok:
            QMessageBox.warning(self, "Firmware Update Failed", msg)

    def _on_cancel(self):
        if self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._status_label.setText("Cancelling — waiting for current chunk to finish…")
        else:
            self.reject()

    def closeEvent(self, event):
        if self._worker.isRunning():
            event.ignore()   # Block close while flashing
        else:
            event.accept()
