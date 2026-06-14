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
    parser.add_argument('--host', help='Specify a host where the PolyKybd is physically connected to')
    parser.add_argument('--host-file', help='Path to a file containing the host IP, written by a session hook (see folder autorun_forwarder for examples). This option has higher priority than `--host`.')
    args=parser.parse_args()

    # Pillow logs every PNG chunk at DEBUG ("STREAM b'IDAT' …", "Importing
    # PngImagePlugin"); under --debug that floods the host log (and interleaves
    # with our lines) since overlay decode moved to Pillow. Cap the PIL logger
    # so our DEBUG output stays readable. Harmless when not debugging.
    logging.getLogger("PIL").setLevel(logging.INFO)

    # Client mode (--connect): the tray GUI attaches to an already-running core
    # over the control socket. It owns no device, so it neither registers
    # autostart (that's the daemon's job) nor takes the single-instance lock —
    # it connects to the existing instance rather than becoming one.
    client_mode = args.connect is not None

    if args.portable or client_mode:
        # Portable / client run: don't autostart, and remove any entry a
        # previous (non-portable) run may have left behind so nothing lingers.
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
    # socket, and client mode (--connect) WANTS the existing instance, so both
    # are excluded here.
    if not (args.host or args.host_file or client_mode):
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
        run_headless(logging.DEBUG if args.debug > 0 else logging.INFO,
                     ignore_version=args.ignore_version)
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
        app = PolyForwarder(logging.DEBUG if args.debug>0 else logging.INFO, args.host, args.host_file)
    else:
        from polyhost.host import PolyHost
        if client_mode:
            print("Executing PolyHost (client of a running core)...")
        else:
            print("Executing PolyHost...")
        app = PolyHost(logging.DEBUG if args.debug>0 else logging.INFO, args.debug,
                       ignore_version=args.ignore_version,
                       client_mode=client_mode, endpoint=args.connect or None)

    sys.exit(app.exec_())
