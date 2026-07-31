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


def get_icon(name):
    icon = _cache.get(name)
    if icon is None:
        icon = QIcon(str(_ICON_DIR / name))
        _cache[name] = icon
    return icon
