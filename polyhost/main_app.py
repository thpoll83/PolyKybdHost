
import argparse
import logging
import sys

from polyhost.forwarder import PolyForwarder
from polyhost.host import PolyHost
from polyhost.services.add_to_startup import setup_autostart_for_app

def main():
    parser = argparse.ArgumentParser(
                    prog='PolyHost',
                    usage='%(prog)s [options]',
                    description='Communication with your PolyKybd')
    parser.add_argument('--autorun', default=False, action='store_true',
                        help='Add an autorun entry to your system')
    parser.add_argument('--debug', default=False, action='store_true', help='Include debug level messages to the log file')
    parser.add_argument('--host', help='Specify a host where the PolyKybd is physically connected to')
    args=parser.parse_args()

    if args.autorun:
        argv = [arg for arg in sys.argv[1:] if arg != '--autorun']
        setup_autostart_for_app(__file__, argv)

    if args.host:
        print(f"Executing Forwarder. Sending to {args.host}")
        app = PolyForwarder(logging.DEBUG if args.debug else logging.INFO, args.host)
    else:
        print("Executing PolyHost...")
        app = PolyHost(logging.DEBUG if args.debug else logging.INFO)
        
    sys.exit(app.exec_())
    