import pathlib

from PyQt5.QtGui import QIcon

_ICON_DIR = pathlib.Path(__file__).parent.parent.resolve() / "res" / "icons"

# Icons are immutable on disk, so cache the QIcon per name. Without this,
# get_icon re-read the file on every call (48 call sites) — and the tray icon
# is rebuilt on every overlay send / app switch (set_thinking/set_idle) plus
# every menu rebuild, so that disk churn ran on the Qt main thread and showed
# up as lag when opening the tray menu. QIcon is implicitly shared, so handing
# out the same instance is safe.
_cache: dict[str, QIcon] = {}


def get_icon(name):
    icon = _cache.get(name)
    if icon is None:
        icon = QIcon(str(_ICON_DIR / name))
        _cache[name] = icon
    return icon
