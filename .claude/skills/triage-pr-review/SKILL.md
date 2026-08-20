---
name: triage-pr-review
description: Triage the review feedback on a PolyKybd pull request and drive it to a resolution — fetch the comments and reviews, work out which bots actually reviewed (several post long comments without reviewing), verify every finding against the real code before acting, fix the true ones, decline the false ones with evidence, and post a single reply. Use when asked to "check the PR for feedback / comments / reviews", "what did CodeRabbit say", "address the review", or after opening a PR and waiting for the bots. NOT for CI failures (that's diagnose-hil-failure for HIL, or the build job's own log).
---

# Triage PR review feedback

Three bots review PolyKybd PRs — **CodeRabbit**, **Sourcery** and **Qodo** — and
their output is *not* uniformly trustworthy or even uniformly a review. This skill
is the loop: find out what actually ran, verify each finding against the code, act,
and reply once.

The standing repo rule is **verify, not dismiss**: on one PR, 3 of 7 CodeRabbit
findings were false and two were refuted by their own evidence — but the same round
produced a genuinely valuable one. Both halves of that matter.

## 1. Fetch what's there

```
mcp__github__pull_request_read  method=get_comments  owner=thpoll83 repo=<repo> pullNumber=<n>
mcp__github__pull_request_read  method=get_reviews   owner=thpoll83 repo=<repo> pullNumber=<n>
```

⚠️ **`get_comments` routinely exceeds the tool's token limit** (51k characters on a
medium PR — the bots' walkthroughs are enormous). It then saves to a file and tells
you the path. Don't read that file whole; parse it:

```bash
python3 - <<'EOF'
import json, re, html
items = json.loads(open("<saved path>").read())
for c in items:
    u = (c.get("user") or {}).get("login"); b = c.get("body") or ""
    print("---", u, c.get("created_at"), len(b), "chars")
    print(b[:400].replace("\n", " "))
EOF
```

To read one bot's finding in full, strip the HTML (`re.sub(r"<[^>]+>", "\n", body)`
+ `html.unescape`) — Qodo in particular wraps everything in `<details>`/`<dl>`.

## 2. Establish which bots ACTUALLY reviewed

A long, confident comment with a walkthrough and a file table is not a review.
Check each:

| Bot | Reviewed | Didn't review — tells |
|---|---|---|
| **CodeRabbit** | body contains **`Actionable comments posted: N`** | `> [!WARNING] Review limit reached … next review in N minutes`; a "Reviews paused … under active development" note (auto-pause) |
| **Sourcery** | a review with per-comment findings ("Hey - I've found N issues") | its **review object's body is the rate-limit notice** (`you have reached your weekly rate limit of 500000 diff characters`) while its *Reviewer's Guide comment still renders in full* and looks like a review |
| **Qodo** | a comment headed **`Code Review by Qodo`** with a bug count | only `PR Summary by Qodo` — that is a description, never a review |

The findings live in **`get_reviews`**, not only in `get_comments` — CodeRabbit's
actionable list is the review body, and Sourcery's rate-limit notice arrives as a
review too. Always pull both.

If nothing actually reviewed and it matters, comment `@coderabbitai review` (and
`@coderabbitai full review` after an aborted run) rather than merging on the
appearance of review.

⚠️ **Spend that request once.** A refused request costs a slot too, and the stated
wait *grows* with each one — host #170 answered "next review in 19 minutes", then
**52** after the retry that wait invited. So:

- **Never chase the clock.** "Wait N minutes, ask again" is the one loop that
  reliably starves the PR; each retry buys a longer wait than it cost.
- **On an under-10-stars repo** (`PolyKybdHost`, `polykybd-docs` — no auto-review,
  rendered as a *"Review available on request"* box) the **checkbox and the chat
  command are the same quota**. Ticking the box *and* commenting is two slots for
  one review.
- **A push re-triggers a review for free.** If more commits are coming anyway,
  push first and ask afterwards — ask on the commit you intend to merge.

## 2b. When nothing reviewed at all

Sometimes the honest answer is that **no reviewer read this PR**. All three bots
can be unavailable at once, each in its own disguise (§2), and there is no
fallback: an on-demand Claude reviewer was tried across all three repos and
removed on 2026-08-20 — it published one review in its life and burned ~$4 of
subscription posting nothing the rest of the time, with the deciding detail
(which tool it was denied) unreadable from the log.

So when §2 says nothing reviewed:

- **Say so on the PR**, rather than letting a page of bot output imply otherwise.
- **Spend the one CodeRabbit slot deliberately** — on the commit you intend to
  merge, per the rate-limit note above.
- **Lean on what actually catches things here**: the HIL rig, cppcheck (the only
  non-LLM reviewer, and the one with no quota), and the unit suites. That
  asymmetry is the point — the bots are a convenience, those are the coverage.

## 3. Verify every finding against the code — before touching anything

For each finding, reproduce or refute it. Cheapest first:

- **A crash/exception claim** → run the expression in isolation. A five-line
  `python3 -c` beats reading the code twice:
  ```bash
  .venv/bin/python -c '"{a} {stale}".format(stale="x", **{"stale": True, "a": 1})'
  # TypeError: got multiple values for keyword argument 'stale'  -> the finding is real
  ```
- **A contract/logic claim** → read the exact lines it cites and trace the caller.
  Ask what input reaches the branch (e.g. "`--dev 0` makes `verbosity` falsey, so
  the flag is dropped, so the daemon re-reads the setting" — real).
- **A "should use a worker / is blocking" claim** → check what the call actually
  does. A local socket round-trip to a cached comparison is not the network I/O the
  rule is about; the codebase's own docstrings often already state the design.
- **A "pre-existing" finding is still a finding** — decide on merit, not on blame.
  (The Developer submenu being unreachable while disconnected predated the PR and
  was still worth fixing in it.)

**If a finding is real and no test caught it, add the test in the same change** —
and confirm the test *fails against the old code* rather than assuming it would.
The one crash this loop caught existed precisely because nothing rendered that
string in a test.

## 4. Fix, decline, reply once

- Fix the true ones. Keep each fix minimal and commented where the reason is
  non-obvious.
- Decline the false/inapplicable ones **with the evidence**, so they aren't
  re-raised on the next push.
- Skip nitpicks that add coupling (e.g. caching a subprocess result across tests) —
  say so briefly rather than silently ignoring them.
- Post **one** comment, not one per finding. Table of findings → verdict, then a
  short section for what you declined and why. End with the attribution footer:

```
---
_Generated by [Claude Code](https://claude.ai/code)_
```

Suggested shape:

```markdown
Review addressed in <sha>. Each finding was reproduced against the code before acting on it.

| Finding | Verdict |
|---|---|
| <finding> (bot) | **Real.** <what actually happens> |
| <finding> (bot) | **Fair.** <the narrower true version> |

**Not taken**
> <quoted finding>
<why, in terms of what the code does — plus any residue you are choosing to leave>
```

## Pitfalls

- **Don't trust the walkthrough.** Every bot renders one; only some of them
  reviewed. Check §2 before reporting a PR as "reviewed, no findings".
- **Don't dump `get_comments` into context** — it will blow the token limit and
  cost you the turn. Parse the saved file.
- **Don't batch-accept.** The autofix checkbox ("Push a commit to this branch")
  applies findings unverified; that is the opposite of this skill.
- **Don't batch-reject either.** The two most valuable findings this loop has
  produced were a hard `TypeError` on a menu path and a security-adjacent flag
  being dropped — both from bots that were wrong elsewhere in the same round.
- **Re-run the affected suites after fixing** (`.venv/bin/python -m unittest
  discover -s tests/<pkg> -t .`), and the xvfb GUI ones if the GUI changed. Clear
  `__pycache__` if a fix appears not to take (see CLAUDE.md § Test discovery).
- **A verdict table is not a merge.** Note anything still unverified on hardware
  in the reply, rather than implying the PR is fully validated.
