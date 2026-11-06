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

# Kept on the gdb module, so a second `source` of this file (a reloaded init
# file, a manual source) keeps the pushed-title state and replaces the event
# handlers instead of adding a second set.
_state = getattr(gdb, "_polykybd_title_state", None) or {"pushed": False, "last": None}
gdb._polykybd_title_state = _state


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
    """Write `seq` to the terminal. True when it was written and flushed."""
    out = _out()
    if out is None:
        return False
    # A closed or vanished terminal (GDB exiting, a detached session) must not
    # turn a title update into a Python error in the middle of a GDB command.
    with contextlib.suppress(OSError, ValueError):
        out.write(seq)
        out.flush()
        return True
    return False


def set_title(state):
    """Write ``gdb <state> <program>`` as the window title (OSC 2)."""
    title = " ".join(part for part in ("gdb", state, _program()) if part)
    if title == _state["last"]:
        return
    if not _state["pushed"]:
        # Save the terminal's title (xterm title stack), restored on exit.
        # Terminals without the stack ignore the sequence.
        _state["pushed"] = _write("\x1b[22;2t")
    # Remember the title only once it reached the terminal, so a failed write
    # is retried at the next prompt.
    _state["last"] = title if _write("\x1b]2;" + title + "\x07") else None


def _on_prompt():
    set_title(STOPPED)


def _on_cont(_event):
    set_title(RUNNING)


def _on_exiting(_event):
    if _state["pushed"]:
        _write("\x1b[23;2t")
        _state["pushed"] = False


_HANDLERS = [(gdb.events.before_prompt, _on_prompt), (gdb.events.cont, _on_cont)]
if hasattr(gdb.events, "gdb_exiting"):      # GDB 12 and later
    _HANDLERS.append((gdb.events.gdb_exiting, _on_exiting))

for _registry, _handler in getattr(gdb, "_polykybd_title_handlers", ()):
    with contextlib.suppress(ValueError, RuntimeError):
        _registry.disconnect(_handler)
for _registry, _handler in _HANDLERS:
    _registry.connect(_handler)
gdb._polykybd_title_handlers = _HANDLERS
