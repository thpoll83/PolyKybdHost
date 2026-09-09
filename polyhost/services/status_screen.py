"""What the split72 status OLED shows, for the layout editor's board preview.

The editor draws the two 0.96" panels the halves carry (see
`scripts/export_board_outline.py`), and they were flat rectangles: the picture said
"there is a screen here" and nothing else. This composes the part of that screen the
EDITOR actually knows, so the panel shows the layer you are editing.

⚠️ **A SUBSET, deliberately — this is not a mirror of `oled_update_buffer`.** The real
panel also carries the RGB effect, WPM, brightness, the language and the lock LEDs, and
every one of those is live device state the editor does not have. Drawing placeholders
for them would put numbers on screen that are not true of anything, so those rows are
left dark. What is drawn is drawn at the FIRMWARE's own coordinates (the constants
below are `split72/status_oled.c`'s, and `qmk_firmware/keyboards/polykybd/tools/
status_oled_preview.py` is the faithful whole-panel renderer to check against):

* the top row -- `ICON_LAYER` plus the active layer's hex digit, and the L/R side
  marker on the inner edge;
* the layout-name row, on the layout (USB) panel only.

⚠️ One honest departure, because the editor has no default layer: hardware names the
BASE layout there (`Qwerty`), while this names the layer being edited. For layers 0..4
that is the same string; above them it says `Fn` / `Numpad` / `Utility`, which is more
use in an editor than repeating the base layout would be.

Qt-free and pixel-exact: `render()` returns the lit pixels, so it can be tested without
a display and drawn by whoever wants it.
"""

from __future__ import annotations

from polyhost.services import macro_look as mk

#: The split72 status panel. split42's is 128x32 and mounted rotated, which is a
#: different composer entirely (`split42/status_oled.c` draws in a portrait space) --
#: this covers the board the editor draws.
PANEL_W, PANEL_H = 128, 64

#: Baselines and columns from `split72/status_oled.c` `oled_update_buffer`.
TOP_BASE = 15           # layer icon / hex layer / role
LOCK_ROW_B = 29         # layout name
SIDE_MARKER_BASE = 63   # the physical-side marker, bottomed out
LAYER_DIGIT_X = 20      # from the panel's text origin
ICON_LAYER = 0x80

#: Each half's indicator column sits on its INNER edge, so the text origin and the
#: marker column differ per panel: (text_x, col_x, marker_dx).
SIDES = {"left": (0, 108, 6), "right": (20, 0, 5)}


def render(layer: int, layer_name: str, side: str, faces: dict):
    """The lit pixels of one panel, as a set of (x, y).

    `faces` wants `icons` (IconsFont), `mid` (`_Mid_` 19px) and `small` (`_Small_`
    15px) -- the same three the firmware draws these rows with. A missing face drops
    the elements that need it rather than failing: the panel is decoration, and a
    partial screen still says which layer is selected.
    """
    text_x, col_x, marker_dx = SIDES.get(side, SIDES["left"])
    pts: set = set()

    icons, mid, small = faces.get("icons"), faces.get("mid"), faces.get("small")
    _draw(pts, icons, text_x, TOP_BASE, chr(ICON_LAYER))
    # Hex, as the firmware prints it -- there are twelve layers and the row has room
    # for one character.
    _draw(pts, mid, text_x + LAYER_DIGIT_X, TOP_BASE, "%X" % max(0, layer))
    _draw(pts, small, col_x + marker_dx, SIDE_MARKER_BASE,
          "L" if side == "left" else "R")
    if side == "left" and layer_name:
        _draw(pts, small, text_x, LOCK_ROW_B, layer_name)
    return pts


def _draw(pts: set, font, x: int, baseline: int, text: str):
    """Plot `text` at (x, baseline) through ONE face, column-native.

    The firmware draws each of these rows through a single-font array, so there is no
    front-to-back pool and no `fonts[0]` baseline shift to fold in -- which is exactly
    why these three faces are unreachable by codepoint in the first place.

    Pixels outside the panel are DROPPED rather than clipped into range: the hardware's
    `SET_PIXEL_CLIPPED` drops them too, so a row that no longer fits goes missing here
    the same way it would on the board.
    """
    if font is None:
        return
    for ch in text:
        hit = mk.find_glyph([font], ord(ch))
        if hit is None:
            continue
        f, g = hit
        bo, cb = g["bitmapOffset"], (g["height"] + 7) >> 3      # column-native
        for gx in range(g["width"]):
            col = bo + gx * cb
            for gy in range(g["height"]):
                if f.bitmap[col + (gy >> 3)] & (1 << (gy & 7)):
                    px, py = x + g["xOffset"] + gx, baseline + g["yOffset"] + gy
                    if 0 <= px < PANEL_W and 0 <= py < PANEL_H:
                        pts.add((px, py))
        x += g["xAdvance"]
