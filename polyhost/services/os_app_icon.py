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

⚠️ This module must NOT import `app_icons`, which imports it -- that direction
is the import cycle, and it is also the design: this is a pure LOOKUP that
finds bytes and converts nothing. Anything that needs to render belongs on the
other side of the boundary. `tools/os_icon_probe.py` is the runnable check that
exercises both together, and it lives there for exactly that reason.

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
from typing import NamedTuple

log = logging.getLogger('PolyHost')

class AppIdentity(NamedTuple):
    """What the OS knows about a running application.

    ⚠️ The two halves come from ONE resolution, deliberately: the icon and the
    name are read from the same desktop entry / the same PE / the same
    Info.plist, so they cannot describe two different applications. Two separate
    lookups could not promise that, and a mark captioned with someone else's
    name is the kind of wrong nobody can explain.

    `names` is a preference ORDER, not a set of equals, and it may be non-empty
    while `icon` is None -- a name with no icon still resolves a catalog mark,
    which is the whole point of reading it.
    """

    icon: bytes | None
    icon_path: str
    names: tuple


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


def _linux_entry(exe: str, app_name: str) -> dict:
    """The desktop entry for this process, or {}.

    ⚠️ Resolving the ENTRY rather than the `Icon=` string is what stops the icon
    and the display name coming from two different applications. They are read
    from the same dict by construction; two separate walks could not promise it.

    Four exact matches, in confidence order:

    1. `StartupWMClass` equal to the app name -- the key exists precisely to tie
       a window back to its launcher, which is the question being asked here;
    2. the desktop file's own stem equal to the app name;
    3. the stem's LAST reverse-DNS component equal to the app name, so
       `org.gnome.gedit.desktop` is found for a window calling itself `gedit`
       (the same reduction `app_icons.normalise` applies to an application id);
    4. the `Exec=` program equal to `/proc/<pid>/exe`.

    ⚠️ Rank 3 exists because rank 4 TIES and the tie is broken by readdir order.
    Measured on a stock Xfce install: `org.xfce.mousepad.desktop` and
    `org.xfce.mousepad-settings.desktop` both have the `Exec` stem `mousepad`,
    and the settings one sorts first (`-` < `.`), so Mousepad resolved to *"Text
    Editor Settings"*. It went unnoticed for as long as only `Icon=` was read,
    because those two entries carry the SAME icon -- the display name is what
    made a pre-existing ambiguity visible.

    ⚠️ The APP NAME beats the executable, and that order is load-bearing rather
    than arbitrary. The name comes from the window manager and identifies the
    APPLICATION; `/proc/<pid>/exe` identifies the BINARY, and for anything
    running under an interpreter those are different things. Taking the exe
    first gave every Python app the Python icon.
    """
    exe_stem = os.path.basename(exe).lower() if exe else ""
    wanted = (app_name or "").strip().lower()

    def _pick(require_icon: bool):
        """(entry, which rank matched). The rank is for the log only.

        ⚠️ Reported from HERE rather than re-derived afterwards. The obvious
        version walked `_desktop_entries()` again and matched the winner by
        identity -- which can never hit, because that generator re-parses every
        file and hands back fresh dicts, so ranks 2 and 3 were both logged as
        "4/Exec-vs-exe". A diagnostic that lies is worse than none.
        """
        by_stem = {}
        by_dns = {}
        by_exec = {}
        for path, entry in _desktop_entries():
            if require_icon and not entry.get("Icon", ""):
                continue
            if wanted and entry.get("StartupWMClass", "").strip().lower() == wanted:
                return entry, "1/StartupWMClass"
            stem = os.path.basename(path)[:-len(".desktop")].lower()
            if wanted and not by_stem and stem == wanted:
                by_stem = entry
            if wanted and not by_dns and stem.rsplit(".", 1)[-1] == wanted:
                by_dns = entry
            if (exe_stem and not by_exec and not _is_runtime(exe_stem)
                    and _exec_stem(entry.get("Exec", "")) == exe_stem):
                by_exec = entry
        if by_stem:
            return by_stem, "2/stem"
        if by_dns:
            return by_dns, "3/reverse-dns"
        if by_exec:
            return by_exec, "4/Exec-vs-exe"
        return {}, "none"

    # ⚠️ The icon-bearing pass runs FIRST and unchanged, so this refactor cannot
    # move an icon that resolves today. Only when nothing carries an `Icon=` do
    # we look again for a name alone -- a name with no icon is still worth
    # having (it is what the catalog match is keyed on), a wrong icon is not.
    # ⚠️ Logged at INFO with the RANK, once per application. "No icon appeared"
    # and "no desktop entry matched" look identical from outside, and telling
    # them apart is what decides whether to look at the lookup or at the 1-bit
    # score -- a session was spent building a fixture to answer it.
    entry, rank = _pick(True)
    if not entry:
        entry, rank = _pick(False)
        rank += " (name-only pass)"
    log.info("Desktop entry for %r (exe %r): %s [match %s]",
             app_name, exe_stem or "<none>",
             (entry.get("Name") if entry else None) or "<no match>", rank)
    return entry



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


def _linux_identity(pid, app_name: str):
    exe = ""
    if pid:
        try:
            exe = os.readlink("/proc/%d/exe" % int(pid))
        except OSError as exc:
            log.debug("No /proc/%s/exe: %s", pid, exc)
    entry = _linux_entry(exe, app_name)
    names = tuple(n for n in (entry.get("Name", "").strip(),) if n)
    icon = entry.get("Icon", "")
    for path in _theme_candidates(icon) if icon else ():
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            log.debug("Could not read %s: %s", path, exc)
            continue
        # ⚠️ The FILE, not just "an icon was found". Which one the theme hands
        # back decides everything downstream -- `_theme_candidates` sorts raster
        # AHEAD of svg, so the same application can resolve to a 48px PNG on one
        # machine and a scalable SVG on another, and those take different
        # branches in `render_os_overlay`. Diagnosing a blank keycap without
        # this line means guessing which one was read.
        log.info("Icon for %r: %s (%d B) via Icon=%r, names=%s",
                 app_name, path, len(data), icon, ", ".join(names) or "<none>")
        return AppIdentity(data, path, names)
    # The other half of the question, and the one that looks identical from
    # outside: an entry with a name but no icon file on disk. Only the catalog
    # can draw for it, keyed on those names.
    log.info("No icon FILE for %r: Icon=%r resolved to nothing, names=%s",
             app_name, icon or "<unset>", ", ".join(names) or "<none>")
    return AppIdentity(None, "", names)


# ---------------------------------------------------------------------------
# Windows: pid -> exe -> PE resource icon
# ---------------------------------------------------------------------------

_RT_ICON = 3
_RT_GROUP_ICON = 14


def _windows_exe(pid) -> str:
    """The full image path of a running process, or "".

    ⚠️ **The arg/restypes are load-bearing, not decoration.** `OpenProcess`
    returns a HANDLE; with no explicit `restype` ctypes defaults to `c_int` and
    TRUNCATES it on 64-bit, so `CloseHandle` then closes the wrong thing or
    nothing at all. Handles are usually small enough that it appears to work,
    which is what makes it a latent bug rather than an obvious one -- and this
    path has never run on Windows, so "it seems fine" is not evidence.

    ⚠️ Spelled `import ctypes.wintypes`, not `from ctypes import wintypes`, so
    the module is imported one way only (CodeQL py/import-and-import-from), and
    imported lazily because `ctypes.wintypes` raises off Windows.

    ⚠️ This duplicates the binding in `handler/win_process.py`, which resolves
    the same thing from an HWND. Two hand-written copies of one Win32 binding is
    the shape this repo has already been bitten by; unifying them means moving
    the loader somewhere both a service and a handler may import, which is its
    own change -- see `docs/generic-icons-plan.md`.
    """
    try:
        import ctypes
        import ctypes.wintypes
        wintypes = ctypes.wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                         wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            # ⚠️ SAY WHY. This returned "" silently, which `_windows_identity`
            # turns into an empty AppIdentity and the tick renders as
            # `OS names: <none>` -- i.e. "this OS has nothing to say about the
            # app", when the truth is "I could not open the process". Measured
            # 2026-09-21: 7zFM reported no names and no icon while
            # `os_icon_probe.py` on the same binary read `FileDescription:
            # 7-Zip File Manager` and drew the icon. That is the E13 defect
            # again -- a message naming the wrong cause -- and the real one is
            # already in hand, because the DLL is loaded `use_last_error=True`.
            # ERROR_ACCESS_DENIED (5) is the one to expect: an elevated process
            # cannot be opened by an unelevated host.
            log.debug("Could not open pid %s to read its image path "
                      "(GetLastError=%d); its name and icon are unavailable, "
                      "which is NOT the same as the OS having none.",
                      pid, ctypes.get_last_error())
            return ""
        try:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(
                    handle, 0, buffer, ctypes.byref(size)):
                log.debug("Opened pid %s but could not read its image path "
                          "(GetLastError=%d).", pid, ctypes.get_last_error())
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


_RT_VERSION = 16

# The two StringFileInfo keys that can name an application, best first.
#
# ⚠️ NEITHER is reliable alone, which is why both are offered and the catalog's
# own 404 is left to reject. `ProductName` is frequently the SUITE -- Word,
# Excel and PowerPoint are all expected to answer "Microsoft Office", which
# would hand the three of them one identical mark -- while `FileDescription` is
# frequently a sentence ("Notepad++ : a free (GNU) source code editor") or the
# bare exe name (`pwsh`, whose ProductName is the useful "PowerShell").
# ⚠️ EXPECTED, not measured: no Windows machine has run this. `os_icon_probe.py`
# prints both keys so the ordering can be settled with evidence rather than kept
# on this comment's say-so.
_PE_NAME_KEYS = ("FileDescription", "ProductName")


def _align4(offset: int) -> int:
    return (offset + 3) & ~3


def _vs_key(data: bytes, pos: int, end: int):
    """The NUL-terminated UTF-16LE key at `pos`, and the offset just past it."""
    cursor = pos
    while cursor + 2 <= end:
        if data[cursor:cursor + 2] == b"\x00\x00":
            return data[pos:cursor].decode("utf-16-le", "replace"), cursor + 2
        cursor += 2
    return "", end


def _vs_walk(data: bytes, start: int, end: int, depth: int = 0):
    """Yield (key, text) for every String leaf in a VS_VERSIONINFO subtree.

    Every node is `wLength wValueLength wType` then a NUL-terminated UTF-16LE
    key, each part padded to a 32-bit boundary. A node with `wType == 1` and a
    non-zero value length is a String leaf; anything else is a container whose
    children fill the rest of its length.
    """
    if depth > 8:
        return
    pos = start
    while pos + 6 <= end:
        length, value_len, value_type = struct.unpack_from("<HHH", data, pos)
        # ⚠️ A zero (or sub-header) length is not merely malformed, it is an
        # INFINITE LOOP -- `pos` would never advance. Stop rather than trust it.
        if length < 6:
            return
        node_end = min(pos + length, end)
        key, after_key = _vs_key(data, pos + 6, node_end)
        value_start = _align4(after_key)
        if value_type == 1 and value_len:
            # ⚠️ `wValueLength` is documented in WCHARs and some producers write
            # BYTES. Clamping to the node covers both: an already-in-bytes count
            # doubled simply runs to the end of the node, and the NUL strip below
            # gives the same string either way.
            stop = min(value_start + value_len * 2, node_end)
            text = data[value_start:stop].decode("utf-16-le", "replace")
            yield key, text.split("\x00", 1)[0].strip()
        else:
            child = _align4(value_start + value_len)
            yield from _vs_walk(data, child, node_end, depth + 1)
        pos = _align4(pos + length)


def version_strings(data: bytes) -> dict:
    """Every StringFileInfo key/value in a PE's RT_VERSION resource, or {}.

    Reached with the resource walker `icon_from_pe` already uses -- the only new
    part is the VS_VERSIONINFO node format, so this costs no new dependency and
    no second PE parse.
    """
    reader = _pe_resource_reader(data)
    if reader is None:
        return {}
    # ⚠️ (to_offset, root), and this unpacked it BACKWARDS -- so `_resource_blob`
    # got a function where it wants an int, raised, and `app_identity` caught it
    # and returned an empty identity. Every Windows version-resource name was
    # silently lost, icon included (Greptile, #240). `icon_from_pe` is the
    # working caller and unpacks it this way round.
    to_offset, root = reader
    blob = _resource_blob(data, root, to_offset, _RT_VERSION)
    if not blob:
        return {}
    out = {}
    for key, text in _vs_walk(blob, 0, len(blob)):
        if key and text:
            out.setdefault(key, text)
    return out


def names_from_version_strings(strings: dict) -> tuple:
    """Display-name candidates from a version-string table, best first.

    Split out from the PE walk because the ORDER is the decision worth testing
    and the resource parse is not: given the table, which key names the
    application is a judgement, and it is wrong in both directions often enough
    that both keys are offered.
    """
    seen = []
    for key in _PE_NAME_KEYS:
        value = (strings.get(key) or "").strip()
        if value and value not in seen:
            seen.append(value)
    return tuple(seen)


def names_from_pe(data: bytes) -> tuple:
    """Display-name candidates from a PE's version resource, best first."""
    return names_from_version_strings(version_strings(data))


def _windows_identity(pid, app_name: str):
    exe = _windows_exe(pid)
    if not exe or not os.path.isfile(exe):
        return AppIdentity(None, "", ())
    try:
        with open(exe, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        log.debug("Could not read %s: %s", exe, exc)
        return AppIdentity(None, "", ())
    # One read serves both: the icon and the name are different resource types
    # in the same table, so asking for the name costs no second file read.
    blob = icon_from_pe(data)
    return AppIdentity(blob or None, exe if blob else "", names_from_pe(data))


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


def _macos_identity(pid, app_name: str):
    bundle = _macos_bundle(pid)
    if not bundle:
        return AppIdentity(None, "", ())
    resources = os.path.join(bundle, "Contents", "Resources")
    name = ""
    names = ()
    try:
        import plistlib
        with open(os.path.join(bundle, "Contents", "Info.plist"), "rb") as handle:
            plist = plistlib.load(handle)
        name = str(plist.get("CFBundleIconFile", "") or "")
        # DisplayName is what Finder shows and may be localised; CFBundleName is
        # the short one. Both are offered, best first, and the catalog rejects.
        names = tuple(dict.fromkeys(
            value for value in (str(plist.get("CFBundleDisplayName", "") or "").strip(),
                                str(plist.get("CFBundleName", "") or "").strip())
            if value))
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
                return AppIdentity(handle.read(), path, names)
        except OSError:
            continue
    return AppIdentity(None, "", names)


# ---------------------------------------------------------------------------

BACKENDS = {
    "linux": _linux_identity,
    "win32": _windows_identity,
    "darwin": _macos_identity,
}

_EMPTY = AppIdentity(None, "", ())


def platform_key() -> str:
    return "linux" if sys.platform.startswith("linux") else sys.platform


def app_identity(pid, app_name: str = "") -> AppIdentity:
    """What this OS can say about a running application. Never raises.

    Always returns an `AppIdentity`; an unsupported platform or a failed lookup
    is an empty one rather than None, so a caller reading `.names` needs no
    guard. This is decoration, and a lookup that throws must not take the
    overlay send with it.
    """
    backend = BACKENDS.get(platform_key())
    if backend is None:
        return _EMPTY
    try:
        return backend(pid, app_name or "") or _EMPTY
    except Exception as exc:            # noqa: BLE001 - cosmetic lookup
        log.debug("OS identity lookup failed for pid=%s app=%s: %s", pid, app_name, exc)
        return _EMPTY


def icon_bytes(pid, app_name: str = ""):
    """(image bytes, source path) for the focused app's own icon, or None."""
    found = app_identity(pid, app_name)
    return (found.icon, found.icon_path) if found.icon else None


def display_names(pid, app_name: str = "") -> tuple:
    """Display-name candidates for a running application, best first.

    Empty when the OS has nothing to say. These are what a catalog match should
    be keyed on: `kebab("Microsoft Word")` is mdi's own `microsoft-word`, which
    the executable name `winword` can never reach -- see
    `docs/generic-icons-plan.md` B.2 for the measurement.
    """
    return app_identity(pid, app_name).names
