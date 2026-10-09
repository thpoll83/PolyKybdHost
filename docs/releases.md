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
- ⚠️ **The bump lands through a PR of its own** (since 2026-10-09). `main` requires a
  pull request for every change, and a personal repository's ruleset cannot list the
  built-in `GITHUB_TOKEN` as a bypass actor, so the old direct push failed with `GH013`
  (#326's bump never landed). `bump-version.yml` now commits the bump to
  `bump/host-<version>-<run id>-<attempt>`, opens a PR with `GITHUB_TOKEN` and merges it
  at once (squash, else a merge commit), deleting the branch: #330 was the first.
  - It needs **Settings → Actions → General → "Allow GitHub Actions to create and approve
    pull requests"**, and a `main` rule that requires a PR and **nothing more**. A PR
    opened with `GITHUB_TOKEN` starts no workflows, so a required status check or
    approval would never be met and every bump would hang open.
  - For the same reason the bump PR's merge does not start `bump-version.yml` again
    (no loop), and CodeQL does not run on it.
  - The squash commit keeps the old subject, `chore: bump host version to X.Y.Z [skip ci]
    (#NNN)`, so the release anchors below still match.
  - A failed attempt can leave its `bump/…` branch or an open bump PR behind. Close it by
    hand and re-run the job; the attempt number keeps the retry's branch name unique.
  - The review bots that pick up a bump PR still spend quota on it: Sourcery and Revix
    did on #330. Greptile and Qodo did not.
  - The firmware repo meets the same rule the other way: its bump checks out with
    `secrets.BUMP_PAT`, a personal access token whose owner is on the `PolyKybd`
    bypass list, and pushes directly. That needs no extra PR, but its bump stops when
    the token expires (checkout fails to authenticate) or its owner leaves the bypass
    list (`GH013`); `keyboards/polykybd/RELEASES.md` there has both.
- **Version bump is label-driven**: the merged PR's `bump:major`/`bump:minor`/
  `bump:protocol` label (else patch) drives `bump-version.yml`. Bump `__protocol__` in
  lockstep with the firmware (see the connect-gate note in [`protocol-gate.md`](protocol-gate.md)).
  - ⚠️ **Since 1.0, patch (no label) is the default.** `bump:minor` is for a feature an
    owner would call new, the kind that names a release; a fix, a diagnostic, a developer
    tool or a small addition stays a patch even when it bumps the protocol. After 1.0
    nearly every PR took `bump:minor` (firmware 1.0.0 → 1.7.0 in six days, host 1.3.0 →
    1.15.0 in nine), and the maintainer asked for the 0.9.x habit back (2026-10-03).
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

