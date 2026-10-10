import json
import logging
import math
import pathlib
import traceback

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QBrush, QGuiApplication, QCursor, QPixmap, QTransform
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox,
    QToolButton, QButtonGroup,
    QGraphicsScene, QDialog, QFormLayout
)

from polyhost.device.device_settings import DeviceSettings
from polyhost.gui.button_array import ButtonArray
from polyhost.gui.get_icon import get_icon
from polyhost.gui.layout_dialog.qmk_keycode_helper import describe_keycode, parse_layer_names
from polyhost.gui.layout_dialog.keycap_preview import KC_NO, KC_TRANSPARENT, KeycapPreview
from polyhost.gui import oled_look
from polyhost.gui import theme as gui_theme
from polyhost.gui.layout_dialog.macro_keycap_render import MacroKeycapRenderer
from polyhost.gui.layout_dialog.macro_tab import QK_MACRO
from polyhost.gui.layout_dialog.board_plate import add_board, set_screen_images
from polyhost.gui.layout_dialog import real_board
from polyhost.gui.layout_dialog import status_screen_render as ssr
from polyhost.gui.layout_dialog.status_screen_render import StatusScreenRenderer
from polyhost.gui.layout_dialog.renderable_key import RenderableKey, key_transform
from polyhost.gui.layout_dialog.keycode_browser import KeycodeBrowser
from polyhost.gui.zoomable_graphics_view import ZoomableGraphicsView
from polyhost.i18n import _, _f
from polyhost.kle.kle_praser import parse_kle
from polyhost.services import macro_label as ml
from polyhost.services import macro_look as mkl

# How a key is drawn. SYMBOL is the keycode text, PREVIEW the flat 72x40 keycap the
# keyboard composes, REAL that keycap through the panel simulation the font-pack
# inspector uses -- emissive pixels, bloom, the staggered grid and the diffusion of
# the clear cover. Three modes rather than a checkbox because REAL answers a question
# PREVIEW cannot: whether a legend still READS once the cover has softened it.
KEYCAP_SYMBOL = "symbol"
KEYCAP_PREVIEW = "preview"
KEYCAP_REAL = "real"

# Output pixels per logical OLED pixel for REAL. The grid, the bloom radius and the
# per-pixel jitter are all sized from it, so at 1 there is nothing to see; the tile
# then scales the larger image down, and zooming the view in reveals more of the panel
# rather than a bigger flat bitmap.
KEYCAP_REAL_SCALE = 3

KEY_SCALE = 80.0
# the case around the KLE key tiles, in scene units
FIT_PAD = 0.5 * KEY_SCALE
KLE_DEFINITION = pathlib.Path(__file__).parent.parent.parent.resolve() / "res" / "polykybd-split72.json"

class KeyEditDialog(QDialog):
    """Key editing dialog"""
    def __init__(self, key_dict):
        super().__init__()
        self.setWindowTitle(_("Edit Key"))
        self.key = key_dict
        layout = QFormLayout()
        
        self.qmk_edit = QLineEdit(self.key.get('qmk', ''))
        layout.addRow(_("QMK Keycode:"), self.qmk_edit)
        
        self.label_edit = QTextEdit(self.key.get('label', ''))
        layout.addRow(_("Visual Label:"), self.label_edit)
        
        if self.key.get('r', 0) != 0:
            info = _f("Rotation: {angle}° around ({x}, {y})",
                      angle=self.key['r'], x=self.key['rx'], y=self.key['ry'])
            layout.addRow(_("Info:"), QLabel(info))
        
        btn_ok = QPushButton(_("OK"))
        btn_cancel = QPushButton(_("Cancel"))
        btn_ok.clicked.connect(self.accept_changes)
        btn_cancel.clicked.connect(self.reject)
        h = QHBoxLayout()
        h.addWidget(btn_ok)
        h.addWidget(btn_cancel)
        layout.addRow(h)
        self.setLayout(layout)
        
        self.setWindowIcon(get_icon("pcolor.png"))
    
    def accept_changes(self):
        self.key['qmk'] = self.qmk_edit.text().strip()
        self.key['label'] = self.label_edit.toPlainText()
        self.accept()


class KbLayoutDialog(QMainWindow):
    def __init__(self, core, settings: DeviceSettings, parent=None):
        super().__init__(parent)
        self.log = logging.getLogger('PolyHost')
        self.settings = settings
        self.setWindowTitle(_("PolyKybd Split72 Layout"))
        self.key_matrix = {}
        self.mapping = {}
        self.row_count = 0
        self.col_count = 0

        # Keymap I/O goes through the core's keymap_* methods, which return a
        # uniform (ok, payload) in BOTH modes: PolyCore runs them on the HID
        # worker (run_sync), RemoteCore over the control socket (RPC). So the
        # dialog works identically for an in-process or a --connect GUI.
        self.core = core

        # zoom RELATIVE to the window: 1.0 shows the whole board, and the view
        # re-applies it on every resize (ZoomableGraphicsView fit_scene)
        self.scale_factor = 1.0
        self._zoom_step = 1.2   # multiplicative step for each + / - press
        self._zoom_min = 0.5
        self._zoom_max = 8.0
        self.selected_key = None
        self.keys = {}
        self.current_layer = 0
        self.key_buffer = None
        # A macro key draws its real keycap rather than reading `MACRO(3)`, so the
        # editor needs the same fonts and the macro list the Macros tab uses. Loaded
        # once and cached per macro id -- see `_keycap_for`. A missing font pack costs
        # only the picture: `usable` goes False and every key falls back to its text.
        self._macros: list = []
        self._keycap_cache: dict = {}     # macro id -> pixmap
        self._key_cache: dict = {}        # keycode -> pixmap or None
        self._keycap_render = None
        # Everything that is NOT a macro: the firmware composes those legends, so
        # this drives the firmware-side renderers rather than reimplementing them.
        self._preview = KeycapPreview()
        # The status panels on the board plate. Built from the SAME source the
        # keycaps came from, so one board cannot show two firmwares.
        self._status_render = None
        self._board_items: list = []
        # SYMBOL / PREVIEW / REAL, driving the header's button group. A plain field
        # rather than reading a widget back, so `_keycap_for` does not depend on one
        # init_ui has not built yet. Set to the default once the fonts below have
        # loaded (`_default_keycap_mode`); SYMBOL until then.
        self._keycap_mode = KEYCAP_SYMBOL
        try:
            faces = ml.load_caption_faces(ml.default_font_dir())
            nano = faces[-1]
            mid = mkl.load_ui_font(ml.default_font_dir(), "util_font.h",
                                   mkl.MID_FONT_SYMBOL)
            fonts, _src = mkl.load_render_fonts()
            ladder = mkl.caption_ladder(mkl.load_pack_fonts(), mid_font=mid,
                                        nano_font=nano)
            self._keycap_render = MacroKeycapRenderer(fonts, nano, mid, ladder, faces)
        except Exception:
            self.log.debug("macro keycap fonts unavailable; keys show their keycode")
        self._keycap_mode = self._default_keycap_mode()

        self.init_ui()

    def _default_keycap_mode(self):
        """REAL when it can draw, else the best mode that can: the editor opens on
        the board as it looks (the maintainer's call, 2026-10-07), and falls back
        to Preview without the panel simulation and to Symbol without the fonts,
        the same rules that enable the header's buttons."""
        macro_ok = self._keycap_render is not None and self._keycap_render.usable
        if not (macro_ok or self._preview.usable):
            return KEYCAP_SYMBOL
        return KEYCAP_REAL if oled_look.available() else KEYCAP_PREVIEW

    def get_selected_key(self):
        return self.selected_key

    def _layer_names(self) -> dict[int, str]:
        """Layer labels, preferring what the keyboard says over the shipped map.

        Firmware v14+ answers cmd 35 with its own names — `Qwerty`, `Fn`, `Numpad` —
        which cannot drift from the board and read better than an enum tag. The
        shipped `LAYER_TAGS` is the fallback for older boards, and gives `FL`/`NL`.
        """
        try:
            ok, names = self.core.keymap_layer_names()
        except Exception:
            ok, names = False, []
        if ok and names:
            return {idx: name for idx, name in enumerate(names) if name}
        return parse_layer_names()

    def init_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout()
        
        # Left: keyboard view
        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView(zoom_callback=self.zoom, fit_scene=True)
        self.view.setScene(self.scene)

        self.keycode_browser = KeycodeBrowser(core=self.core)
        self.keycode_browser.keycodeSelected.connect(self.keycodeSelected)
        self.keycode_browser.macrosChanged.connect(self.refresh_macro_keycaps)

        success, num_layers = self.core.keymap_layer_count()
        self.num_layers = num_layers if success else 0
        layer_names = self._layer_names()

        if not success:
            QMessageBox.warning(
                None, _("Not Connected"),
                _("PolyKybd is not reachable. Please connect the keyboard and try again."))
            my_options = [_("Could not read layers from device")]
        else:
            self.keycode_browser.set_layer_count(self.num_layers)
            my_options = []
            for idx in range(self.num_layers):
                hint = layer_names.get(idx)
                my_options.append(f"{idx} {hint}" if hint else str(idx))

        header_layout = QHBoxLayout()
        self.layers = ButtonArray(my_options)
        self.layers.setMaximumHeight(40)
        self.layers.connect(self.layerChanged)
        label = QLabel(_("Layers:"))
        # ⚠️ NO width cap here. It carried setMaximumWidth(50) and the string needs
        # 62 px, so the header read "Layer:" -- clipped in the app itself, and in
        # every docs screenshot of it. The cap was there to stop the label eating
        # width, which the stretch factor on the ButtonArray below already does.
        header_layout.addWidget(label)
        # ⚠️ The stretch factor goes ON the ButtonArray -- do NOT push the toggle
        # right with an addStretch() between them. `self.layers` holds a FlowLayout
        # and is capped at 40 px high, so a stretch that takes the spare width
        # squeezes it to ~118 px, the flow wraps every layer onto its own row, and
        # the cap hides all but the FIRST: eight layers render as one, with nothing
        # clipped-looking to give it away.
        header_layout.addWidget(self.layers, 1)
        header_layout.addWidget(self._build_keycap_modes())
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.view)
        main_layout.addWidget(self.keycode_browser)
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.set_preferred_size(1800, 1000)

        self.load_from_file(str(KLE_DEFINITION))

        success, buf = self.core.keymap_buffer()
        self.key_buffer = buf if success else None
        if success:
            self.log.info("Received dynamic key buffer: %d", len(self.key_buffer))
            ok, default_layer = self.core.keymap_default_layer()
            if ok and self.num_layers and 0 <= default_layer < self.num_layers:
                self.current_layer = default_layer
                self.layers.set_active(default_layer)
            # BEFORE the first paint: `_keycap_for` reads this list, so drawing the
            # layer first leaves every macro key showing MACRO(3) until something
            # else happens to refresh it.
            self._load_macros()
            self.set_keycodes_for_layer(self.current_layer)
        else:
            self.log.warning("Failed to receive dynamic key buffer")
            # key_buffer is None: any layer switch or keycode assignment would
            # index it and crash, so lock the interactive widgets down.
            self.layers.setEnabled(False)
            self.keycode_browser.setEnabled(False)
    
    # -- macro keycaps ------------------------------------------------------

    def _build_keycap_modes(self):
        """The header's Symbol / Preview / Real group.

        SYMBOL is the keycode text. PREVIEW draws the keycap the KEYBOARD draws:
        macros through the host's own composer, everything else through the
        firmware-side renderers in `keycap_preview` (the language LUT for
        letters/digits/punctuation, the `keycode_helper.c` static-text map for
        modifiers, arrows and the custom PolyKybd keys). REAL puts that same keycap
        through the panel simulation -- the one the font-pack inspector offers -- so
        the board shows what the glyphs look like through the clear cover rather than
        as a crisp bitmap, which is the difference that decides whether a small legend
        is actually readable.

        ⚠️ Coverage is NOT total and the labels must not imply it is: a keycode neither
        table names simply keeps its text, mixed in with the previewed keys. The data
        SHIPS with the host (`res/preview/`), so this works on an ordinary install; a
        firmware checkout beside the repo overrides it only when it is newer. When
        neither loads, PREVIEW and REAL are DISABLED and say why -- but SYMBOL stays
        enabled, because it is the fallback every other mode degrades to and a group
        with nothing selectable is worse than a group with one choice.
        """
        macro_ok = self._keycap_render is not None and self._keycap_render.usable
        usable = macro_ok or self._preview.usable
        # ⚠️ Say WHY when a half is missing. A partly-loaded preview renders macros and
        # modifiers while every letter falls back to text, which reads as "broken" with
        # nothing anywhere to explain it -- the shape that shipped once already, when a
        # missing openpyxl silently disabled everything but the macros. `source_info()`
        # below then names WHICH data drew them, which is the other half of the same
        # question: a legend can be perfectly rendered and still be the wrong vintage.
        tip = _("Draw each key as the keycap the keyboard shows. A key whose legend is "
                "not modelled here keeps its keycode text.") if usable else _(
              "Unavailable: the keycap fonts and layout tables could not be loaded, so "
              "keys show their keycode.")
        why = self._preview.reason
        if why:
            # `reason` is English (it is logged too); the fixed ones are marked msgids,
            # and an exception text simply has no translation and passes through.
            tip += "\n\n" + _f("Partly unavailable — {reason}", reason=_(why))
        # Name the checkout the legends came from. Without it, a preview drawing
        # legends the keyboard has moved past looks the same as one that is wrong.
        src = self._preview.source_info()
        if src:
            tip += "\n\n" + _f("Legends read from:\n{source}", source=src)
        # One exclusive group of push buttons rather than three checkboxes: the modes
        # are alternatives, and a segmented control says so where three ticks would
        # invite the reader to look for a combination that does not exist.
        # ⚠️ Parented to the ROW, not to the dialog: a test builds this through
        # __new__ to check the no-fonts state, and a QObject parented to a QWidget
        # whose super().__init__ never ran raises rather than being disabled.
        row = QWidget()
        self.keycap_group = QButtonGroup(row)
        self.keycap_group.setExclusive(True)
        self.keycap_buttons = {}
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        real_ok = usable and oled_look.available()
        for mode, text, hint in (
            # TRANSLATORS: keycap display mode -- show the raw keycode text.
            (KEYCAP_SYMBOL, _("Symbol"), _("Every key shows its keycode.")),
            # TRANSLATORS: keycap display mode -- the rendered keycap image.
            (KEYCAP_PREVIEW, _("Preview"), tip),
            # TRANSLATORS: keycap display mode -- the keycap through the panel simulation.
            (KEYCAP_REAL, _("Real"), tip + "\n\n" + _("Through the panel simulation: emissive "
                                                       "pixels, bloom and the diffusion of the clear "
                                                       "keycap cover — how the key actually reads.")),
        ):
            b = QToolButton(row)
            b.setText(text)
            b.setCheckable(True)
            b.setToolTip(hint if mode == KEYCAP_SYMBOL or usable else tip)
            # ⚠️ Symbol stays available even with no fonts: it is the FALLBACK, so
            # disabling it would leave the group with nothing selectable at all.
            b.setEnabled(True if mode == KEYCAP_SYMBOL
                         else (real_ok if mode == KEYCAP_REAL else usable))
            b.setChecked(mode == self._keycap_mode)
            self.keycap_group.addButton(b)
            self.keycap_buttons[mode] = b
            lay.addWidget(b)
        if not oled_look.available():
            self.keycap_buttons[KEYCAP_REAL].setToolTip(
                _f("Unavailable: {reason}", reason=oled_look.reason()))
        self.keycap_group.buttonClicked.connect(self._on_keycap_button)
        self.keycap_modes = row
        return row

    def _on_keycap_button(self, button):
        for mode, b in self.keycap_buttons.items():
            if b is button:
                self.set_keycap_mode(mode)
                return

    def set_keycap_mode(self, mode):
        """Switch how every key is drawn, and repaint.

        ⚠️ Both caches hold PIXMAPS, so they have to be dropped here -- a mode change
        is exactly the thing they cannot represent, and keeping them would leave the
        board showing the previous mode until something else happened to invalidate it.
        """
        if mode == self._keycap_mode:
            return
        was_photo = self._real_board() is not None
        self._keycap_mode = mode
        self._keycap_cache.clear()
        self._key_cache.clear()
        # Real mode lays the keys out on the rendered photo, the others on the KLE
        # grid: a change between the two rebuilds the scene before it is repainted.
        if (self._real_board() is not None) != was_photo:
            self.render_keys()
        btn = self.keycap_buttons.get(mode) if hasattr(self, "keycap_buttons") else None
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)
        if self.key_buffer is not None:
            self.set_keycodes_for_layer(self.current_layer)
        else:
            # ⚠️ The panels carry the LAYER, not the keymap, so they follow a mode
            # change even when the keycodes could not be read -- the branch above is
            # the only reason they did not, and a board whose keys are locked down
            # still says which layer is selected.
            self._refresh_screens(self.current_layer)
        # every mode lays the board out differently (and Real on another scene
        # rect), so the view is put back on the middle of the board, at the
        # same zoom relative to the window
        self.view.refit()

    def _pixmap(self, img):
        """One QImage -> QPixmap step for BOTH halves of the preview.

        The macro keycaps and the firmware-composed legends are rendered by different
        code and used to convert separately, which is how a board could end up half
        simulated. Routing both through here means a mode can only ever apply to all
        of it. A failed simulation falls back to the flat keycap rather than to a
        blank key.
        """
        if img is None:
            return None
        if self._keycap_mode == KEYCAP_REAL:
            lit = oled_look.render(img, "keycap", KEYCAP_REAL_SCALE)
            if lit is not None:
                return QPixmap.fromImage(lit)
        return QPixmap.fromImage(img)

    def _tile_main(self, keycode, main):
        """The tile caption for a macro key, when no keycap is drawn over it.

        `describe_keycode` answers `MACRO(12)`, which is the right name in the
        keycode BROWSER and too long for a tile: the label item is centred and not
        clipped, so it overflows the key and the neighbouring tiles paint over its
        head -- `MACRO(0)` renders as a bare `0`, which reads like a digit key.
        `M0` is what the KEYBOARD itself draws as its fallback mark (`_index_mark`),
        so the off state of the toggle matches the hardware and fits.

        Bounded by QMK's macro range rather than the list the keyboard reported: an
        id past the end still IS a macro keycode with nothing to draw, and shortening
        its name is right for the same reason.
        """
        if 0x7700 <= keycode <= 0x777F:
            return f"M{keycode - 0x7700}"
        return main

    def _macro_index(self, keycode):
        """The macro id a keycode names, or None.

        Bounded by the number the KEYBOARD reports rather than QMK's 0x7700..0x777F
        range: the firmware ships 16, and an out-of-range id has no macro to draw.
        """
        idx = keycode - QK_MACRO
        return idx if 0 <= idx < len(self._macros) else None

    # ⚠️ 74 keys, 72 OLEDs. The inner key at matrix (3,7) on the left half and (8,0)
    # on the right have no display and no RGB LED — they sit under the rotary encoder.
    # Previewing them would promise a keycap the hardware cannot show.
    NO_DISPLAY_MATRIX = ((3, 7), (8, 0))

    def _has_display(self, idx):
        cols = self.settings.MATRIX_COLUMNS
        return all(idx != r * cols + c for r, c in self.NO_DISPLAY_MATRIX)

    def _keycap_for(self, keycode):
        """The rendered keycap for a macro keycode, or None for everything else.

        Cached per macro id: `set_keycodes_for_layer` runs over every key on every
        layer switch, and re-composing a 72x40 keycap glyph-by-glyph per key per switch
        is real work for a picture that only changes when the macro does.
        """
        if self._keycap_mode == KEYCAP_SYMBOL:
            return None
        idx = self._macro_index(keycode)
        if idx is None:
            # Not a macro: the firmware composes this legend.
            return self._preview_for(keycode)
        if self._keycap_render is None or not self._keycap_render.usable:
            return None
        hit = self._keycap_cache.get(idx)
        if hit is None:
            m = self._macros[idx]
            img = self._keycap_render.render(m.get("label", ""), m.get("style", 0),
                                             icon=m.get("icon", 0), index=m.get("id", idx))
            hit = self._pixmap(img)
            self._keycap_cache[idx] = hit
        return hit

    def _resolve(self, idx, layer):
        """The keycode at this slot, WITHOUT following a transparent fall-through.

        ⚠️ This used to walk down to the layer below, because that is what the
        keyboard shows. It reads wrong in an EDITOR: the tile then displays a keycap
        for a key that is not bound on the layer you are looking at, and the text
        beside it still says transparent — so a `=` appears on a layer where nothing
        was assigned (field, 2026-08-28: "an unrendered key saying EQL in layer 3").
        A transparent slot now previews nothing and keeps its own label.
        """
        max_idx = self.settings.MATRIX_COLUMNS * self.settings.MATRIX_ROWS
        return self.key_buffer[idx + layer * max_idx]

    def _preview_for(self, keycode):
        """The keycap for an ordinary (non-macro) keycode, or None.

        Cached INCLUDING the misses: a keycode with no preview is asked about once per
        key per layer switch, and re-deciding that costs a name lookup and two dict
        probes for an answer that cannot change while the dialog is open. `None` is a
        real cached value here, so the sentinel has to be the absence of the KEY.
        """
        if keycode in self._key_cache:
            return self._key_cache[keycode]
        name = self.keycode_browser.get_keycode_to_name_mapping().get(keycode)
        img = self._preview.render(keycode, name)
        pm = self._pixmap(img)
        self._key_cache[keycode] = pm
        return pm

    def _load_macros(self):
        """Pull the macro list the keycaps are drawn from. Never fatal -- a keyboard
        too old for macros, or a failed read, just means no key draws one."""
        try:
            ok, info = self.core.macro_list()
        except Exception:
            ok, info = False, {}
        self._macros = info.get("macros", []) if ok else []
        self._keycap_cache.clear()

    def refresh_macro_keycaps(self):
        """Re-read the macros and repaint every key showing one.

        Called when the Macros tab saves: the editor holds its own copy for rendering,
        so without this a caption edit shows on the tab's preview and on the keyboard
        while the key tile keeps the picture it drew when the dialog opened.
        """
        self._load_macros()
        if self.key_buffer is not None:
            self.set_keycodes_for_layer(self.current_layer)

    def set_keycodes_for_layer(self, layer):
        """Draw `layer` on every key, and on the two status panels.

        ⚠️ It ADOPTS the layer as `current_layer`, because it is the one that ends up
        on screen and everything else reads that attribute to mean "the layer being
        edited" -- the keycode assignment indexes the buffer with it, and a mode
        change repaints with it. It used to be written only by `layerChanged`, so
        calling this directly left the two disagreeing and the next mode switch
        silently reverted the board and both panels to whatever the last BUTTON
        click had said (measured: switch to layer 5, toggle Symbol -> Preview, get
        layer 0 back).
        """
        self.current_layer = layer
        mapping = self.keycode_browser.get_keycode_to_name_mapping()
        num_keys = len(self.keys)
        max_idx = self.settings.MATRIX_COLUMNS*self.settings.MATRIX_ROWS
        offset = layer*max_idx
        photo = self._real_board() is not None
        idx = 0
        for _key in range(num_keys):
            # skip matrix positions without junctions (no physical key)
            while idx not in self.keys and idx < max_idx:
                idx += 1
            keycode = self.key_buffer[idx + offset]
            self._show_key(self.keys[idx], idx, keycode, self._resolve(idx, layer),
                           mapping, photo)
            idx += 1
        # The status panels name the layer, so they follow it -- and this is the one
        # path both a layer change and a mode change go through.
        self._refresh_screens(layer)

    def layerChanged(self, button):
        self.current_layer = self.layers.group.id(button)
        self.set_keycodes_for_layer(self.current_layer)
        
    # call this from your MainWindow (e.g., at end of init_ui)
    def set_preferred_size(self, pref_w, pref_h):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()

        # if preferred fits, use it; otherwise clamp to available size
        if geom.width() >= pref_w and geom.height() >= pref_h:
            w, h = pref_w, pref_h
        else:
            w = min(pref_w, geom.width())
            h = min(pref_h, geom.height())

        self.resize(w, h)

        # center on that screen's available area
        x = geom.x() + (geom.width() - w) // 2
        y = geom.y() + (geom.height() - h) // 2
        self.move(x, y)
    
    def zoom(self, step):
        """
        step: positive int to zoom in, negative to zoom out.
        Uses multiplicative scaling so zoom is smooth.
        """
        if step == 0:
            return
        if step > 0:
            factor = self._zoom_step ** step
        else:
            factor = (1.0 / self._zoom_step) ** (-step)

        new_scale = self.scale_factor * factor
        new_scale = max(self._zoom_min, min(self._zoom_max, new_scale))
        # the view keeps it relative to the window from here on
        self.view.zoom_by(new_scale / self.scale_factor)
        self.scale_factor = new_scale

        
    def load_from_file(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.row_count, self.col_count, self.key_matrix = parse_kle(data)
            # self.row_count, self.col_count, self.mapping = build_matrix(self.matrix_pos)
            self.render_keys()
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _f("Failed to load:\n{error}\n{details}",
                                                     error=e, details=traceback.format_exc()))
            
    # def load_kle(self):
    #     filename, _ = QFileDialog.getOpenFileName(self, "Open KLE JSON", "", "JSON (*.json)")
    #     self.load_from_file(filename)

    def mouseClickEvent(self, item):
        self.selected_key = item
        # Reflect the clicked key's current keycode in the composer so its
        # layer/modifier/tap setup is shown and ready to tweak.
        idx = item.matrix_index
        if idx is not None and self.key_buffer:
            max_idx = self.settings.MATRIX_COLUMNS * self.settings.MATRIX_ROWS
            self.keycode_browser.show_keycode(self.key_buffer[idx + self.current_layer * max_idx])

    def _show_key(self, item, idx, keycode, preview_keycode, mapping, photo):
        """Draw one key: its tile text and its keycap picture.

        The ONE place both the whole-layer redraw and a single-key edit go through,
        so the two cannot disagree about how a key looks. `preview_keycode` is what
        the picture shows: the layer redraw passes the slot's own keycode (see
        `_resolve`), an edit the keycode just assigned.
        """
        main, badge, color = describe_keycode(keycode, mapping)
        main = self._tile_main(keycode, main)
        if photo and keycode in (KC_NO, KC_TRANSPARENT):
            # nothing assigned: the keyboard shows nothing there, and neither does
            # the photo -- no "NO", "TRNS" or "______" over the picture
            main, badge = "", ""
        item.set_display(main, badge, color, 9 if len(main) < 5 else 7)
        # After set_display, which restores the text a keycap hides. The PREVIEW
        # resolves transparency; the TEXT deliberately does not, so the tile still
        # says the slot is transparent rather than claiming it holds that key.
        # On the photo every key has a picture to show: the displays their panel,
        # the two expansion-port keys their legend over the lid. None for a key
        # with no picture clears one it showed before (a key that WAS a macro).
        shown = photo or idx is None or self._has_display(idx)
        item.set_keycap(self._keycap_for(preview_keycode) if shown else None)

    def keycodeSelected(self, nice_name, name, keycode, font_size_hint):
        if self.selected_key is None:
            return
        if self.key_buffer is None:
            self.log.warning("Cannot write keycode: key buffer not initialized")
            return
        mapping = self.keycode_browser.get_keycode_to_name_mapping()
        # the same drawing rules as a whole-layer redraw, so an edit looks right at
        # once rather than after the next layer or mode switch
        self._show_key(self.selected_key, self.selected_key.matrix_index, keycode, keycode,
                       mapping, self._real_board() is not None)
        idx = self.selected_key.matrix_index
        if idx is None:
            return
        max_idx = self.settings.MATRIX_COLUMNS * self.settings.MATRIX_ROWS
        self.key_buffer[idx + self.current_layer * max_idx] = keycode
        row = idx // self.settings.MATRIX_COLUMNS
        col = idx % self.settings.MATRIX_COLUMNS
        layer = self.current_layer

        # Single-key write via the core (a quick HID write in-process, or an RPC
        # round-trip in client mode); keeps the local buffer in sync above.
        ok, _unused = self.core.keymap_set(layer, row, col, keycode)
        if not ok:
            self.log.warning("Failed to write keycode 0x%04x to device (layer=%d row=%d col=%d)",
                             keycode, layer, row, col)

            
    def _real_board(self):
        """The rendered photo for Real mode, or None (not shipped, or another mode)."""
        if self._keycap_mode != KEYCAP_REAL:
            return None
        if not hasattr(self, "_photo"):
            self._photo = real_board.load()
        return self._photo

    def render_keys(self):
        """Render keys with rotation applied"""
        selected = getattr(self.selected_key, "matrix_index", None)
        self.selected_key = None        # the scene is rebuilt: the old item is gone
        self.scene.clear()
        self.scene.setBackgroundBrush(QBrush(Qt.NoBrush))   # each mode sets its own
        
        if not self.key_matrix:
            return
        
        minx = min(p['x'] for p in self.key_matrix.values())
        miny = min(p['y'] for p in self.key_matrix.values())

        photo = self._real_board()
        if photo is not None and self._render_on_photo(photo, minx, miny):
            self._set_fit_rect(minx, miny)
            if selected is not None and selected in self.keys:
                self.keys[selected].setSelected(True)
                self.selected_key = self.keys[selected]
            return

        # The board the keys are mounted on, behind them. Decoration only, and
        # it fails soft -- see `board_plate`. Added FIRST so the plate is under
        # every key even before Z-values are considered.
        self._add_board(minx, miny)

        for name, info in self.key_matrix.items():
            index = info["row"] * self.settings.MATRIX_COLUMNS + info["col"]
            item = RenderableKey(name, info, KEY_SCALE, matrix_index=index)
            item.pressed.connect(self.mouseClickEvent)
            self.keys[index] = item
            item.setTransform(key_transform(info, minx, miny, KEY_SCALE))
            self.scene.addItem(item)
        
        self.view.setSceneRect(self.scene.itemsBoundingRect())
        self._set_fit_rect(minx, miny)
        if selected is not None and selected in self.keys:
            self.keys[selected].setSelected(True)
            self.selected_key = self.keys[selected]

    def _set_fit_rect(self, minx, miny):
        """What a relative zoom of 1 shows, and the scene rect: the board at
        ONE size in every mode, so a mode switch keeps the keyboard's size.

        The SIZE is the KLE layout's (every key's tile on the grid, plus a
        margin for the case), whatever the mode draws; it is centred on the
        keys as this mode places them. Fitting each mode's own scene rect
        showed the keyboard at different sizes: the photo carries a white
        margin the drawn board does not, and on the photo a key's extent is
        its display, not its tile. The keys themselves come out the same size
        in both layouts (KEY_SCALE per U, the photo by its mm_per_px).
        """
        kle, here = QRectF(), QRectF()
        for name, info in self.key_matrix.items():
            index = info["row"] * self.settings.MATRIX_COLUMNS + info["col"]
            item = self.keys.get(index)
            if item is None:
                continue
            kle = kle.united(key_transform(info, minx, miny, KEY_SCALE).mapRect(item.boundingRect()))
            here = here.united(item.sceneBoundingRect())
        if not kle.isValid():
            self.view.fit_rect = None
            return
        fit = kle.adjusted(-FIT_PAD, -FIT_PAD, FIT_PAD, FIT_PAD)
        fit.moveCenter(here.center())
        self.view.fit_rect = fit
        # the scene rect with it: the photo's white margin beyond the case put
        # scroll bars on a fully visible board and let it pan into nothing
        self.view.setSceneRect(fit)

    def _render_on_photo(self, photo, minx, miny):
        """Real mode on the rendered top view: every key on its photographed OLED.

        See `real_board`. Returns False (and leaves the scene to the normal path)
        when the photo cannot be shown, so Real mode never ends up with no board.
        """
        items = real_board.add_photo(self.scene, photo, KEY_SCALE)
        if not items:
            self.scene.clear()
            return False
        self._board_items = items
        pairs = {"left": [], "right": []}
        loose, placed = [], []
        for name, info in self.key_matrix.items():
            index = info["row"] * self.settings.MATRIX_COLUMNS + info["col"]
            item = RenderableKey(name, info, KEY_SCALE, matrix_index=index)
            item.pressed.connect(self.mouseClickEvent)
            self.keys[index] = item
            kle = key_transform(info, minx, miny, KEY_SCALE)
            side = "left" if info["row"] < self.settings.MATRIX_ROWS // 2 else "right"
            key = (info["row"], info["col"])
            t = None
            if key in photo.quads:
                t = real_board.quad_transform(item.display_rect(), photo.scene_quad(key, KEY_SCALE))
            if t is not None:
                item.setTransform(t)
                item.set_photo_mode(True)
                placed.append((t, item))
                c = QRectF(item.display_rect()).center()
                pairs[side].append((kle.map(c), t.map(c)))
            else:
                loose.append((item, kle, side))
            self.scene.addItem(item)
        # how much a key's display rect shrinks onto its photographed OLED
        panel = sum(math.hypot(t.m11(), t.m12()) for t, _ in placed) / max(1, len(placed))
        # the keys without a display: a label alone, centred on the half's
        # expansion-port lid and turned with it (or, without lid data, their KLE
        # place moved by the half's fit)
        for item, kle, side in loose:
            item.set_label_only(True)
            pose = photo.port_pose(side, KEY_SCALE)
            if pose is None:
                item.setTransform(kle * real_board.fit_affine(pairs[side]))
                continue
            centre, angle = pose
            anchor = item.label_anchor()
            t = QTransform()
            t.translate(centre.x(), centre.y())
            t.rotate(angle)
            # the legend at the size of the photographed displays around it, not
            # of the editor's tile (about twice that)
            t.scale(panel, panel)
            t.translate(-anchor.x(), -anchor.y())
            item.setTransform(t)
        # the photo is rendered on pure white, so a white scene leaves no edge
        # around it at any zoom
        self.scene.setBackgroundBrush(QBrush(Qt.white))
        self.view.setSceneRect(real_board.scene_rect(photo, KEY_SCALE))
        self._refresh_screens(self.current_layer)
        return True

    def _add_board(self, minx, miny):
        """Draw the board outline + status screens under the keys.

        Reads the theme from the live palette rather than the `ui_theme`
        setting: the setting is `auto` on most installs and does not move when
        Windows flips, while the palette is what was actually applied.
        """
        self._board_items = []
        try:
            dark = gui_theme.is_dark(self.palette())
            self._board_items = add_board(self.scene, KEY_SCALE, minx, miny, dark=dark)
            self._refresh_screens(self.current_layer)
        except Exception:
            self.log.debug("board outline not drawn", exc_info=True)

    def _refresh_screens(self, layer):
        """Paint the layer being edited onto the two status panels.

        Follows the SAME Symbol / Preview / Real control the keys do: Symbol clears
        them back to the plain lit rectangle, Preview draws the panel, Real puts it
        through the simulation. ⚠️ With the **`oled`** preset, not `keycap` -- there is
        no keycap over a status display, so the cover's diffusion would be modelling
        something that is not there.

        The layer being edited goes in the LAYOUT-name slot. On hardware that row
        names the base layout; here it names the layer, which is what an editor
        wants and is the one place this panel departs from the firmware's.

        Decoration, so it fails soft the same way the plate does: a renderer that
        cannot load leaves the rectangles plain and the editor unchanged.
        """
        if not self._board_items:
            return
        try:
            if self._keycap_mode == KEYCAP_SYMBOL:
                set_screen_images(self._board_items, {})
                return
            if self._status_render is None:
                self._status_render = StatusScreenRenderer(self._preview.status_faces())
            if not self._status_render.usable:
                set_screen_images(self._board_items, {})
                return
            name = self._layer_name(layer)
            shots = {}
            for side in ("left", "right"):
                img = self._status_render.render(side, layer, name)
                if self._keycap_mode == KEYCAP_REAL:
                    img = oled_look.render(img, "oled", ssr.REAL_SCALE) or img
                shots[side] = img
            set_screen_images(self._board_items, shots)
        except Exception:
            self.log.debug("status screens not drawn", exc_info=True)

    def _pixmaps_possible(self) -> bool:
        """Whether the status panels can be drawn at all (the UI faces loaded).

        Exists so a test can SKIP rather than assert a blank board on an install
        without the preview export -- the editor itself just leaves them flat.
        """
        if self._status_render is None:
            self._status_render = StatusScreenRenderer(self._preview.status_faces())
        return self._status_render.usable

    def _layer_name(self, layer):
        """What the panel calls this layer -- the same string the layer tab shows.

        Cached: `_layer_names` asks the KEYBOARD (cmd 35), and a layer change must
        not cost an HID round trip to relabel a decoration.
        """
        names = getattr(self, "_layer_name_cache", None)
        if names is None:
            try:
                names = self._layer_names()
            except Exception:
                names = {}
            self._layer_name_cache = names
        return names.get(layer, "")


