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
* OpenCode, Gemini CLI, Qwen Code, Aider -- drawn letter frames
  (`../rect_mark.py`).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/aicli/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, rect_mark  # noqa: E402

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

LETTERS = {"opencode.png": "OC", "gemini.png": "Gm", "qwen.png": "Qw",
           "aider.png": "Ai"}

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


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for fname, letters in LETTERS.items():
        rect_mark.ensure(out / fname, letters)
    n += icon_fetch.borrow(BORROWED, out)
    print(f"Wrote {n} icons (+ {len(LETTERS)} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
