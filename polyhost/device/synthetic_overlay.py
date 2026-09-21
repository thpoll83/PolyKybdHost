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

    `modifier_invariant` declares that every variant this source offers is the
    SAME image, so the send loop may key it once instead of per modifier. It
    defaults to False, which is what every file-backed converter is: a
    `*.mods.png` carries a different picture in each channel.
    """

    def __init__(self, overlays: dict, modifier_invariant: bool = False):
        # {Modifier: {keycode: OverlayData}} — keyed by the Modifier enum member,
        # because that is what the send loop iterates.
        self._overlays = {mod: dict(keys) for mod, keys in overlays.items() if keys}
        self.modifier_invariant = modifier_invariant

    def open(self, filename) -> bool:       # noqa: ARG002 - signature parity
        return True

    def extract_overlays(self, modifier):
        return self._overlays.get(modifier)

    def __len__(self):
        return sum(len(v) for v in self._overlays.values())


def program_converter(device_settings, keycode, mask):
    """The program mark as an overlay source for ONE device, on EVERY variant.

    ⚠️ Built per device, not once and shared: `OverlayData` derives its message
    counts from that device's `DeviceSettings` (payload size, per-command
    overhead), so a single instance handed to two devices would report the wrong
    transfer cost for at least one of them.

    Returns None when the mask carries no ink -- `OverlayData` refuses an
    all-black image, and an empty overlay would cost a pool slot and a send to
    draw exactly nothing.

    ⚠️ **It offers the mark under every modifier, and that is a FIX rather than
    a flourish.** A template-covered app draws `program_icon:` on every channel
    of both PNGs, so on those apps the mark stays put while you hold Ctrl; a
    generic app used to offer `NO_MOD` alone, so the same keycap went blank the
    moment a modifier went down. Same key, same feature, two behaviours.

    It costs ONE upload, not N. The mapping is display -> pool
    (`display_to_pool[display_flat_idx(keycode, modifier)] = slot`), so N display
    indices may point at one slot, and `modifier_invariant` makes the MRU key
    modifier-free so the second variant onwards is a cache HIT that uploads
    nothing. ⚠️ Do NOT instead allocate a slot per variant: the pool holds 600
    and one menubar app already takes ~20 for its shortcuts.

    The single `OverlayData` is shared across the variants rather than rebuilt
    per modifier -- it is a read-only value object, and rebuilding it 16 times
    would re-run the RLE and ROI encoders on identical pixels.

    Variants a given keyboard cannot address are NOT filtered here: the send loop
    already drops anything above `LEGACY_MAX_MODIFIER_VALUE` on a pre-v12 device,
    which is the one place that knows what the device supports. So this yields 9
    mappings on an older keyboard and 16 on a current one, from one upload either
    way.
    """
    from polyhost.device.keys import Modifier
    from polyhost.device.overlay_data import OverlayData
    try:
        data = OverlayData(device_settings, mask)
    except ValueError:
        return None
    return SyntheticConverter({mod: {keycode: data} for mod in Modifier},
                              modifier_invariant=True)


SHORTCUT_PREFIX = "@sc:"


def is_shortcut(filename: str) -> bool:
    return bool(filename) and filename.startswith(SHORTCUT_PREFIX)


def shortcut_converter(device_settings, keys):
    """One icon's overlay source, on every (modifier, keycode) it lands on.

    `keys` is {(modifier_value, keycode): mask} — the shape
    `shortcut_overlays.render()` produces for ONE concept. One converter per
    concept rather than per key, because the mask does not depend on the key:
    the MRU cache keys on (name, modifier, keycode), so the same icon on Ctrl+S
    in two applications is one pool slot and one upload.

    ⚠️ `Modifier`'s value IS the harvested nibble, so the conversion is a lookup
    rather than a mapping — an unknown value (a pre-v12 keyboard cannot address
    9..15, and the caller has no business inventing 16) is dropped rather than
    guessed. Returns None when nothing survives, so an empty source never costs
    a pool slot.

    ⚠️ NOT modifier-invariant, unlike the program mark: a shortcut icon means
    *this chord does Save*, so the same concept on Ctrl+S and on Ctrl+Shift+S is
    two different statements and each variant has to be keyed on its own. The
    sharing here is across APPLICATIONS, which the name already carries.
    """
    from polyhost.device.keys import Modifier
    from polyhost.device.overlay_data import OverlayData
    overlays: dict = {}
    for (modifier_value, keycode), mask in (keys or {}).items():
        try:
            modifier = Modifier(modifier_value)
        except ValueError:
            continue
        try:
            data = OverlayData(device_settings, mask)
        except ValueError:
            continue                    # all-black: nothing to draw
        overlays.setdefault(modifier, {})[keycode] = data
    if not overlays:
        return None
    return SyntheticConverter(overlays)
