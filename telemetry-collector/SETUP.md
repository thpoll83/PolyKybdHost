# Setting up the telemetry collector (Cloudflare Worker + D1)

A start-to-finish walkthrough for standing up the ingest end of
[`../docs/telemetry.md`](../docs/telemetry.md). Everything here fits inside
Cloudflare's free plan and takes about ten minutes.

Two things to know before you start:

- **Nothing is sent until the last step.** `TELEMETRY_ENDPOINT` in
  `polyhost/settings.py` ships empty, and an empty endpoint disables sending
  entirely — so a half-finished setup cannot leak anything.
- **You can do steps 1–5 entirely locally**, with no Cloudflare account and no
  network, and only go remote once you have seen it work.

---

## 0. Prerequisites

- **Node.js 18+** (`node --version`).
- **A Cloudflare account.** The free plan is enough: Workers gives 100,000
  requests/day and D1 gives 5 GB of storage with 100,000 row-writes/day. One ping
  per install per day means a hundred testers use roughly 0.1 % of that.
- **Wrangler**, Cloudflare's CLI. No global install needed — `npx wrangler@latest`
  works everywhere below, and pins you to the current release.

```bash
cd telemetry-collector
npx wrangler@latest --version
```

---

## 1. Try it locally first (no account needed)

Wrangler can run the Worker against a local SQLite file. This validates the schema
and the Worker's parsing before anything is deployed.

```bash
# create the tables in the LOCAL database
npx wrangler d1 execute polyhost-telemetry --local --file=./schema.sql

# run the Worker on http://localhost:8787
npx wrangler dev
```

In a second terminal, send a ping by hand:

```bash
curl -i -X POST http://localhost:8787/v1/ping \
  -H 'content-type: application/json' \
  -d '{"schema":1,"install_id":"00112233445566778899aabbccddeeff",
       "host_version":"0.11.5","host_protocol":12,
       "os":"Linux","os_release":"6.8","arch":"x86_64","python":"3.12","mode":"daemon",
       "device":{"present":true,"connected":true,"name":"PolyKybd Split72",
                 "fw_version":"0.11.4","protocol":12,"hw_version":"1.0",
                 "fontpack":{"symbol":5}},
       "counters":{"sessions":1,"connects":2}}'
```

Expected: **`HTTP/1.1 204 No Content`**. Confirm the row landed, then confirm the
dedupe works by sending the same request again — the row count stays at 1:

```bash
npx wrangler d1 execute polyhost-telemetry --local \
  --command="SELECT day, install_id, host_version, fw_version, country FROM ping"
```

Worth trying while you are here, because these are the paths that matter in
production: a malformed body (`-d 'nonsense'`) must return **400**, and a `GET
/v1/ping` must return **405**.

<!-- If you skipped straight to production and something is wrong, come back here:
     the local loop is far faster to debug than a deployed Worker. -->

---

## 2. Log in and create the database

```bash
npx wrangler login          # opens a browser; authorises this machine
npx wrangler d1 create polyhost-telemetry
```

The output ends with a config block containing a `database_id`. Copy that ID into
the **existing** `[[d1_databases]]` block in `wrangler.toml`, replacing
`REPLACE_WITH_D1_DATABASE_ID`:

```toml
[[d1_databases]]
binding = "DB"
database_name = "polyhost-telemetry"
database_id = "a1b2c3d4-…"
```

> ⚠️ **Keep `binding = "DB"`.** If you let Wrangler add the block for you (or use
> `--update-config`), it names the binding after the database —
> `polyhost_telemetry` — and `src/index.js` reads `env.DB`. The mismatch does not
> fail at deploy time: it fails at the first ping, with `Cannot read properties of
> undefined (reading 'prepare')`, and every ping returns 503. Either keep the block
> that is already in the file, or rename the binding back to `DB`.

### If you created the database in the dashboard instead

Everything above still applies — you just need the ID that `d1 create` would have
printed:

```bash
npx wrangler d1 list          # every database on the account: uuid + name
```

> ⚠️ **Use `d1 list`, not `d1 info polyhost-telemetry`.** `d1 info` resolves the name
> through your local `wrangler.toml` **first**, so while the placeholder is still in
> there it looks up `REPLACE_WITH_D1_DATABASE_ID` and fails with
> `The database REPLACE_WITH_D1_DATABASE_ID could not be found [code: 7404]` — which
> reads like the database does not exist, when in fact it is the config that is
> unfilled. `d1 list` queries the account directly and ignores local config. Once the
> real ID is in `wrangler.toml`, `d1 info` works fine.

Lost the ID later? Same command.

---

## 3. Create the tables in production

```bash
npx wrangler d1 execute polyhost-telemetry --remote --file=./schema.sql
```

`--remote` is the difference between the real database and the local file from
step 1 — and it is easy to omit. If a later query returns "no such table: ping",
this is almost always why.

Verify:

```bash
npx wrangler d1 execute polyhost-telemetry --remote \
  --command="SELECT name, type FROM sqlite_master ORDER BY type, name"
```

You should see the `ping` table, three indexes, and the two views
(`daily_by_host_version`, `daily_by_fw_version`).

---

## 4. Deploy the Worker

```bash
npx wrangler deploy
```

Wrangler prints the URL, typically
`https://polyhost-telemetry.<your-subdomain>.workers.dev`. Check it is alive:

```bash
curl https://polyhost-telemetry.<subdomain>.workers.dev/
# -> PolyHost telemetry collector. POST /v1/ping
```

Then send the same hand-made ping as step 1 against the deployed URL and confirm a
**204**, followed by:

```bash
npx wrangler d1 execute polyhost-telemetry --remote --command="SELECT * FROM ping"
```

The `country` column should now be populated — that is Cloudflare's edge deriving
it from your connection, which is exactly the field the Worker keeps *instead* of
the IP.

To watch requests live while testing, run `npx wrangler tail` in another terminal.

---

## 5. The rate limit

Already configured — the `[[ratelimits]]` binding in `wrangler.toml` caps `/v1/ping`
at **10 requests per minute per IP**, enforced inside the Worker and deployed with
it. Nothing to click. Ten a minute is roughly 14,000× what an honest client sends
(one per day), so it can never affect a real user.

> ⚠️ **Do not go looking for a WAF rate-limiting rule instead.** WAF rules are
> **zone**-scoped, and the endpoint lives on `workers.dev` — Cloudflare's zone, not
> yours — so there is no zone to attach one to. The binding is the mechanism that
> works here.

Verify it by sending the test ping from step 4 a dozen times in a row: the first ten
return `204`, the rest `429`. It resets within the minute. If a **Custom Domain** is
added later, a WAF rule becomes available as an extra outer layer — but keep this
binding regardless, since clients already in the field keep posting to the
workers.dev address, which a WAF rule on your own zone would never see.

---

## 6. Point the client at it

Per install, for testing:

```bash
polyctl settings set telemetry_endpoint https://polyhost-telemetry.<subdomain>.workers.dev/v1/ping
polyctl telemetry send      # ignores the once-a-day throttle
polyctl telemetry status    # last ping should read "HTTP 204"
```

For a release, set the same URL as `TELEMETRY_ENDPOINT` in
`polyhost/settings.py` — one line, in the release that turns telemetry on.
Existing installs pick it up because settings `load()` uses `setdefault`, so a key
they have never seen adopts the new default.

<!-- Reminder: the first-run notice stays hidden while the endpoint is empty, so
     this is also the step that starts showing users the disclosure dialog. -->

---

## 7. Reading the data

There is no read API — the Worker only accepts writes, so there is no route that
could leak the dataset. Query it directly:

```bash
# daily actives by host version, last two weeks
npx wrangler d1 execute polyhost-telemetry --remote --command \
  "SELECT * FROM daily_by_host_version WHERE day >= date('now','-14 day')"

# which firmware is actually out there
npx wrangler d1 execute polyhost-telemetry --remote --command \
  "SELECT * FROM daily_by_fw_version WHERE day >= date('now','-14 day')"

# installs whose link is flapping (the number you would otherwise have to ask for)
npx wrangler d1 execute polyhost-telemetry --remote --command \
  "SELECT day, install_id, json_extract(counters,'\$.reconnect_flaps') AS flaps
   FROM ping WHERE flaps > 0 ORDER BY day DESC LIMIT 20"

# did anyone flash firmware, and did their version actually move?
npx wrangler d1 execute polyhost-telemetry --remote --command \
  "SELECT day, install_id, fw_version, json_extract(counters,'\$.fw_flashes') AS flashes
   FROM ping WHERE flashes > 0 ORDER BY day DESC"
```

Add `--json` for machine-readable output.

> ⚠️ In **bash**, escape the `$` in a `json_extract` path (`'\$.fw_flashes'`) or the
> shell expands it to nothing and the query silently returns NULLs rather than
> erroring. In PowerShell, `$` inside single quotes is already literal.

---

## 8. Backups and recovery

Two independent mechanisms; use both.

**Time Travel** is built in and needs no setup — D1 can restore any point in the
last 30 days:

```bash
npx wrangler d1 time-travel info polyhost-telemetry
npx wrangler d1 time-travel restore polyhost-telemetry --timestamp=2026-08-01T12:00:00Z
```

**Exports** cover the case Time Travel does not: losing the account. This is the
whole database as SQL, small enough to keep with the project:

```bash
npx wrangler d1 export polyhost-telemetry --remote --output=telemetry-$(date +%F).sql
```

Worth doing quarterly. The point of owning the data was to escape someone else's
retention clock — an un-backed-up database in one account is only half of that.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Every ping returns **503**, `wrangler tail` shows `Cannot read properties of undefined (reading 'prepare')` | Binding is not named `DB` | Fix `binding = "DB"` in `wrangler.toml`, redeploy |
| `no such table: ping` | Schema applied locally but not remotely | Re-run step 3 **with `--remote`** |
| `polyctl telemetry send` says `error: disabled` | Telemetry switched off | `polyctl telemetry enable` |
| `send` says `no endpoint` | Endpoint empty | Step 6 |
| `send` reports `HTTP 405` | Endpoint URL missing the `/v1/ping` path | Append it |
| Pings succeed, no new rows | Same install already reported today | Expected — the daily dedupe. Query with `WHERE day = date('now')` to confirm |
| `HTTP 413` | Payload over 8 KB | Not reachable from a real client; suspect a hand-made request |
| Writes fail late in the day, recover next morning | Free-plan 100k row-writes/day exhausted | Limits reset at 00:00 UTC; investigate what is writing that much |

`npx wrangler tail` is the fastest way to see what the deployed Worker actually did
with a request — it streams live logs including the `console.error` on insert
failure.

---

## 10. Teardown

```bash
npx wrangler delete polyhost-telemetry          # the Worker
npx wrangler d1 delete polyhost-telemetry       # the database (irreversible)
```

Export first if you want to keep the data. To stop collection without tearing
anything down, blank `TELEMETRY_ENDPOINT` in the next host release — clients stop
sending immediately on update, and the deployed Worker simply goes quiet.
