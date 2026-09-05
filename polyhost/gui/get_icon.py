import pathlib

from PyQt5.QtGui import QIcon

# Every .svg in res/icons is a Google Material Symbol (Apache 2.0, weight 400,
# viewBox "0 -960 960 960") with a single `fill` on the <svg> element. The fill
# is not decorative — it groups the menu by meaning, so keep new icons on this
# palette:
#
#   #5985E1  blue    object / configuration      (keyboard, language, settings)
#   #78A75A  green   enabled / ok                (toggle_on, select_all, sync)
#   #999999  grey    off / cleared               (toggle_off, deselect)
#   #DA954B  amber   caution, staged             (usb, bug_report, deployed_code)
#   #D16D6A  red     destructive, reboots        (power, deployed_code_update)
#   #8B7DBE  purple  overlay domain              (overlays, layers_clear)
#   #FFFF55  yellow  brightness ramp             (backlight_*)
#
# One glyph should mean one thing: before reusing an icon for a second action,
# check it is not already spoken for elsewhere in the tray menu.
_ICON_DIR = pathlib.Path(__file__).parent.parent.resolve() / "res" / "icons"

# Icons are immutable on disk, so cache the QIcon per name. Without this,
# get_icon re-read the file on every call (48 call sites) — and the tray icon
# is rebuilt on every overlay send / app switch (set_thinking/set_idle) plus
# every menu rebuild, so that disk churn ran on the Qt main thread and showed
# up as lag when opening the tray menu. QIcon is implicitly shared, so handing
# out the same instance is safe.
_cache = {}   # name -> QIcon


# The brand mark (p{color,gray,think,warn}) ships a ladder of purpose-rendered
# sizes beside the canonical file -- pcolor.png plus pcolor_16.png, _24, _32 ...
# A tray at 16 px otherwise gets a 256 px master smoothly downscaled, which
# blurs a mark made of hard-edged squares. Everything under res/icons named
# p*.png/.ico/.icns/.svg is written by tools/gen_brand_icons.py; edit that.
_LADDER = (16, 24, 32, 48, 64, 128, 256)


def icon_files(name, icon_dir=_ICON_DIR):
    """The file(s) QIcon should be built from, most specific first.

    Split out from get_icon() so the filename arithmetic is testable without Qt:
    a wrong stem yields an EMPTY QIcon rather than an error, which is the silent
    failure tests/gui/icon_assets_test.py exists to prevent.
    """
    path = pathlib.Path(icon_dir) / name
    if path.suffix == ".png":
        sized = [
            path.with_name(f"{path.stem}_{size}.png")
            for size in _LADDER
        ]
        sized = [p for p in sized if p.exists()]
        if sized:
            return sized
    return [path]


def get_icon(name):
    icon = _cache.get(name)
    if icon is None:
        icon = QIcon()
        for path in icon_files(name):
            icon.addFile(str(path))
        _cache[name] = icon
    return icon
