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


class DownloadError(Exception):
    """Raised by download_font when the result is truncated/corrupt (a clean
    early connection close, a proxy error page, etc.) — so a bad file never
    silently becomes a trusted cache entry."""


def _validate_sfnt_dir(f, dir_off: int, size: int) -> bool:
    """Validate one sfnt table directory at `dir_off`: a plausible table count and
    every entry's (offset+length) within the `size`-byte file.  Shared by the plain
    TTF/OTF path and each member of a TTC collection."""
    import struct
    f.seek(dir_off)
    hdr = f.read(12)
    if len(hdr) < 12:
        return False
    num_tables = struct.unpack(">H", hdr[4:6])[0]
    if num_tables == 0:
        return False
    directory = f.read(num_tables * 16)
    if len(directory) < num_tables * 16:
        return False
    for i in range(num_tables):
        off, length = struct.unpack(">II", directory[i * 16 + 8:i * 16 + 16])
        if off + length > size:                  # a table runs past EOF → truncated
            return False
    return True


def _validate_sfnt(path: str) -> bool:
    """Cheap structural check that `path` is a complete sfnt font (TTF/OTF/TTC):
    a known signature and every table-directory entry's (offset+length) within the
    file.  Catches a truncated download (the failure mode that left a 2.38 MB
    NotoColorEmoji that FreeType then refused to open) without parsing the font."""
    import struct
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(12)
            if len(head) < 12:
                return False
            tag = head[:4]
            if tag == b"ttcf":
                # Collection: validate the offset table + every member font directory
                # so a truncated .ttc is rejected (not blindly trusted).
                num_fonts = struct.unpack(">I", head[8:12])[0]
                if num_fonts == 0:
                    return False
                offsets_raw = f.read(num_fonts * 4)
                if len(offsets_raw) < num_fonts * 4:
                    return False
                offsets = struct.unpack(f">{num_fonts}I", offsets_raw)
                return all(_validate_sfnt_dir(f, off, size) for off in offsets)
            if tag not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"):
                return False
            return _validate_sfnt_dir(f, 0, size)
    except Exception:                                # noqa: BLE001
        return False


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
    """True only when a *valid* (complete) font is cached.  A truncated/corrupt
    file reads as not-downloaded, so the UI offers it for (re)download instead of
    handing a broken path to the renderer."""
    p = local_path(font, dest_dir)
    return os.path.exists(p) and os.path.getsize(p) > 0 and _validate_sfnt(p)


def download_font(font: NotoFont, dest_dir: str | None = None,
                  progress_cb=None, timeout: float = 60.0, cancel_event=None,
                  force: bool = False) -> str:
    """Download one font into ``dest_dir`` (default cache).  Returns the local path.

    Skips the transfer if a **valid** file is already cached (a truncated/corrupt
    one is re-fetched, overwriting it); pass ``force=True`` to always re-download.
    ``progress_cb(done_bytes, total_bytes)`` is called during transfer (``total``
    may be -1 if the server sends no Content-Length).  Writes to a ``.part`` temp
    then renames, and **validates the result** (Content-Length match when known +
    sfnt structure) — a short read (a clean early close / proxy error page) raises
    ``DownloadError`` and leaves no file, instead of caching a broken font.

    ``cancel_event`` (a ``threading.Event``-like with ``is_set()``) is polled
    between chunks; when set, the partial file is removed and ``DownloadCancelled``
    is raised — this is how the GUI's Cancel button aborts a transfer."""
    dest_dir = dest_dir or default_cache_dir()
    os.makedirs(dest_dir, exist_ok=True)
    final = os.path.join(dest_dir, font.filename)
    if not force and is_downloaded(font, dest_dir):     # valid cache → reuse
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
        # Reject a short/corrupt transfer rather than caching it (the bug that left
        # a truncated NotoColorEmoji FreeType couldn't open).
        if total >= 0 and done != total:
            raise DownloadError(f"truncated download: got {done} of {total} bytes "
                                f"for {font.filename}")
        if not _validate_sfnt(tmp):
            raise DownloadError(f"downloaded {font.filename} is not a complete font "
                                "(truncated or an error page)")
    except BaseException:
        # don't leave a half file behind on cancel/error (only our own temp)
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise
    # A concurrent attempt may have finished first with a valid file; if so, use it.
    if not force and is_downloaded(font, dest_dir):
        try:
            os.remove(tmp)
        except OSError:
            pass
        return final
    os.replace(tmp, final)
    return final
