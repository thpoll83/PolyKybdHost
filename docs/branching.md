# Branching (all PolyKybd repos) — worked examples

Moved out of `CLAUDE.md` 2026-09-14. Verbatim.

## Branching (all PolyKybd repos)

- **Give every branch a name that hints at its content.** When creating a branch, append a short, descriptive slug describing the change (e.g. `claude/fix-firmware-update-menu-daemon-mode`, not just the auto-generated `claude/<random-scientist>-<id>`). The random scientist/id suffix from Claude Code on the web is auto-assigned server-side and can't always be overridden mid-session, but whenever a branch name is chosen by us, make it self-explanatory so the branch list reads as a changelog.
- **Always start new work on a FRESH branch cut from the updated default branch — never keep committing to a branch whose PR has already merged.** Once a PR is merged, that branch is done: `git fetch origin <default>` (and for the next piece of work `git checkout -b claude/<new-slug> origin/<default>`). Cherry-pick only the still-unmerged commits onto the fresh branch if needed. This keeps each PR a clean, focused diff against the current default (`main` for host/rig, `PolyKybd` for the firmware) and avoids a new PR accidentally re-including already-merged commits.
  - ⚠️ **Violating this is INVISIBLE — a push to a branch whose PR has already
    merged SUCCEEDS and orphans the commit.** git reports an ordinary fast-forward,
    GitHub shows nothing (a merged PR does not reopen, update, or list the new
    commit), and the work is simply not in `main` and not in any PR. It is easy to
    hit without meaning to: the window is "the PR merged while you were still
    working", not "you deliberately reused an old branch" — that is exactly how
    the CLAUDE.md commit from #168 was stranded (2026-08-17, recovered as #171).
    The one check, worth running before reporting any push as done:
    `git merge-base --is-ancestor <sha> origin/main` (and `git log --oneline
    --merges -5 origin/main` to see whether your PR's merge already went in).
    Recovery is the restart above: `git checkout -B <branch> origin/<default>`,
    cherry-pick the orphan, `git push --force-with-lease`, open a NEW PR — expect
    an add/add conflict if another PR touched the same region meanwhile.
- ⚠️ **A CLAUDE.md conflict is one of TWO kinds, and telling them apart matters —
  the second one deletes your work silently if you resolve it the usual way.**
  This file is append-heavy and every branch adds notes at the same anchors, so
  conflicts here are routine (two in 90 minutes on 2026-08-18):
  - **Addition beside addition** — main and your branch each inserted a new note
    at the same anchor. Keep BOTH; put main's first so the diff against main
    stays minimal.
  - **Supersession** — main's PR *implemented* something and rewrote the note
    that said it was impossible (`Browser-URL matching is LOCAL-ONLY` → `…DOES
    cross machines`, #173). Main's version wins **outright**; keeping both ships
    a file that contradicts itself. Verify you contributed nothing to that region
    first — `git show <base>:CLAUDE.md | grep -c "<phrase>"` against your branch
    proves it is inherited, not yours.
  - ⚠️ **After resolving, grep each of your notes back by name.** Taking one side
    wholesale also deletes anything of yours that merely *shared the conflict
    block* — git reports a clean merge, the file has no markers, and the loss is
    invisible. That happened on 2026-08-18: a supersession block also contained
    two unrelated new notes, and "take theirs" removed them. The check is
    `for pat in "<note phrase>" …; do grep -c "$pat" CLAUDE.md; done` — one line,
    and the only thing standing between you and silently dropped work.
    ⚠️ Grep **prose**, not a phrase containing markup: this file wraps identifiers
    in backticks, so a pattern typed as `crash_summary() puts the crash counts`
    scores 0 against a line reading ``` `crash_summary()` puts the crash counts ```
    — a false "note lost" scare mid-resolution (2026-08-18). Pick a distinctive
    run of plain words, or include the backticks.
  - ⚠️ **The same grep-back is the check for a SCRIPTED edit, not just a merge —
    and there it catches a different cause.** Editing this file with a
    `s.replace(anchor, new)` drops whatever sits between the two when the
    replacement does not repeat the anchor's opening lines verbatim: python does
    exactly what it was told, nothing errors, and the file reads fine because the
    surviving text still forms a sentence. That is how a line vanished on
    2026-09-01 — the anchor began *"bot) does not re-raise it…"* and the
    replacement began one line lower, so that clause was silently deleted from a
    note being extended, not rewritten. Assert the anchor count before writing
    (`assert s.count(anchor) == 1`), then grep each note back by name afterwards.
    The merge case and this one share nothing but the remedy, which is the reason
    to state it once for both.

