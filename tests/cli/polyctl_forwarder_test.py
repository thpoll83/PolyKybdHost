"""`polyctl forwarder pairing-code` prints the code on stdout and nothing else there."""
import contextlib
import io
import types
import unittest
import unittest.mock as mock

from polyhost.cli import polyctl


class PairingCodeTest(unittest.TestCase):
    def test_code_on_stdout_instructions_on_stderr(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("polyhost.services.forwarder_pairing.pairing_code",
                        return_value="aaaaaaaa-bbbbbbbb"), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = polyctl._cmd_forwarder(None, types.SimpleNamespace(forwarder_cmd="pairing-code"))
        self.assertEqual(rc, 0)
        self.assertEqual(out.getvalue(), "aaaaaaaa-bbbbbbbb\n")
        self.assertIn("polyctl forwarder pair", err.getvalue())


if __name__ == "__main__":
    unittest.main()
