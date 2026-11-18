"""Refuse a Worker deploy while the live D1 table lacks a column the Worker writes.

The Worker's INSERT names every column. Deployed before the matching ALTER, it
fails every ping with a 503, and that day's data is lost (pings are daily and
never retried). Schema changes stay manual (schema.sql, SETUP.md); this check
only stops the deploy until they are done.

Usage, from telemetry-collector/:
    npx wrangler d1 execute polyhost-telemetry --remote --json \\
        --command "PRAGMA table_info(ping)" > cols.json
    python3 check_schema.py src/index.js cols.json
Exit 0 when every INSERT column exists, 1 (and the missing names) otherwise.
"""
import re
import sys
from pathlib import Path

from dashboard import parse_wrangler_json


def insert_columns(worker_source: str) -> list[str]:
    """The column list of the Worker's `INSERT OR IGNORE INTO ping (...)`."""
    m = re.search(r"INSERT OR IGNORE INTO ping \((.*?)\) VALUES", worker_source, re.S)
    if not m:
        raise ValueError("INSERT statement not found in the Worker source")
    return [c.strip() for c in m.group(1).split(",") if c.strip()]


def table_columns(wrangler_output: str) -> set[str]:
    """Column names from `PRAGMA table_info(ping)` run through wrangler --json."""
    return {str(r["name"]) for r in parse_wrangler_json(wrangler_output) if "name" in r}


def missing_columns(worker_source: str, wrangler_output: str) -> list[str]:
    have = table_columns(wrangler_output)
    if not have:
        # An empty result means no table (or the local database): never pass that.
        raise ValueError("the table has no columns: is the ping table there, "
                         "and did the query use --remote?")
    return [c for c in insert_columns(worker_source) if c not in have]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    worker, cols = (Path(a).read_text(encoding="utf-8") for a in argv)
    try:
        missing = missing_columns(worker, cols)
    except ValueError as exc:
        print(f"::error::schema check failed: {exc}")
        return 1
    if missing:
        print("::error::the live ping table lacks columns the Worker writes: "
              + ", ".join(missing)
              + ". Apply the ALTER statements in schema.sql (with --remote), then re-run.")
        return 1
    print("schema check OK: every column the Worker writes exists")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
