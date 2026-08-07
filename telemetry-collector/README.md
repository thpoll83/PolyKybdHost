# PolyHost telemetry collector

A Cloudflare Worker + D1 database that receives the once-a-day ping from
PolyHost (`polyhost/services/telemetry.py`). See [`../docs/telemetry.md`](../docs/telemetry.md)
for what is sent and why it is shaped this way.

**The client is inert until this is deployed.** `TELEMETRY_ENDPOINT` in
`polyhost/settings.py` ships empty, and an empty endpoint means the reporter
never sends. Nothing leaves a user's machine until someone sets that string to a
hostname we actually own.

## Deploy

**[`SETUP.md`](SETUP.md) is the full walkthrough** — local dry-run first, the
binding-name trap, the rate-limit rule, backups and a troubleshooting table. The
short version:

```bash
npx wrangler@latest login
npx wrangler d1 create polyhost-telemetry      # paste database_id into wrangler.toml
npx wrangler d1 execute polyhost-telemetry --remote --file=./schema.sql
npx wrangler deploy
```

Then point the client at it — either per install:

```bash
polyctl settings set telemetry_endpoint https://polyhost-telemetry.<subdomain>.workers.dev/v1/ping
```

…or, for a release, by setting `TELEMETRY_ENDPOINT` in `polyhost/settings.py`.
Verify end to end with `polyctl telemetry send` (bypasses the daily throttle),
which prints the HTTP status it got back.

## Rate limiting

Already wired: the `[[ratelimits]]` binding in `wrangler.toml` caps `/v1/ping` at
**10 requests per minute per IP**, checked in the Worker before the body is even
read, and deployed along with the code. That is ~14,000× what an honest client
sends (one request per day), so it cannot affect a real user.

⚠️ **Not a WAF rule** — those are *zone*-scoped, and the endpoint lives on
`workers.dev`, which is Cloudflare's zone rather than ours, so there is no zone to
attach one to. If a Custom Domain is added later a WAF rule becomes available as an
extra outer layer, but keep this binding: clients already shipped keep posting to
the workers.dev address, which such a rule would never see.

## Querying

There is no read API — the Worker only accepts writes, so there is no endpoint
to leak the data. Query it directly:

```bash
# daily actives by host version, last two weeks
wrangler d1 execute polyhost-telemetry --remote --command \
  "SELECT * FROM daily_by_host_version WHERE day >= date('now','-14 day')"

# which firmware is actually in the field
wrangler d1 execute polyhost-telemetry --remote --command \
  "SELECT * FROM daily_by_fw_version WHERE day >= date('now','-14 day')"

# installs that flashed firmware in the last week
wrangler d1 execute polyhost-telemetry --remote --command \
  "SELECT day, install_id, json_extract(counters,'$.fw_flashes') AS flashes
   FROM ping WHERE flashes > 0 AND day >= date('now','-7 day')"
```

## Backups

D1 is the system of record and there is no vendor retention clock on it, but the
account is a single point of failure. Export periodically and keep the dump
where the rest of the project lives:

```bash
wrangler d1 export polyhost-telemetry --remote --output=telemetry-$(date +%F).sql
```

## Adding a dashboard later

Nothing here needs to change to get charts. The two options, in order of effort:

1. Point Grafana at D1 (or copy the daily rollup into whatever store the
   dashboard uses) and build the panels there.
2. Have this Worker *also* forward each accepted ping to an OTLP endpoint —
   Grafana Cloud, Axiom, SigNoz, Dynatrace, whatever is in favour. This is the
   reason the client posts plain JSON to us instead of speaking OTLP itself:
   the protocol boundary is here, so swapping the dashboard backend is a
   `wrangler deploy`, not a PolyHost release that takes months to reach the
   field.

## Schema changes

The payload carries a `schema` integer. Bump it in
`polyhost/services/telemetry.py` when a field changes meaning, add the new value
to `SUPPORTED_SCHEMAS` here, and keep accepting the old one — hosts in the field
live for months and will keep sending the old shape. The full validated payload
is stored in `ping.raw`, so a field added in a later schema can be queried
retroactively with `json_extract` without a migration having been in place.
