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

## 2. Log in

```bash
npx wrangler login          # opens a browser; authorises this machine
```

**The database already exists and its `database_id` is committed in
`wrangler.toml`**, so for the live collector there is nothing to create and nothing
to paste — skip to step 3.

The ID is checked in deliberately: it is an identifier rather than a credential (it
grants nothing without account authentication), Wrangler supports no variable
interpolation that could keep it out of the file, and the alternative — everyone
carrying a local edit — means `git pull` never runs clean and every future change to
this config has to be hand-merged.

<details>
<summary>Standing up a <em>separate</em> collector (a fork, or a staging copy)</summary>

```bash
npx wrangler d1 create polyhost-telemetry-staging
```

The output ends with a config block containing a `database_id`. Copy that ID into
the **existing** `[[d1_databases]]` block in `wrangler.toml` (and change
`database_name` to match):

```toml
[[d1_databases]]
binding = "DB"
database_name = "polyhost-telemetry-staging"
database_id = "a1b2c3d4-…"
```
</details>

> ⚠️ **Keep `binding = "DB"`.** If you let Wrangler add the block for you (or use
> `--update-config`), it names the binding after the database —
> `polyhost_telemetry` — and `src/index.js` reads `env.DB`. The mismatch does not
> fail at deploy time: it fails at the first ping, with `Cannot read properties of
> undefined (reading 'prepare')`, and every ping returns 503. Either keep the block
> that is already in the file, or rename the binding back to `DB`.

> ⚠️ **To look an ID up, use `d1 list`, not `d1 info <name>`.** `d1 info` resolves
> the name through your local `wrangler.toml` **first**, so if that file holds a
> placeholder (or the wrong ID) it queries *that* and reports
> `The database … could not be found [code: 7404]` — which reads like the database
> does not exist, when in fact it is the config that is wrong. `d1 list` queries the
> account directly and ignores local config.

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

### Delete the test rows when you are done

That hand-made ping is now a real row in the production table, and while the
dataset is this small a couple of fake installs visibly skew it. Remove them by
`install_id`:

```bash
npx wrangler d1 execute polyhost-telemetry --remote --command \
  "DELETE FROM ping WHERE install_id IN
     ('00112233445566778899aabbccddeeff',
      'deadbeefdeadbeefdeadbeefdeadbeef')"
```

⚠️ **Without `--remote` this deletes from the local file and still reports
success** — the same trap as applying the schema in step 3. If a row you just
deleted is still there in the next `SELECT`, check which database each of the two
commands hit before concluding something is re-creating it.

Nothing does re-create them: the deploy workflow's smoke test only fetches the
banner, deliberately, so shipping the collector never writes a junk row.

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

> ⚠️ **Write the release notes before shipping the release that sets this.**
> There is no first-run dialog (removed in PolyKybdHost#153), so the release
> notes *are* the disclosure — this step is the moment reporting starts for
> real. See `docs/telemetry.md` § How users find out.

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

### The dashboard

`dashboard.py` runs those queries for you and writes one self-contained HTML file
— charts inlined, no CDN, no scripts — that you open locally:

```bash
python telemetry-collector/dashboard.py --open      # queries --remote, writes dashboard.html
python telemetry-collector/dashboard.py --days 90   # widen the time-series window
```

It shows installs reporting per day, host/firmware/OS/country/mode splits **per
install** (the newest report per install, so a long-running tester does not
outvote a new one by having reported more often), the activity counters over
time, font-pack versions, and a table of every install.

It is a **generator, not a service**, and that is the point: the Worker keeps its
"no read route, so no route can leak the dataset" property, and there is no
dashboard credential to leak because it borrows the wrangler login you already
have. The cost is that it shows the data as of the moment you ran it.

A hosted, always-current version is planned but **not built** — it needs a real
auth story, and on `workers.dev` that cannot be Cloudflare Access (same
zone-scoping trap as the WAF rate limit in §5). The design, the options and the
things that must change with it are in
[`HOSTED_DASHBOARD.md`](./HOSTED_DASHBOARD.md); read that before starting it.

`--from-json FILE` renders saved `--json` output without touching the network,
which is also how the tests cover it.

> ⚠️ In **bash**, escape the `$` in a `json_extract` path (`'\$.fw_flashes'`) or the
> shell expands it to nothing and the query silently returns NULLs rather than
> erroring. In PowerShell, `$` inside single quotes is already literal.

---

## 8. Backups and recovery

Two independent mechanisms; use both.

**Time Travel** is built in and needs no setup — D1 can restore any point within
its retention window. ⚠️ That window is **7 days on the Workers Free plan** (what
this collector runs on) and 30 days on Workers Paid. Do not plan a recovery around
30 days here; past a week, the export below is the only thing that will still have
the data.

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
