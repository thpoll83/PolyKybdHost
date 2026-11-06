#!/usr/bin/env python3
"""Fetch + render icons for the terminal AI CLI overlays.

One icon folder serves seven sets: `claude_code_cli.yaml`, `codex_cli.yaml`,
`opencode.yaml`, `gemini_cli.yaml`, `qwen_code.yaml`, `copilot_cli.yaml` and
`aider.yaml`. They share most of their vocabulary (interrupt, new line,
external editor, paste image), so the icons are in one place.

Style route: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match, as for the AI desktop
apps (`../aichat/`). Icons those apps or nano already draw are copied byte for
byte, so each glyph is stored once in the icon library. Program marks:

* Claude, Codex, Copilot -- copied from `../aichat/icons`.
* Gemini CLI, Qwen Code -- the CLIs' own marks from Simple Icons
  (`googlegemini`, `qwen`; CC0 artwork, `../brand_marks.py`).
* OpenCode -- its start-screen logo, drawn in pixels (`opencode_mark()`).
* Aider -- a drawn letter frame (`../rect_mark.py`).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/aicli/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks, icon_fetch, rect_mark  # noqa: E402

FLUENT = {
    # --- shared by several CLIs ---
    "stop": "Stop",
    "newline": "Arrow Enter Left",
    "editor": "Document Edit",
    "pasteimage": "Image Add",
    "suspend": "Pause",
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "clear": "Eraser",
    "transcript": "Document Text",
    "thinking": "Lightbulb",
    "background": "Window Arrow Up",
    "queue": "Text Bullet List Add",
    "checklist": "ms:checklist",
    # --- Claude Code ---
    "stash": "Archive",
    # --- Codex ---
    "rawoutput": "Code Text",
    "warnings": "Warning",
    "activity": "Pulse",
    "mute": "Mic Off",
    "effortdown": "Arrow Trending Down",
    "editqueue": "Text Edit Style",
    "stackback": "Arrow Previous",
    "skip": "Next",
    # --- OpenCode ---
    "leader": "Keyboard Shift",
    "clearinput": "Dismiss Circle",
    "deleteline": "Text Clear Formatting",
    # --- Gemini CLI, Qwen Code ---
    "yolo": "Flash",
    "markdown": "ms:markdown",
    "ide": "Window Dev Tools",
    "copymode": "Copy Select",
    "errordetails": "Error Circle",
    "retry": "Arrow Counterclockwise",
    "tooldesc": "Wrench",
    # --- Copilot CLI ---
    "history": "History",
    "plan": "ms:assignment",
}

# The CLIs' own marks from Simple Icons (CC0 artwork, `../brand_marks.py`).
BRAND = {"gemini.png": "googlegemini", "qwen.png": "qwen"}
LETTERS = {"aider.png": "Ai"}

BORROWED = {
    **{name: "aichat" for name in (
        "claude.png", "codex.png", "copilot.png", "assistant.png",
        "commandpalette.png", "copyresponse.png", "dictation.png", "effort.png",
        "expand.png", "fastmode.png", "find.png", "model.png", "next.png",
        "permission.png", "prev.png", "reload.png", "rename.png", "search.png",
        "send.png", "shortcuts.png", "sidechat.png", "terminal.png",
        "viewmode.png")},
    **{name: "nano" for name in (
        "complete.png", "exit.png", "file_end.png", "file_start.png",
        "mouse.png", "page_down.png", "page_up.png", "scroll_down.png",
        "scroll_up.png")},
}


# OpenCode's start-screen logo, as the TUI draws it: the `left` ("open") and
# `right` ("code") rows of its logo object (opencode-linux-x64 1.19.5 on npm,
# the bundled JS). `_`, `^` and `~` are cells it draws in the dim shade; `^`
# carries the crossbar of each "e", so it counts as an upper half-block here,
# and the other two stay dark.
_OC_LOGO = (
    ["█▀▀█ █▀▀█ █▀▀█ █▀▀▄",
     "█__█ █__█ █^^^ █__█",
     "▀▀▀▀ █▀▀▀ ▀▀▀▀ ▀~~▀"],
    ["             ▄     ",
     "█▀▀▀ █▀▀█ █▀▀█ █▀▀█",
     "█___ █__█ █__█ █^^^",
     "▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀"],
)


def opencode_mark(dest: Path) -> None:
    """`opencode.png`: the logo's two words stacked, each terminal cell drawn
    as two 2x2-pixel half-blocks (38x28 px), white on transparent."""
    from PIL import Image
    words = []
    for rows in _OC_LOGO:
        w = max(len(r) for r in rows)
        im = Image.new("L", (w * 2, len(rows) * 4), 0)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                for half, on in ((0, ch in "█▀^"), (1, ch in "█▄")):
                    if on:
                        im.paste(255, (x * 2, (2 * y + half) * 2, x * 2 + 2, (2 * y + half) * 2 + 2))
        words.append(im.crop(im.getbbox()))
    gap = 4
    width = max(im.width for im in words)
    mark = Image.new("L", (width, sum(im.height for im in words) + gap), 0)
    mark.paste(words[0], (width - words[0].width, 0))
    mark.paste(words[1], (width - words[1].width, words[0].height + gap))
    Image.merge("RGBA", (mark,) * 4).save(dest)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    opencode_mark(out / "opencode.png")
    for fname, slug in BRAND.items():
        brand_marks.ensure(out / fname, slug)
    for fname, letters in LETTERS.items():
        rect_mark.ensure(out / fname, letters)
    n += icon_fetch.borrow(BORROWED, out)
    print(f"Wrote {n} icons (+ {len(BRAND) + len(LETTERS) + 1} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
