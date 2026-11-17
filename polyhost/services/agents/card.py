"""Render an agent card: the 72x40 1-bit image a number key shows in AI mode.

    +------------------------------------+
    | [vendor ] title, first words       |   line 1  rows  0..12
    | [ mark  ] more words               |   line 2  rows 13..25
    | the title goes on, full width      |   line 3  rows 26..39
    +------------------------------------+

The vendor mark is drawn whole at up to 24 px, top left, with the text 1 px to
its right; lines below the mark use the full width. Three lines of 14 px text
(card experiments, 2026-11-17). No state icon: the key's light shows the state
(ai_rgb_paint in the firmware). When the first word does not fit beside the
mark, the mark is drawn smaller (24, 20, 16 or 12 px) until it does.

A title that does not fit one card is split into pages of three lines, without
the mark after the first; the controller switches the key between them
(TEXT_PAGE_S). Text breaks at spaces and after '-'; only a word wider than the
key is split between letters. Text is Pillow's bundled sans font (Aileron)
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

from polyhost.services.agents.model import vendor

log = logging.getLogger("PolyHost")

PANEL_W, PANEL_H = 72, 40
MARK_BOX = 24          # the largest mark, px (its larger side)
MARK_SIZES = (24, 20, 16, 12)   # tried in this order until the first word fits
MARK_GAP = 1           # px between the mark and the text beside it
FONT_SIZE = 14
LINE_PITCH = 13        # three lines in 40 rows; a descender may touch the cap below
LINES = 3
TEXT_W = PANEL_W - 2   # a full-width line: 1 px margin each side
WORDMARK_RATIO = 1.5   # wider than this times its height: a wordmark, never scaled
MAX_PAGES = 4          # a longer title ends with '.' on the last page
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


def _beside(mask) -> int:
    """How many text lines sit right of a mark this tall."""
    if mask is None:
        return 0
    return min(LINES, -(-mask.shape[0] // LINE_PITCH))   # 1..13 rows: 1, 14..26: 2


def paginate(text: str, mask=None, size: int = FONT_SIZE) -> list[list[str]]:
    """The pages of a card: lists of at most LINES lines. On page 1 the first
    _beside(mask) lines are narrowed by the mark; later pages are full width."""
    beside = _beside(mask)
    narrow = TEXT_W + 1 - (mask.shape[1] + MARK_GAP) if beside else TEXT_W
    first = flow(text, [narrow] * beside + [TEXT_W], size)
    pages = [first[:LINES]]
    rest = " ".join(line for line in first[LINES:] if line)
    if rest:
        more = flow(rest, [TEXT_W], size)
        pages += [more[i:i + LINES] for i in range(0, len(more), LINES)]
    if len(pages) > MAX_PAGES:
        pages = pages[:MAX_PAGES]
        pages[-1][-1] = fit_text(pages[-1][-1] + "\u2026", TEXT_W, size)
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


def _shipped_mark(name: str, box: int):
    """A shipped mark, at most `box` rows tall: drawn for the card at up to 24 px,
    scaled down only for a smaller mark (the first word does not fit beside it)."""
    try:
        import numpy as np
        from PIL import Image
        with Image.open(os.path.join(AGENT_MARK_DIR, name + ".png")) as img:
            img = img.convert("L")
            if img.height > box:
                img = img.resize((max(1, round(img.width * box / img.height)), box),
                                 Image.LANCZOS)
            mask = np.array(img) > 110
    except Exception as e:  # noqa: BLE001 - cosmetic: fall back to the next slug
        log.debug("Agent mark %s: %s", name, e)
        return None
    return _crop(mask)


class VendorMarks:
    """Vendor marks as 1-bit masks, from app_icons' cache or shipped marks, one per
    (vendor, size).

    ⚠️ Never fetches on the caller's thread: the card is rendered on the HID
    worker, and a download there would stall the keyboard. A missing mark is
    fetched once in the background (when auto-fetch is on) and `version`
    increments, so the controller redraws the card."""

    def __init__(self):
        self._masks: dict[tuple, object] = {}
        self._fetching: set[str] = set()
        self._lock = threading.Lock()
        self.version = 0

    def get(self, vid: str, box: int = MARK_BOX):
        with self._lock:
            if (vid, box) in self._masks:
                return self._masks[(vid, box)]
        mask = self._load(vid, box, allow_network=False)
        if mask is None:
            self._fetch_later(vid)
            return None
        with self._lock:
            self._masks[(vid, box)] = mask
        return mask

    def _load(self, vid, box, allow_network):
        for slug in vendor(vid).slugs:
            if slug.startswith(AGENT_MARK_PREFIX):
                mask = _shipped_mark(slug[len(AGENT_MARK_PREFIX):], box)
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
                mask = app_icons.render_overlay(path, box=box)
                if mask is not None:
                    return _crop(mask)
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
            # Fetched once into app_icons' cache; get() renders each size from it.
            if self._load(vid, MARK_BOX, allow_network=True) is not None:
                with self._lock:
                    for key in [k for k in self._masks if k[0] == vid]:
                        del self._masks[key]
                    self.version += 1
        threading.Thread(target=run, name=f"agent-mark-{vid}", daemon=True).start()


def _paste(canvas, mask, x, y):
    """OR a bool mask into the (40, 72) canvas at (x, y), clipped to the panel."""
    h = min(mask.shape[0], canvas.shape[0] - y)
    w = min(mask.shape[1], canvas.shape[1] - x)
    canvas[y:y + h, x:x + w] |= mask[:h, :w]


def _text_mark(text: str):
    """The vendor's short name as a mark, while its logo is not fetched yet."""
    import numpy as np
    from PIL import Image
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    _draw(img).text((0, 0), text, font=_font(10), fill=1)
    return _crop(np.array(img, dtype=bool))


@dataclass
class CardLayout:
    """What an agent card shows: the mark (or None) and the pages of text."""
    mark: object
    pages: list

    @property
    def page_count(self) -> int:
        return len(self.pages)


def card_layout(vendor_id: str, headline: str, marks: VendorMarks | None = None) -> CardLayout:
    """The mark size and pages for one agent. The largest mark in MARK_SIZES that
    leaves room beside it for the title's first word; the smallest when none does."""
    tokens = _tokens(headline)
    first = tokens[0][0] if tokens else ""
    mark = None
    for box in MARK_SIZES:
        mark = marks.get(vendor_id, box) if marks is not None else None
        if mark is None:
            mark = _text_mark(vendor(vendor_id).short[:3])
        if (mark is None or _ink_width(first) <= TEXT_W + 1 - (mark.shape[1] + MARK_GAP)
                or mark.shape[1] > WORDMARK_RATIO * mark.shape[0]):
            # A wordmark (aider, opencode, the short-name text) is not scaled: it
            # stops reading. The first word then starts below it.
            break
    return CardLayout(mark, paginate(headline, mark))


def render_page(layout: CardLayout, page: int = 0):
    """A (40, 72) bool array: one page of an agent card. The text block (and the
    mark, on page 1) is centred vertically when it is shorter than the panel."""
    import numpy as np
    from PIL import Image
    lines = layout.pages[page % layout.page_count] if layout.pages else []
    mark = layout.mark if page % max(1, layout.page_count) == 0 else None
    beside = _beside(mark)
    cap = _measure("H")[1]
    text_h = (len(lines) - 1) * LINE_PITCH + (_measure("Hg")[3] - cap) if lines else 0
    block = max(text_h, mark.shape[0] if mark is not None else 0)
    top = max(0, (PANEL_H - block) // 2)
    img = Image.new("1", (PANEL_W, PANEL_H), 0)
    draw = _draw(img)
    # A title that fits beside the mark is centred on the mark, not on its top.
    shift = (block - text_h) // 2 if mark is not None and len(lines) <= beside else 0
    for k, line in enumerate(lines):
        if not line:
            continue
        box = _measure(line)
        if k < beside:
            left = mark.shape[1] + MARK_GAP
            x = left - box[0]
        else:
            x = (PANEL_W - (box[2] - box[0])) // 2 - box[0]
        draw.text((x, top + shift + k * LINE_PITCH - cap), line, font=_font(FONT_SIZE), fill=1)
    canvas = np.array(img, dtype=bool)
    if mark is not None:
        rows = beside * LINE_PITCH - 1
        _paste(canvas, np.asarray(mark, dtype=bool), 0,
               top + max(0, (min(rows, block) - mark.shape[0]) // 2))
    return canvas


def render_card(vendor_id: str, headline: str, marks: VendorMarks | None = None, page: int = 0):
    """A (40, 72) bool array for one page of one agent card."""
    return render_page(card_layout(vendor_id, headline, marks), page)


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
