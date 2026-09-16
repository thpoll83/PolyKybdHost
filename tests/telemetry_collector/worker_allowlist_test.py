"""Cross-checks on the Worker's half of the allow-list (src/index.js).

There is no JS test runner in this repo, and these two invariants both fail
SILENTLY in production, which is the worst combination:

  * **Column / placeholder / bind alignment.** SQLite binds positionally. Add a
    column in the middle of the INSERT and forget the matching position in
    `.bind(...)` and every later value lands one column to the left — no error,
    no 503, just a table where `arch` holds a python version. Nothing downstream
    can detect it either, because every value is still a plausible string.

  * **Drift against the host's bucket tables.** `telemetry.py` maps a session /
    desktop to a known name and the Worker accepts only names it knows. Add one
    end and not the other and the field silently becomes '' for exactly the
    users you added it for — a zero where you would read "nobody runs that".

Parsed out of the JS as text on purpose: importing it would need a JS runtime,
and the thing being checked IS the source text.
"""
import re
import unittest
from pathlib import Path

from polyhost.services import telemetry

_SRC = (Path(__file__).resolve().parents[2]
        / "telemetry-collector" / "src" / "index.js").read_text(encoding="utf-8")


def _js_set(name):
    """The literal members of `const <name> = new Set([...])`."""
    m = re.search(rf"const {name} = new Set\(\[(.*?)\]\)", _SRC, re.S)
    assert m, f"{name} not found in index.js"
    return {v for v in re.findall(r"'([^']*)'", m.group(1))}


class InsertAlignment(unittest.TestCase):
    def _insert(self):
        m = re.search(r"INSERT OR IGNORE INTO ping \(\n(.*?)\n\) VALUES \((.*?)\)",
                      _SRC, re.S)
        self.assertIsNotNone(m, "INSERT statement not found")
        cols = [c.strip() for c in m.group(1).replace("\n", " ").split(",") if c.strip()]
        return cols, m.group(2).count("?")

    def _binds(self):
        m = re.search(r"\.bind\(\n(.*?)\n\s*\)\n\s*\.run\(\)", _SRC, re.S)
        self.assertIsNotNone(m, "bind() call not found")
        return [b.strip() for b in m.group(1).replace("\n", " ").split(",") if b.strip()]

    def test_counts_match(self):
        cols, holders = self._insert()
        self.assertEqual(len(cols), holders, "column count != placeholder count")
        self.assertEqual(len(cols), len(self._binds()),
                         "column count != bind-argument count")

    def test_each_bind_is_the_column_it_sits_under(self):
        cols, _ = self._insert()
        for col, arg in zip(cols, self._binds()):
            if col == "raw":          # the canonical row blob, not a field
                self.assertEqual(arg, "JSON.stringify(row)")
                continue
            self.assertEqual(arg, f"row.{col}",
                             f"column '{col}' is bound to '{arg}'")

    def test_the_new_linux_columns_are_actually_wired(self):
        cols, _ = self._insert()
        for col in ("session", "desktop", "window_backend"):
            self.assertIn(col, cols)


class HostWorkerParity(unittest.TestCase):
    def test_worker_accepts_every_session_the_host_can_send(self):
        sendable = set(telemetry._SESSIONS.values()) | {"other"}
        self.assertLessEqual(sendable, _js_set("SESSIONS"))

    def test_worker_accepts_every_desktop_the_host_can_send(self):
        sendable = set(telemetry._DESKTOPS.values()) | {"other"}
        self.assertLessEqual(sendable, _js_set("DESKTOPS"))

    def test_worker_accepts_every_backend_the_host_can_send(self):
        self.assertLessEqual(set(telemetry._WINDOW_BACKENDS),
                             _js_set("WINDOW_BACKENDS"))

    def test_the_bumped_schema_is_supported_and_the_old_one_still_is(self):
        # Hosts shipped before the bump keep pinging for months; dropping
        # schema 1 would silently zero the install count rather than error.
        m = re.search(r"SUPPORTED_SCHEMAS = new Set\(\[(.*?)\]\)", _SRC)
        supported = {int(v) for v in re.findall(r"\d+", m.group(1))}
        self.assertIn(telemetry.PAYLOAD_SCHEMA, supported)
        self.assertIn(1, supported)


if __name__ == "__main__":
    unittest.main()
