
import argparse
import logging
import os
import sys

from polyhost.PolyForwarder import PolyForwarder
from polyhost.PolyHost import PolyHost

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(
                    prog='PolyHost',
                    usage='%(prog)s [options]',
                    description='Communication with your PolyKybd')
    parser.add_argument('--debug', default=False, action='store_true', help='Include debug level messages to the log file')
    parser.add_argument('--host', help='Specify a host where the PolyKybd is physically connected to')
    args=parser.parse_args()

    if args.host:
        print(f"Executing Forwarder. Sending to {args.host}")
        app = PolyForwarder(logging.DEBUG if args.debug else logging.INFO, args.host)
    else:
        print("Executing PolyHost...")
        app = PolyHost(logging.DEBUG if args.debug else logging.INFO)
        
    sys.exit(app.exec_())
    