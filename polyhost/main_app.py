import argparse
import logging
import sys

from PyQt5.QtWidgets import QApplication

from polyhost.forwarder import PolyForwarder
from polyhost.host import PolyHost
from polyhost.services.add_to_startup import setup_autostart_for_app

def main():
    parser = argparse.ArgumentParser(
                    prog='PolyHost',
                    usage='%(prog)s [options]',
                    description='Communication with your PolyKybd')
    parser.add_argument('--portable', default=False, action='store_true',
                        help='Do not add an autorun entry to your system')
    parser.add_argument('--debug', type=int, default=0, choices=[0, 1, 2], help='Set debug level: 0 (no debug), 1 (basic debug), 2 (detailed debug)')
    parser.add_argument('--host', help='Specify a host where the PolyKybd is physically connected to')
    args=parser.parse_args()

    if not args.portable:
        setup_autostart_for_app(__file__, sys.argv[1:])

    # Important for XWayland icon matching
    if sys.platform.startswith('linux'):
        QApplication.setDesktopFileName('PolyHost')

    if args.host:
        print(f"Executing Forwarder. Sending to {args.host}")
        app = PolyForwarder(logging.DEBUG if args.debug>0 else logging.INFO, args.host)
    else:
        print("Executing PolyHost...")
        app = PolyHost(logging.DEBUG if args.debug>0 else logging.INFO, args.debug)

    sys.exit(app.exec_())
    