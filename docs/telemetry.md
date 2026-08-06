# Telemetry — what PolyHost sends, and why it is built this way

PolyHost sends **one small anonymous report per install per day**. This document
is the complete description; if the code and this file ever disagree, the code
is wrong.

You can print the exact report that would be sent from your own machine:

```bash
polyctl telemetry preview
```

Turn it off with `polyctl telemetry disable`, in the tray GUI under
**Settings → Telemetry**, or by setting `telemetry_enabled: false` in
`settings.yaml`.

## What is sent

```json
{
  "schema": 1,
  "install_id": "9f2c…",           // random uuid4, generated on this machine
  "host_version": "0.11.5",
  "host_protocol": 12,
  "os": "Windows", "os_release": "11", "arch": "AMD64",
  "python": "3.12",
  "mode": "daemon",
  "device": {
    "present": true, "connected": true,
    "name": "PolyKybd Split72",
    "fw_version": "0.11.4", "protocol": 12, "hw_version": "1.0",
    "fontpack": {"symbol": 5, "emoji": 1}
  },
  "counters": {
    "sessions": 1, "connects": 3, "reconnect_flaps": 0,
    "fw_flashes": 0, "fontpack_flashes": 0, "update_installs": 0
  }
}
```

The server adds the arrival time and a two-letter country derived from the
connection, then **discards the IP address**. Nothing else is stored.

## What is never sent

The host application can see all of the following. None of it is collected:

- **window titles and application names** — the host reads these continuously to
  pick keycap overlays; they are the most sensitive thing it touches
- **keystrokes** — the host can inject them in developer mode; it never records
  them
- **your location** — the daylight-brightness feature may look up an approximate
  location; that never reaches telemetry
- user name, machine name, MAC address, keyboard serial number
- file paths, overlay contents, keymaps

This is enforced by construction: `build_payload()` copies named fields only,
and the test suite asserts the payload's key set exactly matches a frozen list,
so a new field cannot arrive by accident when the internal status snapshot grows.

## Why it exists

With a handful of keyboards in the field, the questions that are otherwise
unanswerable are: *which host version is actually running*, *which firmware is
on the keyboards it talks to*, *did that update install succeed*, and *is
someone's split link flapping*. `reconnect_flaps` and `fw_flashes` are there for
the last two — they are the numbers that would otherwise require asking a tester
to send a log.

Note that with a small user base, "anonymous" means the report carries nothing
identifying — not that it is lost in a crowd. Until there are many installs, a
daily report is effectively per-device, and we would rather say so than imply an
anonymity set that does not exist yet.

## How it is built (and why not the OpenTelemetry SDK)

The client ships **no observability SDK and no credentials** — it does one
`POST` of the JSON above. The OpenTelemetry side, if and when we want
dashboards, lives in the collector (`telemetry-collector/`), for three reasons:

1. **Credentials.** Any OTLP write key shipped in an open-source client is a
   public key. Posting to our own unauthenticated, rate-limited, write-only
   endpoint is honest about that instead of pretending otherwise.
2. **Data model.** This is a census, not tracing. Sliced by
   `host_version × fw_version × os`, it is a handful of rows a day — trivial in
   a table, a label-cardinality problem in a metrics backend.
3. **Retention and portability.** Hosted observability free tiers forget after
   14–30 days, and version adoption is a question that spans months. Rows in our
   own database have no retention clock, and because the protocol boundary is at
   the collector, changing dashboard vendors never requires a PolyHost release.

## Operational guarantees

- **A dead endpoint is a no-op.** Five-second timeout, failures swallowed, no
  retry storm — a ping failure can never surface as an error or delay anything.
- **It never runs on the HID worker.** The reporter owns a daemon thread and
  reads only cached state, so it does no device I/O and cannot block the
  keyboard.
- **The throttle is persisted** in the cache directory, so restarting the app
  repeatedly does not produce repeated pings.
- **Counters survive a failed send** and ride along with the next one, so a
  laptop that was offline does not lose its history.
- **In daemon mode only the daemon reports.** The tray GUI is a client of it, so
  one install is one ping regardless of how many times you restart the GUI.

## Endpoint configuration

`TELEMETRY_ENDPOINT` in `polyhost/settings.py` ships **empty**, which disables
sending entirely — deliberately, so that a build cannot post to a hostname we do
not yet control. See [`../telemetry-collector/README.md`](../telemetry-collector/README.md)
for deploying the collector and pointing the client at it.
