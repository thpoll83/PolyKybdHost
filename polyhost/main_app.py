import argparse
import logging
import sys

# NOTE: Qt (PyQt5) and the Qt-dependent classes (PolyHost / PolyForwarder)
# are imported LAZILY inside the GUI branch of main() so that
# `--headless` runs in a process that never imports Qt (M2). Keep the
# top level Qt-free — guarded by tests/headless/headless_entry_test.py.
from polyhost.services.add_to_startup import setup_autostart_for_app, remove_autostart, get_autostart_status

def main():
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
    is_plain_gui = not (args.headless or explicit_connect or args.host or args.host_file)
    if is_plain_gui:
        if args.daemon is None:
            from polyhost.settings import PolySettings  # Qt-free
            daemon_mode = bool(PolySettings().get("daemon_mode"))
        else:
            daemon_mode = args.daemon
        if daemon_mode:
            from polyhost.server import daemon_launch as dl
            from polyhost.server.instance import probe_existing, clear_stale_endpoint
            action = dl.decide_startup_mode(probe_existing(), True)
            if action == dl.DEFER:
                print("PolyKybdHost control endpoint is in use but not answering "
                      "compatibly. Exiting rather than starting a second host. "
                      "Restart the running instance if this is unexpected.")
                sys.exit(0)
            elif action == dl.CLIENT:
                print("Attaching to the running PolyKybdHost core (daemon mode).")
                client_mode, endpoint, daemon_handled_instance = True, None, True
            elif action == dl.SPAWN_CLIENT:
                print("Starting the PolyKybdHost core daemon...")
                spawned = dl.spawn_headless_daemon(
                    extra_args=_spawned_daemon_flags(args),
                    log=logging.getLogger("PolyHost"))
                if spawned is not None and dl.wait_until_live():
                    print("Core daemon is up; attaching as a client.")
                    client_mode, endpoint, daemon_handled_instance = True, None, True
                else:
                    print("Core daemon did not come up; running in-process instead.")
                    if spawned is not None:
                        try:
                            spawned.terminate()
                        except Exception:
                            pass
                    clear_stale_endpoint()
                    daemon_handled_instance = True  # socket already resolved here

    # Autostart: a portable run removes any existing entry; an explicit --connect
    # client and the GUI-spawned daemon (--no-autostart) leave autostart alone;
    # everything else (incl. a daemon-mode GUI, which still autostarts and brings
    # the daemon up) registers. The daemon's lifecycle is owned by the GUI, so
    # the daemon must NOT register its own autostart entry.
    if args.portable or explicit_connect or args.no_autostart:
        if args.portable:
            existing = get_autostart_status()
            if existing != "none":
                print(f"Portable mode: removing existing autostart ({existing}).")
                remove_autostart()
    else:
        setup_autostart_for_app(__file__, sys.argv[1:])

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
        if outcome == LIVE:
            print("PolyKybdHost is already running (control socket answered). Exiting.")
            sys.exit(0)
        if outcome != STALE:
            # INCOMPATIBLE / AUTH_MISMATCH: a real process owns the endpoint but
            # we can't speak to it. Don't unlink its socket and fight over the
            # HID device — defer and let the user sort out the version/key.
            print(f"PolyKybdHost control endpoint is in use ({outcome}) but not "
                  "answering compatibly. Exiting rather than starting a second "
                  "host. Restart the running instance if this is unexpected.")
            sys.exit(0)
        clear_stale_endpoint()

    if args.headless:
        # No Qt in this process — import nothing Qt-dependent.
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

    if args.host or args.host_file:
        from polyhost.forwarder import PolyForwarder
        addr = args.host or f"IP set in {args.host_file}"
        print(f"Executing Forwarder. Sending to {addr}.")
        app = PolyForwarder(logging.DEBUG if args.debug>0 else logging.INFO, args.host, args.host_file,
                            report_rpc=args.report_rpc, report_port=args.report_port,
                            report_authkey_file=args.report_authkey_file)
    else:
        from polyhost.host import PolyHost
        if client_mode:
            print("Executing PolyHost (client of a running core)...")
        else:
            print("Executing PolyHost...")
        app = PolyHost(logging.DEBUG if args.debug>0 else logging.INFO, args.debug,
                       ignore_version=args.ignore_version,
                       client_mode=client_mode, endpoint=endpoint)

    sys.exit(app.exec_())


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
