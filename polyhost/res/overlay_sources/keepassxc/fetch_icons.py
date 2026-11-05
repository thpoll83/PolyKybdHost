#!/usr/bin/env python3
"""Fetch and render the KeePassXC shortcut icons.

Most icons are KeePassXC's OWN toolbar and menu icons, from
`share/icons/application/scalable/` of keepassxreboot/keepassxc at tag 2.8.0.
They are the pictures a KeePassXC user already sees in the menus. KeePassXC's
COPYING lists them as Pictogrammers Material Design Icons, Apache-2.0
("some icons are modified to fit KeePassXC design"). Apache-2.0 is compatible
with this host's GPL-3.0-or-later.

The ESC program mark is KeePassXC's own monochrome tray icon
(`apps/keepassxc-monochrome-light.svg`). COPYING names no separate licence for
it, so the repository licence applies: GPL-2 or GPL-3.

Fluent UI System Icons (MIT) and Material Symbols (Apache-2.0) fill the actions
KeePassXC has no icon for. The SSH agent add and remove icons are drawn here:
KeePassXC uses one terminal icon for both, so a plus or minus is added.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/keepassxc/fetch_icons.py
"""
from __future__ import annotations

import sys
import time
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import icon_fetch  # noqa: E402
import number_badge  # noqa: E402

TAG = "2.8.0"
RAW = ("https://raw.githubusercontent.com/keepassxreboot/keepassxc/"
       f"{TAG}/share/icons/application/scalable/{{}}.svg")
RENDER_PX = 96

# {file stem: path below share/icons/application/scalable/, without .svg}
OWN = {
    "kp_settings": "actions/configure",
    "kp_dbsettings": "actions/database-settings",
    "kp_open": "actions/document-open",
    "kp_save": "actions/document-save",
    "kp_saveas": "actions/document-save-as",
    "kp_newdb": "actions/document-new",
    "kp_lock": "actions/database-lock",
    "kp_lockall": "actions/database-lock-all",
    "kp_reports": "actions/reports",
    "kp_quit": "actions/application-exit",
    "kp_entrynew": "actions/entry-new",
    "kp_entryedit": "actions/entry-edit",
    "kp_entrydelete": "actions/entry-delete",
    "kp_entryclone": "actions/entry-clone",
    "kp_entryrestore": "actions/entry-restore",
    "kp_copyuser": "actions/username-copy",
    "kp_copypass": "actions/password-copy",
    "kp_copyurl": "actions/url-copy",
    "kp_openurl": "actions/web",
    "kp_copytotp": "actions/totp-copy",
    "kp_copypasstotp": "actions/totp-copy-password",
    "kp_showtotp": "actions/totp",
    "kp_autotype": "actions/auto-type",
    "kp_moveup": "actions/move-up",
    "kp_movedown": "actions/move-down",
    "kp_sortasc": "actions/sort-alphabetical-ascending",
    "kp_sortdesc": "actions/sort-alphabetical-descending",
    "kp_hidepass": "actions/password-show-off",
    "kp_search": "actions/database-search",
    "kp_shortcuts": "actions/keyboard-shortcuts",
    "kp_favicon": "actions/favicon-download",
    "kp_terminal": "apps/utilities-terminal",
    "kp_copytitle": "actions/attributes-copy",
}

FLUENT = {
    "kp_minimize": "Subtract Square",
    "kp_hidewindow": "ms:select_window_off",
    "kp_hideuser": "ms:person_off",
    "kp_nexttab": "Arrow Next",
    "kp_prevtab": "Arrow Previous",
    "kp_nextgroup": "Folder Arrow Right",
    "kp_prevgroup": "Folder Arrow Left",
    "kp_jumpgroup": "Folder Arrow Up",
    "kp_focusgroups": "Folder",
    "kp_focusentries": "Text Bullet List",
    "kp_ontop": "Pin",
    "kp_database": "Database",
}

PROGMARK = "apps/keepassxc-monochrome-light"


def _get(url: str, tries: int = 4) -> bytes:
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)
    raise RuntimeError(url)


def own(mapping: dict[str, str], out: Path) -> int:
    for stem, path in mapping.items():
        svg = _get(RAW.format(path))
        png = cairosvg.svg2png(bytestring=svg, output_width=RENDER_PX,
                               output_height=RENDER_PX)
        (out / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- keepassxc {TAG} {path}.svg")
    return len(mapping)


def badge(base: Path, dest: Path, sign: str) -> None:
    """The terminal icon with a plus or minus in the top-right corner.

    The sign is opaque and the cleared disc transparent, so the binding's alpha
    mode reads it the same way as the KeePassXC icons.
    """
    im = Image.open(base).convert("RGBA")
    w, h = im.size
    big = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
    big.paste(im.resize((w * 4, h * 4), Image.LANCZOS))
    d = ImageDraw.Draw(big)
    s = w * 4
    # Top right is empty in the ">_" icon. A minus at the bottom would read as
    # the prompt's own underscore.
    cx, cy, r = int(s * 0.78), int(s * 0.24), int(s * 0.22)
    # Clear a disc so the sign does not touch the terminal outline.
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 0))
    bar, half = int(s * 0.07), int(s * 0.16)
    colour = (0, 0, 0, 255)
    d.rectangle([cx - half, cy - bar // 2, cx + half, cy + bar // 2], fill=colour)
    if sign == "+":
        d.rectangle([cx - bar // 2, cy - half, cx + bar // 2, cy + half], fill=colour)
    big.resize((w, h), Image.LANCZOS).save(dest)
    print(f"  {dest.name}  <- drawn: terminal icon {sign}")


def close_db(base: Path, dest: Path) -> None:
    """The database cylinder with a bold X inside, for Close database.

    KeePassXC's own `document-close` is a bare X, which reads as any "close" on
    a keycap. The cylinder ties it to the numbered database tab icons.
    """
    im = Image.open(base).convert("RGBA")
    d = ImageDraw.Draw(im)
    for a, b in (((36, 46), (60, 72)), ((60, 46), (36, 72))):
        d.line([a, b], fill=(0, 0, 0, 255), width=7)
    im.save(dest)
    print(f"  {dest.name}  <- drawn: database cylinder + X")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = own(OWN, out)
    n += icon_fetch.fluent(FLUENT, out)
    badge(out / "kp_terminal.png", out / "kp_agentadd.png", "+")
    badge(out / "kp_terminal.png", out / "kp_agentremove.png", "-")
    n += 2
    # Ctrl+1..9 selects database tab N (9 is the last tab): the number is the
    # information, so it is drawn inside the database glyph.
    # Smaller and lower than the number_badge default, so the digit clears the
    # cylinder's top rim.
    n += number_badge.numbered(out / "kp_database.png", "123456789", out, "kp_db",
                               size=44 / 96, centre=(0.50, 0.64))
    close_db(out / "kp_database.png", out / "kp_closedb.png")
    n += 1

    mark = out / "progmark.png"
    if mark.exists():
        print("  progmark.png  <- committed asset (left as-is)")
    else:
        svg = _get(RAW.format(PROGMARK))
        mark.write_bytes(cairosvg.svg2png(bytestring=svg, output_width=128,
                                          output_height=128))
        print(f"  progmark.png  <- keepassxc {TAG} {PROGMARK}.svg")
    n += 1
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
