"""Recovery help for "the other keyboard half did not confirm".

Shown when a firmware update or a font-pack flash timed out with the USB half
still answering (``device/split_link.py``). An HID update cannot reach a half
that does not answer, so the only fix the host can offer is the manual one:
check the cable between the halves, and if a half stays dark, copy the firmware
``.uf2`` onto it in BOOTSEL mode. The dialog explains that and downloads the
``.uf2`` on request.

⚠️ Open it with ``show_split_link_help()``, never ``exec_()``. It is reached from
bridge-event handlers (``fw_flash_done``, ``fontpack_flash_done``), and a modal
opened there dispatches the other queued bridge events (CLAUDE.md, threading
model). One shared instance also means a second failure raises the open dialog
instead of stacking another.
"""

import html
import logging

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from polyhost.gui.dialog_util import bring_to_front
from polyhost.gui.log_bundle_dialog import reveal_in_file_manager
from polyhost.services.updater import FwUf2Downloader

# The docs section with the BOOT-button procedure (polykybd-docs
# src/content/docs/setup/flashing.mdx, "Fallback: UF2 bootloader drive").
UF2_GUIDE_URL = "https://www.polykybd.org/setup/flashing/#fallback-uf2-bootloader-drive"

# Plain paragraphs, not <ol>/<ul>: QLabel's height-for-width undercounts nested
# lists, which clipped the steps mid-sentence in the first render.
_TEXT = (
    "<p>The half plugged into USB answered, but the other half did not. Firmware "
    "updates and font installs need both halves, so they stop here.</p>"
    "<p><b>1.</b> Unplug the keyboard. Reseat the cable between the two halves at "
    "both ends, then plug the keyboard back in and try again.</p>"
    "<p><b>2.</b> If the other half stays dark (no lights, blank keycaps), it is not "
    "running firmware. Copy the firmware .uf2 onto it by hand:</p>"
    "<p style='margin-left:18px'>Unplug both halves. Hold the <b>BOOT</b> button on "
    "the dark half and connect it to the computer by USB, then release the button. "
    "A drive named <b>RPI-RP2</b> appears. Drag the .uf2 onto it. The drive "
    "disappears when the copy is done.</p>"
    "<p><b>3.</b> Reconnect both halves and run the update again.</p>"
    "<p>Copy the firmware .uf2 only. The small left/right handedness .uf2 files "
    "that came with releases 0.23 to 0.27 are ignored by the chip and leave the "
    "half dark.</p>"
)


# Text column width. Each wrapped label gets this as a fixed width and its own
# heightForWidth() as its height: a top-level QLayout does not ask for
# height-for-width, so without this the first renders clipped the steps.
_TEXT_WIDTH = 580


def _fit(label: QLabel):
    label.setFixedWidth(_TEXT_WIDTH)
    label.setFixedHeight(label.heightForWidth(_TEXT_WIDTH))


class SplitLinkHelpDialog(QDialog):
    # (ok, error, uf2_path, release_page) — emitted from the download thread;
    # Qt queues it onto the GUI thread because this dialog lives there.
    _downloaded = pyqtSignal(bool, str, str, str)

    def __init__(self, detail: str = "", parent=None):
        super().__init__(parent)
        self.log = logging.getLogger("PolyHost")
        self._downloader = None
        self._uf2_path = ""
        self._release_page = ""

        self.setWindowTitle("The other keyboard half is not answering")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        body = QLabel(_TEXT)
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        _fit(body)
        layout.addWidget(body)

        self._detail = QLabel()
        self._detail.setWordWrap(True)
        self._detail.setStyleSheet("color: gray;")
        self._detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._detail)
        self.set_detail(detail)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._status)

        row = QHBoxLayout()
        self._download_btn = QPushButton("Download .uf2")
        self._download_btn.clicked.connect(self._start_download)
        self._reveal_btn = QPushButton("Show in folder")
        self._reveal_btn.setVisible(False)
        self._reveal_btn.clicked.connect(lambda: reveal_in_file_manager(self._uf2_path, self.log))
        guide_btn = QPushButton("Open guide")
        guide_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(UF2_GUIDE_URL)))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        row.addWidget(self._download_btn)
        row.addWidget(self._reveal_btn)
        row.addWidget(guide_btn)
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)

        self._downloaded.connect(self._on_downloaded)

    def set_detail(self, detail: str):
        """The failure message that led here, so a screenshot carries it."""
        self._detail.setText(detail or "")
        self._detail.setVisible(bool(detail))
        _fit(self._detail)

    def _start_download(self):
        if self._downloader is not None and self._downloader.is_alive():
            return
        self._download_btn.setEnabled(False)
        self._set_status("Looking up the newest firmware release…")
        self._downloader = FwUf2Downloader(
            on_finished=lambda *a: self._downloaded.emit(*a))
        self._downloader.start()

    def _set_status(self, text: str, rich: bool = False):
        self._status.setTextFormat(Qt.RichText if rich else Qt.PlainText)
        self._status.setOpenExternalLinks(rich)
        self._status.setText(text)
        _fit(self._status)
        self.adjustSize()

    def _on_downloaded(self, ok: bool, error: str, path: str, page: str):
        self._download_btn.setEnabled(True)
        self._release_page = page
        if ok:
            self._uf2_path = path
            self._set_status(f"Saved: {path}")
            self._reveal_btn.setVisible(True)
            self._download_btn.setText("Download again")
            return
        self._set_status(
            f"The download failed ({html.escape(error)}). You can get the .uf2 from "
            f"<a href=\"{html.escape(page, quote=True)}\">the release page</a> instead.",
            rich=True)


_instance = None


def show_split_link_help(detail: str = "") -> SplitLinkHelpDialog:
    """Show the shared help dialog (non-modal), creating it on first use."""
    global _instance
    if _instance is None:
        _instance = SplitLinkHelpDialog(detail)
    else:
        _instance.set_detail(detail)
    _instance.show()
    bring_to_front(_instance)
    return _instance
