"""Spawn-or-attach a headless daemon for daemon-by-default mode (headless-core H4b).

Qt-free by construction — imported from the Qt-free ``main_app`` decision path
and from tests, never from Qt code. Provides three small pieces:

  - :func:`decide_startup_mode` — a **pure** mapping from a
    :func:`polyhost.server.instance.probe_existing` outcome + the ``daemon_mode``
    flag to one of the startup actions (``CLIENT`` / ``SPAWN_CLIENT`` /
    ``IN_PROCESS`` / ``DEFER``). All the branching logic lives here so it can be
    unit-tested without spawning anything.
  - :func:`spawn_headless_daemon` — launch ``python -m polyhost --headless``
    **detached** so the daemon outlives the GUI that spawned it (the daemon owns
    the device; quitting the GUI must not take it down).
  - :func:`wait_until_live` — poll the control endpoint until the freshly
    spawned daemon answers ``hello``.

The GUI spawns the daemon as a child of its **own already-venv-activated**
process, so the daemon inherits ``PATH``/the venv. That sidesteps the autostart
PATH-activation landmine documented in CLAUDE.md — that one bites a cold
``pythonw -m polyhost`` launched by the Windows scheduler, not a child of a
running interpreter.
"""
import subprocess
import sys
import time

from polyhost.server import instance as inst

# decide_startup_mode results.
CLIENT = "client"               # a daemon is LIVE — attach this GUI as a client
SPAWN_CLIENT = "spawn_client"   # nothing there — spawn a daemon, then attach
IN_PROCESS = "in_process"       # legacy: own the device in this process
DEFER = "defer"                 # endpoint in use but incompatible — exit


def decide_startup_mode(outcome, daemon_mode):
    """Pure decision: a ``probe_existing`` outcome + ``daemon_mode`` -> action.

    ``daemon_mode`` **off** reproduces today's single-instance behavior exactly:
    a LIVE endpoint means "already running" (defer/exit); STALE means "become
    the in-process host"; anything else (incompatible / auth mismatch) defers.

    ``daemon_mode`` **on** makes this GUI a *client* of a daemon: attach to a
    LIVE one, spawn + attach when the endpoint is STALE, and defer when a real
    but incompatible process owns it (never fight over the HID device)."""
    if not daemon_mode:
        if outcome == inst.STALE:
            return IN_PROCESS
        return DEFER            # LIVE (duplicate) or INCOMPATIBLE / AUTH_MISMATCH
    if outcome == inst.LIVE:
        return CLIENT
    if outcome == inst.STALE:
        return SPAWN_CLIENT
    return DEFER                # INCOMPATIBLE / AUTH_MISMATCH


def build_daemon_argv(extra_args=None):
    """The argv to spawn a headless daemon with the current interpreter."""
    argv = [sys.executable, "-m", "polyhost", "--headless"]
    if extra_args:
        argv.extend(extra_args)
    return argv


def spawn_headless_daemon(extra_args=None, log=None):
    """Launch the headless daemon **detached** so it outlives this process.

    Returns the :class:`subprocess.Popen` handle (so the caller can terminate it
    if it never comes up) or ``None`` if the spawn itself failed. stdio is sent
    to ``DEVNULL`` — the daemon logs through its own facilities, and a detached
    process must not inherit the GUI's console handles."""
    argv = build_daemon_argv(extra_args)
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        # DETACHED_PROCESS: the daemon gets no console (so no flash and it can't
        # die with the GUI's console). CREATE_NEW_PROCESS_GROUP keeps it from
        # receiving Ctrl+C/Ctrl+Break sent to the GUI's group.
        #
        # Do NOT also OR in CREATE_NO_WINDOW: DETACHED_PROCESS and
        # CREATE_NO_WINDOW are mutually exclusive console-disposition flags, and
        # combining them makes CreateProcess fail with ERROR_INVALID_PARAMETER
        # (87). That failure was swallowed here (spawn returns None), so on
        # Windows the daemon *never* spawned and daemon-by-default silently fell
        # back to in-process on every launch. DETACHED_PROCESS alone already
        # guarantees no console window for both python.exe and pythonw.exe.
        kwargs["creationflags"] = (
            subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        # setsid: the daemon leads its own session, so it survives the GUI
        # exiting / its controlling terminal closing.
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(argv, **kwargs)
    except Exception as e:  # noqa: BLE001 — spawn failure must degrade, not crash
        if log is not None:
            log.warning("Failed to spawn headless daemon: %s", e)
        return None
    if log is not None:
        log.info("Spawned headless daemon (pid %s).", proc.pid)
    return proc


def wait_until_live(timeout=8.0, poll_interval=0.15, address=None, authkey=None):
    """Poll the control endpoint until a daemon answers ``hello`` (LIVE).

    Returns True once LIVE, or False if ``timeout`` elapses first."""
    deadline = time.monotonic() + timeout
    while True:
        if inst.probe_existing(address, authkey) == inst.LIVE:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)
