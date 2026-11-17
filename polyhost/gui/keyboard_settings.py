"""Settings > Keyboard: the settings stored on the keyboard itself.

Idle display, idle timeout, keycap script and its placement, keycap size and the
tap-hold terms are not in settings.yaml. The keyboard stores them, so the
Settings dialog reads them from the keyboard when it opens (off the GUI thread,
``PolyHost.open_settings``) and sends only what changed when the user clicks OK.

Each value has a pseudo key that starts with ``kbd_``. The dialog places these
keys like settings keys (``settings_dialog.SECTIONS``), but they are never
written to settings.yaml: ``SettingsDialog.get_updated_settings`` leaves them
out and ``keyboard_changes`` returns them.
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QButtonGroup, QToolButton, QWidget

from polyhost.device.command_ids import (GlyphPlacement, GlyphScript, GlyphSize, IdleStyle,
                                         IdleTimeout, TapTerms)
from polyhost.gui.flow_layout import FlowLayout
from polyhost.gui.menu_tiles import wrap_caption
from polyhost.gui.ui_kit import px
from polyhost.i18n import N_, _

# Tray labels for the keycap scripts. Generic names (no franchise branding,
# trademark caveat on the fictional scripts); the fonts themselves are OK to
# embed. Keys cover every GlyphScript. The tiles are shown in THIS dict's order,
# not the enum's: the enum values are on the wire and in the keyboard's EEPROM,
# so they are append-only, but related scripts belong together (the two
# Commodore 64 faces, 7 and 11).
GLYPH_SCRIPT_LABELS = {
    GlyphScript.STANDARD: N_("Standard (normal legends)"),
    GlyphScript.TENGWAR:  N_("Tengwar (fantasy)"),
    GlyphScript.RUNES:    N_("Elder Futhark runes"),
    GlyphScript.AUREBESH: N_("Aurebesh (sci-fi)"),
    GlyphScript.SGA:      N_("Standard Galactic"),
    GlyphScript.CIRTH:    N_("Cirth / Angerthas"),
    GlyphScript.IBMVGA:   N_("IBM VGA / CP437"),
    GlyphScript.C64:      N_("Commodore 64 (screen)"),
    GlyphScript.C64KEYS:  N_("Commodore 64 (keycap)"),
    GlyphScript.AMIGA:    N_("Amiga Topaz"),
    GlyphScript.APL:      N_("APL"),
    GlyphScript.BRAILLE:  N_("Braille"),
}

# Shorter captions for the script tiles, where the description in brackets
# does not fit under a keycap. A script not listed uses its full label.
GLYPH_SCRIPT_TILE_LABELS = {
    GlyphScript.STANDARD: N_("Standard"),
    GlyphScript.TENGWAR:  N_("Tengwar"),
    GlyphScript.RUNES:    N_("Runes"),
    GlyphScript.AUREBESH: N_("Aurebesh"),
    GlyphScript.CIRTH:    N_("Cirth"),
    GlyphScript.IBMVGA:   N_("IBM VGA"),
    GlyphScript.C64:      N_("C64 screen"),
    GlyphScript.C64KEYS:  N_("C64 keycap"),
    GlyphScript.AMIGA:    N_("Amiga Topaz"),
}

# Keys cover every GlyphSize. Worded as what the user sees on the keycap.
GLYPH_SIZE_LABELS = {
    GlyphSize.SMALL:  N_("Small (standard)"),
    GlyphSize.MEDIUM: N_("Medium"),
    GlyphSize.LARGE:  N_("Large"),
}

IDLE_STYLE_LABELS = {
    IdleStyle.PULSE:  N_("Pulse"),
    IdleStyle.JITTER: N_("Jitter"),
    IdleStyle.IDDQD:  "IDDQD",
    IdleStyle.EDEN:   N_("Eden"),
}

# The pseudo keys, in the order the dialog shows them.
IDLE_STYLE = "kbd_idle_style"
IDLE_TIMEOUT = "kbd_idle_timeout"
GLYPH_SCRIPT = "kbd_glyph_script"
GLYPH_PLACEMENT = "kbd_glyph_placement"
GLYPH_SIZE = "kbd_glyph_size"
TAPPING_TERM = "kbd_tapping_term"
FLOW_TAP_TERM = "kbd_flow_tap_term"
AUTO_SHIFT = "kbd_auto_shift"
AUTO_SHIFT_MS = "kbd_auto_shift_ms"
KEYS = (IDLE_STYLE, IDLE_TIMEOUT, GLYPH_SCRIPT, GLYPH_PLACEMENT, GLYPH_SIZE,
        TAPPING_TERM, FLOW_TAP_TERM, AUTO_SHIFT, AUTO_SHIFT_MS)
TAP_KEYS = (TAPPING_TERM, FLOW_TAP_TERM, AUTO_SHIFT, AUTO_SHIFT_MS)

# The core getter for each read. The dialog asks all of them in one background
# call, see read_all().
READS = ("idle_style", "idle_timeout", "glyph_script", "glyph_placement", "glyph_size",
         "tap_terms")


def read_all(core):
    """{read name: (ok, value)} from the keyboard. Runs OFF the GUI thread: in
    client mode each call is an RPC with no timeout. An exception is kept as the
    result of that read, so one failure does not hide the others."""
    out = {}
    for name in READS:
        try:
            out[name] = getattr(core, f"get_{name}")()
        except Exception as exc:  # noqa: BLE001 — shown as "could not read"
            out[name] = (False, str(exc))
    return out


def _ok_value(result):
    """(ok, value) from a core answer; JSON over RPC turns a tuple into a list."""
    if isinstance(result, (tuple, list)) and len(result) == 2:
        return bool(result[0]), result[1]
    return False, result


def values_from_reads(reads):
    """{pseudo key: value} for each read that succeeded, and {pseudo key: reason}
    for each that failed. A key whose firmware has no such setting (Flow Tap,
    Auto Shift) is in neither: its row stays disabled with its own reason."""
    values, failed = {}, {}

    def put(key, ok, value):
        if ok:
            values[key] = value
        else:
            failed[key] = str(value)

    for name, key in (("idle_style", IDLE_STYLE), ("glyph_script", GLYPH_SCRIPT),
                      ("glyph_placement", GLYPH_PLACEMENT), ("glyph_size", GLYPH_SIZE)):
        ok, value = _ok_value(reads.get(name))
        put(key, ok, int(value) if ok else value)
    ok, value = _ok_value(reads.get("idle_timeout"))
    # (preset index, seconds); the preset is what the host sends back.
    put(IDLE_TIMEOUT, ok and bool(value), int(value[0]) if ok and value else value)
    ok, terms = _ok_value(reads.get("tap_terms"))
    if not ok or not isinstance(terms, dict):
        for key in TAP_KEYS:
            failed[key] = str(terms)
        return values, failed
    values[TAPPING_TERM] = int(terms.get("tapping_term", TapTerms.DEFAULT_TAPPING_MS))
    if terms.get("flow_tap_available", True):
        values[FLOW_TAP_TERM] = int(terms.get("flow_tap_term", TapTerms.DEFAULT_FLOW_TAP_MS))
    if terms.get("auto_shift_available", False):
        values[AUTO_SHIFT] = bool(terms.get("auto_shift", False))
        values[AUTO_SHIFT_MS] = int(terms.get("auto_shift_ms", TapTerms.DEFAULT_AUTO_SHIFT_MS))
    return values, failed


def snap_ms(value):
    """A typed value is not forced onto the 10 ms grid by QSpinBox; send the
    nearest step, as the old Tap-Hold Timing dialog did."""
    step = TapTerms.STEP_MS
    return int(round(value / step)) * step


def tap_terms_call(changes):
    """The set_tap_terms arguments for the changed tap keys (None keeps a value),
    or None when no tap key changed. One call sends all of them."""
    if not any(k in changes for k in TAP_KEYS):
        return None
    return (changes.get(TAPPING_TERM), changes.get(FLOW_TAP_TERM),
            changes.get(AUTO_SHIFT), changes.get(AUTO_SHIFT_MS))


class TileChoice(QWidget):
    """One choice out of several, as keycap pictures with a caption below.

    The same picture tiles as the tray submenus had. The tiles wrap to the next
    line when the dialog is narrow."""

    changed = pyqtSignal()

    _STYLE = """
    QToolButton { padding: 4px; border: 2px solid transparent; border-radius: 6px; }
    QToolButton:hover { background: palette(midlight); }
    QToolButton:checked { border-color: palette(highlight); background: palette(base); }
    QToolButton:disabled { color: palette(mid); }
    """

    def __init__(self, choices, icon_size, parent=None):
        """``choices`` is [(value, caption, tooltip, icon)]."""
        super().__init__(parent)
        self.setStyleSheet(self._STYLE)
        self.setProperty("wideEditor", True)
        layout = FlowLayout(self, margin=0, spacing=px(4))
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        width = icon_size.width() + px(20)
        for value, caption, tooltip, icon in choices:
            button = QToolButton(self)
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.setAutoRaise(True)
            button.setCheckable(True)
            button.setIconSize(icon_size)
            button.setFixedWidth(width)
            if icon is not None:
                button.setIcon(icon)
            # Two lines at most, as the tray's tiles: "Standard Galactic".
            button.setText(wrap_caption(caption, button.fontMetrics(), width - px(24)))
            button.setToolTip(tooltip or "")
            button.setAccessibleName(tooltip or caption)
            self._group.addButton(button)
            self._buttons[value] = button
            layout.addWidget(button)
        # noinspection PyUnresolvedReferences
        self._group.buttonClicked.connect(lambda _b: self.changed.emit())

    def value(self):
        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return None

    def set_value(self, value):
        button = self._buttons.get(value)
        if button is None:
            # A value this host does not know (a newer firmware's script): no
            # tile is ticked, and an untouched choice is not sent back.
            self._group.setExclusive(False)
            for b in self._buttons.values():
                b.setChecked(False)
            self._group.setExclusive(True)
        else:
            button.setChecked(True)

    def buttons(self):
        return dict(self._buttons)


def _tile_icons(panels):
    from polyhost.gui import keycap_tiles
    return [keycap_tiles.to_icon(p) for p in panels]


def make_idle_style_editor():
    from polyhost.gui import keycap_tiles
    styles = list(IDLE_STYLE_LABELS)
    icons = _tile_icons([keycap_tiles.idle_panel(s.value) for s in styles])
    return TileChoice([(s.value, _(IDLE_STYLE_LABELS[s]), None, icon)
                       for s, icon in zip(styles, icons)], keycap_tiles.tile_size())


def make_glyph_script_editor():
    from polyhost.gui import keycap_tiles
    scripts = list(GLYPH_SCRIPT_LABELS)
    icons = _tile_icons([keycap_tiles.script_panel(s.value) for s in scripts])
    choices = []
    for script, icon in zip(scripts, icons):
        full = _(GLYPH_SCRIPT_LABELS[script])
        short = _(GLYPH_SCRIPT_TILE_LABELS.get(script, GLYPH_SCRIPT_LABELS[script]))
        choices.append((script.value, short, full if full != short else None, icon))
    return TileChoice(choices, keycap_tiles.tile_size())


def make_glyph_size_editor():
    from polyhost.gui import keycap_tiles
    sizes = list(GlyphSize)
    icons = _tile_icons(keycap_tiles.size_panels([s.value for s in sizes]))
    captions = {GlyphSize.SMALL: N_("Small"), GlyphSize.MEDIUM: N_("Medium"),
                GlyphSize.LARGE: N_("Large")}
    return TileChoice([(s.value, _(captions[s]), _(GLYPH_SIZE_LABELS[s]), icon)
                       for s, icon in zip(sizes, icons)], keycap_tiles.tile_size())


def idle_timeout_choices():
    """[(preset value, label)] for the Idle after list."""
    return [(p.value, IdleTimeout.label_for(p.value, p.seconds, tr=_)) for p in IdleTimeout]


def glyph_placement_choices():
    return [(GlyphPlacement.CENTRE.value, _("Centred on the keycap")),
            (GlyphPlacement.TOP_LEFT.value, _("In the top-left corner"))]

