"""Tests for the lightweight Sunlight helper (no pvlib/pandas/geocoder/pytz).

Pins the pure-math clear-sky fallback, the open-meteo online parse (with the
utc_offset_seconds-based local-hour match), the no-location fallback, and the
guarantee that importing the module stays free of the heavy scientific stack.
"""
import subprocess
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest import mock

from polyhost.services.sunlight_helper import Sunlight


def _sun(online=False, location=False):
    return Sunlight(location, online)


class ClearSkyModelTest(unittest.TestCase):
    def test_noon_equator_is_bright(self):
        s = _sun()
        s.latitude, s.longitude = 0.0, 0.0
        # lon=0 so solar noon is 12:00 UTC -> hour angle 0 -> sun near zenith.
        ghi = s._clearsky_ghi(datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc))
        self.assertGreater(ghi, 800.0)
        self.assertLess(ghi, 1098.0)      # Haurwitz can never exceed the prefactor

    def test_midnight_equator_is_zero(self):
        s = _sun()
        s.latitude, s.longitude = 0.0, 0.0
        # 00:00 UTC at lon 0 -> sun on the far side -> below horizon -> 0.
        self.assertEqual(s._clearsky_ghi(datetime(2026, 6, 21, 0, 0, tzinfo=timezone.utc)), 0.0)

    def test_longitude_shifts_solar_noon(self):
        s = _sun()
        s.latitude = 0.0
        # At lon +180 (UTC+12-ish solar offset) the bright hour is ~00:00 UTC.
        s.longitude = 180.0
        bright = s._clearsky_ghi(datetime(2026, 3, 21, 0, 0, tzinfo=timezone.utc))
        dark = s._clearsky_ghi(datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc))
        self.assertGreater(bright, dark)


class IrradianceFallbackTest(unittest.TestCase):
    def test_offline_known_location_uses_clearsky(self):
        s = _sun(online=False, location=False)
        s.location_known = True
        s.latitude, s.longitude = 0.0, 0.0
        with mock.patch.object(s, "_clearsky_ghi", return_value=123.4) as cs:
            self.assertEqual(s.get_irradiance_now(), 123.4)
        cs.assert_called_once()

    def test_no_location_uses_hour_of_day(self):
        s = _sun(online=False, location=False)
        s.location_known = False
        val = s.get_irradiance_now()
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_online_failure_falls_back_to_clearsky(self):
        s = _sun(online=True, location=False)
        s.location_known = True
        s.latitude, s.longitude = 0.0, 0.0
        with mock.patch.object(s, "_online_irradiance", return_value=None), \
             mock.patch.object(s, "_clearsky_ghi", return_value=42.0):
            self.assertEqual(s.get_irradiance_now(), 42.0)


class OnlineParseTest(unittest.TestCase):
    def test_matches_current_hour_via_utc_offset(self):
        s = _sun(online=True, location=False)
        s.location_known = True
        s.latitude, s.longitude = 52.0, 13.0
        # Build a response covering the current AND next location-local hour
        # (offset 0 -> local == UTC), so an hour-boundary crossing between this
        # snapshot and the code under test still finds a matching entry.
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        ts0 = now.strftime("%Y-%m-%dT%H:00")
        ts1 = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")
        fake = mock.Mock()
        fake.json.return_value = {
            "utc_offset_seconds": 0,
            "hourly": {"time": [ts0, ts1], "shortwave_radiation": [500.0, 500.0]},
        }
        with mock.patch("requests.get", return_value=fake) as get:
            self.assertEqual(s._online_irradiance(), 500.0)
        self.assertIn("open-meteo.com", get.call_args.args[0])

    def test_null_radiation_is_treated_as_zero(self):
        s = _sun(online=True, location=False)
        s.location_known = True
        s.latitude, s.longitude = 52.0, 13.0
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        ts0 = now.strftime("%Y-%m-%dT%H:00")
        ts1 = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00")
        fake = mock.Mock()
        fake.json.return_value = {
            "utc_offset_seconds": 0,
            "hourly": {"time": [ts0, ts1], "shortwave_radiation": [None, None]},
        }
        with mock.patch("requests.get", return_value=fake):
            self.assertEqual(s._online_irradiance(), 0.0)

    def test_network_error_returns_none(self):
        s = _sun(online=True, location=False)
        s.location_known = True
        s.latitude, s.longitude = 1.0, 2.0
        with mock.patch("requests.get", side_effect=OSError("down")):
            self.assertIsNone(s._online_irradiance())


class InitLocationTest(unittest.TestCase):
    def test_ip_api_success_sets_location(self):
        s = _sun(online=False, location=True)
        fake = mock.Mock()
        fake.json.return_value = {"status": "success", "lat": 52.5, "lon": 13.4,
                                  "timezone": "Europe/Berlin"}
        with mock.patch("requests.get", return_value=fake):
            s.init_location()
        self.assertTrue(s.location_known)
        self.assertAlmostEqual(s.latitude, 52.5)
        self.assertAlmostEqual(s.longitude, 13.4)

    def test_failure_leaves_location_unknown(self):
        s = _sun(online=False, location=True)
        with mock.patch("requests.get", side_effect=OSError("no net")):
            s.init_location()
        self.assertFalse(s.location_known)

    def test_disabled_lookup_does_no_request(self):
        s = _sun(online=False, location=False)
        with mock.patch("requests.get", side_effect=AssertionError("must not call")):
            s.init_location()
        self.assertFalse(s.location_known)


class ImportWeightTest(unittest.TestCase):
    def test_module_import_pulls_no_heavy_stack(self):
        # The whole point of the rewrite: importing sunlight_helper must not drag
        # in pvlib/pandas/scipy/geocoder/pytz. Check in a fresh subprocess.
        code = (
            "import sys\n"
            "import polyhost.services.sunlight_helper\n"
            "bad = [m for m in ('pvlib','pandas','scipy','geocoder','pytz') "
            "if m in sys.modules]\n"
            "assert not bad, bad\n"
            "print('OK')\n"
        )
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
