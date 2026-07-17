import argparse
import logging
import sys
import time

# NOTE: Qt (PyQt5) and the Qt-dependent classes (PolyHost / PolyForwarder)
# are imported LAZILY inside the GUI branch of main() so that
# `--headless` runs in a process that never imports Qt (M2). Keep the
# top level Qt-free — guarded by tests/headless/headless_entry_test.py.
from polyhost.services.add_to_startup import setup_autostart_for_app, remove_autostart, get_autostart_status


def _setup_startup_logging(debug=0):
    """Configure a persistent diagnostic log for the **pre-GUI launch phase**.

    Everything before ``PolyHost``/``HeadlessHost`` configures logging — the
    daemon spawn/attach decision, autostart registration, the single-instance
    lock — previously only used bare ``print()``. On Windows the tray GUI runs
    under ``pythonw.exe``, where ``sys.stdout``/``sys.stderr`` are ``None`` and
    ``print()`` is a silent no-op, so when a launch went wrong (daemon failed to
    come up, instance deferred, autostart errored) there was **no trace
    anywhere** to diagnose it from.

    This writes that phase to ``startup_log.txt`` (next to ``host_log.txt`` /
    ``daemon_log.txt``) regardless of console availability. It uses its own
    dedicated logger with ``propagate=False`` so it never collides with the
    root-logger ``logging.basicConfig`` that ``PolyHost``/``HeadlessHost`` run
    later (``basicConfig`` is a no-op once the root has handlers — touching the
    root here would silently break ``host_log.txt``).

    Stdlib-only / Qt-free so it stays usable from the top-level launch path.
    Returns the configured logger.
    """
    from logging.handlers import RotatingFileHandler

    slog = logging.getLogger("PolyHostStartup")
    slog.setLevel(logging.DEBUG if debug else logging.INFO)
    slog.propagate = False
    if slog.handlers:  # idempotent if main() is ever re-entered (tests)
        return slog

    fmt = logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s")
    try:
        fh = RotatingFileHandler(
            filename="startup_log.txt", maxBytes=1 * 1024 * 1024, backupCount=2,
            encoding="utf-8")
        fh.setFormatter(fmt)
        slog.addHandler(fh)
    except OSError:
        # A read-only cwd shouldn't stop the app from launching.
        pass

    # Mirror to the console too, but only when there's a real stream to write to
    # — under pythonw.exe sys.stdout is None and a StreamHandler would raise.
    if getattr(sys, "stdout", None) is not None:
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(fmt)
        slog.addHandler(sh)
    return slog

def main(launch_monotonic=None, post_bootstrap_monotonic=None):
    parser = argparse.ArgumentParser(
                    prog='PolyHost',
                    usage='%(prog)s [options]',
                    description='Communication with your PolyKybd')
    parser.add_argument('--portable', default=False, action='store_true',
                        help='Do not add an autorun entry to your system')
    parser.add_argument('--debug', type=int, default=0, choices=[0, 1, 2], help='Set debug level: 0 (no debug), 1 (basic debug), 2 (detailed debug)')
    parser.add_argument('--ignore-version', default=False, action='store_true',
                        help='Skip firmware version/protocol compatibility check (use as a last resort if the keyboard cannot connect due to a version mismatch)')
    parser.add_argument('--headless', default=False, action='store_true',
                        help='Run the operational core + control socket with no GUI (no Qt). Drive it with the polyctl CLI.')
    parser.add_argument('--connect', nargs='?', const='', default=None, metavar='ENDPOINT',
                        help='Run the tray GUI as a CLIENT of an already-running core over the '
                             'control socket (H4a), instead of owning the device in-process. '
                             'Optionally pass a socket path; omit for the default endpoint.')
    parser.add_argument('--daemon', dest='daemon', action='store_true', default=None,
                        help='Daemon-by-default (H4b): run the operational core in a separate '
                             'headless daemon and attach this GUI to it as a client (spawning the '
                             'daemon if none is running). Overrides the daemon_mode setting.')
    parser.add_argument('--no-daemon', dest='daemon', action='store_false',
                        help='Force the legacy in-process GUI even if the daemon_mode setting is on.')
    parser.add_argument('--no-autostart', default=False, action='store_true',
                        help='Internal: skip autostart registration/removal. Used for the '
                             'GUI-spawned headless daemon so it does not touch the GUI autostart entry.')
    parser.add_argument('--host', help='Specify a host where the PolyKybd is physically connected to')
    parser.add_argument('--host-file', help='Path to a file containing the host IP, written by a session hook (see folder autorun_forwarder for examples). This option has higher priority than `--host`.')
    parser.add_argument('--report-rpc', default=False, action='store_true',
                        help='Forwarder: push the active window over the authenticated, '
                             'version-gated window-report network endpoint (H4d) instead of the '
                             'legacy unauthenticated plaintext TCP relay. The target host must '
                             'have window_report_network_enabled set.')
    parser.add_argument('--report-port', type=int, default=None,
                        help='Forwarder (--report-rpc): port of the window-report endpoint '
                             '(default: the built-in WINDOW_REPORT_PORT).')
    parser.add_argument('--report-authkey-file',
                        help='Forwarder (--report-rpc): path to a file holding the target '
                             "daemon's window-report authkey (its polykybd-winreport.authkey, "
                             'copied from the keyboard machine). Required across machines; if '
                             "omitted, this machine's local key is used (same-machine only).")
    args=parser.parse_args()

    # Pillow logs every PNG chunk at DEBUG ("STREAM b'IDAT' …", "Importing
    # PngImagePlugin"); under --debug that floods the host log (and interleaves
    # with our lines) since overlay decode moved to Pillow. Cap the PIL logger
    # so our DEBUG output stays readable. Harmless when not debugging.
    logging.getLogger("PIL").setLevel(logging.INFO)

    # Diagnostic log for the pre-GUI launch phase (works under pythonw, where
    # print() is a silent no-op). Captures the daemon decision, autostart, and
    # single-instance handling that otherwise leave no trace when a launch fails.
    import platform as _platform
    slog = _setup_startup_logging(args.debug)
    from polyhost._version import __version__ as _ver  # Qt-free
    slog.info("PolyKybdHost %s launching | platform=%s %s | interpreter=%s | argv=%s",
              _ver, _platform.system(), _platform.release(), sys.executable, sys.argv[1:])
    # Pre-logging timing: how long the dependency bootstrap and the imports
    # before this point took. If both are small, the rest of the "desktop ->
    # tray" gap is Windows firing the logon task + cold-starting the interpreter
    # (outside our control), not our startup code.
    if launch_monotonic is not None:
        now = time.monotonic()
        boot_ms = ((post_bootstrap_monotonic or now) - launch_monotonic) * 1000
        imports_ms = (now - (post_bootstrap_monotonic or launch_monotonic)) * 1000
        slog.info("Startup timing: dependency-bootstrap %.0f ms, pre-logging imports %.0f ms "
                  "(process-start -> here %.0f ms)",
                  boot_ms, imports_ms, (now - launch_monotonic) * 1000)

    # --connect: the user EXPLICITLY asked to run the GUI as a client of an
    # already-running core. `client_mode` is the *runtime* flag (it may also be
    # turned on below by daemon-by-default); `explicit_connect` records the
    # explicit request, which alone suppresses autostart registration.
    explicit_connect = args.connect is not None
    client_mode = explicit_connect
    endpoint = args.connect or None

    # Daemon-by-default (H4b): for a plain GUI launch (no --headless / --connect /
    # --host) optionally run the operational core in a SEPARATE headless daemon
    # and attach this GUI to it as a client — spawning the daemon if none is
    # running. Opt-in via the daemon_mode setting (overridable with
    # --daemon/--no-daemon). When off, the block is skipped and behavior is
    # identical to before. host.py is untouched: this only flips client_mode and
    # resolves the single-instance lock the same way --connect already does.
    daemon_handled_instance = False
    # Connect the GUI to the daemon in the background (tray appears immediately,
    # fills in once the daemon is live) instead of blocking startup — set only
    # when we spawn a fresh daemon, which takes a moment to bind its socket.
    defer_connect = False
    # Flags for a daemon we will spawn AFTER the heavy GUI imports load (so the
    # daemon's cold import doesn't contend with PyQt5 for CPU/disk/AV). None
    # means "no spawn pending".
    pending_daemon_spawn = None
    is_plain_gui = not (args.headless or explicit_connect or args.host or args.host_file)
    if is_plain_gui:
        if args.daemon is None:
            from polyhost.settings import PolySettings  # Qt-free
            daemon_mode = bool(PolySettings().get("daemon_mode"))
        else:
            daemon_mode = args.daemon
        slog.info("Daemon-by-default: daemon_mode=%s (source=%s)", daemon_mode,
                  "--daemon/--no-daemon" if args.daemon is not None else "setting")
        if daemon_mode:
            from polyhost.server import daemon_launch as dl
            from polyhost.server.instance import probe_existing
            outcome = probe_existing()
            action = dl.decide_startup_mode(outcome, True)
            slog.info("Control-endpoint probe=%s -> startup action=%s", outcome, action)
            if action == dl.DEFER:
                slog.warning("Control endpoint is in use but not answering compatibly; "
                             "exiting rather than starting a second host.")
                print("PolyKybdHost control endpoint is in use but not answering "
                      "compatibly. Exiting rather than starting a second host. "
                      "Restart the running instance if this is unexpected.")
                sys.exit(0)
            elif action == dl.CLIENT:
                slog.info("A core daemon is already live; attaching this GUI as a client.")
                print("Attaching to the running PolyKybdHost core (daemon mode).")
                client_mode, endpoint, daemon_handled_instance = True, None, True
            elif action == dl.SPAWN_CLIENT:
                # Don't spawn yet: defer until after the GUI's heavy imports
                # (PyQt5 / polyhost.host) have loaded, so the daemon's own cold
                # import doesn't compete with them for CPU/disk/antivirus and the
                # tray appears sooner. The actual spawn happens in the GUI branch
                # below; RemoteCore then connects in the background once it binds.
                slog.info("No core daemon running; will spawn one after the GUI imports load.")
                print("Starting the PolyKybdHost core daemon...")
                client_mode, endpoint, daemon_handled_instance = True, None, True
                defer_connect = True
                pending_daemon_spawn = _spawned_daemon_flags(args)

    # Autostart: a portable run removes any existing entry; an explicit --connect
    # client and the GUI-spawned daemon (--no-autostart) leave autostart alone;
    # everything else (incl. a daemon-mode GUI, which still autostarts and brings
    # the daemon up) registers. The daemon's lifecycle is owned by the GUI, so
    # the daemon must NOT register its own autostart entry.
    if args.portable or explicit_connect or args.no_autostart:
        if args.portable:
            existing = get_autostart_status()
            if existing != "none":
                slog.info("Portable mode: removing existing autostart (%s).", existing)
                print(f"Portable mode: removing existing autostart ({existing}).")
                remove_autostart()
        else:
            slog.info("Autostart registration skipped (%s).",
                      "--connect client" if explicit_connect else "--no-autostart daemon")
    else:
        # Registering autostart shells out to PowerShell on Windows (slow cold
        # starts for the scheduled task + Start-menu shortcut) and nothing in
        # startup depends on it completing — run it on a background thread so it
        # never delays the tray appearing. Qt-free, so it's safe off-thread.
        import threading as _threading

        def _register_autostart():
            try:
                method = setup_autostart_for_app(__file__, sys.argv[1:])
                slog.info("Autostart registration: %s", method)
            except Exception:
                slog.exception("Autostart registration failed")

        _threading.Thread(target=_register_autostart, name="autostart-register",
                          daemon=True).start()

    # Single-instance lock: the control socket is the lock. Guards both the
    # GUI and headless paths — if a PolyHost already serves the socket, defer
    # to it instead of fighting over the HID device; otherwise clear any stale
    # socket and become the host. Forwarder mode (--host) has no device and no
    # socket, client mode (--connect) WANTS the existing instance, and the
    # daemon-by-default block above already resolved the endpoint, so all are
    # excluded here.
    if not (args.host or args.host_file or client_mode or daemon_handled_instance):
        from polyhost.server.instance import (
            probe_existing, clear_stale_endpoint, LIVE, STALE)
        outcome = probe_existing()
        slog.info("Single-instance lock: control-endpoint probe=%s", outcome)
        if outcome == LIVE:
            slog.warning("Another PolyKybdHost already serves the control socket; exiting.")
            print("PolyKybdHost is already running (control socket answered). Exiting.")
            sys.exit(0)
        if outcome != STALE:
            # INCOMPATIBLE / AUTH_MISMATCH: a real process owns the endpoint but
            # we can't speak to it. Don't unlink its socket and fight over the
            # HID device — defer and let the user sort out the version/key.
            slog.warning("Control endpoint in use (%s) but not answering compatibly; exiting.",
                         outcome)
            print(f"PolyKybdHost control endpoint is in use ({outcome}) but not "
                  "answering compatibly. Exiting rather than starting a second "
                  "host. Restart the running instance if this is unexpected.")
            sys.exit(0)
        clear_stale_endpoint()

    if args.headless:
        # No Qt in this process — import nothing Qt-dependent.
        slog.info("Launch path: headless daemon (no Qt).")
        print("Executing PolyHost (headless)...")
        from polyhost.headless import run_headless
        from polyhost.util.log_util import DEBUG_DETAILED  # Qt-free
        # Mirror the GUI's level mapping: --debug 2 drops to DEBUG_DETAILED so the
        # daemon surfaces debug_detailed lines (e.g. window-report receipts);
        # --debug 1 = DEBUG, no flag = INFO.
        if args.debug > 1:
            hl_level = DEBUG_DETAILED
        elif args.debug > 0:
            hl_level = logging.DEBUG
        else:
            hl_level = logging.INFO
        run_headless(hl_level, ignore_version=args.ignore_version)
        sys.exit(0)

    # GUI / forwarder paths: import Qt lazily, only here.
    from PyQt5.QtWidgets import QApplication
    # Important for XWayland icon matching
    if sys.platform.startswith('linux'):
        QApplication.setDesktopFileName('PolyHost')
        # On KDE, route native file dialogs through xdg-desktop-portal so the
        # picker is the modern Plasma dialog (our pip Qt has no KDE plugin).
        # Must run before the QApplication instance below reads the env.
        from polyhost.gui import file_dialogs
        file_dialogs.maybe_set_portal_platformtheme()

    if args.host or args.host_file:
        from polyhost.forwarder import PolyForwarder
        addr = args.host or f"IP set in {args.host_file}"
        slog.info("Launch path: forwarder -> %s", addr)
        print(f"Executing Forwarder. Sending to {addr}.")
        app = PolyForwarder(logging.DEBUG if args.debug>0 else logging.INFO, args.host, args.host_file,
                            report_rpc=args.report_rpc, report_port=args.report_port,
                            report_authkey_file=args.report_authkey_file)
    else:
        from polyhost.host import PolyHost
        # Spawn the deferred daemon now — AFTER the heavy GUI imports above, so
        # its cold import doesn't slow the tray's appearance. On spawn failure
        # fall back to owning the device in-process (mirrors the old behavior).
        if pending_daemon_spawn is not None:
            from polyhost.server import daemon_launch as dl
            spawned = dl.spawn_headless_daemon(extra_args=pending_daemon_spawn, log=slog)
            if spawned is not None:
                slog.info("Core daemon (pid %s) spawned; attaching as a client "
                          "(connecting in the background).", getattr(spawned, "pid", "?"))
                print("Core daemon starting; the tray will connect as soon as it's up.")
            else:
                slog.warning("Could not spawn the core daemon; running in-process instead.")
                print("Could not start the core daemon; running in-process instead.")
                # Re-probe before unlinking: the endpoint was last probed well
                # before this deferred spawn attempt, and another process could
                # have bound it meanwhile — only clear it if it's still stale.
                from polyhost.server.instance import probe_existing, clear_stale_endpoint, STALE
                if probe_existing() == STALE:
                    clear_stale_endpoint()
                client_mode, defer_connect = False, False
        if client_mode:
            slog.info("Launch path: GUI as client of a running core (endpoint=%s).",
                      endpoint or "default")
            print("Executing PolyHost (client of a running core)...")
        else:
            slog.info("Launch path: GUI owning the device in-process.")
            print("Executing PolyHost...")
        try:
            app = PolyHost(logging.DEBUG if args.debug>0 else logging.INFO, args.debug,
                           ignore_version=args.ignore_version,
                           client_mode=client_mode, endpoint=endpoint,
                           connect_retry=defer_connect)
        except Exception:
            # PolyHost configures its own host_log.txt; if it dies during
            # construction (e.g. the client can't reach the daemon) that file may
            # never be written, so record it in the startup log too.
            slog.exception("PolyHost construction failed")
            raise

    slog.info("Handoff complete; entering the Qt event loop.")
    rc = app.exec_()
    # A self-update that lands mid-session asks for a re-exec into the freshly
    # installed version. Do it here — after the event loop has fully unwound —
    # rather than calling os.execv from inside a Qt slot with the tray/timer
    # still live (the forwarder used to, and a transient execv failure then
    # left it dead with no relaunch). This mirrors the headless daemon, which
    # re-execs only after its run loop ends. `restart_app()` re-execs (or, on
    # failure, spawns a detached child) and never returns.
    if getattr(app, "wants_restart", False):
        from polyhost.services.updater import restart_app
        del app  # let the QApplication release its X/tray/D-Bus resources first
        restart_app()
    sys.exit(rc)


def _spawned_daemon_flags(args):
    """Flags to pass to a GUI-spawned headless daemon.

    Propagates the operational flags (--debug / --ignore-version) and adds
    --no-autostart so the daemon never registers or removes the GUI's autostart
    entry (the GUI owns the autostart lifecycle in daemon mode)."""
    flags = ["--no-autostart"]
    if args.debug:
        flags += ["--debug", str(args.debug)]
    if args.ignore_version:
        flags.append("--ignore-version")
    return flags
