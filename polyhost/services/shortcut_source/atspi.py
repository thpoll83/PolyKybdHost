"""AT-SPI2 discovery — the Linux backend.

Extracted from `tools/shortcut_probe.py` unchanged; see `model.py` for why the
probe imports this rather than carrying its own copy.

⚠️ MEASURED CEILING: this finds shortcuts for CLASSIC-MENUBAR apps only. An app
whose menu lives in a hamburger popover exposes no accelerator at all -- gedit's
real Ctrl+S is simply absent from its accessible tree, and GTK4 answers
"<VoidSymbol>" for every keybinding it has. That is not a bug to fix here; it is
the reason `services/shortcut_overlays.py` must degrade to drawing nothing.
"""

from __future__ import annotations

import re

from polyhost.services.shortcut_source.model import (
    Shortcut, parse_accel, pick_binding)


def _import_gi():
    """PyGObject, reaching into the distro's packages when this venv hides them.

    ⚠️ **A venv is the STANDARD way to run this app, and PyGObject cannot be
    installed into one** -- it is a distro package (`python3-gi`, living in
    `/usr/lib/python3/dist-packages`), and `pip install PyGObject` builds from
    source against the gobject-introspection headers, which a managed machine
    will not have. So `python -m venv .venv` without `--system-site-packages`
    silently costs the whole shortcut feature, and the user's only remedy was to
    know to edit `pyvenv.cfg`. Reported 2026-09-18.

    ⚠️ **Guarded on the ABI TAG, and that guard is the whole safety argument.**
    `gi` is a COMPILED extension built for one Python minor version; importing
    3.12's `_gi.cpython-312-*.so` into 3.11 fails with a circular-import error
    that names neither cause (measured -- it is what this container does). So
    the directory is added only when it holds a `_gi` built for exactly this
    interpreter, which is true precisely when the venv was made from the system
    python3 -- the case worth rescuing.

    The path goes on `sys.path` only for this import and is removed again, so a
    venv's own packages are never shadowed by the distro's.
    """
    try:
        import gi
        return gi
    except ImportError as exc:
        first = exc
    extra = _system_site_dir()
    if extra is None:
        raise first
    import sys
    sys.path.append(extra)
    try:
        import gi
        return gi
    finally:
        try:
            sys.path.remove(extra)
        except ValueError:
            pass


_BUS_OK = None


def _bus_ok(Atspi) -> bool:
    """Did `Atspi.init()` succeed? Asked ONCE per process, and cached.

    ⚠️ **`Atspi.init()` is not idempotent as a probe.** The first call returns 2
    when the bus is unreachable; a SECOND call then returns 1 ("already
    initialised") even though it failed, so re-probing reports success and the
    next `get_desktop()` aborts the process. Measured 2026-09-18: the first
    `unavailable_reason()` answered correctly and the one right after it died
    with SIGTRAP.

    Caching is also what the harvest path wants -- it is a per-process fact, and
    a user who starts the a11y bus after the app can restart the app.
    """
    global _BUS_OK
    if _BUS_OK is None:
        _BUS_OK = Atspi.init() < 2
    return _BUS_OK


def _system_site_dir():
    """The distro package dir whose compiled `gi` matches THIS interpreter, or None."""
    import glob
    import os
    import sysconfig
    suffix = sysconfig.get_config_var("EXT_SUFFIX") or ""
    if not suffix:
        return None
    for root in ("/usr/lib/python3/dist-packages",
                 "/usr/lib64/python3/site-packages"):
        if os.path.exists(os.path.join(root, "gi", "_gi" + suffix)):
            return root
    return None


def _atspi():
    gi = _import_gi()
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    return Atspi


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def walk(node, atspi, budget: list[int], depth: int = 0, path: tuple[str, ...] = ()):
    """Yield (accessible, role_name, path) over the subtree, bounded by `budget`.

    The budget is a shared mutable counter rather than a depth limit: an app's
    accessible tree can be tens of thousands of nodes and every child access is a
    D-Bus round trip, so the cost has to be capped globally, not per branch.
    """
    if budget[0] <= 0 or depth > 24:
        return
    budget[0] -= 1
    role = _safe(node.get_role_name, "") or ""
    name = _safe(node.get_name, "") or ""
    yield node, role, path
    count = _safe(node.get_child_count, 0) or 0
    here = path + (name or f"<{role}>",)
    for i in range(count):
        child = _safe(lambda i=i: node.get_child_at_index(i))
        if child is None:
            continue
        yield from walk(child, atspi, budget, depth + 1, here)


def shortcuts_for(app, atspi, budget: list[int]) -> list[Shortcut]:
    found: list[Shortcut] = []
    seen: set[tuple[int, str]] = set()
    for node, role, path in walk(app, atspi, budget):
        action = _safe(node.get_action_iface)
        if action is None:
            continue
        n = _safe(action.get_n_actions, 0) or 0
        for i in range(n):
            raw = _safe(lambda i=i: action.get_key_binding(i), "") or ""
            accel_text, kind = pick_binding(raw, role)
            if not accel_text:
                continue
            accel = parse_accel(accel_text)
            if accel is None:
                continue
            label = (_safe(node.get_name, "") or "").strip()
            key = (accel.mods, accel.keysym)
            if key in seen:
                continue
            seen.add(key)
            found.append(Shortcut(
                label=label, role=role, accel=accel.pretty(), mods=accel.mods,
                keysym=accel.keysym, hid=accel.hid, displayable=accel.displayable,
                kind=kind, path=list(path), raw=raw,
            ))
    return found


def list_apps(atspi) -> list[tuple[int, str]]:
    desktop = atspi.get_desktop(0)
    out = []
    for i in range(desktop.get_child_count()):
        child = _safe(lambda i=i: desktop.get_child_at_index(i))
        if child is None:
            continue
        out.append((i, _safe(child.get_name, "") or "<unnamed>"))
    return out


DEFAULT_NODE_BUDGET = 4000


def available() -> bool:
    """Is the accessibility bridge reachable at all?

    A plain import check: `Atspi` imports fine without a session bus and only
    fails when asked for the desktop, so the desktop is what is asked for.
    """
    return unavailable_reason() is None


def unavailable_reason() -> str | None:
    """WHY the bridge is unusable, or None when it works.

    ⚠️ **Three different causes used to collapse into one sentence, and the most
    likely of the three was the one the sentence ruled out.** `available()`
    swallowed every exception, so the caller could only say *"no accessibility
    backend on this platform"* -- which is true on macOS, and actively
    misleading when the real cause is that THIS INTERPRETER cannot see the
    system PyGObject. PyGObject is a distro package living in
    `/usr/lib/python3/dist-packages`; a virtualenv built without
    `--system-site-packages` cannot import it however thoroughly it is
    installed, so a user reading that line goes and installs a package they
    already have (reported 2026-09-18, from `python3 tools/shortcut_probe.py`
    answering `No module named 'gi'`).

    The three are told apart because they need opposite fixes: a different
    interpreter (or one line in `pyvenv.cfg`), a distro package, or starting a
    service. Cheap enough for the harvest path -- no subprocess, no bus call
    beyond the one `available()` always made.
    """
    try:
        _import_gi()
    except ImportError:
        return _no_pygobject_reason()
    try:
        # Through `_atspi()` rather than repeating its three lines here: the two
        # must agree about what "usable" means, and a second copy of the import
        # is a second thing to keep in step.
        Atspi = _atspi()
    except Exception as exc:
        return ("the Atspi typelib is missing (install gir1.2-atspi-2.0): %s"
                % exc)
    # ⚠️ **`Atspi.get_desktop()` does not RAISE when the bus is down -- it
    # `g_error()`s, which calls abort(). SIGTRAP, exit 133, and no Python
    # exception to catch** (measured 2026-09-18: `dbind-ERROR **: AT-SPI:
    # Couldn't connect to accessibility bus`). This runs on the fetcher's
    # background thread inside the user's tray app, so reaching it would take
    # the whole application down for a cosmetic feature.
    #
    # `Atspi.init()` is the probe that does NOT abort: it RETURNS 0 on success,
    # 1 if already initialised and 2 on error. Check it first, and touch the
    # desktop only once it has said yes.
    #
    # ⚠️ The hazard is OLDER than this function and was simply unreachable: in a
    # venv `import gi` failed long before anything called AT-SPI. `_import_gi`'s
    # rescue is exactly what makes it reachable, so the two had to land together.
    if not _bus_ok(Atspi):
        return "the accessibility bus is not running (org.a11y.Bus)"
    try:
        Atspi.get_desktop(0).get_child_count()
    except Exception as exc:
        return "the accessibility bus is not answering: %s" % exc
    return None


def _no_pygobject_reason() -> str:
    """`gi` is not importable AND `_import_gi`'s rescue could not fix it.

    ⚠️ The advice *"set include-system-site-packages"* used to live here and is
    gone on purpose: the rescue now covers that case automatically, so reaching
    this function means one of only two things. Either PyGObject is not on the
    machine at all, or it is there and built for a different Python minor
    version than this interpreter -- which `include-system-site-packages` would
    NOT have fixed, because the compiled `_gi` still would not load.
    """
    import glob
    import sys
    import sysconfig
    # ⚠️ "not installed" is the wrong word whenever the distro package is on
    # disk for a DIFFERENT interpreter, which is the whole point of this
    # function -- saying it would reproduce the misleading message one level
    # down. So look before saying it.
    found = (glob.glob("/usr/lib/python3*/dist-packages/gi/_gi.*.so")
             + glob.glob("/usr/lib64/python3*/site-packages/gi/_gi.*.so"))
    if not found:
        return "PyGObject is not installed (install python3-gi)"
    theirs = re.search(r"cpython-(\d+)", found[0])
    ours = sysconfig.get_config_var("EXT_SUFFIX") or ""
    mine = re.search(r"cpython-(\d+)", ours)
    versions = ""
    if theirs and mine:
        versions = " (it is built for %s, this is %s)" % (
            _dotted(theirs.group(1)), _dotted(mine.group(1)))
    if sys.prefix != sys.base_prefix:
        return ("this virtualenv is a different Python version than the system "
                "PyGObject%s -- recreate it with the system python3" % versions)
    return ("PyGObject is installed for a different Python than %s%s -- run the "
            "interpreter it was built for" % (sys.executable, versions))


def _dotted(tag: str) -> str:
    """`312` -> `3.12`, so the message names a version a human recognises."""
    return "%s.%s" % (tag[0], tag[1:]) if len(tag) > 1 else tag

def shortcuts_for_app(name: str, budget: int = DEFAULT_NODE_BUDGET,
                      reason: dict | None = None) -> list[Shortcut]:
    """Every shortcut the named application exposes, or [] for anything at all.

    Matched on a substring of the desktop child's name, the same rule the probe's
    `--app` uses, because the accessible name ("gedit") and the window-manager
    class the host tracks ("org.gnome.gedit") agree only loosely.

    ⚠️ Returns [] rather than raising on ANY failure. This runs on a background
    thread for a cosmetic feature; an app that died mid-walk, a bridge that is
    not running, or a D-Bus timeout must all cost nothing.

    `reason` is accepted and not filled in, so all three backends share ONE
    signature and `harvest()` needs no branch to call them -- the same reason
    `_backend_module()` replaced the if/else that `pick()` and
    `unavailable_reason()` each carried. A backend that fills it tells the
    caller WHICH empty answer this was (`macos` does); one that does not leaves
    the caller on its generic sentence, which is today's behaviour.
    """
    if not name:
        return []
    needle = name.lower()
    try:
        atspi = _atspi()
        desktop = atspi.get_desktop(0)
        counter = [budget]
        for i in range(desktop.get_child_count()):
            child = _safe(lambda i=i: desktop.get_child_at_index(i))
            if child is None:
                continue
            child_name = (_safe(child.get_name, "") or "").lower()
            if not child_name or needle not in child_name and child_name not in needle:
                continue
            return shortcuts_for(child, atspi, counter)
    except Exception:
        return []
    return []
