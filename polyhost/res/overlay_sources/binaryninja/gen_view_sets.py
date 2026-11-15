#!/usr/bin/env python3
"""Write the per-view binding files of Binary Ninja from `bindings.yaml`.

The mode reporter (`binaryninja-plugin/`) tells the host which view the
focused pane shows, or that the scripting console or the cross-references
pane has the keyboard focus. Four binding files are derived here from the
main one, which stays the set for Graph view and for every view without a
report:

- `bindings_linear.yaml` (Linear view): the main set without the graph zoom
  keys. The user guide lists Ctrl+Shift+= / Ctrl+Shift+- (Cmd on macOS) as
  "Graph view zoom in / out", and W / Z as "Zoom to Fit" / "Zoom to Cursor"
  of the graph view.
- `bindings_hex.yaml` (Hex view): the guide says that in Hex view "you can
  manually type in hexadecimal or ASCII values" and that Tab moves between
  the hex and the ASCII column. So a key that types a character (no modifier,
  or Shift only) is left blank, Tab draws the column switch, and the graph
  zoom keys are left out. Chords with Ctrl/Cmd or Alt, and the function keys,
  keep the main set's cells.
- `bindings_console.yaml` (scripting console command line): the line takes
  the typed text, so only the keys the guide lists for the console are drawn
  ("Script (Python) Console": Tab, Up / Down, Ctrl+R, Ctrl+Enter,
  Shift+Enter), plus the command palette, which the guide calls
  "application-wide".
- `bindings_xrefs.yaml` (cross-references pane): the keys the guide lists as
  "only available when the cross-references pane is in focus" (Ctrl+F,
  Ctrl+A, Up / Down, Enter; Esc is the program mark), plus the command
  palette.

The IL level (disassembly, LLIL, MLIL, HLIL, pseudo C) changes no default
hotkey in the guide, so it has no set of its own.

    python polyhost/res/overlay_sources/binaryninja/gen_view_sets.py
    python scripts/generate_app_overlays.py \\
        polyhost/res/overlay_sources/binaryninja/bindings_linear.yaml
    python scripts/generate_app_overlays.py \\
        polyhost/res/overlay_sources/binaryninja/bindings_hex.yaml
    python scripts/generate_app_overlays.py \\
        polyhost/res/overlay_sources/binaryninja/bindings_console.yaml
    python scripts/generate_app_overlays.py \\
        polyhost/res/overlay_sources/binaryninja/bindings_xrefs.yaml

`--check` exits 1 when a written file differs from what this script makes.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MAIN = HERE / "bindings.yaml"

# Graph view only (user guide: "Default Hotkeys" for the zoom chords, "Graph
# View" for W and Z).
GRAPH_ONLY = {("=", ("CMDCTRL", "SHIFT")), ("-", ("CMDCTRL", "SHIFT")),
              ("W", ()), ("Z", ())}
# The command palette, which the guide calls "application-wide": it is drawn
# in the console and cross-references sets too (copied from the main set).
APP_WIDE = {("P", ("CMDCTRL",)), ("P", ("CMDCTRL", "SHIFT"))}
# Modifiers that make a key a command instead of typed text.
COMMAND_MODS = {"CMDCTRL", "CTRL", "ALT", "GUI"}

HEX_TAB = {"key": "TAB", "icon": "hex_ascii_col.png", "label": "Switch hex / ASCII column",
           "region": [40, 40], "mode": "alpha"}


_WORD = {"region": [40, 40], "mode": "alpha"}

# Scripting console (guide, "Script (Python) Console"). The guide writes
# <CTRL> here; Qt maps Ctrl to Cmd on macOS, so CMDCTRL (not checked on a Mac).
CONSOLE = [
    {"key": "TAB", "icon": "autocomplete.png", "label": "Complete"},
    {"key": "UP", "icon": "hist_prev.png", "label": "Previous command (history)", **_WORD},
    {"key": "DOWN", "icon": "hist_next.png", "label": "Next command (history)", **_WORD},
    {"key": "R", "mods": ["CMDCTRL"], "icon": "hist_search.png",
     "label": "Reverse search the history", **_WORD},
    {"key": "ENTER", "mods": ["CMDCTRL"], "icon": "run_multi.png",
     "label": "Run multi-line input", **_WORD},
    {"key": "ENTER", "mods": ["SHIFT"], "icon": "multi_line.png",
     "label": "Force multi-line input", **_WORD},
]

# Cross-references pane (guide, "Cross-Reference Hotkeys": "only available
# when the cross-references pane is in focus"). Esc ("Clear the search
# dialog") is the program mark.
XREFS = [
    {"key": "F", "mods": ["CMDCTRL"], "icon": "filter.png", "label": "Filter references"},
    {"key": "A", "mods": ["CMDCTRL"], "icon": "selectall.png",
     "label": "Select all references"},
    {"key": "UP", "icon": "xref_sel_prev.png", "label": "Select previous reference", **_WORD},
    {"key": "DOWN", "icon": "xref_sel_next.png", "label": "Select next reference", **_WORD},
    {"key": "ENTER", "icon": "xref_goto.png", "label": "Go to the selected reference",
     **_WORD},
]


def _sig(b):
    return (str(b["key"]), tuple(b.get("mods") or ()))


def _types_text(b) -> bool:
    """A key that types a character in Hex view: no command modifier, and not
    a function key or Esc."""
    if COMMAND_MODS & set(b.get("mods") or ()):
        return False
    key = str(b["key"])
    if key.upper() in ("ESC", "ESCAPE"):
        return False
    return not (key.upper().startswith("F") and key[1:].isdigit())


def linear_bindings(main):
    return [b for b in main if _sig(b) not in GRAPH_ONLY]


def hex_bindings(main):
    out = [b for b in main if _sig(b) not in GRAPH_ONLY and not _types_text(b)]
    return [dict(HEX_TAB)] + out


def _app_wide(main):
    return [b for b in main if _sig(b) in APP_WIDE]


def console_bindings(main):
    return [dict(b) for b in CONSOLE] + _app_wide(main)


def xrefs_bindings(main):
    return [dict(b) for b in XREFS] + _app_wide(main)


def _spec(main_spec, output, bindings):
    spec = copy.deepcopy(main_spec)
    spec["output"] = output
    spec.pop("_word", None)
    spec["bindings"] = bindings
    return spec


def _dump(spec, title) -> str:
    head = (f"# GENERATED by gen_view_sets.py from bindings.yaml -- do not edit.\n"
            f"# {title}\n")
    bindings = spec.pop("bindings")
    body = yaml.safe_dump(spec, sort_keys=False, default_flow_style=None, allow_unicode=True)
    lines = ["bindings:"]
    for b in bindings:
        lines.append("  - " + yaml.safe_dump(b, default_flow_style=True, sort_keys=False,
                                             width=1000, allow_unicode=True).strip())
    return head + body + "\n".join(lines) + "\n"


def build():
    main_spec = yaml.safe_load(MAIN.read_text(encoding="utf-8"))
    main = main_spec["bindings"]
    return {
        HERE / "bindings_linear.yaml": _dump(
            _spec(main_spec, "binaryninja_linear_template", linear_bindings(main)),
            "Linear view: the main set without the graph zoom keys."),
        HERE / "bindings_hex.yaml": _dump(
            _spec(main_spec, "binaryninja_hex_template", hex_bindings(main)),
            "Hex view: keys that type text are blank; Tab switches the hex / ASCII column."),
        HERE / "bindings_console.yaml": _dump(
            _spec(main_spec, "binaryninja_console_template", console_bindings(main)),
            "Scripting console: only the console keys and the command palette."),
        HERE / "bindings_xrefs.yaml": _dump(
            _spec(main_spec, "binaryninja_xrefs_template", xrefs_bindings(main)),
            "Cross-references pane: the pane's keys and the command palette."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare, do not write")
    args = ap.parse_args()
    stale = []
    for path, text in build().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(path.name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"Wrote {path}")
    if stale:
        print("stale: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
