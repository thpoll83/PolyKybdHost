"""polyctl rgb | uptime | matrix (firmware v39+)."""
import unittest

from polyhost.server import protocol
from tests.cli.polyctl_test import run_main

STATE = {"enabled": True, "effect": 3, "brightness": 51, "speed": 128, "hue": 10, "sat": 255}


class RgbCliTest(unittest.TestCase):
    def test_status_reads_only(self):
        rc, out, _, server = run_main(["rgb"], {protocol.M_RGB_MATRIX_GET: STATE})
        self.assertEqual(rc, 0)
        self.assertNotIn(protocol.M_RGB_MATRIX_SET, [m for m, _ in server.received])
        self.assertIn("rgb:         on", out)
        self.assertIn("effect:      3", out)

    def test_off_sends_enabled_false(self):
        rc, _, _, server = run_main(["rgb", "off"], {protocol.M_RGB_MATRIX_SET: "ok",
                                                     protocol.M_RGB_MATRIX_GET: STATE})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_RGB_MATRIX_SET], {"enabled": False})

    def test_set_sends_only_the_given_values(self):
        rc, _, _, server = run_main(["rgb", "set", "--brightness", "200", "--hue", "5", "--sat", "9"],
                                    {protocol.M_RGB_MATRIX_SET: "ok", protocol.M_RGB_MATRIX_GET: STATE})
        self.assertEqual(rc, 0)
        self.assertEqual(dict(server.received)[protocol.M_RGB_MATRIX_SET],
                         {"brightness": 200, "hue": 5, "sat": 9})

    def test_set_without_values_is_an_error(self):
        rc, _, err, server = run_main(["rgb", "set"], {})
        self.assertEqual(rc, 2)
        self.assertNotIn(protocol.M_RGB_MATRIX_SET, [m for m, _ in server.received])

    def test_indicate(self):
        rc, out, _, server = run_main(["rgb", "indicate"], {protocol.M_INDICATE: "ok"})
        self.assertEqual(rc, 0)
        self.assertIn(protocol.M_INDICATE, [m for m, _ in server.received])

    def test_uptime(self):
        rc, out, _, _ = run_main(["uptime"], {protocol.M_UPTIME_GET: 3723004})
        self.assertEqual(rc, 0)
        self.assertIn("uptime: 1:02:03 (3723004 ms)", out)

    def test_matrix_prints_column_0_first(self):
        rc, out, _, _ = run_main(["matrix"], {protocol.M_SWITCH_MATRIX_GET: [0, 0x05]})
        self.assertEqual(rc, 0)
        self.assertIn("row  0: ........", out)
        self.assertIn("row  1: x.x.....", out)


if __name__ == "__main__":
    unittest.main()
