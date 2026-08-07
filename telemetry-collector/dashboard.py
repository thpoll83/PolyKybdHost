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
    python dashboard.py --local            # query the local dev DB instead
    python dashboard.py --from-json rows.json   # no wrangler; feed saved --json output
    python dashboard.py --out /tmp/t.html

Stdlib only, so it runs from a bare checkout on any OS.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

DB_NAME = "polyhost-telemetry"
SELECT_ALL = "SELECT * FROM ping ORDER BY received_at"

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
        raise ValueError("no JSON found in wrangler output")
    doc = json.JSONDecoder().raw_decode(text[start:])[0]

    if isinstance(doc, dict):
        doc = [doc]
    rows: list[dict] = []
    for part in doc:
        if isinstance(part, dict):
            rows.extend(part.get("results") or [])
        elif isinstance(part, list):  # already a bare row list
            rows.extend(part)
    return rows


def fetch_rows(remote: bool, wrangler: str) -> list[dict]:
    parts = wrangler.split() + [
        "d1", "execute", DB_NAME,
        "--remote" if remote else "--local",
        "--json", "--command", SELECT_ALL,
    ]
    exe = shutil.which(parts[0])
    if exe is None:
        raise SystemExit(
            f"error: {parts[0]!r} not found on PATH.\n"
            "Install Node (which provides npx), or pass --wrangler to name the\n"
            "binary, or use --from-json to render a saved export instead."
        )
    parts[0] = exe

    proc = subprocess.run(
        parts, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
        raise SystemExit(f"error: wrangler exited {proc.returncode}")
    return parse_wrangler_json(proc.stdout)


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


def day_range(rows: list[dict], days: int) -> list[str]:
    """Every day in the window, including ones with no pings.

    Gaps matter here — a day where nobody reported is a real observation, and
    plotting only the days that have rows silently closes the gap and turns an
    outage into a straight line.
    """
    if not rows:
        return []
    last = max(str(r.get("day") or "") for r in rows)
    try:
        end = date.fromisoformat(last)
    except ValueError:
        return []
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


def breakdown(rows: list[dict], field: str, blank: str = "(none)") -> list[tuple[str, int]]:
    counts: Counter = Counter(str(r.get(field) or "").strip() or blank for r in rows)
    return counts.most_common()


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
            versions[str(bundle)][str(version)] += 1
    out = []
    for bundle in sorted(versions):
        seen = versions[bundle]
        out.append((bundle, ", ".join(f"v{v} ×{n}" for v, n in sorted(seen.items()))))
    return out


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
    for i, (day, value) in enumerate(series):
        h = plot_h * (value / top)
        x = pad_l + i * step + (step - bar_w) / 2
        y = pad_t + plot_h - h
        parts.append(
            f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="1">'
            f"<title>{esc(day)}: {value}</title></rect>"
        )
        if i % every == 0 or i == len(series) - 1:
            parts.append(
                f'<text class="tick" x="{x + bar_w / 2:.1f}" y="{height - 6}" '
                f'text-anchor="middle">{esc(day[5:])}</text>'
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


def install_table(rows: list[dict]) -> str:
    if not rows:
        return '<p class="empty">No installs have reported yet.</p>'
    head = (
        "<tr><th>Install</th><th>Last seen (UTC)</th><th>Host</th><th>OS</th>"
        "<th>Mode</th><th>Keyboard</th><th>Firmware</th><th>Country</th></tr>"
    )
    body = []
    for r in rows:
        if r.get("device_connected"):
            device = esc(r.get("device_name") or "connected")
        elif r.get("device_present"):
            device = "present, not connected"
        else:
            device = '<span class="muted">none</span>'
        body.append(
            "<tr>"
            f'<td class="mono">{esc(str(r.get("install_id") or "")[:12])}…</td>'
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
:root{--bg:#f7f7f8;--card:#fff;--fg:#1a1a1c;--muted:#6b6b73;--line:#e3e3e7;
      --accent:#3f6fd8;--accent-soft:#c9d8f6;--grid:#ececf0}
@media (prefers-color-scheme:dark){
  :root{--bg:#131316;--card:#1b1b1f;--fg:#e8e8ea;--muted:#9a9aa3;--line:#2c2c32;
        --accent:#6f9bef;--accent-soft:#2b3f68;--grid:#26262c}}
*{box-sizing:border-box}
body{margin:0;padding:28px 20px 60px;background:var(--bg);color:var(--fg);
     font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1040px;margin:0 auto}
h1{font-size:22px;margin:0 0 2px}
h2{font-size:15px;margin:0 0 12px;font-weight:600}
.sub{color:var(--muted);font-size:13px;margin:0 0 22px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-bottom:16px}
.card.span{grid-column:1/-1}
svg{width:100%;height:auto;display:block;overflow:visible}
.bar{fill:var(--accent)}
.grid{stroke:var(--grid);stroke-width:1}
.tick{fill:var(--muted);font-size:10px}
.hbar{display:flex;align-items:center;gap:10px;margin:5px 0}
.hlabel{flex:0 0 150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}
.htrack{flex:1;background:var(--accent-soft);border-radius:3px;height:9px;overflow:hidden}
.hfill{display:block;height:100%;background:var(--accent)}
.hval{flex:0 0 34px;text-align:right;font-size:13px;color:var(--muted);
      font-variant-numeric:tabular-nums}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:24px;font-variant-numeric:tabular-nums;line-height:1.2}
.kpi span{color:var(--muted);font-size:12px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600}
.tablewrap{overflow-x:auto}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.muted,.empty{color:var(--muted)}
.empty{font-size:13px;margin:6px 0}
footer{color:var(--muted);font-size:12px;margin-top:26px;line-height:1.7}
"""


def render(rows: list[dict], days: int, generated: str) -> str:
    window = day_range(rows, days)
    latest = latest_per_install(rows)
    in_window = [r for r in rows if str(r.get("day") or "") in set(window)]
    installs_today = daily_installs(rows, window)[-1][1] if window else 0

    kpis = [
        (len(latest), "installs ever seen"),
        (installs_today, "reported on the last day"),
        (len({r.get("host_version") for r in latest if r.get("host_version")}), "host versions in the field"),
        (sum(1 for r in latest if r.get("device_present")), "with a keyboard attached"),
        (len(rows), "reports total"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><b>{value}</b><span>{esc(label)}</span></div>' for value, label in kpis
    )

    counter_cards = "".join(
        f'<div class="card"><h2>{esc(label)}</h2>'
        f'{svg_bars(daily_counter(in_window, key, window), 120, max_labels=3)}</div>'
        for key, label in COUNTERS
    )
    totals = "".join(
        f'<div class="kpi"><b>{n}</b><span>{esc(label)} (window)</span></div>'
        for _, label, n in counter_totals(in_window)
    )

    fontpack = fontpack_summary(latest)
    fontpack_html = (
        "".join(
            f'<div class="hbar"><span class="hlabel">{esc(b)}</span>'
            f'<span class="hval" style="flex:1;text-align:left">{esc(v)}</span></div>'
            for b, v in fontpack
        )
        or '<p class="empty">No font-pack versions reported yet.</p>'
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PolyHost telemetry</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>PolyHost telemetry</h1>
<p class="sub">Generated {esc(generated)} · window: last {days} days · {len(rows)} reports
from {len(latest)} installs</p>

<div class="kpis" style="margin-bottom:16px">{kpi_html}</div>

<div class="card"><h2>Installs reporting per day</h2>{svg_bars(daily_installs(rows, window))}</div>

<div class="grid2">
  <div class="card"><h2>Host version (current per install)</h2>{hbars(breakdown(latest, "host_version"))}</div>
  <div class="card"><h2>Firmware version (keyboard attached)</h2>{hbars(fw_breakdown(latest), "No install has reported a keyboard yet.")}</div>
  <div class="card"><h2>Operating system</h2>{hbars(breakdown(latest, "os"))}</div>
  <div class="card"><h2>Run mode</h2>{hbars(breakdown(latest, "mode"))}</div>
  <div class="card"><h2>Country</h2>{hbars(breakdown(latest, "country"))}</div>
  <div class="card"><h2>Hardware revision</h2>{hbars(breakdown(latest, "hw_version"))}</div>
</div>

<div class="card"><h2>Activity totals in window</h2><div class="kpis">{totals}</div></div>
<div class="grid2">{counter_cards}</div>

<div class="card"><h2>Font-pack versions on attached keyboards</h2>{fontpack_html}</div>

<div class="card span"><h2>Installs</h2><div class="tablewrap">{install_table(latest)}</div></div>

<footer>
Each install reports at most once per UTC day, so a bar is a count of installs, not of launches.
Counters are per-report totals since that install's previous report.<br>
"Anonymous" here means the data carries nothing identifying — with this few keyboards it is
not lost in a crowd either. Nothing on this page left your machine to produce it.
</footer>
</div></body></html>
"""


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(Path(__file__).with_name("dashboard.html")),
                    help="output file (default: dashboard.html beside this script)")
    ap.add_argument("--days", type=int, default=30, help="time-series window in days (default 30)")
    ap.add_argument("--local", action="store_true", help="query the local dev DB instead of the remote one")
    ap.add_argument("--from-json", metavar="FILE",
                    help="read saved `wrangler d1 execute --json` output instead of querying")
    ap.add_argument("--wrangler", default="npx wrangler", help="how to invoke wrangler")
    ap.add_argument("--open", action="store_true", help="open the result in a browser")
    args = ap.parse_args(argv)

    if args.from_json:
        rows = parse_wrangler_json(Path(args.from_json).read_text(encoding="utf-8"))
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
