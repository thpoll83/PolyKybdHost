"""A stand-in keyboard for core tests that checks every call against `PolyKybd`.

A plain MagicMock accepts any method name and any arguments, so a core test
stays green after a `PolyKybd` method is renamed or changes its signature
(#299 was that drift in the mock keyboard). `create_autospec` refuses a name
the class does not have and a call its signature would reject.
"""
from unittest import mock

from polyhost.device.poly_kybd import PolyKybd


def spec_keyboard():
    keeb = mock.create_autospec(PolyKybd, instance=True)
    # Set in PolyKybd.__init__, so the class-based spec does not know it.
    keeb.hid = mock.MagicMock()
    return keeb
