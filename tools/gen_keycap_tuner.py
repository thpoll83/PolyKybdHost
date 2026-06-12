#!/usr/bin/env python3
"""Generate a self-contained HTML keycap tuner for PolyKybd language layouts.

    .venv/bin/python gen_keycap_tuner.py --lang ps-AF            # one layout
    .venv/bin/python gen_keycap_tuner.py --lang te-IN --out /tmp/te.html
    .venv/bin/python gen_keycap_tuner.py --all                   # every layout, one file
    .venv/bin/python gen_keycap_tuner.py --all --out /tmp/all.html

The tuner is a single offline HTML file (open it in a browser) that renders the
per-keycap OLED preview *exactly* like the firmware and lets you nudge each glyph
(base / Shift / AltGr) and the whole-layout offsets, then export the changes.

With --all every layout is baked into the same file behind a dropdown. The glyph
bitmaps are stored once in a *shared pool* keyed by codepoint (Latin layouts reuse
the same a/b/c bitmaps), so the file stays a few MB even with every script. Edits
are kept per-layout while you switch; Export emits one `=== code ===` block per
edited layout, which apply_tuner.py writes straight back into lang_lut.xlsx.

It reuses oled_preview.py for the layout/glyph/offset data, so the JS render mirror
in keycap_tuner_template.html MUST be kept in sync with oled_preview.render_key /
Renderer.bounds / Renderer.draw (which themselves mirror the firmware — see
KEYCAP_TUNER.md). Verify with the headless diff documented there after any change.
"""
import sys, json, math, os, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oled_preview as op

CTRL = {0x05, 0x06, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x18}   # cursor / positioning control codes


def reverse_named(named: dict) -> dict:
    """codepoint -> a readable named-glyph token (for a friendlier export)."""
    cp2name = {}
    for nm, cps in named.items():
        if len(cps) == 1 and cps[0] not in cp2name:
            cp2name[cps[0]] = nm
    return cp2name


def make_tok_for(cp2name: dict):
    def tok_for(g):
        if not g:
            return ""
        if len(g) == 1 and g[0] in cp2name:
            return cp2name[g[0]]
        return "".join(chr(c) if 0x20 <= c < 0x7f and chr(c) not in '"\\' else f"\\x{c:x}" for c in g)
    return tok_for


def split_cps(cps, tok_for):
    """Split resolved codepoints into leading positioning escapes + the glyph(s)."""
    if not cps:
        return None
    esc, i = [], 0
    while i < len(cps) and cps[i] in CTRL:
        esc.append(cps[i]); i += 1
    return {"esc": esc, "glyph": cps[i:], "tok": tok_for(cps[i:]), "fb": False}


def extract_lang(L: "op.Lang", li: int, tok_for) -> tuple:
    """Per-key base/Shift/AltGr tokens + category offsets for one language index.

    Returns (keys, offsets, used) where `used` is the set of glyph codepoints the
    caller folds into the shared pool.
    """
    keys, used = {}, set()
    for rowk in op.SHEET:
        for kc in rowk:
            if kc not in op.ROW:
                continue
            row = op.ROW[kc]; e = {}
            used_lang, base_cps = L.small(li, row)              # base: en-US fallback (like the firmware)
            e["base"] = split_cps(base_cps, tok_for)
            if e["base"] and used_lang != li:
                e["base"]["fb"] = True
            scps = L.var(li, row, op.VAR_SHIFT)                 # shift: fallback only if no own shift+base
            if scps is None and L.cell(li, row, op.VAR_SMALL) is None:
                scps = L.var(0, row, op.VAR_SHIFT)
            e["shift"] = split_cps(scps, tok_for)
            e["altgr"] = split_cps(L.var(li, row, op.VAR_ALTGR), tok_for)   # altgr: no fallback
            keys[kc] = e
            for el in e.values():
                if el:
                    used.update(c for c in el["glyph"] if c >= 0x20)

    def off(cat, var):
        vrow, hrow = op.SET[cat]
        return {"H": op.get_setting(L, hrow, li, var), "V": op.get_setting(L, vrow, li, var)}

    offsets = {c: {v: off(c, getattr(op, f"VAR_{v.upper()}")) for v in ["small", "shift", "altgr"]}
               for c in ["letter", "num", "sym"]}
    return keys, offsets, used


def glyph_pool(R: "op.Renderer", used: set) -> dict:
    """Shared codepoint -> GFX glyph metrics + bitmap for every glyph any layout uses."""
    glyphs = {}
    for cp in sorted(used):
        f = R._font(cp)
        if not f or not (f.first <= cp <= f.last):
            continue
        g = f.glyphs[cp - f.first]; w, h = g['width'], g['height']
        nb = math.ceil(w * h / 8) if w > 0 and h > 0 else 0
        glyphs[str(cp)] = {"w": w, "h": h, "xadv": g['xAdvance'], "xo": g['xOffset'], "yo": g['yOffset'],
                           "yadv": f.yAdvance, "bits": list(f.bitmap[g['bitmapOffset']:g['bitmapOffset'] + nb])}
    return glyphs


def build_data(qmk: str, codes=None) -> dict:
    """codes=None -> every layout in lang_lut.xlsx; else the given list (in order)."""
    pk = os.path.join(qmk, 'keyboards', 'handwired', 'polykybd')
    named = op.load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    L = op.Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    R = op.Renderer(op.load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    tok_for = make_tok_for(reverse_named(named))

    order = list(L.langs) if codes is None else list(codes)
    for c in order:
        if c not in L.langs:
            sys.exit(f"unknown lang {c}; have {len(L.langs)} langs ({', '.join(L.langs[:6])} ...)")

    langs, used = {}, set()
    for c in order:
        keys, offsets, u = extract_lang(L, L.langs.index(c), tok_for)
        langs[c] = {"keys": keys, "offsets": offsets}
        used |= u

    return {"order": order, "langs": langs, "glyphs": glyph_pool(R, used), "rows": op.SHEET,
            "base_yadv": R.fonts[0].yAdvance, "HIDE": op.HIDE,
            "consts": {"BASELINE": op.BASELINE, "BUFFER_X": op.BUFFER_X, "OLED_W": op.OLED_W,
                       "OLED_H": op.OLED_H, "SCREEN_WIDTH": op.SCREEN_WIDTH}}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--lang', help='single layout, e.g. ps-AF, te-IN, hi-IN')
    g.add_argument('--all', action='store_true', help='bake every layout into one file (dropdown)')
    ap.add_argument('--qmk', default=os.path.join(os.path.dirname(os.path.dirname(HERE)), 'qmk_firmware'))
    ap.add_argument('--out', default=None)
    a = ap.parse_args()

    codes = None if a.all else [a.lang]
    data = build_data(a.qmk, codes)
    tmpl = open(os.path.join(HERE, 'keycap_tuner_template.html'), encoding='utf-8').read()
    # escape "</" so a glyph/token containing "</script>" can't close the <script> block
    data_json = json.dumps(data).replace('</', '<\\/')
    html = tmpl.replace('__DATA__', data_json)
    out = a.out or os.path.join('/tmp', ('all' if a.all else a.lang) + '_tuner.html')
    open(out, 'w', encoding='utf-8').write(html)
    nkeys = sum(len(v["keys"]) for v in data["langs"].values())
    print(f"wrote {out}  ({len(data['order'])} layout(s), {nkeys} keys, {len(data['glyphs'])} shared glyphs)")


if __name__ == '__main__':
    main()
