"""Tests for the offline telemetry dashboard (telemetry-collector/dashboard.py).

Two things are actually worth pinning here:

  * the aggregations, because a dashboard that renders a *plausible* wrong
    number is worse than one that crashes — nobody double-checks a chart;
  * escaping, because `device_name` and friends come off the wire. The Worker
    truncates them but does not sanitise, so the only thing standing between a
    crafted ping and script in this file is `esc()`.

The module lives outside the package tree (it belongs beside the Worker it
queries, not in polyhost/), so it is loaded by path.
"""
import importlib.util
import os
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "telemetry-collector" / "dashboard.py"
_spec = importlib.util.spec_from_file_location("telemetry_dashboard", _PATH)
dash = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dash)


def row(install, day, **kw):
    base = {
        "install_id": install,
        "day": day,
        "received_at": f"{day}T10:00:00.000Z",
        "host_version": "0.11.10",
        "os": "Windows",
        "os_release": "11",
        "mode": "daemon",
        "country": "AT",
        "device_present": 1,
        "device_connected": 1,
        "device_name": "PolyKybd Split72",
        "fw_version": "0.11.4",
        "hw_version": "1.0",
        "fontpack": '{"symbol": 5}',
        "counters": '{"sessions": 1}',
    }
    base.update(kw)
    return base


class ParseWranglerJson(unittest.TestCase):
    def test_plain_list_of_result_objects(self):
        text = '[{"results":[{"install_id":"a"}],"success":true,"meta":{}}]'
        self.assertEqual(dash.parse_wrangler_json(text), [{"install_id": "a"}])

    def test_banner_before_the_json_is_skipped(self):
        text = '⛅️ wrangler 4.119.0\n---\n[{"results":[{"install_id":"a"}]}]\n'
        self.assertEqual(dash.parse_wrangler_json(text), [{"install_id": "a"}])

    def test_bare_object_shape(self):
        self.assertEqual(
            dash.parse_wrangler_json('{"results":[{"install_id":"a"}]}'),
            [{"install_id": "a"}],
        )

    def test_bare_list_of_row_objects(self):
        self.assertEqual(
            dash.parse_wrangler_json('[{"install_id":"a"}]'), [{"install_id": "a"}]
        )

    def test_empty_result_set(self):
        self.assertEqual(dash.parse_wrangler_json('[{"results":[]}]'), [])

    def test_envelope_without_results_is_not_mistaken_for_a_row(self):
        self.assertEqual(dash.parse_wrangler_json('[{"success":true,"meta":{}}]'), [])

    def test_no_json_at_all_raises_with_the_output_quoted(self):
        with self.assertRaises(ValueError) as cm:
            dash.parse_wrangler_json("Authentication error [code: 10000]")
        self.assertIn("Authentication error", str(cm.exception))

    def test_truncated_json_says_what_it_saw(self):
        # A bare JSONDecodeError reports a line/column into output the reader
        # never sees, which is a poor way to discover wrangler printed an error.
        with self.assertRaises(ValueError) as cm:
            dash.parse_wrangler_json('[{"results": [{"install_id"')
        self.assertIn("install_id", str(cm.exception))


class SplitCommand(unittest.TestCase):
    def test_plain_command(self):
        self.assertEqual(dash.split_command("npx wrangler"), ["npx", "wrangler"])

    def test_quoted_path_with_spaces_stays_one_token(self):
        self.assertEqual(
            dash.split_command('"/opt/Cloudflare Wrangler/wrangler" --x'),
            ["/opt/Cloudflare Wrangler/wrangler", "--x"],
        )

    @unittest.skipUnless(os.name == "nt", "Windows path semantics")
    def test_windows_backslashes_survive(self):
        # Plain shlex.split() in POSIX mode eats these, turning
        # C:\tools\wrangler.cmd into C:toolswrangler.cmd.
        self.assertEqual(
            dash.split_command(r'"C:\Program Files\nodejs\wrangler.cmd"'),
            [r"C:\Program Files\nodejs\wrangler.cmd"],
        )


class DayRange(unittest.TestCase):
    def test_includes_days_with_no_pings(self):
        rows = [row("a", "2026-08-01"), row("b", "2026-08-04")]
        self.assertEqual(
            dash.day_range(rows, 4),
            ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04"],
        )

    def test_window_shorter_than_the_data_trims_from_the_left(self):
        rows = [row("a", "2026-08-01"), row("b", "2026-08-04")]
        self.assertEqual(dash.day_range(rows, 2), ["2026-08-03", "2026-08-04"])

    def test_empty_and_malformed_are_empty(self):
        self.assertEqual(dash.day_range([], 30), [])
        self.assertEqual(dash.day_range([row("a", "not-a-date")], 30), [])

    def test_non_positive_days_is_a_single_day(self):
        rows = [row("a", "2026-08-01"), row("b", "2026-08-04")]
        self.assertEqual(dash.day_range(rows, 0), ["2026-08-04"])
        self.assertEqual(dash.day_range(rows, -5), ["2026-08-04"])


class DaysArgument(unittest.TestCase):
    def test_rejects_zero_and_negative(self):
        # day_range clamps defensively, but the subtitle prints what was passed
        # — "window: last 0 days" over a one-day chart.
        for bad in ("0", "-5"):
            with self.assertRaises(SystemExit):
                dash.main(["--from-json", os.devnull, "--days", bad])

    def test_accepts_a_positive_window(self):
        self.assertEqual(dash._positive_days("90"), 90)


class Aggregations(unittest.TestCase):
    def test_daily_installs_counts_distinct_installs(self):
        rows = [
            row("a", "2026-08-01"),
            row("b", "2026-08-01"),
            row("a", "2026-08-02"),
        ]
        window = ["2026-08-01", "2026-08-02"]
        self.assertEqual(dash.daily_installs(rows, window), [("2026-08-01", 2), ("2026-08-02", 1)])

    def test_daily_counter_sums_across_installs_and_zero_fills(self):
        rows = [
            row("a", "2026-08-01", counters='{"sessions": 2}'),
            row("b", "2026-08-01", counters='{"sessions": 3}'),
        ]
        window = ["2026-08-01", "2026-08-02"]
        self.assertEqual(
            dash.daily_counter(rows, "sessions", window),
            [("2026-08-01", 5), ("2026-08-02", 0)],
        )

    def test_counter_blob_junk_does_not_blow_up(self):
        rows = [
            row("a", "2026-08-01", counters="not json"),
            row("b", "2026-08-01", counters=None),
            row("c", "2026-08-01", counters='{"sessions": "lots"}'),
            row("d", "2026-08-01", counters='{"sessions": 4}'),
        ]
        self.assertEqual(dash.daily_counter(rows, "sessions", ["2026-08-01"]), [("2026-08-01", 4)])

    def test_latest_per_install_keeps_the_newest_row(self):
        rows = [
            row("a", "2026-08-01", host_version="0.11.9"),
            row("a", "2026-08-05", host_version="0.11.10"),
            row("b", "2026-08-02", host_version="0.11.8"),
        ]
        latest = dash.latest_per_install(rows)
        self.assertEqual([r["install_id"] for r in latest], ["a", "b"])
        self.assertEqual(latest[0]["host_version"], "0.11.10")

    def test_version_breakdown_is_per_install_not_per_report(self):
        # One long-running install must not outvote a newer one just by having
        # reported more often — that is the whole point of latest_per_install.
        rows = [row("a", f"2026-08-0{d}", host_version="0.11.9") for d in range(1, 6)]
        rows.append(row("b", "2026-08-05", host_version="0.11.10"))
        counts = dict(dash.breakdown(dash.latest_per_install(rows), "host_version"))
        self.assertEqual(counts, {"0.11.9": 1, "0.11.10": 1})

    def test_breakdown_labels_missing_values(self):
        rows = [row("a", "2026-08-01", country=None), row("b", "2026-08-01", country="")]
        self.assertEqual(dash.breakdown(rows, "country"), [("(none)", 2)])

    def test_fw_breakdown_ignores_installs_with_no_keyboard(self):
        rows = [
            row("a", "2026-08-01"),
            row("b", "2026-08-01", device_present=0, fw_version=""),
            row("c", "2026-08-01", device_present=1, fw_version=""),
        ]
        self.assertEqual(dash.fw_breakdown(rows), [("0.11.4", 1)])

    def test_counter_totals_lists_every_known_counter(self):
        totals = dash.counter_totals([row("a", "2026-08-01", counters='{"sessions": 2}')])
        self.assertEqual([k for k, _, _ in totals], [k for k, _ in dash.COUNTERS])
        self.assertEqual(dict((k, n) for k, _, n in totals)["sessions"], 2)
        self.assertEqual(dict((k, n) for k, _, n in totals)["fw_flashes"], 0)

    def test_fontpack_versions_sort_numerically_not_lexicographically(self):
        # content_version is an integer and symbol is already at 5, so a string
        # sort would file v10 before v2 exactly when the split starts mattering.
        rows = [
            row("a", "2026-08-01", fontpack='{"symbol": 10}'),
            row("b", "2026-08-01", fontpack='{"symbol": 2}'),
            row("c", "2026-08-01", fontpack='{"symbol": 9}'),
        ]
        self.assertEqual(dict(dash.fontpack_summary(rows))["symbol"], "v2 ×1, v9 ×1, v10 ×1")

    def test_fontpack_summary_shows_a_split_across_installs(self):
        rows = [
            row("a", "2026-08-01", fontpack='{"symbol": 5, "emoji": 1}'),
            row("b", "2026-08-01", fontpack='{"symbol": 4}'),
        ]
        summary = dict(dash.fontpack_summary(rows))
        self.assertEqual(summary["emoji"], "v1 ×1")
        self.assertIn("v4 ×1", summary["symbol"])
        self.assertIn("v5 ×1", summary["symbol"])


class Render(unittest.TestCase):
    def test_empty_dataset_renders_rather_than_dividing_by_zero(self):
        # This is the state the dashboard is in on day one, so it has to be the
        # case that works, not the one nobody tried.
        out = dash.render([], 30, "now")
        self.assertIn("<html", out)
        self.assertIn("No installs have reported yet.", out)

    def test_versions_appear_in_the_output(self):
        out = dash.render([row("a", "2026-08-01")], 30, "now")
        self.assertIn("0.11.10", out)
        self.assertIn("0.11.4", out)

    def test_client_supplied_strings_are_escaped(self):
        evil = '<script>alert(1)</script>'
        out = dash.render([row("a", "2026-08-01", device_name=evil, os=evil)], 30, "now")
        self.assertNotIn("<script>alert", out)
        self.assertIn("&lt;script&gt;", out)

    def test_install_table_keeps_the_full_id_in_a_tooltip(self):
        full = "d4e6321ebec1407dabbf5e83e5e2b445"
        out = dash.render([row(full, "2026-08-01")], 30, "now")
        self.assertIn(f'title="{full}"', out)
        self.assertIn("d4e6321ebec1…", out)

    def test_bars_are_emitted_for_a_day_with_data(self):
        out = dash.svg_bars([("2026-08-01", 3), ("2026-08-02", 0)])
        self.assertIn("<svg", out)
        self.assertIn("2026-08-01: 3", out)

    def test_bars_on_an_empty_window_say_so(self):
        self.assertIn("No data", dash.svg_bars([]))


if __name__ == "__main__":
    unittest.main()
