# Branching (all PolyKybd repos) — worked examples

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

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


## Worked example: a merged PR whose work never reached `main` (2026-09-19)

The rule in `CLAUDE.md` says a **push** to a merged branch orphans the commit.
A **merge** does it too, and the stated check does not fire, because nothing was
pushed.

Two stacked PRs, eight seconds apart:

```
15:37:09  #244 merged -> main
15:37:17  #245 merged -> claude/mac-duplicate-host-icons-phqu7w
```

#245 was based on #244's branch. GitHub retargets a stacked PR to the base's own
base when the base merges — but not within eight seconds, so #245 merged into a
branch that was itself already merged and closed. **Both PRs read "merged".**
Neither GitHub nor git reported anything wrong. None of #245's work was on
`main`:

```bash
$ git merge-base --is-ancestor b98445b origin/main
b98445b: NOT ON MAIN
$ git cat-file -e origin/main:polyhost/util/filelock.py
filelock.py: ABSENT from main
```

### Why the obvious fix is wrong

The orphan branch was cut before PR #243, so `git diff --stat origin/main
origin/<orphan>` showed **606 deletions** of work that had landed meanwhile —
the idle-timeout feature, `command_ids.py`, `poly_kybd.py`, two version bumps.
Merging it would have reverted all of that to recover 558 lines. By the time an
orphan is noticed it is nearly always too stale to merge.

### The recovery

The orphaned PR's own diff is recoverable exactly, because its base head is on
`main` already:

```bash
git checkout -B <new-branch> origin/main
git diff <pr-base-head> <pr-head> | git apply --3way
```

Here `git diff 45e5bce b98445b` reproduced exactly the 8 files and 558/53 GitHub
had shown for #245, and the 3-way apply kept main's newer `CLAUDE.md` sections
from #243 and #244 rather than reverting them.

⚠️ **Verify against the WORKING TREE, not `HEAD`.** `git apply` stages without
committing, so `git diff <pr-head> HEAD` compares against the branch point and
reads as total content loss — a minute of panic, every time. The right form
takes no second ref:

```bash
git diff <pr-head> -- <the PR's files>      # expect output only where main moved
```

Then grep every note back by name, both directions — the re-landed PR's and the
ones `main` gained while it was orphaned. A 3-way apply that quietly dropped one
side looks identical to one that did not.

The whole procedure, including how to tell an orphan from a PR that simply has
not merged, is the **`re-land-orphaned-pr`** skill.

### Preventing it

Merge the base. Wait for the stacked PR's `base.ref` to change to the default
branch. Then merge the stacked one. Merging both inside a minute is the whole
bug.
