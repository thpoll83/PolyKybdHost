"""Tests for the anonymous usage census (polyhost/services/telemetry.py).

The privacy-relevant assertions are `test_payload_*`: they pin the payload to a
frozen key set, so any future field has to be added deliberately in two places
(the builder and PAYLOAD_KEYS) rather than sliding in because someone added a
key to PolyCore.get_status().
"""
import json
import logging
import unittest
from unittest import mock

from polyhost.services import telemetry


class _FakeClock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


# A get_status()-shaped snapshot that also carries keys the payload must NOT
# leak — the sensitive ones the host genuinely has access to.
STATUS = {
    "connected": True,
    "device_present": True,
    "paused": False,
    "name": "PolyKybd Split72",
    "fw_version": "0.11.4",
    "protocol": 12,
    "hw_version": "1.0",
    "current_lang": "de-DE",
    "capabilities": {"idle_style": True},
    "host_version": "0.11.5",
    # things that must never be sent, if they ever appear in a snapshot:
    "window_title": "Passwords.kdbx - KeePass",
    "app_name": "keepass.exe",
    "latitude": 48.13,
}

FONTPACK = {"symbol": 5, "emoji": 1}


class BuildPayloadTest(unittest.TestCase):
    def test_payload_only_contains_allow_listed_keys(self):
        p = telemetry.build_payload("abc", "daemon", STATUS, FONTPACK, None)
        self.assertEqual(set(p), set(telemetry.PAYLOAD_KEYS))
        self.assertEqual(set(p["device"]), set(telemetry.DEVICE_KEYS))

    def test_payload_never_leaks_sensitive_snapshot_fields(self):
        p = telemetry.build_payload("abc", "daemon", STATUS, FONTPACK, None)
        blob = json.dumps(p)
        for secret in ("Passwords.kdbx", "keepass.exe", "48.13", "KeePass"):
            self.assertNotIn(secret, blob)

    def test_payload_carries_the_versions_we_actually_want(self):
        p = telemetry.build_payload("abc", "daemon", STATUS, FONTPACK, None)
        self.assertEqual(p["schema"], telemetry.PAYLOAD_SCHEMA)
        self.assertEqual(p["install_id"], "abc")
        self.assertEqual(p["mode"], "daemon")
        self.assertEqual(p["device"]["fw_version"], "0.11.4")
        self.assertEqual(p["device"]["protocol"], 12)
        self.assertEqual(p["device"]["fontpack"], {"symbol": 5, "emoji": 1})
        self.assertTrue(p["host_version"])
        self.assertIsInstance(p["host_protocol"], int)

    def test_payload_survives_an_empty_snapshot(self):
        p = telemetry.build_payload("abc", "in-process")
        self.assertEqual(set(p), set(telemetry.PAYLOAD_KEYS))
        self.assertFalse(p["device"]["present"])
        self.assertEqual(p["device"]["fw_version"], "")
        self.assertIsNone(p["device"]["protocol"])

    def test_counters_are_zero_filled_and_allow_listed(self):
        p = telemetry.build_payload("abc", "daemon", STATUS, FONTPACK,
                                    {"connects": 3, "not_a_counter": 9})
        self.assertEqual(p["counters"]["connects"], 3)
        self.assertNotIn("not_a_counter", p["counters"])
        self.assertEqual(set(p["counters"]), set(telemetry.COUNTER_KEYS))

    def test_payload_is_json_serialisable(self):
        json.dumps(telemetry.build_payload("abc", "daemon", STATUS, FONTPACK, None))

    def test_install_id_is_random_and_not_machine_derived(self):
        ids = {telemetry.new_install_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)
        self.assertTrue(all(len(i) == 32 for i in ids))


class DecideShouldSendTest(unittest.TestCase):
    NOW = 1_000_000.0

    def test_disabled_never_sends(self):
        self.assertFalse(telemetry.decide_should_send(
            False, "https://x/", self.NOW, 0))

    def test_no_endpoint_never_sends(self):
        self.assertFalse(telemetry.decide_should_send(True, "", self.NOW, 0))

    def test_first_run_sends(self):
        self.assertTrue(telemetry.decide_should_send(
            True, "https://x/", self.NOW, 0))

    def test_within_the_interval_does_not_send(self):
        self.assertFalse(telemetry.decide_should_send(
            True, "https://x/", self.NOW, self.NOW - 3600))

    def test_after_the_interval_sends(self):
        self.assertTrue(telemetry.decide_should_send(
            True, "https://x/", self.NOW, self.NOW - telemetry.SEND_INTERVAL_S))

    def test_a_future_last_sent_sends_rather_than_locking_out(self):
        # Clock moved backwards / corrupt cache: must not silence the install.
        self.assertTrue(telemetry.decide_should_send(
            True, "https://x/", self.NOW, self.NOW + 99999))

    def test_garbage_last_sent_sends(self):
        for junk in ("nope", None, float("nan"), float("inf"), -5):
            self.assertTrue(telemetry.decide_should_send(
                True, "https://x/", self.NOW, junk), junk)


class ReporterTest(unittest.TestCase):
    def setUp(self):
        self.clock = _FakeClock()
        self.posted = []
        self.enabled = True
        self.endpoint = "https://example.invalid/v1/ping"
        # Keep the persisted throttle out of the user's real cache dir.
        self.last_sent = 0.0
        patches = [
            mock.patch.object(telemetry, "get_last_sent",
                              side_effect=lambda: self.last_sent),
            mock.patch.object(telemetry, "set_last_sent",
                              side_effect=self._set_last_sent),
            mock.patch.object(telemetry, "get_last_result", return_value=""),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _set_last_sent(self, ts, result=""):
        self.last_sent = ts

    def _reporter(self, post_ok=True, snapshot_fn=None):
        def post(endpoint, payload, timeout=None):
            self.posted.append((endpoint, payload))
            return (True, "HTTP 204") if post_ok else (False, "HTTP 500")

        return telemetry.TelemetryReporter(
            logging.getLogger("test"), "install-1",
            snapshot_fn=snapshot_fn or (lambda: (STATUS, FONTPACK)),
            enabled_fn=lambda: self.enabled,
            endpoint_fn=lambda: self.endpoint,
            mode="daemon", post_fn=post, clock=self.clock)

    def test_sends_when_due(self):
        r = self._reporter()
        sent, _ = r.maybe_send()
        self.assertTrue(sent)
        self.assertEqual(len(self.posted), 1)
        self.assertEqual(self.posted[0][0], self.endpoint)

    def test_does_not_send_twice_within_the_interval(self):
        r = self._reporter()
        r.maybe_send()
        r.maybe_send()
        self.assertEqual(len(self.posted), 1)

    def test_disabled_sends_nothing(self):
        self.enabled = False
        r = self._reporter()
        sent, _msg = r.maybe_send()
        self.assertFalse(sent)
        self.assertEqual(self.posted, [])

    def test_force_ignores_the_throttle_but_not_the_opt_out(self):
        r = self._reporter()
        r.maybe_send()
        r.maybe_send(force=True)
        self.assertEqual(len(self.posted), 2)
        self.enabled = False
        r.maybe_send(force=True)
        self.assertEqual(len(self.posted), 2)

    def test_no_endpoint_sends_nothing(self):
        self.endpoint = ""
        r = self._reporter()
        self.assertEqual(r.maybe_send(force=True)[0], False)
        self.assertEqual(self.posted, [])

    def test_counters_are_reset_after_a_successful_send(self):
        r = self._reporter()
        r.note("connects", 2)
        r.note("fw_flashes")
        r.maybe_send()
        self.assertEqual(self.posted[0][1]["counters"]["connects"], 2)
        r.maybe_send(force=True)
        self.assertEqual(self.posted[1][1]["counters"]["connects"], 0)

    def test_counters_survive_a_failed_send(self):
        r = self._reporter(post_ok=False)
        r.note("connects", 2)
        r.maybe_send()
        r.note("connects")
        r.maybe_send(force=True)
        self.assertEqual(self.posted[1][1]["counters"]["connects"], 3)

    def test_unknown_counter_is_ignored(self):
        r = self._reporter()
        r.note("window_titles", 5)
        r.maybe_send()
        self.assertNotIn("window_titles", self.posted[0][1]["counters"])

    def test_a_broken_snapshot_still_sends_a_valid_payload(self):
        def boom():
            raise RuntimeError("device gone")

        r = self._reporter(snapshot_fn=boom)
        sent, _ = r.maybe_send()
        self.assertTrue(sent)
        self.assertEqual(set(self.posted[0][1]), set(telemetry.PAYLOAD_KEYS))

    def test_a_failing_endpoint_is_not_retried_every_tick(self):
        # A permanently dead endpoint must back off to the normal interval,
        # not hammer once per tick.
        r = self._reporter(post_ok=False)
        r.maybe_send()
        r.maybe_send()
        self.assertEqual(len(self.posted), 1)

    def test_status_reports_state_without_sending(self):
        r = self._reporter()
        st = r.status()
        self.assertTrue(st["enabled"])
        self.assertEqual(st["install_id"], "install-1")
        self.assertEqual(st["endpoint"], self.endpoint)
        self.assertEqual(self.posted, [])

    def test_preview_matches_what_would_be_sent(self):
        r = self._reporter()
        preview = r.preview()
        r.maybe_send()
        self.assertEqual(preview, self.posted[0][1])
        # ... and preview must not consume the counters.
        r2 = self._reporter()
        r2.note("connects")
        r2.preview()
        self.assertEqual(r2.status()["pending_counters"]["connects"], 1)


class PostTest(unittest.TestCase):
    def test_network_failure_is_swallowed(self):
        with mock.patch.object(telemetry.requests, "post",
                               side_effect=OSError("no route to host")):
            ok, msg = telemetry._post("https://example.invalid/", {})
        self.assertFalse(ok)
        self.assertIn("OSError", msg)

    def test_non_2xx_is_a_failure_not_an_exception(self):
        resp = mock.Mock(status_code=503)
        with mock.patch.object(telemetry.requests, "post", return_value=resp):
            ok, msg = telemetry._post("https://example.invalid/", {})
        self.assertFalse(ok)
        self.assertEqual(msg, "HTTP 503")


if __name__ == "__main__":
    unittest.main()
