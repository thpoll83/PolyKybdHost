"""The split72 board shape the layout editor draws its keys on -- Qt-free.

`polyhost/res/board_outline.json` is generated from the PolyKybd hardware repo
by `scripts/export_board_outline.py`: the CASE contour of each half and the
placement of the optional 0.96" status display, both in the same key-unit frame
as `res/polykybd-split72.json`. `bezel_u` is the one key-to-case margin the
outline is fitted to on all four sides -- see the exporter for why that is a
deliberate stylisation rather than the case's own uneven margins.

⚠️ Everything here fails SOFT. The board shape is decoration -- it says which
half a key is on and where the screens are, and nothing depends on it -- so a
missing or malformed file costs the picture and never the editor. `load()`
returns None and the caller draws the keys exactly as it did before.
"""
import json
import logging
import pathlib

__all__ = ["BOARD_FILE", "Display", "Half", "Board", "load"]

BOARD_FILE = pathlib.Path(__file__).resolve().parent.parent / "res" / "board_outline.json"

_log = logging.getLogger("PolyHost")


class Display:
    """One status panel: the glass, and the lit area inside it, in key units."""

    __slots__ = ("cx", "cy", "w", "h", "aw", "ah")

    def __init__(self, cx, cy, w, h, aw, ah):
        self.cx, self.cy, self.w, self.h, self.aw, self.ah = cx, cy, w, h, aw, ah

    @property
    def rect(self):
        """(x, y, w, h) of the glass, top-left anchored."""
        return (self.cx - self.w / 2.0, self.cy - self.h / 2.0, self.w, self.h)

    @property
    def active_rect(self):
        """(x, y, w, h) of the lit area, centred in the glass."""
        return (self.cx - self.aw / 2.0, self.cy - self.ah / 2.0, self.aw, self.ah)


class Half:
    __slots__ = ("side", "outline", "displays")

    def __init__(self, side, outline, displays):
        self.side, self.outline, self.displays = side, outline, displays


class Board:
    __slots__ = ("board", "unit_mm", "bezel_u", "source", "halves")

    def __init__(self, board, unit_mm, bezel_u, source, halves):
        self.board, self.unit_mm, self.bezel_u = board, unit_mm, bezel_u
        self.source, self.halves = source, halves


def load(path=None):
    """Read the shipped board description, or None when it is unusable."""
    path = pathlib.Path(path) if path else BOARD_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        halves = []
        for h in data["halves"]:
            outline = [(float(x), float(y)) for x, y in h["outline"]]
            if len(outline) < 3:
                raise ValueError("half %r has a %d-point outline" % (h.get("side"), len(outline)))
            halves.append(Half(
                str(h["side"]), outline,
                [Display(float(d["cx"]), float(d["cy"]), float(d["w"]), float(d["h"]),
                         float(d["aw"]), float(d["ah"])) for d in h.get("displays", [])]))
        if not halves:
            raise ValueError("no halves")
        return Board(str(data.get("board", "")), float(data.get("unit_mm", 19.05)),
                     float(data.get("bezel_u", 0.0)), str(data.get("source", "")), halves)
    except Exception as exc:                                  # noqa: BLE001
        # Decoration: say why once, then let the editor draw bare keys.
        _log.debug("board outline unavailable (%s): %s", path, exc)
        return None
