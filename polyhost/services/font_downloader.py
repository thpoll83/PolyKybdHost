"""Self-contained downloader for the Noto source fonts used to extend font packs.

The firmware repo's ``fonts/dl-fonts.sh`` fetches the Noto TTFs that
``fontconvert`` renders into the keycap fonts.  The host can't assume a firmware
checkout is present (it ships installed, standalone), so it carries its **own**
byte-identical copy of the catalog — ``polyhost/res/fonts/noto-fonts.yaml`` — the
single source of truth shared with that shell script.  The "Download Noto…" button
in ``fontpack_extend_dialog`` drives this module to fetch on demand into a
per-user cache.

Pure stdlib + PyYAML (already a host dependency); no Qt.  ``urllib`` honours
``HTTPS_PROXY``/``http_proxy`` via ``getproxies()``.

⚠️ ``noto-fonts.yaml`` is mirrored in
``qmk_firmware/keyboards/polykybd/fonts/noto-fonts.yaml`` — keep both in sync
(``cmp``).  Edit the YAML, not this module, to add/change fonts.
"""
from __future__ import annotations

import os
import tempfile
import urllib.request
from dataclasses import dataclass


class DownloadCancelled(Exception):
    """Raised by download_font when the caller's cancel event is set mid-transfer."""


@dataclass(frozen=True)
class NotoFont:
    name: str          # human-friendly label for the picker
    url: str           # upstream download URL
    filename: str      # local (flat) filename once downloaded = basename(dest)


def _catalog_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "res", "fonts", "noto-fonts.yaml")


def load_catalog(path: str | None = None) -> list[NotoFont]:
    """Parse noto-fonts.yaml into a list of NotoFont.  The host stores a flat
    cache, so the local filename is the basename of the firmware-side ``dest``.

    The YAML is UTF-8 (its comments carry — / ⚠️); read it as such so it doesn't
    blow up under a non-UTF-8 locale default (e.g. cp1252 on Windows)."""
    import yaml
    with open(path or _catalog_path(), encoding="utf-8") as f:
        doc = yaml.safe_load(f) or {}
    out, seen = [], set()
    for e in doc.get("fonts", []):
        filename = os.path.basename(e["dest"])
        # filename is the sole cache key (local_path/is_downloaded) — a collision
        # would alias two fonts to one file; fail fast on catalog drift.
        if filename in seen:
            raise ValueError(f"duplicate cache filename in noto-fonts.yaml: {filename}")
        seen.add(filename)
        out.append(NotoFont(name=e["name"], url=e["url"], filename=filename))
    return out


def default_cache_dir() -> str:
    """Per-user cache dir for downloaded source fonts (``platformdirs`` if present,
    else ``~/.cache``)."""
    try:
        import platformdirs
        base = platformdirs.user_cache_dir("PolyKybd", "PolyTasten")
    except Exception:                                   # noqa: BLE001
        base = os.path.join(os.path.expanduser("~"), ".cache", "PolyKybd")
    return os.path.join(base, "fonts")


def local_path(font: NotoFont, dest_dir: str | None = None) -> str:
    return os.path.join(dest_dir or default_cache_dir(), font.filename)


def is_downloaded(font: NotoFont, dest_dir: str | None = None) -> bool:
    p = local_path(font, dest_dir)
    return os.path.exists(p) and os.path.getsize(p) > 0


def download_font(font: NotoFont, dest_dir: str | None = None,
                  progress_cb=None, timeout: float = 60.0, cancel_event=None) -> str:
    """Download one font into ``dest_dir`` (default cache).  Skips if already
    present.  ``progress_cb(done_bytes, total_bytes)`` is called during transfer
    (``total`` may be -1 if the server sends no Content-Length).  Returns the
    local path.  Writes to a ``.part`` temp then renames, so an interrupted
    download never leaves a truncated file that ``is_downloaded`` would trust.

    ``cancel_event`` (a ``threading.Event``-like with ``is_set()``) is polled
    between chunks; when set, the partial file is removed and ``DownloadCancelled``
    is raised — this is how the GUI's Cancel button aborts a transfer."""
    dest_dir = dest_dir or default_cache_dir()
    os.makedirs(dest_dir, exist_ok=True)
    final = os.path.join(dest_dir, font.filename)
    if os.path.exists(final) and os.path.getsize(final) > 0:
        return final
    # Unique temp per attempt so two overlapping downloads of the same font can't
    # clobber or delete each other's partial file.
    fd, tmp = tempfile.mkstemp(prefix=font.filename + ".", suffix=".part", dir=dest_dir)
    os.close(fd)
    req = urllib.request.Request(font.url, headers={"User-Agent": "PolyKybdHost"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", -1))
            done = 0
            with open(tmp, "wb") as f:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise DownloadCancelled()
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
    except BaseException:
        # don't leave a half file behind on cancel/error (only our own temp)
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise
    # A concurrent attempt may have finished first; if so, drop ours and use it.
    if os.path.exists(final) and os.path.getsize(final) > 0:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return final
    os.replace(tmp, final)
    return final
