# Telemetry: the client, the collector and the Cloudflare traps

How the anonymous usage report is built and where it goes, plus the three
Cloudflare/wrangler traps that each cost a round. Moved out of `CLAUDE.md` on
2026-09-10: ~6 KB read when you touch `services/telemetry.py` or
`telemetry-collector/`.

User-facing page: `docs/telemetry.md`. Runbook: `telemetry-collector/SETUP.md`.
Posture and residual risk: `polykybd-ctnd/docs/SECURITY_AUDIT.md` **HOST-3**.

⚠️ **The payload is an ALLOW-LIST at BOTH ends, and that is a privacy guarantee
rather than a style choice** — the host can see window titles and app names,
because it reads them constantly for overlays. `build_payload()` copies named
fields and never spreads a status dict; the Worker re-validates and rebuilds the
row it stores. The frozen `PAYLOAD_KEYS` test exists to make an accidental
widening fail loudly. **Never add a field by spreading.**

---

## The client

- **Anonymous usage telemetry (`polyhost/services/telemetry.py` + `telemetry-collector/`)**:
  one small JSON POST per install per day — host/protocol version, OS + coarse release,
  arch, python, run mode, the attached keyboard's model/fw/protocol/hw/font-pack versions,
  six counters since the last report (sessions, connects, reconnect_flaps, fw_flashes,
  fontpack_flashes, update_installs), and a locally-generated random `install_id`. **On by
  default**, opt out in the settings dialog or `polyctl telemetry disable`;
  `polyctl telemetry status|preview|send` are the rest of the CLI surface. `PolyCore` owns
  the reporter (`start_telemetry()` is called next to `worker.start()` in **both**
  `host.py` and `headless.py` — both construct `PolyCore(start_worker=False)`, so the
  reporter does not start itself). The endpoint is `TELEMETRY_ENDPOINT` in `settings.py`;
  **empty disables sending entirely**, which is how it ships before a collector exists.
  - **The payload is an ALLOW-LIST at both ends**, and that is a privacy guarantee, not a
    style choice: `build_payload()` copies named fields (never `**status`), and the Worker
    re-validates and rebuilds the row it stores. The host can see window titles and app
    names — it reads them constantly for overlays — so the frozen `PAYLOAD_KEYS` test in
    `tests/services/telemetry_test.py` exists to make an accidental widening fail loudly.
    Never add a field by spreading a status dict.
  - ⚠️ **There is NO in-app consent step.** The first-run dialog was removed (#153,
    "a modal on every upgrade is a poor trade for a disclosure that arrives after the
    install"), so the **release notes are the disclosure** and the one INFO line
    `_log_telemetry_notice` prints at every start is the only thing a headless daemon can
    say. Don't gate that line on an "already told them" flag, downgrade it to debug, or
    drop it in a logging cleanup. Write the release notes *before* shipping a release that
    sets the endpoint. Posture + residual risk: `polykybd-ctnd/docs/SECURITY_AUDIT.md`
    **HOST-3**; user-facing page: `docs/telemetry.md` and the public
    `software/telemetry` docs page.
  - **Collector**: a Cloudflare Worker + D1 (`telemetry-collector/`, deployed by
    `.github/workflows/deploy-telemetry.yml` on push to `main`). It is **write-only by
    design** — no read route, therefore no route that can leak the dataset. Read the data
    with `wrangler d1 execute` or **`python telemetry-collector/dashboard.py --open`**,
    which renders a self-contained HTML dashboard locally (per-install version splits from
    each install's *newest* report, so a long-running tester doesn't outvote a new one).
    A hosted version is planned but unbuilt — design and its costs in
    `telemetry-collector/HOSTED_DASHBOARD.md`. Full setup/runbook: `telemetry-collector/SETUP.md`.

---

## Cloudflare: what is and is not available on `workers.dev`

- ⚠️ **`workers.dev` is CLOUDFLARE's zone, not ours — so every zone-scoped Cloudflare
  product is unavailable on the collector.** This has now cost a round twice: first on
  rate limiting (WAF rate-limiting rules are zone-scoped, so the **Workers rate-limit
  binding** in `wrangler.toml` is the mechanism that works), then again on **Cloudflare
  Access**, the obvious way to put SSO in front of a hosted dashboard — also unavailable,
  so that auth would have to live *inside* the Worker until a custom domain exists. Rule
  of thumb: anything Cloudflare describes as "protect a route/hostname" needs a zone you
  own; anything configured as a Worker **binding** works. Don't accept advice (including
  mine) that reaches for a zone-level feature here without checking this first.

---

## `wrangler` commands that fail silently

- **`wrangler` gotchas that fail SILENTLY** (full detail in `telemetry-collector/SETUP.md`):
  - ⚠️ **A command without `--remote` hits the LOCAL sqlite file and reports success.**
    So a `DELETE` appears to run and the row is still there on the next `SELECT --remote`
    — deleted three times before the cause was obvious (2026-08-07). This applies to every
    `d1 execute`, not just the schema step.
  - **`d1 info <name>` resolves the name through the local `wrangler.toml`**, so it 7404s
    ("database could not be found") while the file still holds a placeholder id. Use
    **`d1 list`** to get the real id.
  - **The API token needs `Workers Scripts: Edit` (plus `D1: Edit`).** Without it the
    deploy fails with `Authentication error [code: 10000]`, which names the *endpoint* it
    could not reach and not the permission it lacked. Verify a token fix by triggering the
    workflow (`workflow_dispatch`) rather than assuming — that is a 30 s check.
  - **`binding = "DB"` in `wrangler.toml` must stay `DB`**: `d1 create` prints a suggested
    binding named after the *database*, and adopting it 503s every ping.

---

## Why the collector cannot double as a problem-report backend

- ⚠️ **The telemetry collector CANNOT double as a problem-report backend — four
  independent reasons, and the last one is a feature.** The obvious idea when
  "Report a Problem" was designed (2026-08-18) was to POST the report to the
  Cloudflare Worker that already exists. It doesn't fit, and each obstacle would
  have to be removed separately: the Worker caps a request body at **8 KB** (a
  description plus diagnostics blows past it, let alone logs); the D1 schema is
  `UNIQUE(install_id, day)` and upserts, so a **second report the same day
  overwrites the first** — exactly when a user is retrying because it broke
  again; the payload is an **allow-list rebuilt server-side** (`PAYLOAD_KEYS`,
  frozen by a test *designed* to make widening fail loudly), so free text can only
  arrive by deliberately undoing that guarantee; and the Worker is **write-only by
  design — there is no read route**, which is precisely what makes the dataset
  unleakable, so retrieval would mean building the route the design exists to
  avoid, plus auth *inside* the Worker (Cloudflare Access is zone-scoped and
  unavailable on `workers.dev` — see the note above). Hence the shipped design is
  a **pre-filled GitHub issue** with the bundle attached by the reporter: no
  backend, no new data store, and the user sees what they send. Don't re-propose
  the Worker without answering all four.
