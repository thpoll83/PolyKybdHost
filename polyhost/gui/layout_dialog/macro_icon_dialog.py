"""Pick the glyph a macro keycap draws above its caption.

The candidates are the glyphs the KEYBOARD has -- the font-pack bundles this host
ships -- rather than a hand-kept list, so a bundle that grows offers more icons with no
code change here, and one the keyboard cannot draw is never offered in the first place.

⚠️ Cells are rendered in BATCHES rather than up front. Measured across the shipped
bundles: 6167 drawable glyphs at ~0.6 ms each is 3.7 s, which as a modal dialog reads
as a hang. Emoji and symbols alone (the sources a pictographic icon actually comes
from) are ~1350, and even those are worth spreading out -- so the dialog opens
immediately and fills in while you look at it.
"""

from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtGui import QIcon, QImage, QPixmap
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
    QListView, QListWidget, QListWidgetItem, QVBoxLayout,
)

from polyhost.services import fontpack_render as fpr
from polyhost.services import macro_look as mk

CELL = 40
# ⚠️ The CELL the glyph is rendered into is wider than the glyph needs, because in
# IconMode Qt sizes the item from the ICON and elides the label to that -- not to the
# grid cell. At icon width 40 every five-digit codepoint came out as "1F4...", and even
# four-digit ones elided inconsistently. Padding the render is what makes the labels
# legible; the glyph is centred, so the extra width costs nothing visually.
CELL_W = 58
BATCH = 60          # cells per timer tick -- ~36 ms of rendering, comfortably under a frame

# The bundles a pictograph would come from, and the ones that would only add noise:
# `latinbig` is the big latin faces, `flags` the language flags, and the script bundles
# are keycap letters. All of them stay REACHABLE through the selector -- they are just
# not what "pick an icon" means.
PICTOGRAPH_BUNDLES = ("emoji", "symbol")


def _to_pixmap(img) -> QPixmap:
    if img.mode == "RGB":
        return QPixmap.fromImage(QImage(img.tobytes(), img.width, img.height,
                                        img.width * 3, QImage.Format_RGB888))
    img = img.convert("L")
    return QPixmap.fromImage(QImage(img.tobytes(), img.width, img.height,
                                    img.width, QImage.Format_Grayscale8))


class MacroIconDialog(QDialog):
    """Returns the chosen codepoint, or None."""

    def __init__(self, current: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose a keycap icon")
        self.resize(640, 520)
        self._current = current
        self._pending: list = []
        self._all: list = []

        outer = QVBoxLayout(self)

        row = QHBoxLayout()
        self.source = QComboBox()
        self.source.addItem("Emoji and symbols", "pictographs")
        self.source.addItem("Every bundle", "all")
        self.source.currentIndexChanged.connect(self._reload)
        row.addWidget(QLabel("Show:"))
        row.addWidget(self.source)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("filter by codepoint — 1F4E7, U+2699, or a character")
        self.filter.textChanged.connect(self._reload)
        row.addWidget(self.filter, 1)
        outer.addLayout(row)

        self.grid = QListWidget()
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setIconSize(QSize(CELL_W, CELL))
        # Wide enough for a five-digit codepoint: the interesting glyphs are emoji at
        # 0x1F300+, so a cell sized for four digits elides every one of them to "1F4..."
        # and the labels stop distinguishing anything.
        self.grid.setGridSize(QSize(CELL_W + 12, CELL + 26))
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.itemDoubleClicked.connect(lambda _i: self.accept())
        outer.addWidget(self.grid, 1)

        self.status = QLabel()
        self.status.setStyleSheet("color: palette(mid);")
        outer.addWidget(self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._fill = QTimer(self)
        self._fill.setInterval(0)
        self._fill.timeout.connect(self._fill_batch)

        self._fonts, self._source_kind = mk.load_render_fonts()
        self._reload()

    # -- data ---------------------------------------------------------------

    def _bundles(self):
        return None if self.source.currentData() == "all" else PICTOGRAPH_BUNDLES

    def _wanted(self, cp: int) -> bool:
        text = self.filter.text().strip()
        if not text:
            return True
        if len(text) == 1 and not text.isalnum():
            return cp == ord(text)
        try:
            body = text[2:] if text.upper().startswith(("U+", "0X")) else text
            return f"{cp:04X}".startswith(body.upper()) or cp == int(body, 16)
        except ValueError:
            return False

    def _candidates(self):
        """Every drawable glyph in the selected bundles, deduped by codepoint.

        Deduped front-to-back, so a codepoint two fonts both cover is offered once and
        shown as the one that would actually draw -- the same rule the keyboard applies.
        """
        wanted = self._bundles()
        seen = set()
        out = []
        for font in mk.load_pack_fonts(bundles=wanted):
            for i, g in enumerate(font.glyphs):
                if not (g["width"] and g["height"]):
                    continue
                cp = font.first + i
                if cp in seen:
                    continue
                seen.add(cp)
                out.append(cp)
        return sorted(out)

    def _reload(self):
        self._fill.stop()
        self.grid.clear()
        self._pending = [cp for cp in self._candidates() if self._wanted(cp)]
        self.status.setText(f"{len(self._pending)} glyphs")
        self._fill.start()

    def _fill_batch(self):
        if not self._pending:
            self._fill.stop()
            return
        chunk, self._pending = self._pending[:BATCH], self._pending[BATCH:]
        for cp in chunk:
            hit = mk.find_glyph(self._fonts, cp)
            if hit is None:
                continue
            item = QListWidgetItem(f"{cp:04X}")
            item.setData(Qt.UserRole, cp)
            item.setIcon(QIcon(_to_pixmap(
                fpr.glyph_cell(hit[0], cp, CELL_W, CELL, scale=1, label=False))))
            item.setToolTip(f"U+{cp:04X}")
            self.grid.addItem(item)
            if cp == self._current:
                self.grid.setCurrentItem(item)
        if not self._pending:
            self._fill.stop()

    # -- result -------------------------------------------------------------

    def codepoint(self):
        item = self.grid.currentItem()
        return None if item is None else item.data(Qt.UserRole)
