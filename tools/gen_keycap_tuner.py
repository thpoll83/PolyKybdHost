#!/usr/bin/env python3
"""Generate a self-contained HTML keycap tuner for any PolyKybd language layout.

    python gen_keycap_tuner.py --lang ps-AF
    python gen_keycap_tuner.py --lang te-IN --out /tmp/te.html

The tuner is a single offline HTML file (open it in a browser) that renders the
per-keycap OLED preview *exactly* like the firmware and lets you nudge each glyph
(base / Shift / AltGr) and the whole-layout offsets, then export the changes.

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


def extract(lang: str, qmk: str) -> dict:
    pk = os.path.join(qmk, 'keyboards', 'handwired', 'polykybd')
    named = op.load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    L = op.Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    R = op.Renderer(op.load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    if lang not in L.langs:
        sys.exit(f"unknown lang {lang}; have {L.langs}")
    li = L.langs.index(lang)

    cp2name = {}                                   # reverse map for a readable export token
    for nm, cps in named.items():
        if len(cps) == 1 and cps[0] not in cp2name:
            cp2name[cps[0]] = nm

    def tok_for(g):
        if not g:
            return ""
        if len(g) == 1 and g[0] in cp2name:
            return cp2name[g[0]]
        return "".join(chr(c) if 0x20 <= c < 0x7f and chr(c) not in '"\\' else f"\\x{c:x}" for c in g)

    def split_cps(cps):
        """Split resolved codepoints into leading positioning escapes + the glyph(s)."""
        if not cps:
            return None
        esc, i = [], 0
        while i < len(cps) and cps[i] in CTRL:
            esc.append(cps[i]); i += 1
        return {"esc": esc, "glyph": cps[i:], "tok": tok_for(cps[i:]), "fb": False}

    keys, used = {}, set()
    for rowk in op.SHEET:
        for kc in rowk:
            if kc not in op.ROW:
                continue
            row = op.ROW[kc]; e = {}
            used_lang, base_cps = L.small(li, row)              # base: en-US fallback (like the firmware)
            e["base"] = split_cps(base_cps)
            if e["base"] and used_lang != li:
                e["base"]["fb"] = True
            scps = L.var(li, row, op.VAR_SHIFT)                 # shift: fallback only if no own shift+base
            if scps is None and L.cell(li, row, op.VAR_SMALL) is None:
                scps = L.var(0, row, op.VAR_SHIFT)
            e["shift"] = split_cps(scps)
            e["altgr"] = split_cps(L.var(li, row, op.VAR_ALTGR))   # altgr: no fallback
            keys[kc] = e
            for el in e.values():
                if el:
                    used.update(c for c in el["glyph"] if c >= 0x20)

    glyphs = {}
    for cp in sorted(used):
        f = R._font(cp)
        if not f or not (f.first <= cp <= f.last):
            continue
        g = f.glyphs[cp - f.first]; w, h = g['width'], g['height']
        nb = math.ceil(w * h / 8) if w > 0 and h > 0 else 0
        glyphs[str(cp)] = {"w": w, "h": h, "xadv": g['xAdvance'], "xo": g['xOffset'], "yo": g['yOffset'],
                           "yadv": f.yAdvance, "bits": list(f.bitmap[g['bitmapOffset']:g['bitmapOffset'] + nb])}

    def off(cat, var):
        vrow, hrow = op.SET[cat]
        return {"H": op.get_setting(L, hrow, li, var), "V": op.get_setting(L, vrow, li, var)}

    offsets = {c: {v: off(c, getattr(op, f"VAR_{v.upper()}")) for v in ["small", "shift", "altgr"]}
               for c in ["letter", "num", "sym"]}
    return {"lang": lang, "rows": op.SHEET, "keys": keys, "glyphs": glyphs, "offsets": offsets,
            "base_yadv": R.fonts[0].yAdvance, "HIDE": op.HIDE,
            "consts": {"BASELINE": op.BASELINE, "BUFFER_X": op.BUFFER_X, "OLED_W": op.OLED_W,
                       "OLED_H": op.OLED_H, "SCREEN_WIDTH": op.SCREEN_WIDTH}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', required=True, help='e.g. ps-AF, te-IN, hi-IN')
    ap.add_argument('--qmk', default=os.path.join(os.path.dirname(os.path.dirname(HERE)), 'qmk_firmware'))
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    data = extract(a.lang, a.qmk)
    tmpl = open(os.path.join(HERE, 'keycap_tuner_template.html'), encoding='utf-8').read()
    html = tmpl.replace('__DATA__', json.dumps(data)).replace('__LANG__', a.lang)
    out = a.out or os.path.join('/tmp', f'{a.lang}_tuner.html')
    open(out, 'w', encoding='utf-8').write(html)
    print(f"wrote {out}  ({len(data['keys'])} keys, {len(data['glyphs'])} glyphs)")


if __name__ == '__main__':
    main()
