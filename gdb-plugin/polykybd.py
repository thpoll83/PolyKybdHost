# PolyKybd state reporter for GDB.
#
# Writes GDB's state into the terminal's window title, so PolyKybdHost shows
# the keys that work now:
#
#   gdb ⏸ <program>   the (gdb) prompt is waiting for a command
#   gdb ▶ <program>   the program runs; only Ctrl+C reaches GDB
#
# Loaded by `source <this file>` from the GDB init file (PolyKybdHost's
# "Set up the terminal and editors…" dialog adds the lines). GDB 8.0 or later
# with Python support. Nothing is sent anywhere: the title is the only output.
#
# PolyKybdHost: polyhost/res/overlay_sources/tui/SOURCES.md, gdb-plugin/README.md.

import contextlib
import os
import sys

import gdb

STOPPED = "⏸"      # ⏸
RUNNING = "▶"      # ▶
_MAX_NAME = 60

_state = {"pushed": False, "last": None}


def _out():
    """The terminal GDB runs in, or None (batch mode, output to a pipe)."""
    stream = sys.__stdout__
    try:
        return stream if stream is not None and stream.isatty() else None
    except (AttributeError, ValueError):
        return None


def _program():
    """The base name of the program being debugged, without control
    characters, or "" when no file is loaded."""
    try:
        name = gdb.current_progspace().filename or ""
    except (gdb.error, RuntimeError):
        name = ""
    name = os.path.basename(name)
    name = "".join(ch for ch in name if ch.isprintable())
    return name[:_MAX_NAME]


def _write(seq):
    out = _out()
    if out is None:
        return
    # A closed or vanished terminal (GDB exiting, a detached session) must not
    # turn a title update into a Python error in the middle of a GDB command.
    with contextlib.suppress(OSError, ValueError):
        out.write(seq)
        out.flush()


def set_title(state):
    """Write ``gdb <state> <program>`` as the window title (OSC 2)."""
    title = " ".join(part for part in ("gdb", state, _program()) if part)
    if title == _state["last"]:
        return
    _state["last"] = title
    if not _state["pushed"]:
        # Save the terminal's title (xterm title stack), restored on exit.
        # Terminals without the stack ignore the sequence.
        _write("\x1b[22;2t")
        _state["pushed"] = True
    _write("\x1b]2;" + title + "\x07")


def _on_prompt():
    set_title(STOPPED)


def _on_cont(_event):
    set_title(RUNNING)


def _on_exiting(_event):
    if _state["pushed"]:
        _write("\x1b[23;2t")
        _state["pushed"] = False


gdb.events.before_prompt.connect(_on_prompt)
gdb.events.cont.connect(_on_cont)
if hasattr(gdb.events, "gdb_exiting"):      # GDB 12 and later
    gdb.events.gdb_exiting.connect(_on_exiting)
