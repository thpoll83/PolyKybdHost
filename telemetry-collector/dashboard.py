#!/usr/bin/env python3
"""Render the telemetry dataset as a self-contained HTML dashboard.

Reads D1 through `wrangler d1 execute --json` and writes one HTML file with the
charts inlined. Deliberately NOT a service:

  * the Worker stays write-only. It has no read route, which is the reason
    there is no route that could leak the dataset — see SETUP.md §7. A hosted
    dashboard would be the first read path and would need a real credential;
    this needs none, because it borrows the wrangler login you already have.
  * the output is one file with no CDN, no fonts and no scripts, so it works
    offline, can be mailed to someone, and cannot phone home.

Usage:
    python dashboard.py                    # query the remote DB, write dashboard.html
    python dashboard.py --open             # ... and open it in a browser
    python dashboard.py --days 90          # widen the time-series window (default 30)
    python dashboard.py --days all         # ... or cover every day in the data
    python dashboard.py --local            # query the local dev DB instead
    python dashboard.py --from-json rows.json   # no wrangler; feed saved --json output
    python dashboard.py --from-json data/       # ... or a directory of them (*.json, recursive)
    python dashboard.py --export-days data/     # append each finished UTC day as
                                                # data/YYYY/YYYY-MM-DD.json, then render
                                                # from the whole directory
    python dashboard.py --out /tmp/t.html

Stdlib only, so it runs from a bare checkout on any OS.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shlex
import shutil
import subprocess
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DB_NAME = "polyhost-telemetry"
SELECT_ALL = "SELECT * FROM ping ORDER BY received_at"

# Keys that mark a `d1 execute --json` result envelope rather than a data row.
# No `ping` column is named any of these, so the two can't be confused.
ENVELOPE_KEYS = frozenset({"results", "success", "meta"})

# The counters the client ships, in the order they tell a story: how much the
# app ran, how well the keyboard stayed attached, what got flashed.
COUNTERS = [
    ("sessions", "App starts"),
    ("connects", "Keyboard connects"),
    ("reconnect_flaps", "Connection drops"),
    ("fw_flashes", "Firmware flashes"),
    ("fontpack_flashes", "Font-pack flashes"),
    ("update_installs", "Host updates"),
]


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def parse_wrangler_json(text: str) -> list[dict]:
    """Pull the result rows out of `wrangler d1 execute --json` output.

    Tolerant on purpose: wrangler has printed a banner above the JSON in some
    versions, and the shape has been both a bare object and a one-element list
    of {results, success, meta}. Anything that only accepted today's exact
    output would break on a wrangler upgrade with a confusing traceback.
    """
    start = min(
        (i for i in (text.find("["), text.find("{")) if i != -1),
        default=-1,
    )
    if start == -1:
        raise ValueError(f"no JSON found in wrangler output: {text[:200]!r}")
    try:
        doc = json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError as exc:
        # Quote from the START of the output, not from `start`: the bracket
        # scan above happily latches onto one inside a prose error message
        # ("Authentication error [code: 10000]"), and clipping to it hides the
        # very words that explain the failure. A bare JSONDecodeError is worse
        # still — a line and column into output the reader never sees.
        raise ValueError(
            f"could not parse wrangler output as JSON ({exc}): {text[:200]!r}"
        ) from exc

    if isinstance(doc, dict):
        doc = [doc]
    rows: list[dict] = []
    for part in doc:
        if isinstance(part, list):  # nested row list
            rows.extend(part)
        elif isinstance(part, dict):
            # Envelope or row? A result envelope is identified by its own
            # keys; anything else is a row. Testing `part.get("results")`
            # alone silently returned NOTHING for a bare row list — the shape
            # this docstring claims to support (caught by CodeRabbit on #154,
            # and by the regression test Sourcery asked for on the same PR).
            if ENVELOPE_KEYS & part.keys():
                rows.extend(part.get("results") or [])
            else:
                rows.append(part)
    return rows


def split_command(cmd: str) -> list[str]:
    """Tokenise the --wrangler string.

    ⚠️ Plain `shlex.split()` is WRONG on Windows: in POSIX mode a backslash is
    an escape character, so `C:\\tools\\wrangler.cmd` comes back as
    `C:toolswrangler.cmd`. Non-POSIX mode keeps backslashes but leaves the
    quotes attached to the token, which then fails `shutil.which()` — hence the
    strip. A plain `.split()` (what this replaced) is fine until someone points
    it at `C:\\Program Files\\...`, which on this platform is where things live.
    """
    if os.name == "nt":
        return [part.strip('"') for part in shlex.split(cmd, posix=False)]
    return shlex.split(cmd)


def fetch_rows(remote: bool, wrangler: str, sql: str = SELECT_ALL) -> list[dict]:
    # shell=False with an argv list: the string below is tokenised, never
    # interpreted by a shell, so there is no metacharacter to inject through.
    # It also comes from this process's own --wrangler argument, i.e. from
    # whoever is already running the command.
    parts = split_command(wrangler) + [
        "d1", "execute", DB_NAME,
        "--remote" if remote else "--local",
        "--json", "--command", sql,
    ]
    exe = shutil.which(parts[0])
    if exe is None:
        raise SystemExit(
            f"error: {parts[0]!r} not found on PATH.\n"
            "Install Node (which provides npx), or pass --wrangler to name the\n"
            "binary, or use --from-json to render a saved export instead."
        )
    parts[0] = exe

    # Say what is happening before blocking. npx resolves (and on a cold cache
    # downloads) wrangler before it runs anything, which takes 10-20s — during
    # which an unannounced wait looks like a hang, not a download.
    print(f"querying {'remote' if remote else 'local'} D1 via wrangler…", flush=True)
    # Audited and accepted (PolyKybdHost#154). This is an *audit* rule: it fires
    # on any non-literal argv and asks a human to check where the data came
    # from. It came from this process's own --wrangler argument, so whoever set
    # it is already running the command; there is no network, file or database
    # input on this path (the D1 rows are fetched BY this call). shell=False
    # with a list means no shell parses it, so there is nothing to inject
    # through — and shlex.quote, the rule's suggested remedy, escapes for a
    # SHELL string and would only corrupt an argv element here.
    #
    # ⚠️ The marker below must stay on the line IMMEDIATELY above the call —
    # semgrep only applies it to the next line, so putting it at the top of
    # this comment block (where it reads better) silently does nothing.
    # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
    proc = subprocess.run(
        parts, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
        raise SystemExit(f"error: wrangler exited {proc.returncode}")
    return parse_wrangler_json(proc.stdout)


def load_rows(path: Path) -> list[dict]:
    """Rows from one saved export, or from every *.json under a directory.

    A directory is what `--export-days` writes: one file per UTC day. Files
    are read in sorted path order, so the result does not depend on the
    order the file system lists them in.
    """
    if not path.is_dir():
        return parse_wrangler_json(path.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for file in sorted(path.rglob("*.json")):
        rows.extend(parse_wrangler_json(file.read_text(encoding="utf-8")))
    return rows


# --------------------------------------------------------------------------
# Daily export — one file per finished UTC day, for an archive kept in git
# --------------------------------------------------------------------------

def newest_export_day(directory: Path) -> date | None:
    """The newest day that already has a file under `directory`, or None.

    Only names that parse as YYYY-MM-DD count, so a stray file cannot move
    the start of the next export.
    """
    newest = None
    for file in directory.rglob("*.json"):
        try:
            day = date.fromisoformat(file.stem)
        except ValueError:
            continue
        if newest is None or day > newest:
            newest = day
    return newest


def export_query(after: date | None, before: date) -> str:
    """SELECT for the days strictly between `after` and `before`.

    Both bounds are `date` objects, so their isoformat() is digits and
    dashes only and is safe to put in the SQL text. Today (UTC) is the
    upper bound and is excluded: installs that have not reported yet today
    still can, and the next run starts after the newest file, so a day
    exported early would stay incomplete. A day is final once it has ended.
    """
    where = f"day < '{before.isoformat()}'"
    if after is not None:
        where = f"day > '{after.isoformat()}' AND {where}"
    return f"SELECT * FROM ping WHERE {where} ORDER BY day, received_at, id"


def split_by_day(rows: list[dict], after: date | None, before: date) -> dict[str, list[dict]]:
    """Group rows by their `day`, keeping only days in (after, before)."""
    lo = after.isoformat() if after else ""
    hi = before.isoformat()
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        day = str(r.get("day") or "")
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        if lo < day < hi:
            out[day].append(r)
    for day_rows in out.values():
        day_rows.sort(key=lambda r: (str(r.get("received_at") or ""), r.get("id") or 0))
    return dict(out)


def write_day_files(directory: Path, by_day: dict[str, list[dict]]) -> list[Path]:
    """Write each day as `<directory>/YYYY/YYYY-MM-DD.json`.

    One row per line with sorted keys, so a later change to a file (which
    should never happen) shows as a readable diff.
    """
    written = []
    for day in sorted(by_day):
        file = directory / day[:4] / f"{day}.json"
        file.parent.mkdir(parents=True, exist_ok=True)
        lines = ",\n".join(
            json.dumps(r, sort_keys=True, ensure_ascii=False) for r in by_day[day]
        )
        # Written beside the target and renamed, so an interrupted run never
        # leaves a truncated YYYY-MM-DD.json that the next run would take as
        # the newest finished day.
        tmp = file.with_name(file.name + ".tmp")
        tmp.write_text(f"[\n{lines}\n]\n", encoding="utf-8")
        os.replace(tmp, file)
        written.append(file)
    return written


def export_days(directory: Path, remote: bool, wrangler: str, today: date) -> list[Path]:
    """Fetch every finished day newer than the newest file, and write it."""
    directory.mkdir(parents=True, exist_ok=True)
    after = newest_export_day(directory)
    if after is not None and after >= today - timedelta(days=1):
        print(f"{directory}: up to date (newest day {after})")
        return []
    rows = fetch_rows(remote, wrangler, export_query(after, today))
    written = write_day_files(directory, split_by_day(rows, after, today))
    print(f"{directory}: wrote {len(written)} day file(s) from {len(rows)} reports")
    return written


# --------------------------------------------------------------------------
# Aggregation — pure functions over the row dicts, so they are unit-testable
# without a database. Every one of them must survive an empty dataset: for the
# first weeks that IS the dataset.
# --------------------------------------------------------------------------

def _jsonmap(value) -> dict:
    """Decode a JSON-blob column (fontpack, counters) defensively."""
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        out = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


def day_range(rows: list[dict], days: int | None) -> list[str]:
    """Every day in the window, including ones with no pings.

    Gaps matter here — a day where nobody reported is a real observation, and
    plotting only the days that have rows silently closes the gap and turns an
    outage into a straight line. `days=None` starts the window at the first
    valid day in the data.
    """
    valid = []
    for r in rows:
        try:
            valid.append(date.fromisoformat(str(r.get("day") or "")))
        except ValueError:
            continue
    if not valid:
        return []
    end = max(valid)
    if days is None:
        start = min(valid)
    else:
        start = end - timedelta(days=max(days, 1) - 1)
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def daily_installs(rows: list[dict], window: list[str]) -> list[tuple[str, int]]:
    seen: dict[str, set] = defaultdict(set)
    for r in rows:
        seen[str(r.get("day") or "")].add(r.get("install_id"))
    return [(d, len(seen.get(d, ()))) for d in window]


def daily_counter(rows: list[dict], name: str, window: list[str]) -> list[tuple[str, int]]:
    total: Counter = Counter()
    for r in rows:
        value = _jsonmap(r.get("counters")).get(name)
        if isinstance(value, (int, float)):
            total[str(r.get("day") or "")] += int(value)
    return [(d, total.get(d, 0)) for d in window]


def latest_per_install(rows: list[dict]) -> list[dict]:
    """The most recent row per install — 'what is out there right now'.

    Counting every row instead would weight a tester who has been running for a
    month 30× against one who installed yesterday, which is exactly backwards
    for a "which versions are in the field" question.
    """
    best: dict[str, dict] = {}
    for r in rows:
        key = r.get("install_id")
        prev = best.get(key)
        if prev is None or str(r.get("received_at") or "") > str(prev.get("received_at") or ""):
            best[key] = r
    return sorted(best.values(), key=lambda r: str(r.get("received_at") or ""), reverse=True)


def _keyboard_groups(rows: list[dict]) -> tuple[dict[str, str], set[tuple[str, str]]]:
    """Map each hardware ID hash to its group root, and collect the pairs.

    Two hashes in one row are taken as one keyboard, so a group is a set of
    hashes linked through rows. A pair is one distinct set {a, b}, in either
    column order.
    """
    parent: dict[str, str] = {}

    def find(h: str) -> str:
        while parent[h] != h:
            parent[h] = parent[parent[h]]
            h = parent[h]
        return h

    pairs: set[tuple[str, str]] = set()
    for r in rows:
        hashes = _row_hashes(r)
        for h in hashes:
            parent.setdefault(h, h)
        if len(hashes) == 2:
            # Sorted: the Worker cannot check the order, and (A, B) and (B, A)
            # are the same two halves.
            pairs.add(tuple(sorted(hashes)))
            ra, rb = find(hashes[0]), find(hashes[1])
            if ra != rb:
                parent[rb] = ra
    return {h: find(h) for h in parent}, pairs


def _row_hashes(r: dict) -> list[str]:
    hashes = [str(r.get(k) or "") for k in ("hw_id_a", "hw_id_b")]
    hashes = [h for h in hashes if h]
    if len(hashes) == 2 and hashes[0] == hashes[1]:
        hashes = hashes[:1]     # the same hash twice is one half, not a pair
    return hashes


def keyboard_counts(rows: list[dict]) -> tuple[int, int, int]:
    """(linked hardware groups, pairs, inferred half replacements) from the
    hardware ID hashes (schema 3+). All three are estimates.

    A row carries up to two hashes, one per half (``hw_id_a``, ``hw_id_b``).
    A group with more than one pair is counted as a half replacement per extra
    pair. A half moved from one keyboard to another links the two keyboards
    into one group, and the group stays merged, so the group count can be too
    low and the replacement count too high. Rows from older hosts or firmware
    carry no hash and are skipped, so this counts only keyboards on firmware
    protocol 37+ with a schema 3 host.
    """
    group, pairs = _keyboard_groups(rows)
    pairs_per_group: Counter = Counter(group[a] for a, _ in pairs)
    replaced = sum(n - 1 for n in pairs_per_group.values() if n > 1)
    return len(set(group.values())), len(pairs), replaced


def daily_keyboards(rows: list[dict], window: list[str]) -> list[tuple[str, int]]:
    """Distinct keyboards (hash groups) that reported on each day."""
    group, _ = _keyboard_groups(rows)
    seen: dict[str, set] = defaultdict(set)
    for r in rows:
        for h in _row_hashes(r):
            seen[str(r.get("day") or "")].add(group[h])
    return [(d, len(seen.get(d, ()))) for d in window]


#: Device name of the emulated keyboard (``dev_mock_primary``, PolyKybdMock).
#: A host running it sends this name in the ping, and its firmware and
#: hardware fields hold host version numbers, so a developer or CI machine
#: would count as a keyboard owner.
MOCK_DEVICE_NAME = "PolyKybdMock"


def mock_install_ids(rows: list[dict]) -> set:
    """Installs that ever reported the mock keyboard. They are left out of
    every count on the page and listed only in the install table."""
    return {r.get("install_id") for r in rows
            if str(r.get("device_name") or "") == MOCK_DEVICE_NAME}


def last_day(rows: list[dict]) -> date | None:
    """The newest valid day in the data; the 'last N days' counts end here."""
    days = []
    for r in rows:
        try:
            days.append(date.fromisoformat(str(r.get("day") or "")))
        except ValueError:
            continue
    return max(days) if days else None


def _days_back(end: date, n: int) -> set[str]:
    return {(end - timedelta(days=i)).isoformat() for i in range(n)}


def active_installs(rows: list[dict], end: date | None, n: int) -> int:
    """Installs with at least one report in the n days ending on `end`."""
    if end is None:
        return 0
    days = _days_back(end, n)
    return len({r.get("install_id") for r in rows if str(r.get("day") or "") in days})


def new_installs(rows: list[dict], end: date | None, n: int) -> int:
    """Installs whose first report is in the n days ending on `end`."""
    if end is None:
        return 0
    first: dict = {}
    for r in rows:
        d = str(r.get("day") or "")
        key = r.get("install_id")
        if key not in first or d < first[key]:
            first[key] = d
    days = _days_back(end, n)
    return sum(1 for d in first.values() if d in days)


def keyboards_without_id(latest: list[dict]) -> int:
    """Installs whose newest report has a keyboard but no hardware ID hash
    (an older host or firmware). Their keyboards may or may not be among the
    ones counted by hash."""
    return sum(1 for r in latest if r.get("device_present") and not _row_hashes(r))


def counter_periods(rows: list[dict], end: date | None) -> list[tuple[str, int, int, int]]:
    """Per counter: (label, last 7 days, last 30 days, all reports)."""
    if end is None:
        return [(label, 0, 0, 0) for _, label in COUNTERS]
    d7, d30 = _days_back(end, 7), _days_back(end, 30)
    t7, t30, tall = (dict((k, n) for k, _, n in counter_totals(sub))
                     for sub in ([r for r in rows if str(r.get("day") or "") in d7],
                                 [r for r in rows if str(r.get("day") or "") in d30],
                                 rows))
    return [(label, t7[key], t30[key], tall[key]) for key, label in COUNTERS]


def breakdown(rows: list[dict], field: str, blank: str = "(none)") -> list[tuple[str, int]]:
    counts: Counter = Counter(str(r.get(field) or "").strip() or blank for r in rows)
    return counts.most_common()


def linux_breakdown(rows: list[dict], field: str) -> list[tuple[str, int]]:
    """A Linux-only field, counted over Linux installs only.

    session/desktop/window_backend are '' on Windows and macOS, so counting
    them over every row would bury the answer under one huge "(none)" bar.
    Rows from a schema-1 host are '' on Linux too and show as "(not reported)"
    — distinct from "other", which means the install told us and we did not
    recognise the value.
    """
    linux = [r for r in rows if str(r.get("os") or "") == "Linux"]
    return breakdown(linux, field, blank="(not reported)")


def fw_breakdown(rows: list[dict]) -> list[tuple[str, int]]:
    """Firmware versions among installs that actually had a keyboard attached."""
    attached = [r for r in rows if r.get("device_present") and str(r.get("fw_version") or "")]
    return breakdown(attached, "fw_version")


def counter_totals(rows: list[dict]) -> list[tuple[str, str, int]]:
    total: Counter = Counter()
    for r in rows:
        counters = _jsonmap(r.get("counters"))
        for key, value in counters.items():
            if isinstance(value, (int, float)):
                total[key] += int(value)
    return [(key, label, total.get(key, 0)) for key, label in COUNTERS]


def fontpack_summary(rows: list[dict]) -> list[tuple[str, str]]:
    """Per bundle: the content_versions seen across installs.

    More than one version for a bundle means somebody's keyboard is behind, and
    that is the whole reason the version block is in the ping.
    """
    versions: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        for bundle, version in _jsonmap(r.get("fontpack")).items():
            versions[str(bundle)][version] += 1
    out = []
    for bundle in sorted(versions):
        seen = versions[bundle]
        # Sort NUMERICALLY. content_version is an integer that already reaches
        # 5 on symbol, so a lexicographic sort would file v10 before v2 exactly
        # when the split starts mattering.
        ordered = sorted(seen.items(), key=lambda kv: _version_key(kv[0]))
        out.append((bundle, ", ".join(f"v{v} ×{n}" for v, n in ordered)))
    return out


def _version_key(value):
    try:
        return (0, int(value), "")
    except (TypeError, ValueError):
        return (1, 0, str(value))


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def svg_bars(series: list[tuple[str, int]], height: int = 170, max_labels: int = 9) -> str:
    """A bar chart per day, as inline SVG (no script, no library).

    `max_labels` exists because the same viewBox is rendered full width for the
    headline chart and a third of that in the small-multiples grid, where nine
    dates collapse into an unreadable smear.
    """
    if not series:
        return '<p class="empty">No data in this window yet.</p>'

    width, pad_l, pad_b, pad_t = 760, 34, 22, 10
    plot_w, plot_h = width - pad_l - 6, height - pad_b - pad_t
    top = max((v for _, v in series), default=0) or 1
    step = plot_w / len(series)
    bar_w = max(1.0, min(step - 2, 28))

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" preserveAspectRatio="xMidYMid meet">'
    ]
    # Gridlines + y labels at 0 / half / top.
    for frac in (0, 0.5, 1):
        y = pad_t + plot_h - plot_h * frac
        label = round(top * frac)
        parts.append(f'<line class="grid" x1="{pad_l}" y1="{y:.1f}" x2="{width - 6}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{pad_l - 6}" y="{y + 4:.1f}" text-anchor="end">{label}</text>')

    every = max(1, -(-len(series) // max(1, max_labels - 1)))
    # MM-DD is enough inside one year. A window across years (--days all)
    # needs the year, or 08-07 at both ends reads as the same day.
    one_year = series[0][0][:4] == series[-1][0][:4]
    for i, (day, value) in enumerate(series):
        h = plot_h * (value / top)
        x = pad_l + i * step + (step - bar_w) / 2
        y = pad_t + plot_h - h
        parts.append(
            f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="1">'
            f"<title>{esc(day)}: {value}</title></rect>"
        )
        # A regular tick closer than half an interval to the last label would
        # run into it (30 days: ticks at 28 and 29), so it is left out.
        regular = i % every == 0 and (len(series) - 1 - i) * 2 >= every
        if regular or i == len(series) - 1:
            # The last label ends at its bar instead of centring on it, so a
            # full YYYY-MM-DD is not cut off at the right edge of the chart.
            last = i == len(series) - 1 and len(series) > 1
            lx, anchor = (x + bar_w, "end") if last else (x + bar_w / 2, "middle")
            parts.append(
                f'<text class="tick" x="{lx:.1f}" y="{height - 6}" '
                f'text-anchor="{anchor}">{esc(day[5:] if one_year else day)}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def hbars(items: list[tuple[str, int]], empty: str = "Nothing reported yet.") -> str:
    if not items:
        return f'<p class="empty">{esc(empty)}</p>'
    top = max(n for _, n in items) or 1
    rows = []
    for label, n in items:
        rows.append(
            '<div class="hbar">'
            f'<span class="hlabel" title="{esc(label)}">{esc(label)}</span>'
            f'<span class="htrack"><span class="hfill" style="width:{n / top * 100:.1f}%"></span></span>'
            f'<span class="hval">{n}</span>'
            "</div>"
        )
    return "".join(rows)


def install_table(rows: list[dict], test_ids: set = frozenset()) -> str:
    if not rows:
        return '<p class="empty">No installs have reported yet.</p>'
    head = (
        "<tr><th>Install</th><th>Last seen (UTC)</th><th>Host</th><th>OS</th>"
        "<th>Mode</th><th>Keyboard</th><th>Firmware</th><th>Country</th></tr>"
    )
    body = []
    for r in rows:
        if r.get("install_id") in test_ids:
            device = f'{esc(r.get("device_name"))} <span class="tag">test, not counted</span>'
        elif r.get("device_connected"):
            device = esc(r.get("device_name") or "connected")
        elif r.get("device_present"):
            device = "present, not connected"
        else:
            device = '<span class="muted">none</span>'
        body.append(
            "<tr>"
            # Full id in the tooltip: the short form is for the column width,
            # but cross-referencing one against `polyctl telemetry status`
            # needs the whole thing.
            f'<td class="mono" title="{esc(r.get("install_id"))}">'
            f'{esc(str(r.get("install_id") or "")[:12])}…</td>'
            f'<td class="mono">{esc(str(r.get("received_at") or "")[:19].replace("T", " "))}</td>'
            f'<td>{esc(r.get("host_version"))}</td>'
            f'<td>{esc(" ".join(x for x in (r.get("os"), r.get("os_release")) if x))}</td>'
            f'<td>{esc(r.get("mode"))}</td>'
            f"<td>{device}</td>"
            f'<td>{esc(r.get("fw_version") or "—")}</td>'
            f'<td>{esc(r.get("country") or "—")}</td>'
            "</tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


CSS = """
:root{--bg:#f4f4f2;--card:#fcfcfb;--fg:#0b0b0b;--muted:#52514e;--line:#e2e1dc;--grid:#ecebe6;
      --kb:#1baf7a;--kb-soft:#cdeee0;--inst:#2a78d6;--inst-soft:#cde2fb;
      --use:#eb6834;--use-soft:#fbdccd;--accent:var(--inst);--accent-soft:var(--inst-soft)}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){
  --bg:#121211;--card:#1a1a19;--fg:#f0efec;--muted:#c3c2b7;--line:#2f2f2c;--grid:#2a2a27;
  --kb:#199e70;--kb-soft:#173a2d;--inst:#3987e5;--inst-soft:#1d3554;
  --use:#d95926;--use-soft:#4a2716}}
:root[data-theme="dark"]{--bg:#121211;--card:#1a1a19;--fg:#f0efec;--muted:#c3c2b7;--line:#2f2f2c;
  --grid:#2a2a27;--kb:#199e70;--kb-soft:#173a2d;--inst:#3987e5;--inst-soft:#1d3554;
  --use:#d95926;--use-soft:#4a2716}
*{box-sizing:border-box}
body{margin:0;padding:28px 16px 60px;background:var(--bg);color:var(--fg);
     font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto}
h1{font-size:24px;margin:0 0 2px}
h2{font-size:15px;margin:0 0 12px;font-weight:600}
.sub{color:var(--muted);font-size:13px;margin:0 0 20px}
.kb{--accent:var(--kb);--accent-soft:var(--kb-soft)}
.inst{--accent:var(--inst);--accent-soft:var(--inst-soft)}
.use{--accent:var(--use);--accent-soft:var(--use-soft)}
section{margin:34px 0 0}
.sechead{display:flex;align-items:baseline;gap:12px;border-left:6px solid var(--accent);
         padding:2px 0 2px 12px;margin:0 0 14px}
.sechead h2{font-size:19px;margin:0}
.sechead p{margin:0;color:var(--muted);font-size:13px}
.hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.big{background:var(--card);border:1px solid var(--line);border-top:5px solid var(--accent);
     border-radius:10px;padding:14px 16px}
.big b{display:block;font-size:38px;line-height:1.1;font-variant-numeric:tabular-nums}
.big .what{display:block;font-weight:600;font-size:14px;margin-top:2px}
.big .how{display:block;color:var(--muted);font-size:12px;margin-top:4px;line-height:1.4}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:16px}
.grid2 .card{margin-bottom:0}
.wide{grid-template-columns:repeat(auto-fit,minmax(420px,1fr))}
@media (max-width:480px){.wide{grid-template-columns:1fr}}
svg{width:100%;height:auto;display:block;overflow:visible}
.bar{fill:var(--accent)}
.grid{stroke:var(--grid);stroke-width:1}
.tick{fill:var(--muted);font-size:10px}
.hbar{display:flex;align-items:center;gap:10px;margin:5px 0}
.hlabel{flex:0 0 130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.htrack{flex:1;background:var(--accent-soft);border-radius:3px;height:9px;overflow:hidden}
.hfill{display:block;height:100%;background:var(--accent);border-radius:0 3px 3px 0}
.hval{flex:0 0 34px;text-align:right;font-size:13px;font-variant-numeric:tabular-nums}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:24px;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi span{color:var(--muted);font-size:12px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.tablewrap{overflow-x:auto}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.muted,.empty{color:var(--muted)}
.empty{font-size:13px;margin:6px 0}
.tag{font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px;margin-left:4px}
.note{color:var(--muted);font-size:13px;margin:-4px 0 16px}
footer{color:var(--muted);font-size:12px;margin-top:30px;line-height:1.7}
"""


def _big(cls: str, value, what: str, how: str) -> str:
    return (f'<div class="big {cls}"><b>{value}</b><span class="what">{esc(what)}</span>'
            f'<span class="how">{esc(how)}</span></div>')


def _kpi(value, label: str) -> str:
    return f'<div class="kpi"><b>{value}</b><span>{esc(label)}</span></div>'


def _section(cls: str, title: str, lead: str, body: str) -> str:
    return (f'<section class="{cls}"><div class="sechead"><h2>{esc(title)}</h2>'
            f'<p>{esc(lead)}</p></div>{body}</section>')


def render(rows: list[dict], days: int | None, generated: str) -> str:
    test_ids = mock_install_ids(rows)
    all_latest = latest_per_install(rows)
    rows_all = rows
    rows = [r for r in rows if r.get("install_id") not in test_ids]
    window = day_range(rows, days)
    latest = latest_per_install(rows)
    # One set for the whole pass: with --days all the window is every day in
    # the archive, and rebuilding it per row is O(rows x days).
    window_days = set(window)
    in_window = [r for r in rows if str(r.get("day") or "") in window_days]
    end = last_day(rows)
    end_label = end.isoformat() if end else "no data"

    kb_groups, _, kb_replaced = keyboard_counts(rows)
    with_kb = sum(1 for r in latest if r.get("device_present"))
    no_id = keyboards_without_id(latest)
    active7, active30 = active_installs(rows, end, 7), active_installs(rows, end, 30)

    summary = "".join([
        _big("kb", kb_groups, "keyboards identified",
             "Counted by hardware ID. Only host 1.28.12+ with firmware 1.13.11+ sends one."),
        _big("inst", active7, "active installs, 7 days", f"At least one report in the 7 days to {end_label}."),
        _big("inst", active30, "active installs, 30 days", f"At least one report in the 30 days to {end_label}."),
        _big("inst", len(latest), "installs ever seen", "Every install that has sent a report."),
    ])

    keyboards = _section("kb", "Keyboards", "Hardware that reports to a host", "".join([
        '<div class="kpis">',
        _kpi(kb_groups, "keyboards identified by hardware ID"),
        _kpi(no_id, "installs with a keyboard but no ID (older host or firmware)"),
        _kpi(with_kb, "installs with a keyboard at their last report"),
        _kpi(kb_replaced, "half replacements, inferred from hash pairs"),
        "</div>",
        f'<div class="card"><h2>Keyboards reporting per day</h2>{_keyboard_chart(rows, window)}</div>',
        '<div class="grid2">',
        f'<div class="card"><h2>Firmware version</h2>{hbars(fw_breakdown(latest), "No install has reported a keyboard yet.")}</div>',
        f'<div class="card"><h2>Keyboard model</h2>{hbars(breakdown([r for r in latest if r.get("device_present")], "device_name"), "No install has reported a keyboard yet.")}</div>',
        f'<div class="card"><h2>Hardware revision</h2>{hbars(breakdown([r for r in latest if r.get("device_present")], "hw_version"), "No install has reported a keyboard yet.")}</div>',
        f'<div class="card"><h2>Font-pack versions</h2>{_fontpack_html(latest)}</div>',
        "</div>",
    ]))

    installs = _section("inst", "Installations", "Computers running PolyHost", "".join([
        '<div class="kpis">',
        _kpi(active7, "active in the last 7 days"),
        _kpi(active30, "active in the last 30 days"),
        _kpi(new_installs(rows, end, 30), "new in the last 30 days"),
        _kpi(len(latest), "installs ever seen"),
        _kpi(len({r.get("host_version") for r in latest if r.get("host_version")}), "host versions in use"),
        "</div>",
        (f'<p class="note">{len(test_ids)} test install(s) with the mock keyboard are not counted '
         f'on this page. They are marked in the table at the bottom.</p>' if test_ids else ""),
        f'<div class="card"><h2>Installs reporting per day</h2>{svg_bars(daily_installs(rows, window))}</div>',
        '<div class="grid2">',
        f'<div class="card"><h2>Host version</h2>{hbars(breakdown(latest, "host_version"))}</div>',
        f'<div class="card"><h2>Operating system</h2>{hbars(breakdown(latest, "os"))}</div>',
        f'<div class="card"><h2>Country</h2>{hbars(breakdown(latest, "country"))}</div>',
        f'<div class="card"><h2>Run mode</h2>{hbars(breakdown(latest, "mode"))}</div>',
        f'<div class="card"><h2>Display server (Linux)</h2>{hbars(linux_breakdown(latest, "session"), "No Linux install has reported yet.")}</div>',
        f'<div class="card"><h2>Desktop (Linux)</h2>{hbars(linux_breakdown(latest, "desktop"), "No Linux install has reported yet.")}</div>',
        f'<div class="card"><h2>Window backend (Linux)</h2>{hbars(linux_breakdown(latest, "window_backend"), "No Linux install has reported yet.")}</div>',
        "</div>",
    ]))

    period_rows = "".join(
        f'<tr><td>{esc(label)}</td><td class="num">{a}</td><td class="num">{b}</td><td class="num">{c}</td></tr>'
        for label, a, b, c in counter_periods(rows, end)
    )
    counter_cards = "".join(
        f'<div class="card"><h2>{esc(label)} per day</h2>'
        f'{svg_bars(daily_counter(in_window, key, window), 150, max_labels=5)}</div>'
        for key, label in COUNTERS
    )
    usage = _section("use", "Usage", "What the installs did, summed over all of them", "".join([
        '<div class="card"><div class="tablewrap"><table>'
        '<tr><th>Event</th><th class="num">Last 7 days</th><th class="num">Last 30 days</th>'
        f'<th class="num">All reports</th></tr>{period_rows}</table></div></div>',
        f'<div class="grid2 wide">{counter_cards}</div>',
    ]))

    table = _section("inst", "All installs", "Newest report of each install, test installs included",
                     f'<div class="card"><div class="tablewrap">{install_table(all_latest, test_ids)}</div></div>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PolyKybd telemetry</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>PolyKybd telemetry</h1>
<p class="sub">Generated {esc(generated)} · data up to {esc(end_label)} (UTC) · window: {esc(_window_label(days, len(window)))}
· {len(rows_all)} reports from {len(all_latest)} installs</p>

<div class="hero">{summary}</div>
{keyboards}
{installs}
{usage}
{table}

<footer>
Each install reports at most once per UTC day, so a bar is a count of installs, not of launches.
Counters are per-report totals since that install's previous report.<br>
The reports carry no names, but the keyboard ID hashes are persistent device identifiers:
someone who knows who owns a keyboard can link its reports to that owner. With this few
keyboards a report is not lost in a crowd either. Nothing on this page left your machine to produce it.
</footer>
</div></body></html>
"""


def _keyboard_chart(rows: list[dict], window: list[str]) -> str:
    """Keyboards per day, from the first day any keyboard sent an ID. The days
    before it are not zero keyboards; no host could send an ID then."""
    series = daily_keyboards(rows, window)
    first = next((i for i, (_, n) in enumerate(series) if n), None)
    if first is None:
        return '<p class="empty">No keyboard has sent a hardware ID yet.</p>'
    return svg_bars(series[first:])


def _fontpack_html(latest: list[dict]) -> str:
    fontpack = fontpack_summary(latest)
    return (
        "".join(
            f'<div class="hbar"><span class="hlabel">bundle {esc(b)}</span>'
            f'<span class="hval" style="flex:1;text-align:left">{esc(v)}</span></div>'
            for b, v in fontpack
        )
        or '<p class="empty">No font-pack versions reported yet.</p>'
    )


# --------------------------------------------------------------------------

def _window_label(days: int | None, shown: int) -> str:
    if days is None:
        return f"all {shown} days"
    return f"last {days} days"


def _positive_days(value: str) -> int | None:
    """Reject --days 0 / negatives at parse time; "all" means no limit (None).

    `day_range` clamps to 1 defensively, but the page subtitle prints whatever
    was passed — so without this the header cheerfully reads "window: last 0
    days" over a chart showing one.
    """
    if value == "all":
        return None
    try:
        days = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer or 'all'") from None
    if days < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return days


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(Path(__file__).with_name("dashboard.html")),
                    help="output file (default: dashboard.html beside this script)")
    ap.add_argument("--days", type=_positive_days, default=30,
                    help="time-series window in days, or 'all' for every day (default 30)")
    ap.add_argument("--local", action="store_true", help="query the local dev DB instead of the remote one")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--from-json", metavar="PATH",
                     help="read saved `wrangler d1 execute --json` output instead of querying; "
                          "a directory reads every *.json under it")
    src.add_argument("--export-days", metavar="DIR",
                     help="write each finished UTC day newer than DIR's newest file to "
                          "DIR/YYYY/YYYY-MM-DD.json, then render from all of DIR")
    ap.add_argument("--wrangler", default="npx wrangler", help="how to invoke wrangler")
    ap.add_argument("--open", action="store_true", help="open the result in a browser")
    args = ap.parse_args(argv)

    if args.export_days:
        export_dir = Path(args.export_days)
        today_utc = datetime.now(timezone.utc).date()
        export_days(export_dir, remote=not args.local, wrangler=args.wrangler, today=today_utc)
        rows = load_rows(export_dir)
    elif args.from_json:
        rows = load_rows(Path(args.from_json))
    else:
        rows = fetch_rows(remote=not args.local, wrangler=args.wrangler)

    out = Path(args.out)
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    out.write_text(render(rows, args.days, generated), encoding="utf-8")

    print(f"{out} — {len(rows)} reports from {len(latest_per_install(rows))} installs")
    # webbrowser.open() returns False rather than raising when it cannot find a
    # browser (a bare Linux box, an SSH session, a locked-down desktop), so
    # --open would otherwise appear to do nothing at all and read as "the tool
    # is broken" when the file is sitting there, finished.
    if args.open and not webbrowser.open(out.resolve().as_uri()):
        print("could not open a browser — open the file above yourself")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
