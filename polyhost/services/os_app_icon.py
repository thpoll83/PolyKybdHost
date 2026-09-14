"""The running application's OWN icon, taken from the operating system.

This is the source a program mark should prefer, because it needs no catalog,
no name guessing and no curation: the OS already knows which picture belongs to
the process that owns the focused window, and it is always the right one. A
catalog lookup can only ever be a guess at the same question -- and a guess that
goes wrong draws Krita's logo on a KiCad window, which a user cannot explain.

Each backend answers the same two-step question:

    pid -> the executable (or bundle) behind the window
        -> the image the desktop draws for it

and nothing here converts, scales or thresholds. The bytes come back as the OS
stores them (PNG, SVG, ICO, ICNS) and `icon_binarise` decides how to read them,
so this module stays a pure lookup and can be tested against real files.

⚠️ NO FUZZY MATCHING, on any platform. Every match below is an exact string
comparison against something the OS itself recorded -- a `StartupWMClass`, an
`Exec` basename, a bundle identifier. The existing rule stands and is the
reason this source is worth having: a *wrong* mark is worse than a missing one,
and an absent one is self-evident where a wrong one is not.

Platform status, stated plainly rather than implied:

  * **Linux** — implemented and tested against the real `.desktop` and icon-theme
    layout. This is the platform the tests run on.
  * **Windows** — implemented as a pure-Python PE resource parse, so it needs no
    pywin32 and no GDI. ⚠️ It has NOT been run against a live application; the
    unit tests drive the ICO assembly, not a real `.exe`. Treat it the way this
    repo already treats the UIA shortcut backend.
  * **macOS** — implemented by walking to the `.app` bundle and reading
    `Info.plist`, deliberately WITHOUT pyobjc so it adds no dependency.
    ⚠️ Also never run against a live application.

A backend that finds nothing returns None, and the caller falls back to the
catalog. None is the normal answer for a process with no desktop entry.
"""

from __future__ import annotations

import logging
import os
import re
import struct
import sys

log = logging.getLogger('PolyHost')

_ICON_EXTENSIONS = (".png", ".svg", ".xpm")

# A trailing version on an executable name (`python3.11`, `wine64`).
_VERSIONED = re.compile(r"[-_]?\d+(\.\d+)*$")


# ---------------------------------------------------------------------------
# Linux: /proc -> .desktop -> Icon= -> icon theme
# ---------------------------------------------------------------------------

def _xdg_data_dirs() -> list:
    """Every XDG data root, most specific first, deduplicated in order."""
    out = []
    home = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share")
    raw = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    for entry in [home] + raw.split(os.pathsep):
        entry = entry.strip()
        if entry and entry not in out:
            out.append(entry)
    return out


def _parse_desktop(path: str) -> dict:
    """The `[Desktop Entry]` group as a dict, or {}.

    Hand-parsed rather than via configparser: a .desktop file legitimately
    carries duplicate localised keys (`Name[de]`) and `%`-escapes that
    configparser's interpolation rejects outright.
    """
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            in_entry = False
            for line in handle:
                line = line.strip()
                if line.startswith("["):
                    in_entry = line == "[Desktop Entry]"
                    continue
                if not in_entry or "=" not in line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                out.setdefault(key.strip(), value.strip())
    except OSError as exc:
        log.debug("Could not read %s: %s", path, exc)
    return out


def _exec_stem(value: str) -> str:
    """The program a `Exec=` line runs, without path, arguments or field codes."""
    for token in (value or "").split():
        if token.startswith("%") or "=" in token:
            continue                    # a field code, or `env VAR=x`
        if token in ("env", "sh", "-c", "/usr/bin/env"):
            continue
        return os.path.basename(token).lower()
    return ""


def _desktop_entries():
    """Every readable desktop entry, as (path, parsed dict)."""
    for root in _xdg_data_dirs():
        folder = os.path.join(root, "applications")
        if not os.path.isdir(folder):
            continue
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for name in names:
            if name.endswith(".desktop"):
                path = os.path.join(folder, name)
                yield path, _parse_desktop(path)


# Executables that are never the application. `/proc/<pid>/exe` for a Python,
# Java or Electron app is the RUNTIME, so an `Exec=` match against it hands back
# the interpreter's icon for every such app -- measured, it resolved all six test
# apps to `python3.11.xpm`.
_RUNTIMES = frozenset((
    "python", "python2", "python3", "pythonw", "java", "javaw", "mono",
    "electron", "node", "ruby", "perl", "wine", "wine64", "sh", "bash", "env",
))


def _is_runtime(stem: str) -> bool:
    base = _VERSIONED.sub("", (stem or "").lower())
    return base in _RUNTIMES


def _linux_icon_name(exe: str, app_name: str) -> str:
    """The `Icon=` value of the desktop entry for this process, or "".

    Three exact matches, in confidence order:

    1. `StartupWMClass` equal to the app name -- the key exists precisely to tie
       a window back to its launcher, which is the question being asked here;
    2. the desktop file's own stem equal to the app name;
    3. the `Exec=` program equal to `/proc/<pid>/exe`.

    ⚠️ The APP NAME beats the executable, and that order is load-bearing rather
    than arbitrary. The name comes from the window manager and identifies the
    APPLICATION; `/proc/<pid>/exe` identifies the BINARY, and for anything
    running under an interpreter those are different things. Taking the exe
    first gave every Python app the Python icon.
    """
    exe_stem = os.path.basename(exe).lower() if exe else ""
    wanted = (app_name or "").strip().lower()
    by_stem = ""
    by_exec = ""
    for path, entry in _desktop_entries():
        icon = entry.get("Icon", "")
        if not icon:
            continue
        if wanted and entry.get("StartupWMClass", "").strip().lower() == wanted:
            return icon
        stem = os.path.basename(path)[:-len(".desktop")].lower()
        if wanted and not by_stem and stem == wanted:
            by_stem = icon
        if (exe_stem and not by_exec and not _is_runtime(exe_stem)
                and _exec_stem(entry.get("Exec", "")) == exe_stem):
            by_exec = icon
    return by_stem or by_exec


def _theme_candidates(icon: str):
    """Every on-disk file that could be `icon`, best first.

    ⚠️ RASTER SORTS AHEAD OF SVG, which is the opposite of what a themed-icon
    lookup usually wants and is right here for one reason: COLOUR. The 1-bit
    render reads a full-colour icon by splitting its own palette, and the
    vector rasteriser in this repo returns alpha COVERAGE only -- so an SVG
    arrives as a silhouette. Measured: gvim came out a filled square, Yelp a
    ring, LibreOffice a solid page. The PNG of the same icon carries the
    drawing. Resolution is the lesser worry; a 256px PNG has plenty for 38x38.
    """
    if os.path.isabs(icon):
        if os.path.isfile(icon):
            yield icon
        return
    found = []
    for root in _xdg_data_dirs():
        pixmaps = os.path.join(root, "pixmaps")
        for extension in _ICON_EXTENSIONS:
            candidate = os.path.join(pixmaps, icon + extension)
            if os.path.isfile(candidate):
                found.append((1, 0, candidate))
        icons = os.path.join(root, "icons")
        if not os.path.isdir(icons):
            continue
        for base, _dirs, files in os.walk(icons):
            if os.path.basename(base) not in ("apps", "applications"):
                continue
            for extension in _ICON_EXTENSIONS:
                candidate = os.path.join(base, icon + extension)
                if os.path.isfile(candidate):
                    found.append((1 if extension == ".svg" else 0,
                                  -_size_hint(base), candidate))
    for _scalable, _size, path in sorted(found):
        yield path


def _size_hint(folder: str) -> int:
    """The pixel size a theme folder advertises in its path, or 0."""
    for part in folder.split(os.sep):
        head, _, tail = part.partition("x")
        if head.isdigit() and (not tail or tail == head):
            return int(head)
        if part.isdigit():
            return int(part)
    return 0


def _linux_icon(pid, app_name: str):
    exe = ""
    if pid:
        try:
            exe = os.readlink("/proc/%d/exe" % int(pid))
        except OSError as exc:
            log.debug("No /proc/%s/exe: %s", pid, exc)
    name = _linux_icon_name(exe, app_name)
    if not name:
        return None
    for path in _theme_candidates(name):
        try:
            with open(path, "rb") as handle:
                return handle.read(), path
        except OSError as exc:
            log.debug("Could not read %s: %s", path, exc)
    return None


# ---------------------------------------------------------------------------
# Windows: pid -> exe -> PE resource icon
# ---------------------------------------------------------------------------

_RT_ICON = 3
_RT_GROUP_ICON = 14


def _windows_exe(pid) -> str:
    """The full image path of a running process, or ""."""
    try:
        import ctypes
        import ctypes.wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return ""
        try:
            size = ctypes.wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(
                    handle, 0, buffer, ctypes.byref(size)):
                return ""
            return buffer.value
        finally:
            kernel32.CloseHandle(handle)
    except Exception as exc:                # noqa: BLE001 - cosmetic lookup
        log.debug("Could not resolve the exe for pid %s: %s", pid, exc)
        return ""


def _pe_resource_reader(data: bytes):
    """(section reader, resource root offset) for a PE image, or None.

    Pure-Python on purpose: the alternative is pywin32 plus GDI to turn an
    HICON back into pixels, and neither is a dependency this repo carries.
    """
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if len(data) < pe_offset + 24 or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        return None
    coff = pe_offset + 4
    sections, = struct.unpack_from("<H", data, coff + 2)
    optional_size, = struct.unpack_from("<H", data, coff + 16)
    optional = coff + 20
    magic, = struct.unpack_from("<H", data, optional)
    # The data directory sits after the optional header's fixed part, whose
    # length is the ONLY thing that differs between PE32 and PE32+.
    directory = optional + (96 if magic == 0x10B else 112)
    if len(data) < directory + 24:
        return None
    resource_rva, _size = struct.unpack_from("<II", data, directory + 8 * 2)
    if not resource_rva:
        return None
    table = []
    for index in range(sections):
        entry = optional + optional_size + index * 40
        if len(data) < entry + 40:
            return None
        virtual_address, = struct.unpack_from("<I", data, entry + 12)
        raw_size, raw_pointer = struct.unpack_from("<II", data, entry + 16)
        table.append((virtual_address, raw_size, raw_pointer))

    def to_offset(rva):
        for virtual_address, raw_size, raw_pointer in table:
            if virtual_address <= rva < virtual_address + max(raw_size, 1):
                return raw_pointer + (rva - virtual_address)
        return None

    root = to_offset(resource_rva)
    return None if root is None else (to_offset, root)


def _resource_entries(data: bytes, offset: int):
    """(id_or_name, child_offset, is_directory) for one resource directory."""
    if len(data) < offset + 16:
        return []
    named, ids = struct.unpack_from("<HH", data, offset + 12)
    out = []
    for index in range(named + ids):
        entry = offset + 16 + index * 8
        if len(data) < entry + 8:
            break
        name, child = struct.unpack_from("<II", data, entry)
        out.append((name & 0x7FFFFFFF, child & 0x7FFFFFFF, bool(child & 0x80000000)))
    return out


def _first_leaf(data: bytes, root: int, offset: int):
    """Walk to the first data leaf under `offset`; returns (rva, size)."""
    for _name, child, is_directory in _resource_entries(data, offset):
        target = root + child
        if is_directory:
            found = _first_leaf(data, root, target)
            if found:
                return found
        elif len(data) >= target + 8:
            return struct.unpack_from("<II", data, target)
    return None


def _resource_blob(data: bytes, root: int, to_offset, type_id: int, wanted_id=None):
    """The bytes of one resource, or None. `wanted_id` None takes the first."""
    for name, child, is_directory in _resource_entries(data, root):
        if name != type_id or not is_directory:
            continue
        for entry_name, entry_child, entry_is_directory in _resource_entries(
                data, root + child):
            if wanted_id is not None and entry_name != wanted_id:
                continue
            if not entry_is_directory:
                continue
            leaf = _first_leaf(data, root, root + entry_child)
            if not leaf:
                continue
            rva, size = leaf
            start = to_offset(rva)
            if start is None or len(data) < start + size:
                continue
            return data[start:start + size]
    return None


def build_ico(group: bytes, images) -> bytes:
    """Reassemble an .ico file from a PE RT_GROUP_ICON plus its RT_ICON blobs.

    The two on-disk structures differ in exactly one field -- the group entry
    ends with a 2-byte resource id where an .ico entry ends with a 4-byte file
    offset -- so this is a rewrite of the directory, never of the images.
    """
    if len(group) < 6:
        return b""
    _reserved, kind, count = struct.unpack_from("<HHH", group, 0)
    entries = []
    for index in range(count):
        at = 6 + index * 14
        if len(group) < at + 14:
            break
        width, height, colours, reserved, planes, bits, size, ident = \
            struct.unpack_from("<BBBBHHIH", group, at)
        blob = images.get(ident)
        if blob:
            entries.append((width, height, colours, reserved, planes, bits, blob))
    if not entries:
        return b""
    header = struct.pack("<HHH", 0, kind or 1, len(entries))
    offset = len(header) + 16 * len(entries)
    directory = b""
    payload = b""
    for width, height, colours, reserved, planes, bits, blob in entries:
        directory += struct.pack("<BBBBHHII", width, height, colours, reserved,
                                 planes, bits, len(blob), offset)
        payload += blob
        offset += len(blob)
    return header + directory + payload


def icon_from_pe(data: bytes) -> bytes:
    """The application icon inside a PE image, as .ico bytes, or b""."""
    parsed = _pe_resource_reader(data)
    if not parsed:
        return b""
    to_offset, root = parsed
    group = _resource_blob(data, root, to_offset, _RT_GROUP_ICON)
    if not group or len(group) < 6:
        return b""
    _reserved, _kind, count = struct.unpack_from("<HHH", group, 0)
    images = {}
    for index in range(count):
        at = 6 + index * 14
        if len(group) < at + 14:
            break
        ident, = struct.unpack_from("<H", group, at + 12)
        blob = _resource_blob(data, root, to_offset, _RT_ICON, ident)
        if blob:
            images[ident] = blob
    return build_ico(group, images)


def _windows_icon(pid, app_name: str):
    exe = _windows_exe(pid)
    if not exe or not os.path.isfile(exe):
        return None
    try:
        with open(exe, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        log.debug("Could not read %s: %s", exe, exc)
        return None
    blob = icon_from_pe(data)
    return (blob, exe) if blob else None


# ---------------------------------------------------------------------------
# macOS: pid -> .app bundle -> Info.plist -> .icns
# ---------------------------------------------------------------------------

def _macos_bundle(pid) -> str:
    """The `.app` directory owning this process, or ""."""
    try:
        import subprocess
        out = subprocess.run(["ps", "-p", str(int(pid)), "-o", "comm="],
                             capture_output=True, text=True, timeout=5)
        path = (out.stdout or "").strip()
    except Exception as exc:            # noqa: BLE001 - cosmetic lookup
        log.debug("Could not resolve the bundle for pid %s: %s", pid, exc)
        return ""
    while path and path != "/":
        if path.endswith(".app"):
            return path
        path = os.path.dirname(path)
    return ""


def _macos_icon(pid, app_name: str):
    bundle = _macos_bundle(pid)
    if not bundle:
        return None
    resources = os.path.join(bundle, "Contents", "Resources")
    name = ""
    try:
        import plistlib
        with open(os.path.join(bundle, "Contents", "Info.plist"), "rb") as handle:
            name = str(plistlib.load(handle).get("CFBundleIconFile", "") or "")
    except Exception as exc:            # noqa: BLE001 - cosmetic lookup
        log.debug("Could not read Info.plist in %s: %s", bundle, exc)
    candidates = []
    if name:
        candidates.append(name if name.endswith(".icns") else name + ".icns")
    try:
        candidates += sorted(f for f in os.listdir(resources) if f.endswith(".icns"))
    except OSError:
        pass            # no readable Resources dir. `candidates` may still hold
                        # the name Info.plist gave, which is the better guess
                        # anyway; an unreadable bundle is a missing icon, not an
                        # error worth raising out of a cosmetic lookup.
    for candidate in candidates:
        path = os.path.join(resources, candidate)
        try:
            with open(path, "rb") as handle:
                return handle.read(), path
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------

BACKENDS = {
    "linux": _linux_icon,
    "win32": _windows_icon,
    "darwin": _macos_icon,
}


def platform_key() -> str:
    return "linux" if sys.platform.startswith("linux") else sys.platform


def icon_bytes(pid, app_name: str = ""):
    """(image bytes, source path) for the focused app's own icon, or None.

    Never raises: this is decoration, and a lookup that throws must not take the
    overlay send with it.
    """
    backend = BACKENDS.get(platform_key())
    if backend is None:
        return None
    try:
        return backend(pid, app_name or "")
    except Exception as exc:            # noqa: BLE001 - cosmetic lookup
        log.debug("OS icon lookup failed for pid=%s app=%s: %s", pid, app_name, exc)
        return None


# ---------------------------------------------------------------------------
# Self-check
# ---------------------------------------------------------------------------
#
# ⚠️ This exists because the Windows and macOS backends have never run against a
# live application, and a claim nobody can check is worth less than a command
# anybody can run:
#
#     python -m polyhost.services.os_app_icon                 # this process
#     python -m polyhost.services.os_app_icon 1234            # a pid
#     python -m polyhost.services.os_app_icon "C:\...\WINWORD.EXE"
#     python -m polyhost.services.os_app_icon 1234 --save out.png
#
# It reports what was found, how the 1-bit reading scored, and prints the keycap
# as text, so "the program mark works on Windows" stops being an assumption.

def _self_check(argv) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", default=None,
                        help="a pid, or a path to an executable/bundle/icon")
    parser.add_argument("--app", default="", help="the app name the tracker reports")
    parser.add_argument("--save", default="", help="write the keycap to this PNG")
    args = parser.parse_args(argv)

    found = None
    if args.target and not str(args.target).isdigit():
        path = str(args.target)
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError as exc:
            print("cannot read %s: %s" % (path, exc))
            return 2
        if path.lower().endswith(".exe") or raw[:2] == b"MZ":
            blob = icon_from_pe(raw)
            if not blob:
                print("no RT_GROUP_ICON resource in %s" % path)
                return 1
            found = (blob, path)
        else:
            found = (raw, path)
    else:
        pid = int(args.target) if args.target else os.getpid()
        found = icon_bytes(pid, args.app)
        if not found:
            print("platform %s: no OS icon for pid %d (app %r)"
                  % (platform_key(), pid, args.app))
            return 1

    data, source = found
    print("source: %s (%d bytes)" % (source, len(data)))
    from polyhost.services import app_icons, icon_binarise
    mask, conversion, score = app_icons.render_os_overlay(data)
    if mask is None:
        print("no 1-bit reading survived")
        return 1
    verdict = "DRAWN" if score >= icon_binarise.MIN_SCORE else "REJECTED (too low)"
    print("conversion: %s   score: %.2f   %s" % (conversion, score, verdict))
    for row in mask:
        print("".join("#" if value else "." for value in row))
    if args.save:
        try:
            from PIL import Image
            Image.fromarray(((~mask) * 255).astype("uint8")).save(args.save)
            print("wrote %s" % args.save)
        except Exception as exc:        # noqa: BLE001 - a convenience, not the check
            print("could not write %s: %s" % (args.save, exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check(sys.argv[1:]))
