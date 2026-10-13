#!/usr/bin/env python3
"""Derive bindings.yaml from Zed's three default keymaps (see SOURCES.md).

    .venv/bin/python polyhost/res/overlay_sources/zed/derive_bindings.py <zed checkout> [out]

Reads <zed>/assets/keymaps/default-{windows,linux,macos}.json and the committed,
hand-chosen table `derive_table.yaml` (contexts, skips, labels, icons, header),
and writes `bindings.yaml` next to this file unless `out` is given. Mechanical
rules, all here:

* A context's depth decides precedence (deeper wins; later block wins at equal
  depth; `null` unbinds). A negative depth only fills cells nothing else binds.
* Two-stroke chords, Escape, media keys and `fn-` are not drawable. Shifted
  punctuation is the US-layout key plus Shift (`ctrl-{` = Ctrl+Shift+[).
* An action's chords are grouped across platforms. A chord becomes `CMDCTRL`
  only if the same action sits on Ctrl+X (Windows/Linux) AND Cmd+X (macOS);
  otherwise it stays literal. A group not bound on all three gets `only:`.
* The keymaps are JSON with comments and trailing commas; the parser strips both.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PLATS = ("windows", "linux", "macos")
MODMAP = {"ctrl": "CTRL", "alt": "ALT", "shift": "SHIFT", "cmd": "GUI", "super": "GUI", "win": "GUI"}
SHIFTED = {"{": "[", "}": "]", "|": "\\", ":": ";", '"': "'", "~": "`", "<": ",", ">": ".",
           "?": "/", "_": "-", "+": "=", ")": "0", "!": "1", "@": "2", "#": "3", "$": "4",
           "%": "5", "^": "6", "&": "7", "*": "8", "(": "9"}
NAMED = {"pageup": "PGUP", "pagedown": "PGDN", "up": "UP", "down": "DOWN", "left": "LEFT",
         "right": "RIGHT", "home": "HOME", "end": "END", "insert": "INSERT", "delete": "DELETE",
         "backspace": "BACKSPACE", "enter": "ENTER", "tab": "TAB", "space": "SPACE"}
PUNCT = set("-=[]\\;',./`")
MODORDER = ["CMDCTRL", "CTRL", "GUI", "ALT", "SHIFT"]


def strip_jsonc(s: str) -> str:
    out, i, n, ins = [], 0, len(s), False
    while i < n:
        c = s[i]
        if ins:
            out.append(c)
            if c == "\\":
                out.append(s[i + 1]); i += 2; continue
            if c == '"':
                ins = False
            i += 1; continue
        if c == '"':
            ins = True; out.append(c); i += 1; continue
        if s.startswith("//", i):
            j = s.find("\n", i); i = n if j < 0 else j; continue
        if s.startswith("/*", i):
            i = s.find("*/", i) + 2; continue
        out.append(c); i += 1
    return re.sub(r",(\s*[\]}])", r"\1", "".join(out))


def parse(k: str):
    """Zed keystroke -> (frozenset(mods), key token), or None if not drawable."""
    if " " in k:
        return None
    parts = k[:-2].split("-") + ["-"] if k.endswith("--") else k.split("-")
    key = parts[-1]
    if any(m not in MODMAP for m in parts[:-1]):
        return None
    mods = {MODMAP[m] for m in parts[:-1]}
    if key in SHIFTED:
        key = SHIFTED[key]; mods.add("SHIFT")
    if len(key) == 1 and key.isalnum():
        key = key.upper()
    elif key in PUNCT:
        pass
    elif key in NAMED:
        key = NAMED[key]
    elif re.fullmatch(r"f([1-9]|1[0-2])", key):
        key = key.upper()
    else:
        return None
    return frozenset(mods), key


def act(a):
    if a is None:
        return None
    if isinstance(a, list):
        return a[0] + (" " + json.dumps(a[1], sort_keys=True) if len(a) > 1 else "")
    return a


def raw_lines(text: str):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r'\s*"((?:[^"\\]|\\.)+)"\s*:\s*(?!\{)', line)
        if m and m.group(1) not in ("context", "use_key_equivalents", "bindings"):
            out.append((i, json.loads('"' + m.group(1) + '"')))
    return out


def resolve(path: Path, depth: dict):
    """{chord: (action, line)} for one platform keymap."""
    text = path.read_text(encoding="utf-8")
    rl, ptr, cells = raw_lines(text), 0, {}
    for blk in json.loads(strip_jsonc(text)):
        c = blk.get("context")
        for k, a in blk.get("bindings", {}).items():
            j = ptr
            while j < len(rl) and rl[j][1] != k:
                j += 1
            if j < len(rl):
                line, ptr = rl[j][0], j + 1
            else:
                line = 0
            if c not in depth:
                continue
            ch = parse(k)
            if ch is None:
                continue
            d = depth[c]
            if ch in cells and cells[ch][0] > d:
                continue
            if d < 0 and (ch in cells or a is None):
                continue
            cells[ch] = (d, act(a), line)
    return {ch: (a, line) for ch, (d, a, line) in cells.items() if a is not None}


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__); return 2
    kdir = Path(sys.argv[1]) / "assets" / "keymaps"
    out = Path(sys.argv[2]) if len(sys.argv) == 3 else HERE / "bindings.yaml"
    T = yaml.safe_load((HERE / "derive_table.yaml").read_text(encoding="utf-8"))
    depth = T["contexts"]
    skip_prefix, skip = tuple(T["skip_prefix"]), set(T["skip"])
    reclaimed = set(T["reclaimed"])
    A = {a: tuple(v) for a, v in T["actions"].items()}

    def lookup(a):
        return A.get(a) or A.get(a.split(" ", 1)[0])

    P = {p: resolve(kdir / f"default-{p}.json", depth) for p in PLATS}
    unknown, skipped = collections.Counter(), collections.Counter()
    groups = collections.defaultdict(dict)
    for p in PLATS:
        for (mods, key), (a, line) in P[p].items():
            if a.startswith(skip_prefix) or a.split(" ", 1)[0] in skip:
                skipped[a] += 1; continue
            if lookup(a) is None:
                unknown[a] += 1; continue
            m = set(mods)
            if p == "macos" and "GUI" in m and "CTRL" not in m:
                m = (m - {"GUI"}) | {"CMDCTRL"}
            elif p != "macos" and "CTRL" in m and "GUI" not in m:
                m = (m - {"CTRL"}) | {"CMDCTRL"}
            groups[(a, frozenset(m), key)][p] = line
    if unknown:
        print("Actions missing from derive_table.yaml (add them, or skip them):", file=sys.stderr)
        for a in sorted(unknown):
            print("  ", a, file=sys.stderr)
        return 1
    final = collections.defaultdict(dict)
    for (a, m, key), pl in groups.items():
        if "CMDCTRL" in m and not ("macos" in pl and set(pl) - {"macos"}):
            for p, line in pl.items():
                lit = (m - {"CMDCTRL"}) | ({"GUI"} if p == "macos" else {"CTRL"})
                final[(a, frozenset(lit), key)][p] = line
        else:
            final[(a, m, key)].update(pl)

    order = {a: i for i, a in enumerate(A)}
    by_group = collections.defaultdict(list)
    for (a, m, key), pl in final.items():
        grp, label, icon = lookup(a)
        by_group[grp].append((order.get(a, order.get(a.split(" ", 1)[0])), key,
                              sorted(m, key=MODORDER.index), a, label, icon, pl))
    lines = []
    for grp in dict.fromkeys(v[0] for v in A.values()):
        rows = sorted(by_group.get(grp, []), key=lambda r: (r[0], -len(r[6]), r[1], r[2]))
        if not rows:
            continue
        lines.append(f"\n  # --- {grp} ---")
        for _, key, mods, a, label, icon, pl in rows:
            parts = [f"key: {json.dumps(key) if not key.isalpha() else key}",
                     f"mods: [{', '.join(mods)}]"]
            if len(pl) < 3:
                parts.append(f"only: [{', '.join(p for p in PLATS if p in pl)}]")
            if icon:
                parts.append(f"icon: {icon}")
                if icon in reclaimed:
                    parts.append("<<: *reclaimed")
            parts.append(f"label: {json.dumps(label)}")
            src = " ".join(f"{p[0]}{pl[p]}" for p in PLATS if p in pl)
            parts.append(f'source: "{a.split(" ", 1)[0]} @ {src}"')
            lines.append("  - { " + ", ".join(parts) + " }")
    out.write_text(T["header"].rstrip("\n") + "\n\nbindings:" + "\n".join(lines) + "\n",
                   encoding="utf-8")
    n = sum(1 for x in lines if x.startswith("  - {"))
    print(f"wrote {n} bindings to {out}; skipped {sum(skipped.values())} chords", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
