#!/usr/bin/env python3
"""Generate PolyKybd overlay PNGs for an application from a binding file.

The PolyKybd overlay PNG format is a 10x9 grid of 72x40 px keycap overlays
(720x360 total). Each colour channel of an RGBA PNG carries one *modifier
variation* of the key in that cell (see polyhost/res/overlay_specification.md):

    primary  "*.mods.png"        R=Ctrl   G=Alt      B=Shift     A=(no mod)
    combo    "*.combo.mods.png"  R=Ctrl+Shift G=Ctrl+Alt B=Alt+Shift A=GUI(dropped)

This script takes a small per-application *binding file* (YAML) that lists each
shortcut as (key, modifiers, icon) and does the tedious, fully-mechanical part:

    1. resolve  (key, mods)            -> (grid cell, file, colour channel)
    2. render   a custom icon PNG      -> 1-bit 72x40 stamp  (scale + threshold)
       (falling back to a text label when the icon art is missing)
    3. pack     the stamp into the correct channel of the correct cell
    4. split    bindings across the primary / combo PNGs automatically
    5. emit     a ready-to-paste overlay-mapping.poly.yaml stanza
    6. preview  a scaled contact sheet per modifier so you can eyeball legibility

Sourcing the shortcut list and the per-action icon art is the human part; the
binding file is where that lives. Everything downstream is automated here.

Usage:
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/notepadpp.yaml
    python scripts/generate_app_overlays.py <bindings.yaml> --out-dir /tmp/ov --preview /tmp/ov
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from polyhost.device.keys import KeyCode, Modifier, keycode_to_mapping_idx  # noqa: E402

GRID_X, GRID_Y = 10, 9
SLOT_W, SLOT_H = 72, 40
IMG_W, IMG_H = GRID_X * SLOT_W, GRID_Y * SLOT_H

# RGBA channel index in the numpy array we build / save.
CH = {"R": 0, "G": 1, "B": 2, "A": 3}

# modifier -> (file kind, channel).  Mirrors polyhost/device/im_converter.py.
PRIMARY_CH = {Modifier.NO_MOD: "A", Modifier.CTRL: "R", Modifier.ALT: "G", Modifier.SHIFT: "B"}
COMBO_CH = {Modifier.CTRL_SHIFT: "R", Modifier.CTRL_ALT: "G", Modifier.ALT_SHIFT: "B",
            Modifier.GUI_KEY: "A"}

MOD_BIT = {"CTRL": 1, "CONTROL": 1, "CTL": 1,
           "SHIFT": 2, "SFT": 2,
           "ALT": 4, "OPT": 4, "OPTION": 4,
           "GUI": 8, "WIN": 8, "CMD": 8, "META": 8, "SUPER": 8}


# --------------------------------------------------------------------------- #
# key-name -> KeyCode (only the 90 keys that actually have an overlay cell)
# --------------------------------------------------------------------------- #
def _build_key_aliases() -> dict[str, KeyCode]:
    a: dict[str, KeyCode] = {}
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        a[c] = KeyCode[f"KC_{c}"]
    for d in "0123456789":
        a[d] = KeyCode[f"KC_{d}"]
    for n in range(1, 13):
        a[f"F{n}"] = KeyCode[f"KC_F{n}"]
    named = {
        "ENTER": "KC_ENTER", "RETURN": "KC_ENTER", "CR": "KC_ENTER",
        "ESC": "KC_ESCAPE", "ESCAPE": "KC_ESCAPE",
        "BACKSPACE": "KC_BACKSPACE", "BKSP": "KC_BACKSPACE", "BSPC": "KC_BACKSPACE",
        "TAB": "KC_TAB", "SPACE": "KC_SPACE", "SPC": "KC_SPACE",
        "MINUS": "KC_MINUS", "-": "KC_MINUS",
        "EQUAL": "KC_EQUAL", "EQUALS": "KC_EQUAL", "=": "KC_EQUAL", "PLUS": "KC_EQUAL",
        "LBRACKET": "KC_LEFT_BRACKET", "[": "KC_LEFT_BRACKET",
        "RBRACKET": "KC_RIGHT_BRACKET", "]": "KC_RIGHT_BRACKET",
        "BACKSLASH": "KC_BACKSLASH", "\\": "KC_BACKSLASH",
        "SEMICOLON": "KC_SEMICOLON", ";": "KC_SEMICOLON",
        "QUOTE": "KC_QUOTE", "'": "KC_QUOTE",
        "GRAVE": "KC_GRAVE", "`": "KC_GRAVE", "TILDE": "KC_GRAVE",
        "COMMA": "KC_COMMA", ",": "KC_COMMA",
        "DOT": "KC_DOT", "PERIOD": "KC_DOT", ".": "KC_DOT",
        "SLASH": "KC_SLASH", "/": "KC_SLASH",
        "CAPS": "KC_CAPS_LOCK", "CAPSLOCK": "KC_CAPS_LOCK",
        "PRINTSCREEN": "KC_PRINT_SCREEN", "PRTSC": "KC_PRINT_SCREEN", "PSCR": "KC_PRINT_SCREEN",
        "SCROLLLOCK": "KC_SCROLL_LOCK", "PAUSE": "KC_PAUSE",
        "INSERT": "KC_INSERT", "INS": "KC_INSERT",
        "HOME": "KC_HOME", "PAGEUP": "KC_PAGE_UP", "PGUP": "KC_PAGE_UP",
        "DELETE": "KC_DELETE", "DEL": "KC_DELETE",
        "END": "KC_END", "PAGEDOWN": "KC_PAGE_DOWN", "PGDN": "KC_PAGE_DOWN",
        "RIGHT": "KC_RIGHT", "LEFT": "KC_LEFT", "DOWN": "KC_DOWN", "UP": "KC_UP",
        "NUMLOCK": "KC_NUM_LOCK", "APP": "KC_APPLICATION", "MENU": "KC_APPLICATION",
    }
    for k, v in named.items():
        a[k] = KeyCode[v]
    return a


KEY_ALIASES = _build_key_aliases()


def resolve_key(token: str) -> KeyCode:
    t = str(token).strip()
    up = t.upper()
    if up in KEY_ALIASES:
        return KEY_ALIASES[up]
    if up.startswith("KC_"):
        try:
            kc = KeyCode[up]
        except KeyError:
            raise ValueError(f"unknown key {token!r}")
        # only the mapped 90 keys carry a cell
        if up in {k.name for k in KEY_ALIASES.values()} or _has_cell(kc):
            return kc
    raise ValueError(f"key {token!r} has no overlay cell (not one of the 90 grid keys)")


def _has_cell(kc: KeyCode) -> bool:
    v = kc.value
    return (KeyCode.KC_A.value <= v <= KeyCode.KC_NUM_LOCK.value
            or v in (KeyCode.KC_NONUS_BACKSLASH.value, KeyCode.KC_APPLICATION.value)
            or KeyCode.KC_LEFT_CTRL.value <= v <= KeyCode.KC_RIGHT_GUI.value)


def resolve_modifier(mods: list[str]) -> Modifier:
    bits = 0
    for m in mods or []:
        key = str(m).strip().upper()
        if key not in MOD_BIT:
            raise ValueError(f"unknown modifier {m!r}")
        bits |= MOD_BIT[key]
    try:
        return Modifier(bits)
    except ValueError:
        raise ValueError(
            f"modifier combination {mods} (bits={bits}) is not representable "
            f"(Ctrl+Alt+Shift and most GUI combos are unsupported by the firmware)")


def cell_for(kc: KeyCode) -> tuple[int, int]:
    slot = keycode_to_mapping_idx(kc)
    row, col = divmod(slot, GRID_X)
    return row, col


# --------------------------------------------------------------------------- #
# rendering a single 72x40 mask
# --------------------------------------------------------------------------- #
# Default placement region inside each 72x40 cell. The firmware draws the real
# key letter in the top-left, so overlays in the existing templates all sit in
# the bottom-right (measured: x~36..71, y reaching the bottom edge). We mirror
# that so the icon never overwrites the legend.
DEFAULT_REGION_W, DEFAULT_REGION_H = 36, 30
DEFAULT_ANCHOR = "bottom-right"
DEFAULT_MARGIN = 2


def region_box(anchor: str, size: tuple[int, int], margin: int) -> tuple[int, int, int, int]:
    """Return (x0, y0, w, h): the sub-rectangle of the 72x40 cell to draw into."""
    bw, bh = min(size[0], SLOT_W), min(size[1], SLOT_H)
    a = anchor.lower()
    if "right" in a:
        x0 = SLOT_W - bw - margin
    elif "left" in a:
        x0 = margin
    else:
        x0 = (SLOT_W - bw) // 2
    if "bottom" in a:
        y0 = SLOT_H - bh - margin
    elif "top" in a:
        y0 = margin
    else:
        y0 = (SLOT_H - bh) // 2
    return max(0, x0), max(0, y0), bw, bh


def _fit_stamp(src: Image.Image, fit: str, region: tuple[int, int, int, int]) -> Image.Image:
    """Scale `src` into `region` and paste onto a full 72x40 canvas (same mode)."""
    x0, y0, bw, bh = region
    if fit == "stretch":
        scaled = src.resize((bw, bh), Image.LANCZOS)
        nw, nh = bw, bh
    else:  # contain: preserve aspect inside the region
        sw, sh = src.size
        scale = min(bw / sw, bh / sh)
        nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
        scaled = src.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new(src.mode, (SLOT_W, SLOT_H), 0 if src.mode == "L" else (0, 0, 0, 0))
    # centre within the region
    canvas.paste(scaled, (x0 + (bw - nw) // 2, y0 + (bh - nh) // 2))
    return canvas


def render_icon(path: Path, fit: str, threshold: int, invert: bool | None,
                region: tuple[int, int, int, int], mode: str = "auto") -> np.ndarray:
    """Load an icon and reduce it to a bool (40,72) lit-pixel mask, placed inside
    `region` (defaults bottom-right, see DEFAULT_ANCHOR).

    `mode`:
      * "alpha" - opaque pixels lit. Good for a glyph on transparent (alpha = shape).
      * "luma"  - light the *dark* pixels (composite over white, threshold). Good
        for duotone/filled icons on a light/transparent background.
      * "bright" - light the *bright* pixels (composite over black, threshold).
        Good for white-on-black / OLED-native art; padding stays unlit.
      * "auto" (default) - alpha when the source has transparency, else luma.
    `invert` flips the result.
    """
    img = Image.open(path).convert("RGBA")
    has_transparency = np.asarray(img.split()[3]).min() < 250
    if mode == "auto":
        mode = "alpha" if has_transparency else "luma"

    fitted = _fit_stamp(img, fit, region)
    if mode == "alpha":
        mask = np.asarray(fitted.split()[3], dtype=np.uint8) > 127
    else:
        arr = np.asarray(fitted, dtype=float)
        a = arr[:, :, 3:4] / 255.0
        if mode == "bright":            # composite over black, light bright pixels
            gray = (arr[:, :, :3] * a) @ [0.2989, 0.5870, 0.1140]
            mask = gray >= threshold
        else:                           # luma: composite over white, light dark pixels
            comp = arr[:, :, :3] * a + 255.0 * (1.0 - a)
            gray = comp @ [0.2989, 0.5870, 0.1140]
            mask = gray < threshold
    return ~mask if invert else mask


_LABEL_FONTS: dict[int, ImageFont.ImageFont] = {}


def _label_font(size: int = 13) -> ImageFont.ImageFont:
    if size not in _LABEL_FONTS:
        font = None
        for cand in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            try:
                font = ImageFont.truetype(cand, size)
                break
            except OSError:
                continue
        _LABEL_FONTS[size] = font or ImageFont.load_default()
    return _LABEL_FONTS[size]


def render_label(text: str, region: tuple[int, int, int, int]) -> np.ndarray:
    """Fallback: render up to two short words white-on-black, auto-sized to fill
    `region` (so a single symbol like '%' renders large, not tiny)."""
    x0, y0, bw, bh = region
    img = Image.new("L", (SLOT_W, SLOT_H), 0)
    draw = ImageDraw.Draw(img)
    words = text.split()
    lines = [text] if len(words) <= 1 else [words[0], " ".join(words[1:])]

    # largest font size whose lines fit within the region
    font, line_h = _label_font(11), 13
    for size in range(min(bh, 40), 6, -1):
        f = _label_font(size)
        try:
            widths = [draw.textlength(ln, font=f) for ln in lines]
        except AttributeError:
            widths = [len(ln) * size * 0.6 for ln in lines]
        lh = size + 2
        if max(widths) <= bw and lh * len(lines) <= bh:
            font, line_h = f, lh
            break

    total_h = line_h * len(lines)
    y = y0 + max(0, (bh - total_h) // 2)
    for line in lines:
        try:
            w = draw.textlength(line, font=font)
        except AttributeError:
            w = len(line) * line_h * 0.6
        draw.text((x0 + (bw - w) / 2, y), line, fill=255, font=font)
        y += line_h
    return np.asarray(img, dtype=np.uint8) > 127


# --------------------------------------------------------------------------- #
# build the overlay images
# --------------------------------------------------------------------------- #
def generate(spec: dict, base_dir: Path) -> dict:
    icon_dir = base_dir / spec.get("icon_dir", "icons")
    fit = spec.get("fit", "contain")
    threshold = int(spec.get("threshold", 128))
    anchor = spec.get("anchor", DEFAULT_ANCHOR)
    margin = int(spec.get("margin", DEFAULT_MARGIN))
    size = tuple(spec.get("region", (DEFAULT_REGION_W, DEFAULT_REGION_H)))
    mode = spec.get("mode", "auto")

    primary = np.zeros((IMG_H, IMG_W, 4), dtype=np.uint8)
    combo = np.zeros((IMG_H, IMG_W, 4), dtype=np.uint8)
    used_primary = used_combo = False
    warnings: list[str] = []
    placed: list[dict] = []

    for b in spec.get("bindings", []):
        try:
            kc = resolve_key(b["key"])
            mod = resolve_modifier(b.get("mods", []))
        except (KeyError, ValueError) as e:
            warnings.append(f"skipped {b}: {e}")
            continue

        if mod in PRIMARY_CH:
            arr, ch_name = primary, PRIMARY_CH[mod]
            used_primary = True
        elif mod in COMBO_CH:
            if mod is Modifier.GUI_KEY:
                warnings.append(f"skipped {b['key']}+GUI: GUI overlays are dropped by the firmware")
                continue
            arr, ch_name = combo, COMBO_CH[mod]
            used_combo = True
        else:
            warnings.append(f"skipped {b}: modifier {mod.name} has no channel")
            continue

        # render the stamp into the per-binding (or default) region
        region = region_box(b.get("anchor", anchor),
                            tuple(b.get("region", size)), int(b.get("margin", margin)))
        icon = b.get("icon")
        label = b.get("label") or b["key"]
        src = (icon_dir / icon) if icon else None
        if src and src.exists():
            mask = render_icon(src, b.get("fit", fit),
                               int(b.get("threshold", threshold)), b.get("invert"),
                               region, b.get("mode", mode))
            source = icon
        else:
            if icon:
                warnings.append(f"icon {icon!r} for {label!r} not found - using text label")
            mask = render_label(label, region)
            source = f"label:{label}"

        row, col = cell_for(kc)
        y0, x0 = row * SLOT_H, col * SLOT_W
        block = arr[y0:y0 + SLOT_H, x0:x0 + SLOT_W, CH[ch_name]]
        block[mask] = 255
        placed.append({"key": kc.name, "mod": mod.name, "ch": ch_name,
                       "cell": (row, col), "src": source, "label": label})

    # Program icon: the app's logo, written into ONE key cell across *all* channels
    # of both PNGs (every modifier layer) so it shows on every layer - a marker of
    # which overlay set is loaded. Defaults to ESC, full-cell, luma.
    prog = spec.get("program_icon")
    if prog:
        src = icon_dir / prog
        if not src.exists():
            warnings.append(f"program_icon {prog!r} not found - skipped")
        else:
            try:
                pkc = resolve_key(spec.get("program_icon_key", "ESC"))
                preg = region_box(spec.get("program_icon_anchor", "center"),
                                  tuple(spec.get("program_icon_region", (72, 40))),
                                  int(spec.get("program_icon_margin", 0)))
                pmask = render_icon(src, spec.get("program_icon_fit", fit),
                                    int(spec.get("program_icon_threshold", threshold)),
                                    spec.get("program_icon_invert"),
                                    preg, spec.get("program_icon_mode", mode))
                row, col = cell_for(pkc)
                y0, x0 = row * SLOT_H, col * SLOT_W
                for arr in (primary, combo):
                    for ax in range(4):              # all channels = all layers
                        block = arr[y0:y0 + SLOT_H, x0:x0 + SLOT_W, ax]
                        block[pmask] = 255
                used_primary = used_combo = True
                placed.append({"key": pkc.name, "mod": "ALL", "ch": "RGBA(x2)",
                               "cell": (row, col), "src": prog, "label": "program icon"})
            except ValueError as e:
                warnings.append(f"program_icon: {e}")

    return {"primary": primary if used_primary else None,
            "combo": combo if used_combo else None,
            "placed": placed, "warnings": warnings}


def save_png(rgba: np.ndarray, path: Path) -> None:
    """Save straight (non-premultiplied) RGBA. PNG keeps RGB bytes where A=0,
    which the loader relies on (the channels carry data independent of alpha)."""
    Image.fromarray(rgba, mode="RGBA").save(path)


# --------------------------------------------------------------------------- #
# preview contact sheet
# --------------------------------------------------------------------------- #
_MOD_SHORT = {"NO_MOD": "", "CTRL": "Ctrl", "SHIFT": "Shift", "CTRL_SHIFT": "Ctrl+Shift",
              "ALT": "Alt", "CTRL_ALT": "Ctrl+Alt", "ALT_SHIFT": "Alt+Shift",
              "GUI_KEY": "Gui", "ALL": ""}


def _plane_for(result: dict, mod_name: str):
    """Return (overlay array, channel index) holding the cell for a placed entry's
    modifier — reading back the REAL rendered overlay, so the preview shows exactly
    what ships (icon position, size, 1-bit threshold) including the program icon."""
    if mod_name == "ALL":                         # program icon: any channel works
        return result["primary"], CH["A"]
    mod = Modifier[mod_name]
    if mod in PRIMARY_CH:
        return result["primary"], CH[PRIMARY_CH[mod]]
    if mod in COMBO_CH:
        return result["combo"], CH[COMBO_CH[mod]]
    return None, None


def write_preview(result: dict, out: Path, scale: int = 6, cols: int = 6) -> list[Path]:
    """Single review sheet of the ORIGINAL overlay: only the populated keys, each
    drawn in its full 72x40 cell (so real placement is visible), enlarged and
    labelled `Mod+Key: action`. The program icon (ESC, all layers) is included
    once in its real position. Lit pixels are black on white for on-screen
    clarity (the OLED shows white-on-black)."""
    out.mkdir(parents=True, exist_ok=True)
    items = []
    for e in result.get("placed", []):
        arr, ch = _plane_for(result, e["mod"])
        if arr is None:
            continue
        r, c = e["cell"]
        cell = arr[r * SLOT_H:(r + 1) * SLOT_H, c * SLOT_W:(c + 1) * SLOT_W, ch] > 127
        key = e["key"].replace("KC_", "")
        if e["mod"] == "ALL":
            label = f"{key}: {e.get('label', 'program')} ★"   # program-icon marker
        else:
            ms = _MOD_SHORT.get(e["mod"], e["mod"])
            label = (f"{ms}+{key}" if ms else key) + (f": {e['label']}" if e.get("label") else "")
        items.append((cell, label, e["mod"] == "ALL"))
    if not items:
        return []

    cw, chh, lbl, pad = SLOT_W * scale, SLOT_H * scale, 22, 10
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cw + pad) + pad, rows * (chh + lbl + pad) + pad + 30),
                      (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 8), "Overlay preview - populated keys in real placement "
           "(black = lit; ★ = program icon)", fill=(0, 0, 0), font=_label_font())
    for i, (cell, label, prog) in enumerate(items):
        rr, cc = divmod(i, cols)
        x0, y0 = pad + cc * (cw + pad), 30 + pad + rr * (chh + lbl + pad)
        stamp = Image.fromarray((~cell * 255).astype(np.uint8), "L").resize(
            (cw, chh), Image.NEAREST).convert("RGB")
        sheet.paste(stamp, (x0, y0 + lbl))
        d.rectangle([x0, y0 + lbl, x0 + cw - 1, y0 + chh + lbl - 1], outline=(120, 120, 120))
        d.text((x0 + 2, y0 + 3), label, fill=(180, 0, 0) if prog else (0, 110, 0),
               font=_label_font())
    p = out / "overlay_preview.png"
    sheet.save(p)
    return [p]


def mapping_stanza(spec: dict, out_dir_label: str) -> str:
    names = spec.get("match") or [spec.get("app", "app")]
    files = []
    if spec.get("_has_primary"):
        files.append(f"{spec['output']}.mods.png")
    if spec.get("_has_combo"):
        files.append(f"{spec['output']}.combo.mods.png")
    overlay = files[0] if len(files) == 1 else "[" + ", ".join(files) + "]"
    title = spec.get("title")
    lines = [f"{','.join(names)}:", f"  overlay: {overlay}"]
    if title:
        lines.append(f"  title: {title}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bindings", type=Path, help="binding YAML file for the app")
    ap.add_argument("--out-dir", type=Path,
                    default=REPO_ROOT / "polyhost" / "res" / "overlays",
                    help="where to write the overlay PNGs (default: polyhost/res/overlays/)")
    ap.add_argument("--preview", type=Path, default=None,
                    help="also write scaled contact-sheet previews to this dir")
    ap.add_argument("--dry-run", action="store_true",
                    help="render + report but do not write the overlay PNGs")
    args = ap.parse_args()

    spec = yaml.safe_load(args.bindings.read_text())
    base_dir = args.bindings.resolve().parent
    result = generate(spec, base_dir)

    spec["_has_primary"] = result["primary"] is not None
    spec["_has_combo"] = result["combo"] is not None

    print(f"Placed {len(result['placed'])} overlays for {spec.get('app', '?')}:")
    for p in result["placed"]:
        print(f"  {p['key']:<18} {p['mod']:<11} ch={p['ch']} cell={p['cell']}  <- {p['src']}")
    for w in result["warnings"]:
        print(f"  ! {w}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        if result["primary"] is not None:
            save_png(result["primary"], args.out_dir / f"{spec['output']}.mods.png")
            print(f"Wrote {args.out_dir / (spec['output'] + '.mods.png')}")
        if result["combo"] is not None:
            save_png(result["combo"], args.out_dir / f"{spec['output']}.combo.mods.png")
            print(f"Wrote {args.out_dir / (spec['output'] + '.combo.mods.png')}")

    if args.preview:
        for p in write_preview(result, args.preview):
            print(f"Preview {p}")

    print("\n--- paste into polyhost/res/overlay-mapping.poly.yaml ---")
    print(mapping_stanza(spec, str(args.out_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
