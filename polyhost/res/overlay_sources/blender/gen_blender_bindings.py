#!/usr/bin/env python3
"""Generate the Blender overlay binding files from Blender's OWN default keymap.

Blender's shortcuts are not one table: they are a STACK of keymaps that depends
on the editor under the mouse and the object's interaction mode. Edit Mesh in the
3D View resolves a key through `Mesh`, then `Object Non-modal`, `Frames`,
`3D View Generic`, `3D View`, and only then the window-level `Window` / `Screen`
maps -- so `Ctrl+R` is Loop Cut there and nothing at all in Object Mode. One
overlay per context, resolved the way Blender resolves it, is the only way the
keycaps can say what a key will actually do.

Input is `scripts/presets/keyconfig/keymap_data/blender_default.py` from a Blender
checkout (it is written to run without Blender: "This script should run without
Blender (no references to the `bpy` module)"), plus
`scripts/modules/bl_keymap_utils/platform_helpers.py` for the macOS Cmd rule.
Both are executed in-process; nothing here imports `bpy`.

    git clone --depth 1 --filter=blob:none --sparse --branch v5.2.2 \\
        https://github.com/blender/blender.git /tmp/blender
    git -C /tmp/blender sparse-checkout set scripts/presets/keyconfig \\
        scripts/modules/bl_keymap_utils
    python polyhost/res/overlay_sources/blender/gen_blender_bindings.py \\
        --blender-src /tmp/blender --render

A Blender release bump is a re-run with the new tag: the stacks below (`STACKS`)
are the only hand-written part about Blender's structure, and `actions.yaml` (the
label + icon per operator) the only hand-written part about its meaning. An
operator that `actions.yaml` does not name is LEFT OFF the keycap (and listed in
COVERAGE.md) rather than guessed at.

What is resolved, and how:

* **Keyboard only.** Mouse, wheel, NDOF, trackpad, timer and keypad (`NUMPAD_*`)
  events have no keycap cell. ESC is the program mark's cell and is skipped too.
* **PRESS / CLICK only.** DOUBLE_CLICK, CLICK_DRAG and RELEASE bindings are a
  second gesture on a key whose plain press the keycap already describes.
* **Shadowing follows Blender.** Within a stack the first keymap that binds a
  (key, modifiers) wins it -- even if that binding is one we do not draw, in
  which case the cell stays EMPTY rather than showing a lower keymap's action
  that would never run. Within ONE keymap the LAST item for a chord wins: Blender
  lists poll-gated special cases first and the general operator last
  (`asset.catalog_undo` then `ed.undo` on Ctrl+Z; `view3d.view_center_camera`
  then `view3d.view_all` on Home).
* **A binding with a "don't care" modifier (`-1`, or `any`)** shadows every
  combination of that modifier and is drawn on the plain one.
* **macOS**: Blender's own `Blender.py` keyconfig runs
  `keyconfig_data_oskey_from_ctrl_for_macos()` on darwin, which ADDS a Cmd copy
  of almost every Ctrl binding (Ctrl keeps working). That function is executed
  here on the same data, so every Cmd binding it creates becomes an
  `only: [macos]` line: the macOS set shows both, exactly as Blender binds both.
  `CMDCTRL` would be wrong here, because it MOVES the artwork off Ctrl.

Outputs (all in this folder): `bindings_<context>.yaml` per context,
`COVERAGE.md` (per-context counts + every undrawn binding), and
`mapping_stanza.yaml` (the `blender` entry for overlay-mapping.poly.yaml).
Deterministic: same Blender checkout + same actions.yaml -> byte-identical files.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import runpy
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]

KEYMAP_DATA = "scripts/presets/keyconfig/keymap_data/blender_default.py"
KEYCONFIG_PRESET = "scripts/presets/keyconfig/Blender.py"
PLATFORM_HELPERS = "scripts/modules/bl_keymap_utils/platform_helpers.py"

WINDOW = ["Window", "Screen"]
VIEW3D_TAIL = ["Object Non-modal", "Frames", "3D View Generic", "3D View"] + WINDOW

# context -> (keymap stack, highest priority first; description).
#
# The 3D View order is `view3d_main_region_init()` (space_view3d.cc): every mode
# keymap, then Object Non-modal, Frames, 3D View Generic, 3D View; the window's
# `Window` and `Screen` handlers run after every region handler. Mode keymaps
# are poll-gated, so only the active mode's map is in a stack. The paint-mask
# maps ("Paint Face Mask", "Paint Vertex Selection") need a mask toggle that is
# off by default and are left out.
#
# The 2D editors add `ed_default_handlers()` (area.cc) BEFORE their own maps:
# View2D, the Animation maps, Frames -- in that order -- then the editor's.
# Markers and Time Scrub are polled on the mouse being over that strip, so they
# are not part of the main-region stack.
STACKS = {
    "global": (WINDOW, "Window + Screen only: an editor without its own overlay"),
    "object": (["Object Mode"] + VIEW3D_TAIL, "3D View, Object Mode"),
    "edit_mesh": (["Mesh"] + VIEW3D_TAIL, "3D View, Edit Mode (mesh)"),
    "sculpt": (["Sculpt"] + VIEW3D_TAIL, "3D View, Sculpt Mode"),
    "pose": (["Pose"] + VIEW3D_TAIL, "3D View, Pose Mode"),
    "edit_armature": (["Armature"] + VIEW3D_TAIL, "3D View, Edit Mode (armature)"),
    "paint_weight": (["Weight Paint"] + VIEW3D_TAIL, "3D View, Weight Paint"),
    "paint_vertex": (["Vertex Paint"] + VIEW3D_TAIL, "3D View, Vertex Paint"),
    "paint_texture": (["Image Paint"] + VIEW3D_TAIL, "3D View, Texture Paint"),
    "node": (["View2D", "Frames", "Node Generic", "Node Editor"] + WINDOW,
             "Node Editor (shader, geometry, compositor)"),
    "uv": (["Frames", "UV Editor", "Image Generic", "Image"] + WINDOW,
           "Image Editor in UV mode with a mesh in Edit Mode"),
    "dopesheet": (["View2D", "Animation", "Frames", "Dopesheet", "Dopesheet Generic"] + WINDOW,
                  "Dope Sheet, incl. Timeline / Action / Shape Key editors"),
    "graph": (["View2D", "Animation", "Frames", "Graph Editor", "Graph Editor Generic"] + WINDOW,
              "Graph Editor (F-Curves, Drivers)"),
}

# The contexts whose INTERSECTION is the `common` overlay: the 3D View modes.
VIEW3D_CONTEXTS = ["object", "edit_mesh", "sculpt", "pose", "edit_armature",
                   "paint_weight", "paint_vertex", "paint_texture"]

# URL routing, in match order. The add-on reports
# `blender://<context.mode>/<area.type>[/<area.ui_type>]` (see blender-addon/).
# The matcher is first-substring-hit in file order, so editor needles come
# before the mode needles (a Node Editor in Object Mode is the Node Editor), and
# two catch-alls close the list: any other 3D View mode gets `common`, any other
# editor `global` -- a Text Editor must not show the 3D View's keys.
ROUTES = [
    ("/NODE_EDITOR", "node"),
    ("EDIT_MESH/IMAGE_EDITOR/UV", "uv"),
    ("/DOPESHEET_EDITOR", "dopesheet"),
    ("/GRAPH_EDITOR", "graph"),
    ("blender://OBJECT/VIEW_3D", "object"),
    ("blender://EDIT_MESH/VIEW_3D", "edit_mesh"),
    ("blender://SCULPT/VIEW_3D", "sculpt"),
    ("blender://POSE/VIEW_3D", "pose"),
    ("blender://EDIT_ARMATURE/VIEW_3D", "edit_armature"),
    ("blender://PAINT_WEIGHT/VIEW_3D", "paint_weight"),
    ("blender://PAINT_VERTEX/VIEW_3D", "paint_vertex"),
    ("blender://PAINT_TEXTURE/VIEW_3D", "paint_texture"),
    ("/VIEW_3D", "common"),
    ("blender://", "global"),
]

# Blender event type -> generator key token. Only keys with a keycap cell.
_KEYS = {**{c: c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
         **{w: str(i) for i, w in enumerate(
             ["ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"])},
         **{f"F{i}": f"F{i}" for i in range(1, 13)},
         "ACCENT_GRAVE": "KC_GRAVE", "QUOTE": "KC_QUOTE", "SEMI_COLON": "KC_SEMICOLON",
         "LEFT_BRACKET": "KC_LEFT_BRACKET", "RIGHT_BRACKET": "KC_RIGHT_BRACKET",
         "BACK_SLASH": "KC_BACKSLASH", "SLASH": "KC_SLASH", "PERIOD": "KC_DOT",
         "COMMA": "KC_COMMA", "EQUAL": "KC_EQUAL", "MINUS": "KC_MINUS",
         "TAB": "KC_TAB", "SPACE": "KC_SPACE", "RET": "KC_ENTER",
         "BACK_SPACE": "KC_BACKSPACE", "DEL": "KC_DELETE", "HOME": "KC_HOME",
         "END": "KC_END", "PAGE_UP": "KC_PAGE_UP", "PAGE_DOWN": "KC_PAGE_DOWN",
         "INSERT": "KC_INSERT", "LEFT_ARROW": "KC_LEFT", "RIGHT_ARROW": "KC_RIGHT",
         "UP_ARROW": "KC_UP", "DOWN_ARROW": "KC_DOWN", "APP": "KC_APPLICATION"}
# Blender modifier name -> generator modifier token, in the order we emit them.
_MODS = (("ctrl", "CTRL"), ("shift", "SHIFT"), ("alt", "ALT"), ("oskey", "GUI"))
_VALUES = ("PRESS", "CLICK")


def keyconfig_pref_defaults(src: Path) -> dict:
    """The keyconfig preference defaults declared in `Blender.py`'s `Prefs` class.

    Read with `ast` because the file imports `bpy`. An EnumProperty without an
    explicit default takes its first item, as Blender does."""
    tree = ast.parse((src / KEYCONFIG_PRESET).read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "Prefs"):
            continue
        for st in node.body:
            if isinstance(st, ast.AnnAssign) and isinstance(st.annotation, ast.Call):
                kw = {k.arg: k.value for k in st.annotation.keywords}
                if "default" in kw:
                    out[st.target.id] = ast.literal_eval(kw["default"])
                elif "items" in kw:
                    out[st.target.id] = ast.literal_eval(kw["items"])[0][0]
    return out


# The keyword names `Blender.py`'s `load()` passes to `Params(...)`. `params_for`
# below mirrors that call; if a Blender release adds or drops a keyword, the
# mirror is stale and the generator refuses to run rather than silently
# producing the keymap of a different preference set.
_LOAD_PARAM_KEYS = {
    "select_mouse", "use_mouse_emulate_3_button", "spacebar_action",
    "use_key_activate_tools", "use_region_toggle_pie", "v3d_tilde_action",
    "use_v3d_mmb_pan", "v3d_alt_mmb_drag_action", "use_select_all_toggle",
    "use_v3d_tab_menu", "use_v3d_shade_ex_pie", "use_gizmo_drag", "use_fallback_tool",
    "use_fallback_tool_select_handled", "use_alt_tool_or_cursor", "use_alt_click_leader",
    "use_pie_click_drag", "use_file_single_click", "use_alt_navigation",
}


def _load_param_keys(src: Path) -> set:
    tree = ast.parse((src / KEYCONFIG_PRESET).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "Params"):
            return {k.arg for k in node.keywords}
    return set()


def params_for(src: Path, ns: dict):
    """`Params` exactly as a fresh install builds them (`Blender.py` `load()`)."""
    found = _load_param_keys(src)
    if found != _LOAD_PARAM_KEYS:
        raise SystemExit(
            f"Blender.py load() now passes different Params keywords "
            f"(added {sorted(found - _LOAD_PARAM_KEYS)}, removed "
            f"{sorted(_LOAD_PARAM_KEYS - found)}); update params_for() to match.")
    p = keyconfig_pref_defaults(src)
    left = p["select_mouse"] == "LEFT"
    return ns["Params"](
        select_mouse=p["select_mouse"],
        use_mouse_emulate_3_button=False,          # an input preference, off by default
        spacebar_action=p["spacebar_action"],
        use_key_activate_tools=(p["tool_key_mode"] == "TOOL"),
        use_region_toggle_pie=p["use_region_toggle_pie"],
        v3d_tilde_action=p["v3d_tilde_action"],
        use_v3d_mmb_pan=(p["v3d_mmb_action"] == "PAN"),
        v3d_alt_mmb_drag_action=p["v3d_alt_mmb_drag_action"],
        use_select_all_toggle=p["use_select_all_toggle"],
        use_v3d_tab_menu=p["use_v3d_tab_menu"],
        use_v3d_shade_ex_pie=p["use_v3d_shade_ex_pie"],
        use_gizmo_drag=(left and p["gizmo_action"] == "DRAG"),
        use_fallback_tool=True,
        use_fallback_tool_select_handled=(False if left else p["rmb_action"] != "FALLBACK_TOOL"),
        use_alt_tool_or_cursor=(p["use_alt_tool"] if left else p["use_alt_cursor"]),
        use_alt_click_leader=p["use_alt_click_leader"],
        use_pie_click_drag=p["use_pie_click_drag"],
        use_file_single_click=p["use_file_single_click"],
        use_alt_navigation=p["use_alt_navigation"],
    )


def load_keymaps(src: Path, macos: bool) -> dict:
    """Blender's default keyconfig as {keymap name: items}, macOS-adjusted if asked."""
    ns = runpy.run_path(str(src / KEYMAP_DATA))
    data = ns["generate_keymaps"](params_for(src, ns))
    if macos:
        helpers = runpy.run_path(str(src / PLATFORM_HELPERS))
        data = helpers["keyconfig_data_oskey_from_ctrl_for_macos"](data)
    return {name: items["items"] for name, _parms, items in data}


def action_key(op: str, props) -> str:
    """`idname(k=v,...)` over the item's scalar properties, sorted."""
    pairs = []
    for k, v in (props or {}).get("properties") or []:
        if isinstance(v, (str, int, float, bool)):
            pairs.append(f"{k}={v}")
    return f"{op}({','.join(sorted(pairs))})" if pairs else op


def _mod_states(ev: dict):
    """Every concrete (ctrl, shift, alt, oskey) the event matches, and the one to draw on."""
    if ev.get("any"):
        base = {m: -1 for m, _ in _MODS}
    else:
        base = {m: ev.get(m, 0) for m, _ in _MODS}
    choices = [(0, 1) if base[m] in (-1, "ANY") else (1 if base[m] else 0,) for m, _ in _MODS]
    states = [()]
    for c in choices:
        states = [s + (x,) for s in states for x in c]
    drawn = tuple(1 if (base[m] not in (-1, "ANY") and base[m]) else 0 for m, _ in _MODS)
    return states, drawn


def resolve(keymaps: dict, stack: list[str]) -> dict:
    """{(key token, mod state): (keymap, action key)} for one context stack.

    `mod state` is a (ctrl, shift, alt, oskey) tuple. A chord bound in a higher
    keymap is claimed even when the binding is a "don't care" or an action we do
    not draw, so nothing lower can show through it.
    """
    claimed: dict = {}
    drawn: dict = {}
    for km in stack:
        local: dict = {}
        local_drawn: dict = {}
        for op, ev, props in keymaps[km]:
            key = _KEYS.get(ev.get("type"))
            if key is None or ev.get("value") not in _VALUES or ev.get("key_modifier"):
                continue
            states, draw_state = _mod_states(ev)
            act = (km, action_key(op, props))
            for st in states:
                local[(key, st)] = act          # last item in one keymap wins
            local_drawn[(key, draw_state)] = act
        for chord, act in local.items():
            if chord not in claimed:
                claimed[chord] = act
        for chord, act in local_drawn.items():
            # Draw only where this keymap actually owns the chord.
            if claimed.get(chord) == act and chord not in drawn:
                drawn[chord] = act
    return drawn


def mods_list(state: tuple) -> list[str]:
    return [tok for (bit, (_name, tok)) in zip(state, _MODS) if bit]


def lookup(actions: dict, act: str):
    """actions.yaml entry for an action key.

    The exact key; else the LONGEST `*` pattern matching it (case-sensitive, so
    the answer does not depend on the OS); else the bare idname."""
    if act in actions:
        return actions[act]
    pats = [k for k in actions if "*" in k and fnmatch.fnmatchcase(act, k)]
    if pats:
        return actions[max(pats, key=lambda k: (len(k), k))]
    return actions.get(act.split("(", 1)[0])


def build(src: Path, actions: dict):
    km_default = load_keymaps(src, macos=False)
    km_mac = load_keymaps(src, macos=True)
    resolved = {ctx: resolve(km_default, stack) for ctx, (stack, _d) in STACKS.items()}
    resolved_mac = {ctx: resolve(km_mac, stack) for ctx, (stack, _d) in STACKS.items()}

    # common = the chords that resolve to the same action in every 3D View mode.
    first = resolved[VIEW3D_CONTEXTS[0]]
    resolved["common"] = {c: a for c, a in first.items()
                          if all(resolved[o].get(c) == a for o in VIEW3D_CONTEXTS[1:])}
    first_m = resolved_mac[VIEW3D_CONTEXTS[0]]
    resolved_mac["common"] = {c: a for c, a in first_m.items()
                              if all(resolved_mac[o].get(c) == a for o in VIEW3D_CONTEXTS[1:])}
    return resolved, resolved_mac


def bindings_for(ctx: str, res: dict, res_mac: dict, actions: dict):
    """(bindings list, undrawn list) for one context."""
    out, missing = [], []

    def entry(chord, act, mac_only):
        key, state = chord
        km, ak = act
        spec = lookup(actions, ak)
        if not spec or spec.get("skip"):
            missing.append((key, mods_list(state), km, ak, mac_only, bool(spec)))
            return
        b = {"key": key, "mods": mods_list(state), "label": spec["label"]}
        if spec.get("icon"):
            b["icon"] = f"{spec['icon']}.png"
        for geo in ("mode", "region", "anchor"):     # per-icon render overrides
            if spec.get(geo):
                b[geo] = spec[geo]
        b["source"] = f"{km}: {ak}"
        if mac_only:
            b["only"] = ["macos"]
        out.append(b)

    for chord in sorted(res, key=_chord_sort):
        entry(chord, res[chord], False)
    for chord in sorted(res_mac, key=_chord_sort):
        key, state = chord
        if state[3] and chord not in res:          # a Cmd chord only macOS binds
            entry(chord, res_mac[chord], True)
    return out, missing


def _chord_sort(chord):
    key, state = chord
    return (sum(state), state, key)


HEADER = """\
# GENERATED by gen_blender_bindings.py from Blender {tag} ({commit}) -- do not edit.
# Context: {ctx} -- {desc}
# Keymap stack (highest priority first): {stack}
# Edit actions.yaml (labels/icons) or the generator, then re-run it.
"""


def write_spec(ctx, desc, stack, bindings, tag, commit) -> str:
    spec = {
        "app": "blender",
        "match": ["blender"],
        "output": f"blender_{ctx}_template",
        "icon_dir": "icons",
        "fit": "contain",
        "anchor": "bottom-right",
        "region": [36, 32],
        "margin": 0,
        "mode": "luma",
        "threshold": 150,
        # Simple Icons' Blender logo (marks/si_blender.svg), the same mark the
        # host's runtime ESC path would fetch as si:blender, baked so it shows
        # offline and cannot lose to the OS icon. A finished 72x40 mask, so it
        # is placed full-cell. Chosen by the maintainer over a drawn "Bl" tile
        # (707 lit px, too heavy). See SOURCES.md.
        "program_icon": "blender_mark.png",
        "program_icon_mode": "alpha",
        "program_icon_anchor": "bottom-right",
        "program_icon_region": [72, 40],
        "program_icon_margin": 0,
        "bindings": bindings,
    }
    head = HEADER.format(tag=tag, commit=commit, ctx=ctx, desc=desc,
                         stack=" > ".join(stack))
    return head + yaml.safe_dump(spec, sort_keys=False, width=120, allow_unicode=True)


def _files(ctx: str, out_dir: Path, suffix: str = "") -> list[str]:
    stem = f"blender_{ctx}_template{suffix}"
    tiers = (".mods.png", ".combo.mods.png", ".extra.mods.png", ".gui.mods.png")
    return [stem + t for t in tiers if (out_dir / (stem + t)).exists()]


def mapping_stanza(out_dir: Path) -> str:
    """The overlay-mapping entry, built from the PNGs that actually exist."""
    def fl(files):
        return "[" + ", ".join(files) + "]"

    def block(indent, suffix):
        pad = " " * indent
        # `layer: false`: a context REPLACES the fallback. Without it the
        # matcher's browser layering would draw `common` (3D View keys) dimmed
        # under every context, the Node Editor's included.
        lines = [f"{pad}overlay: {fl(_files('common', out_dir, suffix))}",
                 f"{pad}layer: false",
                 f"{pad}urls-contains:"]
        for needle, ctx in ROUTES:
            lines.append(f"{pad}  \"{needle}\": {{ overlay: {fl(_files(ctx, out_dir, suffix))} }}")
        return lines

    # Windows reports `blender.exe` cut to `blender`; macOS `Blender`; Linux
    # the process (`blender`, also for Steam and the `blender-softwaregl`
    # wrapper, which execs it); Flatpak/Wayland reporters the app id. These are
    # exactly the `blender` names of `browser_url.CONTEXT_REPORTERS` -- a test
    # keeps the two in step.
    names = "blender,org.blender.blender"
    lines = [f"{names}:"] + block(2, "") + ["  os:", "    macos:"] + block(6, "_mac")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--blender-src", type=Path, required=True,
                    help="Blender checkout (only the keyconfig + bl_keymap_utils dirs are read)")
    ap.add_argument("--render", action="store_true",
                    help="also run scripts/generate_app_overlays.py on every binding file")
    ap.add_argument("--preview-root", type=Path, default=None,
                    help="with --render: write <root>/blender_preview_<ctx>/ review sheets")
    ap.add_argument("--list-unmapped", action="store_true",
                    help="print every undrawn action key (curation aid) and exit")
    args = ap.parse_args()

    src = args.blender_src
    git = ["git", "-C", str(src)]
    commit = subprocess.run(git + ["rev-parse", "--short=12", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"
    tag = subprocess.run(git + ["describe", "--tags", "--exact-match"],
                         capture_output=True, text=True).stdout.strip() or "untagged"

    actions = yaml.safe_load((HERE / "actions.yaml").read_text(encoding="utf-8")) or {}
    res, res_mac = build(src, actions)

    contexts = ["common"] + list(STACKS)
    descs = {"common": "chords identical in every 3D View mode; the fallback with no fresh report"}
    stacks = {"common": ["(intersection of the 3D View mode stacks)"]}
    summary, undrawn_all = [], {}
    for ctx in contexts:
        stack, desc = STACKS.get(ctx, (stacks.get(ctx), descs.get(ctx)))
        bindings, missing = bindings_for(ctx, res[ctx], res_mac[ctx], actions)
        undrawn_all[ctx] = missing
        if args.list_unmapped:
            continue
        text = write_spec(ctx, desc, stack, bindings, tag, commit)
        (HERE / f"bindings_{ctx}.yaml").write_text(text, encoding="utf-8")
        n_def = sum(1 for b in bindings if "only" not in b)
        summary.append((ctx, n_def, len(bindings) - n_def, len(missing)))

    if args.list_unmapped:
        seen = {}
        for ctx, miss in undrawn_all.items():
            for key, mods, km, ak, mac_only, _known in miss:
                if mac_only:
                    continue
                seen.setdefault((km, ak), []).append(f"{ctx}:{'+'.join(mods + [key])}")
        for (km, ak), where in sorted(seen.items()):
            print(f"{km:28} {ak:70} {len(where):3}  {where[0]}")
        return 0

    cov = ["# Blender overlays: coverage", "",
           f"Generated from Blender {tag} ({commit}) by `gen_blender_bindings.py`.", "",
           "| context | drawn (Win/Linux) | extra Cmd chords (macOS) | bound but not drawn |",
           "|---|---:|---:|---:|"]
    cov += [f"| `{c}` | {a} | {m} | {u} |" for c, a, m, u in summary]
    cov += ["", "## Bound but not drawn", "",
            "Chords Blender binds in that context that the keycap leaves empty: either",
            "`actions.yaml` has no entry for the operator, or the entry says `skip`",
            "(a modal/internal operator with nothing useful to draw). Cmd duplicates on",
            "macOS are omitted from this list; they mirror the Ctrl row.", ""]
    for ctx in contexts:
        miss = [m for m in undrawn_all[ctx] if not m[4]]
        if not miss:
            continue
        cov.append(f"### `{ctx}`")
        cov.append("")
        for key, mods, km, ak, _mac, known in miss:
            why = "skip" if known else "no entry"
            cov.append(f"- `{'+'.join(mods + [key])}` {km}: `{ak}` ({why})")
        cov.append("")
    (HERE / "COVERAGE.md").write_text("\n".join(cov), encoding="utf-8")

    for ctx, a, m, u in summary:
        print(f"{ctx:15} drawn={a:3} mac_cmd_extra={m:3} undrawn={u:3}")

    if args.render:
        out_dir = REPO_ROOT / "polyhost" / "res" / "overlays"
        for ctx in contexts:
            cmd = [sys.executable, str(REPO_ROOT / "scripts" / "generate_app_overlays.py"),
                   str(HERE / f"bindings_{ctx}.yaml")]
            if args.preview_root:
                cmd += ["--preview", str(args.preview_root / f"blender_preview_{ctx}")]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode:
                print(r.stdout, r.stderr, file=sys.stderr)
                return r.returncode
            warn = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("!")]
            for w in warn:
                print(f"  [{ctx}] {w.strip()}")
        (HERE / "mapping_stanza.yaml").write_text(
            "# GENERATED by gen_blender_bindings.py -- the `blender` entry of "
            "overlay-mapping.poly.yaml.\n" + mapping_stanza(out_dir), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
