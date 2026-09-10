"""An overlay source that is not a file — a converter built from rendered masks.

`send_overlays_mru` asks each source for `extract_overlays(modifier)` and gets
back `{keycode: OverlayData}`. Nothing in it requires that the source ever read
an image, so a converter assembled in memory rides the whole existing transport:
the MRU cache, the pool allocation, the ROI/RLE encoders and the mapping commit
all work unchanged, and the firmware needs no change at all.

That is what carries the generic icon fall-back — the program mark on ESC, and
later a shortcut icon on any key a template does not draw.

⚠️ THE NAME IS THE CACHE KEY, so it must identify the CONTENT, not the feature.
`send_overlays_mru` keys each image on (basename, modifier, keycode); a fixed
name like `@prog` would file GIMP's mark and Inkscape's under one key, and the
second app to be focused would get the first one's icon out of the MRU cache
with no upload and no way to notice. Hence `@prog:<slug>`.
"""

from __future__ import annotations

SYNTHETIC_PREFIX = "@"
PROGRAM_PREFIX = "@prog:"


def program_name(slug: str) -> str:
    """The pseudo-filename an app's mark is cached and mapped under."""
    return f"{PROGRAM_PREFIX}{slug}"


def is_synthetic(filename: str) -> bool:
    return bool(filename) and filename.startswith(SYNTHETIC_PREFIX)


class SyntheticConverter:
    """Duck-typed stand-in for `ImageConverter`, over already-rendered overlays.

    Only the two methods `send_overlays_mru` calls are implemented, deliberately:
    a fuller imitation would invite callers to depend on behaviour there is no
    image behind.
    """

    def __init__(self, overlays: dict):
        # {Modifier: {keycode: OverlayData}} — keyed by the Modifier enum member,
        # because that is what the send loop iterates.
        self._overlays = {mod: dict(keys) for mod, keys in overlays.items() if keys}

    def open(self, filename) -> bool:       # noqa: ARG002 - signature parity
        return True

    def extract_overlays(self, modifier):
        return self._overlays.get(modifier)

    def __len__(self):
        return sum(len(v) for v in self._overlays.values())


def program_converter(device_settings, keycode, mask):
    """The program mark as an overlay source for ONE device.

    ⚠️ Built per device, not once and shared: `OverlayData` derives its message
    counts from that device's `DeviceSettings` (payload size, per-command
    overhead), so a single instance handed to two devices would report the wrong
    transfer cost for at least one of them.

    Returns None when the mask carries no ink -- `OverlayData` refuses an
    all-black image, and an empty overlay would cost a pool slot and a send to
    draw exactly nothing.
    """
    from polyhost.device.keys import Modifier
    from polyhost.device.overlay_data import OverlayData
    try:
        data = OverlayData(device_settings, mask)
    except ValueError:
        return None
    return SyntheticConverter({Modifier.NO_MOD: {keycode: data}})
