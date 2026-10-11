#!/usr/bin/env python3
"""Keep the UI translations in step with the code.

    python scripts/i18n_strings.py unmarked     # literals shown unmarked in the UI
    python scripts/i18n_strings.py update       # extract polyhost.pot, merge every .po
    python scripts/i18n_strings.py check        # exit 1 if the .pot is stale

``unmarked`` is pure ``ast`` and is what tests/i18n_marking_test.py runs. It
looks at every literal handed straight to a Qt text call (a constructor like
QLabel or a setter like setToolTip) and reports the ones not wrapped in
``_()``, ``_f()``, ``ngettext()`` or ``pgettext()``. It cannot see a string
that reaches the widget through a variable, so a clean scan is a floor, not
proof; the ``pseudo`` locale (POLYHOST_LANG=pseudo) is how you look for the
rest. A literal that must stay as it is (a product name, a file name) carries
``# i18n: skip`` on its line.

``update`` and ``check`` need Babel (tools/requirements.txt), which the app
itself does not: catalogs are read straight from the .po files at runtime.
"""

import ast
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "polyhost")
LOCALE_DIR = os.path.join(PKG, "res", "locale")
POT = os.path.join(LOCALE_DIR, "polyhost.pot")

# The modules whose strings a user reads in the tray app or the forwarder.
# The core, the device layer, polyctl and every log line stay English.
UI_PATHS = ("polyhost/gui", "polyhost/host.py", "polyhost/forwarder.py")
# Modules outside the UI that define N_-marked text the UI shows (extracted,
# but not scanned: their other literals are not UI).
# The device and service modules whose English status messages the GUI shows
# through i18n.translate_message() are listed too (their M_() templates).
EXTRA_EXTRACT = (
    "polyhost/device/command_ids.py", "polyhost/services/lang_regions.py",
    "polyhost/device/hid_fw_up.py", "polyhost/device/split_link.py",
    "polyhost/services/updater.py", "polyhost/services/wincompose_install.py",
)

KEYWORDS = ("_", "_f", "N_", "M_", "_nf:1,2", "ngettext:1,2", "pgettext:1c,2")
MARKERS = {"_", "_f", "N_", "M_", "_nf", "ngettext", "pgettext"}

# Widgets whose constructor takes the shown text.
UI_CONSTRUCTORS = {
    "QAction", "QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox",
    "QMenu", "QToolButton", "QCommandLinkButton", "QMessageBox", "QProgressDialog",
    "QListWidgetItem", "QTreeWidgetItem", "QTableWidgetItem",
}
# Methods whose arguments are shown text. QMessageBox's static helpers take
# (parent, title, text, ...), so every string argument counts.
UI_SETTERS = {
    "setText", "setWindowTitle", "setToolTip", "setStatusTip", "setWhatsThis",
    "setPlaceholderText", "setTitle", "addAction", "addMenu", "addTab", "setTabText",
    "insertTab", "setTabToolTip", "setLabelText", "setInformativeText", "setDetailedText",
    "setCancelButtonText", "showMessage", "addItem", "addItems", "insertItem",
    "setHeaderLabels", "setHorizontalHeaderLabels", "setVerticalHeaderLabels",
    "setPrefix", "setSuffix", "setSpecialValueText", "setButtonText", "addButton",
    "getText", "getItem", "getOpenFileName", "getSaveFileName", "getExistingDirectory",
    "setNameFilter", "setHtml", "setPlainText", "setFormat", "addRow", "setDefaultSuffix",
}
# QMessageBox's static helpers, which share their names with logger methods:
# counted only when called on QMessageBox itself.
MESSAGE_BOX_STATICS = {"information", "warning", "critical", "question", "about"}

_LETTER = re.compile(r"[A-Za-z]{2}")


def _call_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _shown_literal(node):
    """The literal text ``node`` puts on screen unmarked, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value if _LETTER.search(node.value) else None
    if isinstance(node, ast.JoinedStr):
        text = "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
        return f"f{text!r}" if _LETTER.search(text) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _shown_literal(node.left) or _shown_literal(node.right)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == "format":
        return _shown_literal(node.func.value)
    if isinstance(node, ast.IfExp):
        return _shown_literal(node.body) or _shown_literal(node.orelse)
    if isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            found = _shown_literal(elt)
            if found:
                return found
    return None


def _iter_files(paths):
    for rel in paths:
        path = os.path.join(ROOT, rel)
        if os.path.isfile(path):
            yield path
            continue
        for dirpath, _dirs, files in os.walk(path):
            for name in sorted(files):
                if name.endswith(".py"):
                    yield os.path.join(dirpath, name)


def scan_source(source, filename="<string>"):
    """[(line, text)] for each unmarked literal shown by a Qt text call."""
    tree = ast.parse(source, filename)
    lines = source.splitlines()
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if name in MESSAGE_BOX_STATICS:
            owner = node.func.value if isinstance(node.func, ast.Attribute) else None
            if _call_name(owner) != "QMessageBox":
                continue
        elif name not in UI_CONSTRUCTORS and name not in UI_SETTERS:
            continue
        args = list(node.args) + [kw.value for kw in node.keywords
                                  if kw.arg in (None, "text", "title", "toolTip")]
        for arg in args:
            text = _shown_literal(arg)
            if text is None:
                continue
            line = getattr(arg, "lineno", node.lineno)
            span = lines[node.lineno - 1:getattr(node, "end_lineno", node.lineno)]
            if any("i18n: skip" in ln for ln in span):
                continue
            found.append((line, text))
    return found


def scan_shadowed_underscore(source, filename="<string>"):
    """[(line, function)] for each function that calls ``_()`` but also binds
    ``_`` (``for _ in``, ``ok, _ = ...``). Python then treats ``_`` as local
    in the WHOLE function, and the call raises UnboundLocalError."""
    tree = ast.parse(source, filename)
    found = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        calls = binds = False
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "_":
                calls = True
            elif isinstance(node, ast.Name) and node.id == "_" and \
                    isinstance(node.ctx, (ast.Store, ast.Del)):
                binds = True
            elif isinstance(node, ast.arg) and node.arg == "_":
                binds = True
        if calls and binds:
            found.append((fn.lineno, getattr(fn, "name", "<lambda>")))
    return found


def scan_shadowed(paths=UI_PATHS):
    out = []
    for path in _iter_files(paths):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        rel = os.path.relpath(path, ROOT)
        out.extend((rel, line, name) for line, name in scan_shadowed_underscore(source, rel))
    return sorted(out)


def scan_unmarked(paths=UI_PATHS):
    """[(relative path, line, text)] across ``paths``."""
    out = []
    for path in _iter_files(paths):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        rel = os.path.relpath(path, ROOT)
        out.extend((rel, line, text) for line, text in scan_source(source, rel))
    return sorted(out)


def _babel(*args):
    return subprocess.run([sys.executable, "-m", "babel.messages.frontend", *args],
                          cwd=ROOT, check=True, capture_output=True, text=True)


def extract(out_path):
    kw = []
    for k in KEYWORDS:
        kw += ["-k", k]
    _babel("extract", "--no-default-keywords", *kw, "--sort-by-file", "--no-wrap",
           "--add-comments=TRANSLATORS:", "--project=PolyKybdHost",
           "--copyright-holder=PolyKybd contributors",
           "--msgid-bugs-address=https://github.com/thpoll83/PolyKybdHost/issues",
           "-o", out_path, *UI_PATHS, *EXTRA_EXTRACT)


def _msgids(path):
    """The (context, msgid, plural) set of a catalog. Line references, dates
    and the header change on every edit and every year; only this decides
    whether translators have something new."""
    from polyhost import i18n
    with open(path, encoding="utf-8") as fh:
        _header, entries = i18n.parse_po(fh.read())
    return {(e["msgctxt"], e["msgid"], e["msgid_plural"]) for e in entries}


def update():
    from polyhost import i18n
    extract(POT)
    for lang in i18n.LANGUAGES:
        if lang.code == i18n.SOURCE_LANGUAGE:
            continue
        po = i18n.po_path(lang.code)
        if os.path.exists(po):
            _babel("update", "--no-wrap", "--ignore-obsolete", "--no-fuzzy-matching",
                   "-i", POT, "-o", po, "-l", lang.code)
        else:
            _babel("init", "--no-wrap", "-i", POT, "-o", po, "-l", lang.code)
    print(f"Updated {POT} and {len(i18n.LANGUAGES) - 1} catalogs.")


def pot_is_current():
    with tempfile.TemporaryDirectory() as tmp:
        fresh = os.path.join(tmp, "polyhost.pot")
        extract(fresh)
        return _msgids(fresh) == _msgids(POT)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "unmarked"
    if cmd == "unmarked":
        found = scan_unmarked()
        for rel, line, text in found:
            print(f"{rel}:{line}: {text[:90]!r}")
        print(f"{len(found)} unmarked UI literal(s).")
        shadowed = scan_shadowed()
        for rel, line, name in shadowed:
            print(f"{rel}:{line}: {name}() calls _() but also assigns _")
        return 1 if found or shadowed else 0
    if cmd == "update":
        update()
        return 0
    if cmd == "check":
        if pot_is_current():
            print("polyhost.pot is current.")
            return 0
        print("polyhost.pot is stale: run `python scripts/i18n_strings.py update`.")
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    sys.exit(main(sys.argv))
