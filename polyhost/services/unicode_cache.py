import os
import pathlib

import requests
from pathlib import Path
from PyQt5.QtGui import QIcon, QPixmap
from platformdirs import user_config_dir


def _unicode_flag_to_codepoints(flag: str) -> str:
    return '-'.join([f"{ord(c) + 127397:x}" for c in flag.upper()])


class UnicodeCache:
    def __init__(self, size: int = 32):
        self.APP_NAME = "PolyHost"
        self.flag_dir = Path(os.path.join(pathlib.Path(__file__).parent.parent.resolve(), "res", "flags"))
        self.cache_dir = Path(os.path.join(user_config_dir(self.APP_NAME), "icon_cache"))
        self.cache_dir.mkdir(exist_ok=True)
        self.size = size

    def _download_and_cache(self, codepoints: str, filename: Path):
        url = f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{codepoints}.png"

        try:
            response = requests.get(url)
            response.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            pixmap = pixmap.scaled(self.size, self.size)
            pixmap.save(str(filename))
            print(f"[UnicodeCache] Cached: {filename.name}")
        except Exception as e:
            print(f"[UnicodeCache] Failed to fetch icon {codepoints}: {e}")

    def get_icon_for(self, flag: str) -> QIcon:
        codepoints = _unicode_flag_to_codepoints(flag)
        filename = self.flag_dir / f"{codepoints}.png"

        if not filename.exists():
            filename = self.cache_dir / f"{codepoints}.png"

            if not filename.exists():
                self._download_and_cache(codepoints, filename)

        if filename.exists():
            return QIcon(str(filename))
        return QIcon()  # fallback if something goes wrong
