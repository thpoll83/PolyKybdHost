"""Render an agent card: the 72x40 1-bit image a number key shows in AI mode.

    +------------------------------------+
    | [mark] title, first words          |   line 1  rows  0..12
    | the title goes on, full width      |   line 2  rows 13..25
    | and ends with '…' when it is cut   |   line 3  rows 26..39
    +------------------------------------+

The vendor mark is the lower 12 rows of the logo at 26 px, cut by the top edge
(2026-11-18), top left, with the text 1 px to its right; only
line 1 is beside it, lines 2 and 3 use the full width. A cloud session's mark has a cloud outline drawn over the logo's
lower right, inside the logo's box (with_cloud). Marks are never scaled. Three lines of 14 px text
(card experiments, 2026-11-17). The state icon (12 px) is in the bottom right
corner on every page, with a cleared margin of ICON_CLEAR px; only line 3 meets it,
and ends before that margin.

One page per card: a title that does not fit ends with '…'. The controller draws
a session title's subject words (model.card_words). Text breaks at spaces and after
'-'; only a word wider than the key is split between letters. Text is Pillow's bundled sans font (Aileron)
drawn without anti-aliasing.

The result is 360 bytes, the same packing as OverlayData.all_bytes (np.packbits,
row-major, MSB first), uploaded with cmd 46 straight into a pool slot.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass

from polyhost.services.agents.model import AgentState, vendor

log = logging.getLogger("PolyHost")

PANEL_W, PANEL_H = 72, 40
MARK_BOX = 26          # a logo is rendered at this size; its lower part shows
MARK_SHOWN = 12        # rows of the logo shown at the top edge: beside line 1 only
MARK_GAP = 1           # px between the mark and the text beside it
FONT_SIZE = 14
LINE_PITCH = 13        # three lines in 40 rows; a descender may touch the cap below
LINES = 3
TEXT_W = PANEL_W - 2   # a full-width line: 1 px margin each side
ICON = 12              # the state icon, bottom right: it touches line 3 only
ICON_CLEAR = 1         # px kept free left of and above the state icon
MAX_PAGES = 1          # one page; a longer title ends with '…'
_FONTS = {}


def _font(size: int = FONT_SIZE):
    """Pillow's bundled sans (Aileron) at `size` px; the bitmap face if Pillow was
    built without FreeType."""
    if size not in _FONTS:
        from PIL import ImageFont
        try:
            _FONTS[size] = ImageFont.load_default(size=size)
        except (TypeError, OSError):
            _FONTS[size] = ImageFont.load_default_imagefont()
    return _FONTS[size]


def _draw(img):
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1"     # no anti-aliasing: the panel is 1 bit
    return draw


def _measure(text, size=FONT_SIZE):
    """(left, top, right, bottom) of `text` as drawn WITHOUT anti-aliasing.
    ⚠️ Not font.getbbox(): with fontmode "1" the hinting differs, and getbbox read
    "polykybd-docs" as 65 px wide when it draws 76 px, so the headline was clipped."""
    from PIL import Image, ImageDraw
    draw = ImageDraw.Draw(Image.new("1", (1, 1)))
    draw.fontmode = "1"
    return draw.textbbox((0, 0), text, font=_font(size))


def _text_centred(draw, text, y, size=FONT_SIZE):
    box = _measure(text, size)
    draw.text(((PANEL_W - (box[2] - box[0])) // 2 - box[0], y), text, font=_font(size), fill=1)


def fit_text(text: str, width: int = TEXT_W, size: int = FONT_SIZE) -> str:
    """Cut `text` to what fits `width` pixels in the card font, with a trailing '.'."""
    text = " ".join((text or "").split())
    if _measure(text, size)[2] <= width:
        return text
    while text and _measure(text + ".", size)[2] > width:
        text = text[:-1]
    return text.rstrip() + "."


def _cut_with_ellipsis(text: str, width: int, size: int = FONT_SIZE) -> str:
    """`text` cut to what fits `width` pixels, ending with '…'."""
    text = text.rstrip()
    while text and _ink_width(text + "\u2026", size) > width:
        text = text[:-1].rstrip()
    return text + "\u2026"


def _ink_width(text: str, size: int = FONT_SIZE) -> int:
    box = _measure(text, size)
    return box[2] - box[0]


def _tokens(text: str) -> list[tuple[str, bool]]:
    """(token, a space follows) pairs: words, split after each '-'."""
    text = " ".join((text or "").split())
    return [(m.group(1), bool(m.group(2))) for m in re.finditer(r"([^ \-]+-?|-)( ?)", text)]


def flow(text: str, widths, size: int = FONT_SIZE, full: int = TEXT_W) -> list[str]:
    """`text` in lines; line k is `widths[k]` px wide (the last width repeats).
    Lines break at spaces and after '-'. A token that does not fit a narrower line
    moves down to the first line wide enough (the line it leaves stays empty);
    only a token wider than `full` is split between letters."""
    lines, cur, space = [], "", False

    def width():
        return widths[min(len(lines), len(widths) - 1)]

    for tok, space_after in _tokens(text):
        cand = cur + (" " if cur and space else "") + tok
        space = space_after
        if _ink_width(cand, size) <= width():
            cur = cand
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while _ink_width(tok, size) > width() and _ink_width(tok, size) <= full:
            lines.append("")
        while _ink_width(tok, size) > width():
            n = len(tok)
            while n > 1 and _ink_width(tok[:n], size) > width():
                n -= 1
            lines.append(tok[:n])
            tok = tok[n:]
        cur = tok
    if cur:
        lines.append(cur)
    return lines


def _spans(mark, icon) -> list[tuple[int, int]]:
    """(left, right) x of each text line (right exclusive): a line whose rows meet
    the vendor mark (top left) starts MARK_GAP right of it, a line that meets the
    state icon (bottom right) or its cleared margin ends before them."""
    spans = []
    for k in range(LINES):
        top = k * LINE_PITCH
        left, right = 1, PANEL_W - 1
        if mark is not None and top < mark.shape[0]:
            left = mark.shape[1] + MARK_GAP
        if icon is not None and top + LINE_PITCH > PANEL_H - icon.shape[0] - ICON_CLEAR:
            right = PANEL_W - icon.shape[1] - ICON_CLEAR
        spans.append((left, right))
    return spans


def _beside(mask) -> int:
    """How many text lines sit right of a mark this tall."""
    if mask is None:
        return 0
    return min(LINES, -(-mask.shape[0] // LINE_PITCH))   # 1..13 rows: 1, 14..26: 2


def paginate(text: str, mask=None, icon=None, size: int = FONT_SIZE) -> list[list[str]]:
    """The pages of a card: lists of at most LINES lines. Each line is as wide as
    _spans allows: the vendor mark narrows lines on page 1 only, the state icon on
    every page. One flow over all pages, cut every LINES lines: a break after '-'
    or inside a long word stays as it is on the next page."""
    first = [r - l for l, r in _spans(mask, icon)]
    later = [r - l for l, r in _spans(None, icon)]
    # Enough lines for any title: each line holds at least one character.
    widths = first + later * (len(text or "") // LINES + 2)
    lines = flow(text, widths, size)
    pages = [lines[i:i + LINES] for i in range(0, max(1, len(lines)), LINES)]
    if len(pages) > MAX_PAGES:
        pages = pages[:MAX_PAGES]
        last = len(pages[-1]) - 1
        # Its own line's width: the state icon can make it shorter than TEXT_W.
        pages[-1][last] = _cut_with_ellipsis(pages[-1][last], later[last], size)
    return pages


# A vendor slug "agent:<name>" is a finished card mark shipped as
# res/icons/agents/<name>.png (tools/gen_agent_marks.py), for vendors that
# Simple Icons and MDI do not carry. It is used as it is, never scaled.
AGENT_MARK_PREFIX = "agent:"
AGENT_MARK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "res", "icons", "agents")


def _crop(mask):
    rows, cols = mask.any(1).nonzero()[0], mask.any(0).nonzero()[0]
    if not len(rows):
        return None
    return mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


def _shipped_mark(name: str):
    """A shipped mark (res/icons/agents/), as it is: drawn for the card, at most
    MARK_SHOWN rows tall."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(os.path.join(AGENT_MARK_DIR, name + ".png")) as img:
            mask = np.array(img.convert("L")) > 127
    except Exception as e:  # noqa: BLE001 - cosmetic: fall back to the next slug
        log.debug("Agent mark %s: %s", name, e)
        return None
    return _crop(mask[-MARK_SHOWN:]) if mask.any() else None


class VendorMarks:
    """Vendor marks as 1-bit masks, from app_icons' cache or shipped marks.

    ⚠️ Never fetches on the caller's thread: the card is rendered on the HID
    worker, and a download there would stall the keyboard. A missing mark is
    fetched once in the background (when auto-fetch is on) and `version`
    increments, so the controller redraws the card."""

    def __init__(self):
        self._masks: dict[str, object] = {}
        self._fetching: set[str] = set()
        self._lock = threading.Lock()
        self.version = 0

    def get(self, vid: str):
        with self._lock:
            if vid in self._masks:
                return self._masks[vid]
        mask = self._load(vid, allow_network=False)
        if mask is None:
            self._fetch_later(vid)
            return None
        with self._lock:
            self._masks[vid] = mask
        return mask

    def _load(self, vid, allow_network):
        for slug in vendor(vid).slugs:
            if slug.startswith(AGENT_MARK_PREFIX):
                mask = _shipped_mark(slug[len(AGENT_MARK_PREFIX):])
                if mask is not None:
                    return mask
        try:
            from polyhost.services import app_icons
        except Exception:   # noqa: BLE001 - numpy/Pillow missing: draw text instead
            return None
        for slug in vendor(vid).slugs:
            if slug.startswith(AGENT_MARK_PREFIX):
                continue
            try:
                path = app_icons.fetch_icon(slug, allow_network=allow_network)
                if not path:
                    continue
                mask = app_icons.render_overlay(path, box=MARK_BOX)
                if mask is not None:
                    # render_overlay centres the logo in the full 40-row panel; keep
                    # its ink box, then only its lower MARK_SHOWN rows.
                    mask = _crop(mask[:, PANEL_W - MARK_BOX:])
                    return None if mask is None else mask[-MARK_SHOWN:]
            except Exception as e:  # noqa: BLE001 - cosmetic
                log.debug("Agent mark %s for %s failed: %s", slug, vid, e)
        return None

    def _fetch_later(self, vid):
        try:
            from polyhost.services import app_icons
            if not vendor(vid).slugs or not app_icons.auto_fetch_enabled():
                return
        except Exception:   # noqa: BLE001
            return
        with self._lock:
            if vid in self._fetching:
                return
            self._fetching.add(vid)

        def run():
            mask = self._load(vid, allow_network=True)
            if mask is not None:
                with self._lock:
                    self._masks[vid] = mask
                    self.version += 1
        threading.Thread(target=run, name=f"agent-mark-{vid}", daemon=True).start()


def _paste(canvas, mask, x, y):
    """OR a bool mask into the (40, 72) canvas at (x, y), clipped to the panel."""
    h = min(mask.shape[0], canvas.shape[0] - y)
    w = min(mask.shape[1], canvas.shape[1] - x)
    canvas[y:y + h, x:x + w] |= mask[:h, :w]


# Cloud sessions: a cloud outline drawn over the lower right of the agent's logo
# (card experiments, 2026-11-17). Since the logo strip is 12 rows (2026-11-18) the
# cloud stays inside it, so the mark is no wider and no taller and lines 2 and 3
# keep the full width.
CLOUD_W, CLOUD_H = 16, 10   # px


def with_cloud(logo):
    """`logo` with a 1 px cloud outline drawn in front of its lower right corner,
    inside the logo's box. The cloud's inside and a 1 px border are cleared first,
    so the outline reads over the logo. A wordmark gets the same cloud at its
    right end; a mark smaller than the cloud grows to hold it."""
    import numpy as np
    from polyhost.services.agents import icons
    logo = np.asarray(logo, dtype=bool)
    shape = icons.cloud(CLOUD_W, CLOUD_H)
    x = max(0, logo.shape[1] - CLOUD_W)
    y = max(0, logo.shape[0] - CLOUD_H)
    out = np.zeros((max(logo.shape[0], y + CLOUD_H), max(logo.shape[1], x + CLOUD_W)),
                   dtype=bool)
    out[:logo.shape[0], :logo.shape[1]] = logo
    region = np.zeros_like(out)
    region[y:y + CLOUD_H, x:x + CLOUD_W] = shape
    out &= ~icons.grow(region)
    out[y:y + CLOUD_H, x:x + CLOUD_W] |= icons.outline(shape, 1)
    return out


def _text_mark(text: str):
    """The vendor's short name as a mark, while its logo is not fetched yet."""
    import numpy as np
    from PIL import Image
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    _draw(img).text((0, 0), text, font=_font(10), fill=1)
    return _crop(np.array(img, dtype=bool))


_STATE_ICONS = {}


def state_icon(state):
    """The ICON x ICON mask for a state (services/agents/icons.py), or None."""
    from polyhost.services.agents import icons
    if not _STATE_ICONS:
        # The icons of the 16 px card corner (2026-11-11), scaled to ICON: '!'
        # from its 19 px drawing, the rest from 16 px.
        _STATE_ICONS.update({k: icons.scaled(v, ICON) for k, v in {
            AgentState.WAITING: icons.waiting(),
            AgentState.IDLE: icons.idle_16(), AgentState.WORKING: icons.working_16()}.items()})
        # Drawn at 12 px: scaled, the '?' lost its dot and the check was 1 px wide.
        _STATE_ICONS[AgentState.STALE] = (icons.stale_12() if ICON == 12
                                          else icons.scaled(icons.stale_16(), ICON))
        _STATE_ICONS[AgentState.DONE] = (icons.done_12() if ICON == 12
                                         else icons.scaled(icons.done(), ICON))
    return _STATE_ICONS.get(state)


@dataclass
class CardLayout:
    """What an agent card shows: the vendor mark (or None), the state icon (or
    None) and the pages of text."""
    mark: object
    pages: list
    icon: object = None

    @property
    def page_count(self) -> int:
        return len(self.pages)


def card_layout(vendor_id: str, headline: str, marks: VendorMarks | None = None,
                state=None, cloud: bool = False) -> CardLayout:
    """The mark and pages for one agent. `cloud`: a cloud session, whose mark has
    the cloud over the logo (with_cloud). No mark is scaled: a first word that
    does not fit beside the mark starts below it."""
    logo = marks.get(vendor_id) if marks is not None else None
    if logo is None:
        logo = _text_mark(vendor(vendor_id).short[:3])
    mark = with_cloud(logo) if cloud and logo is not None else logo
    icon = state_icon(state)
    return CardLayout(mark, paginate(headline, mark, icon), icon)


def render_page(layout: CardLayout, page: int = 0):
    """A (40, 72) bool array: one page of an agent card. Lines start at the top;
    a title that fits beside the vendor mark is centred on the mark."""
    import numpy as np
    from PIL import Image
    index = page % max(1, layout.page_count)
    lines = layout.pages[index] if layout.pages else []
    mark = layout.mark if index == 0 else None
    spans = _spans(mark, layout.icon)
    beside = _beside(mark)
    cap = _measure("H")[1]
    text_h = (len(lines) - 1) * LINE_PITCH + (_measure("Hg")[3] - cap) if lines else 0
    shift = (mark.shape[0] - text_h) // 2 if mark is not None and len(lines) <= beside else 0
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    draw = _draw(img)
    for k, line in enumerate(lines):
        if not line:
            continue
        box = _measure(line)
        left, right = spans[k]
        if k < beside:
            x = left - box[0]                                   # against the mark
        else:
            x = left + (right - left - (box[2] - box[0])) // 2 - box[0]
        draw.text((x, max(0, shift) + k * LINE_PITCH - cap), line, font=_font(FONT_SIZE), fill=1)
    canvas = np.array(img, dtype=bool)
    if mark is not None:
        _paste(canvas, np.asarray(mark, dtype=bool), 0, 0)
    if layout.icon is not None:
        _paste(canvas, layout.icon, PANEL_W - layout.icon.shape[1],
               PANEL_H - layout.icon.shape[0])
    return canvas


def render_card(vendor_id: str, headline: str, marks: VendorMarks | None = None, page: int = 0,
                state=None, cloud: bool = False):
    """A (40, 72) bool array for one page of one agent card."""
    return render_page(card_layout(vendor_id, headline, marks, state, cloud), page)


MIC_SCALE = 1.7
WAITING_RADIUS = 15
COUNT_SIZE = 28


def render_dictation_card():
    """The '-' key in AI mode: dictation. The microphone alone, centred."""
    import numpy as np
    from polyhost.services.agents import icons
    canvas = np.zeros((PANEL_H, PANEL_W), dtype=bool)
    mic = icons.microphone(MIC_SCALE)
    _paste(canvas, mic, (PANEL_W - mic.shape[1]) // 2, (PANEL_H - mic.shape[0]) // 2)
    return canvas


def render_next_waiting_card(waiting: int):
    """The '+' key in AI mode: go to the next agent that waits. A large waiting
    icon, an arrow and how many wait, no text line. The count shrinks until it
    fits right of the arrow."""
    import numpy as np
    from PIL import Image
    from polyhost.services.agents import icons
    icon = icons.waiting_disk(WAITING_RADIUS)
    arrow = icons.right_arrow(11)
    arrow_x = 3 + icon.shape[1] + 3
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    count = str(waiting) if waiting < 100 else "99+"
    room = PANEL_W - 3 - (arrow_x + arrow.shape[1] + 2)
    size = COUNT_SIZE
    while size > 10 and _measure(count, size)[2] - _measure(count, size)[0] > room:
        size -= 2
    box = _measure(count, size)
    _draw(img).text((PANEL_W - 3 - (box[2] - box[0]) - box[0],
                     (PANEL_H - (box[3] - box[1])) // 2 - box[1]), count,
                    font=_font(size), fill=1)
    canvas = np.array(img, dtype=bool)
    _paste(canvas, icon, 3, (PANEL_H - icon.shape[0]) // 2)
    _paste(canvas, arrow, arrow_x, (PANEL_H - arrow.shape[0]) // 2)
    return canvas


def card_bytes(image) -> bytes:
    """360 bytes in the firmware's overlay layout."""
    import numpy as np
    data = np.packbits(np.asarray(image, dtype=bool), axis=None).tobytes()
    assert len(data) == PANEL_W * PANEL_H // 8
    return data
