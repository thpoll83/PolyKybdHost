import logging

from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QMessageBox,
)

from polyhost.device.ota_updater import flash_firmware


class _OtaWorker(QThread):
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


class OtaDialog(QDialog):
    """Modal progress dialog for OTA firmware updates.

    Starts the update immediately on open; the Cancel button aborts between
    chunks and becomes Close once the update finishes.
    """

    def __init__(self, hid, bin_path: str, parent=None):
        super().__init__(parent)
        self.log      = logging.getLogger('PolyHost')
        self._success = False

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

        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        self._worker = _OtaWorker(hid, bin_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    # ------------------------------------------------------------------
    def _on_progress(self, pct: int, msg: str):
        self._progress_bar.setValue(pct)
        self._status_label.setText(msg)
        self.log.info("OTA %d%% — %s", pct, msg)

    def _on_finished(self, ok: bool, msg: str):
        self._success = ok
        self._progress_bar.setValue(100 if ok else self._progress_bar.value())
        self._status_label.setText(msg)
        if ok:
            self.log.info("OTA finished: ok=%s — %s", ok, msg)
        else:
            self.log.warning("OTA finished: ok=%s — %s", ok, msg)

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
