# Agent-card marks (`agent:<name>`)

Finished 1-bit masks for the AI-mode agent cards (`services/agents/card.py`), for
vendors that Simple Icons and Material Design Icons do not carry. The card shows
each one as it is, bottom-aligned with the 16 px state icon; nothing scales them.

Written by `python tools/gen_agent_marks.py`, from the ESC marks of the AI CLI
overlays (`res/overlay_sources/aicli/icons/`) or from a vendored SVG in `src/`:

| file | from | how |
|---|---|---|
| `qwen.png` | Simple Icons `qwen` (CC0) | rendered at 26 px, lower 16 rows |
| `opencode.png` | OpenCode's start-screen logo, drawn in pixels | the "code" wordmark (lower rows) |
| `aider.png` | Aider's logo: "aider" in the Glass TTY VT220 font | redrawn as 5 x 7 dot glyphs, each dot row a lit row over a dark one (scanlines) |
| `antigravity.png` | Material Symbols `antigravity` (Google, Apache 2.0), `src/antigravity.svg` | the whole arch at 16 px |
| `kimi.png` | Simple Icons `kimi` (CC0) | rendered at 26 px, lower 16 rows |
| `grok.png` | the ESC mark, drawn from the braille art in the grok binary | at half size |
