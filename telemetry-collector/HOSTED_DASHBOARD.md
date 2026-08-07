# Hosted dashboard — the plan, and what it costs

`dashboard.py` renders the telemetry dataset to a local HTML file. That was the
deliberate first step (PolyKybdHost#154): it needs no credential, adds no network
surface, and leaves the collector's central property intact — **the Worker accepts
writes and nothing else, so there is no route that could leak the dataset.**

A hosted view — open a URL, see current numbers, from a phone — is the obvious next
want. This document is what to read before building it, because the hard part is not
the page.

> **Status: not started.** Nothing here is implemented. The offline generator is the
> supported path today.

---

## What actually changes

Not "add a route". Three things move at once:

1. **The Worker gains its first read path.** Every sentence in `SETUP.md` §7 and in
   `SECURITY_AUDIT.md` **HOST-3** that leans on write-only stops being true the moment
   it merges. Those are not documentation chores to do afterwards — they are the
   statement of what the system is, and they have to change in the same PR.
2. **A credential comes into existence.** Today there is nothing to leak: the offline
   generator borrows the operator's existing `wrangler` login. A hosted dashboard needs
   a secret that grants read access to the whole dataset, and it will live in a browser.
3. **The threat model inverts.** The write path's worst case is junk rows — annoying,
   bounded, repairable with a `DELETE`. The read path's worst case is the dataset
   walking out of the door. Same Worker, opposite blast radius.

None of that is a reason not to build it. It is the reason to build it deliberately.

---

## ⚠️ The constraint that decides the design

**The endpoint lives on `workers.dev`, which is Cloudflare's zone, not ours.** Every
zone-scoped Cloudflare product is therefore unavailable — including **Cloudflare
Access**, the thing you would otherwise reach for first (SSO in front of a route, no
credential in the page, free for small teams).

This is the same trap that already cost a round on the rate limit: WAF rate-limiting
rules are zone-scoped too, which is why `wrangler.toml` uses the **Workers rate-limit
binding** instead. Assume any Cloudflare feature described as "protect a route/hostname"
is out until a custom domain exists.

So there are two shapes, and the choice is really "do we own a domain for this yet":

| | **A. Auth inside the Worker** (works on `workers.dev`) | **B. Cloudflare Access** (needs a custom domain) |
|---|---|---|
| Credential | A shared token we mint and rotate by hand | The operator's existing identity (Google/GitHub SSO) |
| Where it lives | Browser `localStorage`, and in whatever the operator pasted it from | Nowhere — Access issues a short-lived JWT |
| Revocation | Rotate the secret, everyone re-enters it | Remove the user from the Access policy |
| Multiple people | One shared secret, so no audit trail | Per-person, with logs |
| Setup cost | ~1 hour, all in this repo | A domain + a Zero Trust app; then the Worker just trusts `Cf-Access-Jwt-Assertion` |
| Fit today | One operator, a handful of testers | The right answer once there is a domain |

**Recommendation: B if a custom domain is on the cards anyway; A only as a stopgap,
and if A, write down that it is one.** A shared bearer token guarding a dataset is
acceptable at this scale and ages badly — the moment a second person needs access it
is being pasted into a chat window.

---

## If building A (token in the Worker)

Sketch, in the order the details bite:

- **Serve aggregates, not rows.** `GET /v1/stats` returns the numbers the page draws,
  computed **in SQL** — the `daily_by_host_version` / `daily_by_fw_version` views
  already exist for exactly this. A compromised token then leaks a version histogram,
  not the raw table. It also avoids re-implementing `dashboard.py`'s aggregations in
  JavaScript, where the two would silently drift and only one of them has tests.
- **Compare the token in constant time.** A byte-by-byte `===` on a secret is a timing
  oracle. Use `crypto.subtle.timingSafeEqual` over digests of equal length.
- **Exchange the token for a cookie.** `POST /v1/login` sets an `HttpOnly`, `Secure`,
  `SameSite=Strict` session cookie so the long-lived secret is not in `localStorage`
  where any script on the origin can read it.
- **Rate-limit the read path separately.** The existing `PING_LIMITER` is tuned for
  one write per install per day. A guessing attack on the token needs its own, much
  tighter, budget — and failures should count, not successes.
- **`Cache-Control: no-store`** on everything under the read path. A cached aggregate
  in a shared proxy outlives the session that fetched it.
- **Keep the offline generator working.** It is the fallback when the hosted view is
  broken or the token is lost, and the only path that works with no credential at all.
  Do not let the two diverge into "the real one" and "the legacy one".

## If building B (Cloudflare Access)

Most of the above still applies (aggregates not rows, no-store, keep the generator).
The Worker's own check becomes: verify the `Cf-Access-Jwt-Assertion` header against
the team's public keys, reject anything without it. There is no secret in the page and
no login endpoint to write. **The Worker must still verify the JWT** — Access sits in
front of the *hostname*, so a request that reaches the Worker by another route would
otherwise be unauthenticated.

---

## Definition of done

A hosted dashboard is not finished when the page renders. It is finished when:

- [ ] `SECURITY_AUDIT.md` **HOST-3** describes the read path, its auth, and its blast
      radius — not the write-only posture it currently records.
- [ ] `SETUP.md` §7 no longer claims there is no read API.
- [ ] `docs/telemetry.md` says the collected data sits behind authentication, since the
      public privacy page is where users are told what happens to it.
- [ ] The token/Access rotation procedure is written down somewhere other than a commit
      message.
- [ ] `dashboard.py` still works, and is still tested.

---

## Why not just use a BI tool

Considered and rejected for now. D1 speaks HTTP and the Cloudflare API, not the
Postgres wire protocol, so Grafana/Metabase/Superset all need a custom data source or a
sync job into something they *can* read. That is a second moving part, a second place
the dataset lives, and a second thing to secure — to display six charts for one person.
Revisit if the dataset outgrows a single page, not before.
