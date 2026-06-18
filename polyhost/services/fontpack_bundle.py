"""Locate the font pack shipped with this host release and decide whether the
connected keyboard needs it.

The host can't make the keyboard fetch anything itself (it's a passive HID
device), so "automatic font-pack updates" means: the host ships a built
``.plyf`` pack, and on a fresh connect compares the keyboard's loaded
``content_version`` against the bundled one, flashing only when the keyboard is
older or has no pack. That comparison is the dedup key — a successful flash
makes the versions equal, so the check is self-terminating (it never loops).

The bundled pack lives in ``polyhost/res/fontpack/*.plyf`` (dropped there by the
release build) or at an explicit ``fontpack_path`` setting. With no pack present
the whole feature is inert (``bundled_pack_info`` returns ``(None, None)``).
"""
import os
from pathlib import Path

from polyhost.device import hid_fontpack


def _res_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "res" / "fontpack"


def bundled_pack_path(override: str = "") -> str | None:
    """Path to the bundled font pack, or None if none is shipped.

    An explicit ``override`` (the ``fontpack_path`` setting) wins; otherwise the
    newest-by-content_version ``.plyf`` in ``polyhost/res/fontpack/`` is used."""
    if override:
        return override if os.path.exists(override) else None
    d = _res_dir()
    if not d.is_dir():
        return None
    packs = sorted(str(p) for p in d.glob("*.plyf"))
    if not packs:
        return None
    if len(packs) == 1:
        return packs[0]
    # Multiple packs present: pick the highest content_version.
    best, best_ver = None, -1
    for p in packs:
        _, info = _read_header(p)
        ver = info["content_version"] if info else -1
        if ver > best_ver:
            best, best_ver = p, ver
    return best or packs[-1]


def _read_header(path: str):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None, None
    ok, info = hid_fontpack.parse_fontpack_header(data)
    return (path, info) if ok else (None, None)


def bundled_pack_info(override: str = ""):
    """Return ``(path, header_info)`` for the bundled pack, or ``(None, None)``
    when nothing is shipped or the file is unreadable / invalid."""
    path = bundled_pack_path(override)
    if not path:
        return None, None
    return _read_header(path)


def decide_auto_flash(status_ok: bool, device_info: dict | None,
                      bundled_info: dict | None) -> tuple[bool, str]:
    """Pure decision: should the host auto-flash the bundled pack?

    Args:
        status_ok:    did the FONTPACK_STATUS query succeed?
        device_info:  parsed status reply ({present, abi, content_version, font_count}) or None.
        bundled_info: parsed bundled-pack header or None.

    Returns ``(should_flash, reason)``. Never flashes a pack whose ABI differs
    from what the firmware reports (the firmware would reject it), and never
    "downgrades" — only flashes when the keyboard is strictly older or has no
    pack, so re-running on every connect is safe and self-terminating.
    """
    if bundled_info is None:
        return False, "no bundled font pack"
    if not status_ok or device_info is None:
        return False, "could not read keyboard font-pack status"
    if device_info.get("abi") != bundled_info.get("abi_version"):
        return False, (f"pack ABI v{bundled_info.get('abi_version')} != firmware ABI "
                       f"v{device_info.get('abi')} — host/firmware out of sync; flash skipped")
    if not device_info.get("present"):
        return True, "keyboard has no font pack"
    dev_ver = device_info.get("content_version", 0)
    bun_ver = bundled_info.get("content_version", 0)
    if dev_ver < bun_ver:
        return True, f"keyboard pack v{dev_ver} older than bundled v{bun_ver}"
    return False, f"keyboard font pack up to date (v{dev_ver})"
