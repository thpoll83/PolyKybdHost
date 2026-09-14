# Host releases — mechanics

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## Releases

Host releases are **GitHub Releases** (tag `vX.Y.Z`; version in `polyhost/_version.py`),
created by **publishing** — *not* by pushing a tag. Use the `polykybd-github-release`
skill to draft the notes and drive the flow. Mechanics (learned 2026-07):

- ⚠️ **A `PROTOCOL_VERSION` bump means BOTH artifacts get released, and the check that
  catches it is the PUBLISHED versions, not the in-tree ones.** The existing "bump
  `__protocol__` in lockstep with `PROTOCOL_VERSION`" rule is about the *sources*, and
  it can be perfectly satisfied while the releases are a protocol apart. Measured
  2026-09-09: firmware `PolyKybd` and host `main` both read protocol 17, while the
  newest **published** host (v0.14.18) was still 16 — so a firmware-only release would
  have shipped protocol 17 to every user's protocol-16 app. Read the sibling's newest
  release (`list_releases`, then its `__protocol__`/`PROTOCOL_VERSION` at that tag)
  before drafting.
  - ⚠️ **Nothing downstream catches it, because the connect gate is NOT exact-match.**
    The host connects to any protocol `>= MIN_SUPPORTED_PROTOCOL` and gates each
    feature through `FEATURE_MIN_PROTOCOL`, so an old host pairs with new firmware and
    silently leaves the new features off — quieter than a refusal, and worse to
    diagnose. (The release skill's own pitfall claimed exact-match for a long time,
    which made the pairing read as self-enforcing when it is not.)
  - **Publish the host first, then the firmware** — the host is the side that has to
    understand the new protocol, so that order never leaves a user holding firmware
    their app cannot drive.

- ⚠️ **The host and firmware version numbers were deliberately aligned at 0.11.0
  (2026-08-05) — and they are NOT kept in lockstep after that.** The two are
  independent lines, each bumped by `bump-version.yml` from the labels on its own
  merged PRs, so a host-only or firmware-only change immediately re-separates them.
  That drift is expected and is **not** a bug to "fix": the thing that genuinely
  must move together is `__protocol__` / `PROTOCOL_VERSION` (see the connect-gate
  note in [`protocol-gate.md`](protocol-gate.md)), which is a different number entirely. Re-aligning the display
  versions is a cosmetic choice to make at a release, by landing a `bump:minor` PR
  that does **not** itself edit `_version.py` — the workflow bumps *after* merge, so
  an edited version file would be bumped on top of.

- **A pushed tag does NOT create a release.** Release tags land on the auto-bump
  `chore: … [skip ci]` commit (`bump-version.yml`), and `[skip ci]` suppresses the
  tag-push trigger — so `release.yml` runs on **`release: published`** (this workflow had
  in fact *never* run; host releases were always hand-created in the UI). No build assets
  (pure Python).
- **`scripts/publish_release.py`** — one OS-independent command (stdlib only, byte-identical
  to the qmk copy; it auto-detects the repo). It publishes the **newest prepared `<TAG>.md`
  on the `release-notes` branch** — the source of truth for what's ready, because the tree
  version drifts *ahead* (every PR merge auto-bumps it). `--dry-run`/`--tag`. It forces
  `encoding="utf-8"` on git output — on Windows the default cp1252 codec crashes on the
  emoji notes.
- **Crafted notes** live one-file-per-tag on the `release-notes` branch (`<TAG>.md`, first
  line `# <title>`, rest = body); `release.yml` applies them on `release: published` via
  `gh release edit`.
- **Version bump is label-driven**: the merged PR's `bump:major`/`bump:minor`/
  `bump:protocol` label (else patch) drives `bump-version.yml`. Bump `__protocol__` in
  lockstep with the firmware (see the connect-gate note in [`protocol-gate.md`](protocol-gate.md)).
  - ⚠️ **Set the label when the PR is OPENED (`issue_write`, `labels:`), never
    only ask for it in the body.** #212 (2026-09-04) asked for `bump:minor` in its
    body, was merged without it, and the label applied as the merge was happening
    landed 12 s too late — host went to **0.14.17**, not 0.15.0. Full note in
    `qmk_firmware/CLAUDE.md` § Releases ("Before the merge means AT OPEN").
- ⚠️ **From Claude Code on the web you can neither push tags (git proxy 403 on
  `refs/tags/*`) nor create a release (no `gh`, no create-release MCP tool)** — stage the
  notes on the branch and hand the user `python scripts/publish_release.py`.
  The same proxy also **403s on branch DELETION** (`git push origin --delete
  <branch>`, verified 2026-08-18), so a leftover branch has to be removed in the
  GitHub UI — don't burn retries on it, and don't create scratch branches you
  can't clean up.

