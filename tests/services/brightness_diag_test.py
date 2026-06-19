import unittest

from polyhost.settings import (
    BRIGHTNESS_ENVIRONMENT_PARAMS,
    DEFAULT_BRIGHTNESS_ENVIRONMENT,
    brightness_environment_params,
)
from polyhost.services.brightness_diag import device_value


class TestEnvironmentParams(unittest.TestCase):
    def test_window_is_no_damping(self):
        # The default 'window' preset must leave the curve untouched (k=1),
        # so it is bit-identical to the pre-environment behaviour.
        baseline, k = brightness_environment_params("window")
        self.assertEqual(k, 1.0)
        self.assertEqual(DEFAULT_BRIGHTNESS_ENVIRONMENT, "window")

    def test_unknown_key_falls_back_to_window(self):
        self.assertEqual(
            brightness_environment_params("does-not-exist"),
            BRIGHTNESS_ENVIRONMENT_PARAMS["window"],
        )

    def test_every_preset_still_dims_at_night(self):
        # The whole point of device-side damping is that even a flat indoor
        # preset keeps k>0, so darkness still pulls the value down below the
        # daytime value (users want less light at night, not a flat constant).
        for key, (baseline, k) in BRIGHTNESS_ENVIRONMENT_PARAMS.items():
            self.assertGreater(k, 0.0, key)
            night = device_value(0.0, env=(baseline, k))   # curve floor (2)
            noon = device_value(1.0, env=(baseline, k))     # curve full (50)
            self.assertLess(night, noon, f"{key} must dim at night")


class TestDeviceValueDamping(unittest.TestCase):
    def test_window_endpoints_match_legacy(self):
        # Legacy mapping was exactly 2..50 across the normalized 0..1 range.
        self.assertAlmostEqual(device_value(0.0, env=(2.0, 1.0)), 2.0)
        self.assertAlmostEqual(device_value(1.0, env=(2.0, 1.0)), 50.0)

    def test_damping_compresses_toward_baseline(self):
        # device = baseline + k*(curve - baseline); a half-strength preset
        # around baseline 20 halves the distance from 20 at both ends.
        env = (20.0, 0.5)
        self.assertAlmostEqual(device_value(0.0, env=env), 20.0 + 0.5 * (2.0 - 20.0))
        self.assertAlmostEqual(device_value(1.0, env=env), 20.0 + 0.5 * (50.0 - 20.0))

    def test_gamma_then_damping_order(self):
        # gamma shapes the curve first, then damping is applied to the result.
        n, gamma, env = 0.5, 2.0, (10.0, 0.5)
        curve = 2 + (n ** gamma) * 48
        self.assertAlmostEqual(
            device_value(n, gamma=gamma, env=env), 10.0 + 0.5 * (curve - 10.0)
        )


if __name__ == "__main__":
    unittest.main()
