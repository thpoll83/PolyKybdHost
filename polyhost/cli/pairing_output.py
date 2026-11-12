"""Prints the forwarder pairing code for `polyctl forwarder pairing-code`.

The code is the window-report key (services/forwarder_pairing.py): showing it to
the user who pairs a forwarder is the command's purpose (security audit HOST-6).
It is printed here, in a file of its own, so the CodeQL workflow can drop
py/clear-text-logging-sensitive-data for this file alone and still check the rest
of polyctl. Print nothing else secret from this file.
"""
import sys


def print_pairing_code(code: str) -> None:
    """The code on stdout, the instructions on stderr."""
    print(code)
    print("Enter it on the forwarder's computer: polyctl forwarder pair <code>, or the "
          "forwarder's tray menu. Anyone with it can send reports to this computer.",
          file=sys.stderr)
