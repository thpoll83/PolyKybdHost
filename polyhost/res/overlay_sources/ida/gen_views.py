#!/usr/bin/env python3
"""Write the per-view IDA specs from `bindings.yaml` (reproducible).

The IDA plugin (`ida-plugin/`) reports which kind of widget has the focus as
`ida://<view>[/<sub>]`. The mapping entry routes three of them to their own
set; `bindings.yaml` (`ida_template`) stays the fallback for when no report
arrives:

* `bindings_disasm.yaml` (`ida_disasm_template`): the disassembly view (text
  or graph) and the hex view. `bindings.yaml` without the four keys that act
  only in the pseudocode window (`/`, `\\`, `=`, Shift+5).
* `bindings_pseudocode.yaml` (`ida_pseudocode_template`): the window-level keys
  of `global` plus the pseudocode window's own keys (`PSEUDOCODE` below, from
  the Hex-Rays decompiler manual, IDA 9.2). Where a key has another meaning
  there (N, Y, H, Tab, F5, Ins, ...), the pseudocode meaning is drawn.
* `bindings_global.yaml` (`ida_global_template`): every other widget (lists,
  local types, output, command line). Only the keys that act from any window:
  the function keys and the modifier chords that open views, jump, search,
  save and run the debugger. Single letters are left out, because a list
  takes them as a quick search.

Edit `bindings.yaml` or the tables below, never the generated files, then:

    python polyhost/res/overlay_sources/ida/gen_views.py
    for v in disasm pseudocode global; do
        python scripts/generate_app_overlays.py \\
            polyhost/res/overlay_sources/ida/bindings_$v.yaml
    done

`--check` exits 1 when a generated file differs from what this script writes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
BASE = HERE / "bindings.yaml"

# Spec keys copied from bindings.yaml into every view spec.
HEADER_KEYS = ("app", "match", "icon_dir", "fit", "anchor", "region", "margin", "mode",
               "threshold", "program_icon", "program_icon_mode", "program_icon_anchor",
               "program_icon_region", "program_icon_margin")

# The keys of bindings.yaml that act only in the pseudocode window.
PSEUDOCODE_ONLY = {("/", ()), ("\\", ()), ("=", ()), ("5", ("SHIFT",))}

# Chords of bindings.yaml that act on the disassembly listing (an item, an
# operand, the cursor position, the graph), not from any window.
_LISTING = [
    ("F2", ()), ("F4", ()), ("F5", ()), ("F1", ("ALT",)), ("F2", ("ALT",)),
    ("ENTER", ("CMDCTRL",)), ("ENTER", ("ALT",)),
    ("UP", ("CMDCTRL", "SHIFT")), ("DOWN", ("CMDCTRL", "SHIFT")), ("C", ("CMDCTRL", "SHIFT")),
    ("UP", ("ALT",)), ("DOWN", ("ALT",)),
    ("UP", ("ALT", "SHIFT")), ("DOWN", ("ALT", "SHIFT")), ("V", ("ALT", "SHIFT")),
]
_LISTING += [(k, ("CMDCTRL",)) for k in "XJORKNDUAVFIBT"]
_LISTING += [(k, ("ALT",)) for k in "CPRQYADKSGL"]
_LISTING += [(str(n), ("ALT", "CMDCTRL")) for n in range(9)]
LISTING = set(_LISTING)

_WORD = {"region": [40, 40], "mode": "alpha"}

# The pseudocode window's own keys. Source: the Hex-Rays decompiler manual,
# "Interactive operation" and its cmd_*.md pages (IDA 9.2); see SOURCES.md.
PSEUDOCODE = [
    {"key": "N", "icon": "label.png", "label": "Rename variable"},
    {"key": "Y", "icon": "type_retype.png", "label": "Set type", **_WORD},
    {"key": "H", "icon": "op_hexdec.png", "label": "Hex / decimal", **_WORD},
    {"key": "R", "icon": "op_char.png", "label": "Character", **_WORD},
    {"key": "M", "icon": "op_enum.png", "label": "Enum member", **_WORD},
    {"key": "T", "icon": "op_structofs.png", "label": "Structure offset", **_WORD},
    {"key": "-", "mods": ["SHIFT"], "icon": "op_sign.png", "label": "Invert sign (_)", **_WORD},
    {"key": "/", "icon": "comment_pseudo.png", "label": "Comment", **_WORD},
    {"key": "INSERT", "icon": "comment_block.png", "label": "Block comment", **_WORD},
    {"key": "X", "icon": "references.png", "label": "Jump to cross reference"},
    {"key": "\\", "icon": "casts.png", "label": "Hide casts"},
    {"key": "=", "icon": "map_var.png", "label": "Map to another variable", **_WORD},
    {"key": "S", "mods": ["SHIFT"], "icon": "split_var.png", "label": "Split variable", **_WORD},
    {"key": "Y", "mods": ["ALT"], "icon": "union_member.png", "label": "Select union field", **_WORD},
    {"key": "DELETE", "mods": ["SHIFT"], "icon": "del_arg.png", "label": "Delete function argument", **_WORD},
    {"key": "R", "mods": ["CMDCTRL", "SHIFT"], "icon": "ret_type.png", "label": "Add/delete return type", **_WORD},
    {"key": "5", "mods": ["SHIFT"], "icon": "paren_pair.png", "label": "Jump to paired paren (%)", **_WORD},
    {"key": "TAB", "icon": "asm_toggle.png", "label": "Jump to disassembly", **_WORD},
    {"key": "F5", "icon": "refresh.png", "label": "Refresh pseudocode"},
    {"key": "ENTER", "mods": ["CMDCTRL"], "icon": "jump_newwin.png", "label": "Decompile in a new window"},
    {"key": "G", "icon": "goto.png", "label": "Jump to address"},
    {"key": "F2", "icon": "breakpoint.png", "label": "Toggle breakpoint"},
    {"key": "F4", "icon": "run_to_cursor.png", "label": "Run to cursor", **_WORD},
]

VIEWS = {
    "disasm": "the disassembly view (text and graph) and the hex view",
    "pseudocode": "the pseudocode window",
    "global": "every other IDA window (lists, local types, output, command line)",
}


def chord(b: dict) -> tuple[str, tuple[str, ...]]:
    return str(b["key"]), tuple(sorted(b.get("mods") or ()))


def is_global(b: dict) -> bool:
    """A key that acts from any IDA window: a function key, or a chord with
    Ctrl/Cmd or Alt that does not act on the listing."""
    key, mods = chord(b)
    if (key, mods) in LISTING:
        return False
    if key.startswith("F") and key[1:].isdigit():
        return True
    return any(m in mods for m in ("CMDCTRL", "CTRL", "ALT"))


def view_bindings(view: str, base: list[dict]) -> list[dict]:
    if view == "disasm":
        return [b for b in base if chord(b) not in PSEUDOCODE_ONLY]
    globals_ = [b for b in base if is_global(b)]
    if view == "global":
        return globals_
    own = {chord(b) for b in PSEUDOCODE}
    return [*(b for b in globals_ if chord(b) not in own), *PSEUDOCODE]


def render(view: str, spec: dict) -> str:
    out = {k: spec[k] for k in HEADER_KEYS if k in spec}
    out["output"] = f"ida_{view}_template"
    lines = [
        f"# GENERATED by gen_views.py from bindings.yaml: do not edit. IDA overlay for",
        f"# {VIEWS[view]}, loaded when the IDA plugin (ida-plugin/) reports",
        f"# ida://{view if view != 'global' else '<other view>'}. See SOURCES.md.",
        yaml.safe_dump(out, sort_keys=False, default_flow_style=None, allow_unicode=True).rstrip(),
        "bindings:",
    ]
    first = ("key", "mods", "icon", "label")
    for b in view_bindings(view, spec["bindings"]):
        b = {**{k: b[k] for k in first if k in b}, **{k: v for k, v in b.items() if k not in first}}
        lines.append("  - " + yaml.safe_dump(b, sort_keys=False, default_flow_style=True,
                                             allow_unicode=True, width=1000).strip())
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    check = "--check" in argv
    spec = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    stale = []
    for view in VIEWS:
        dest = HERE / f"bindings_{view}.yaml"
        text = render(view, spec)
        if check:
            if not dest.is_file() or dest.read_text(encoding="utf-8") != text:
                stale.append(dest.name)
        else:
            dest.write_text(text, encoding="utf-8", newline="\n")
            print(f"Wrote {dest.name} ({len(view_bindings(view, spec['bindings']))} bindings)")
    if stale:
        print("stale, re-run gen_views.py: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
