---
name: re-land-orphaned-pr
description: Recover work that a merge did NOT deliver to the default branch — a stacked PR merged into its base before GitHub retargeted it, a PR merged into an already-merged branch, or a push onto a branch whose PR had closed. Use when a PR reads "merged" but its files are missing from main, when `git merge-base --is-ancestor <head> origin/main` says not-an-ancestor, when a feature you shipped is absent from a fresh clone, or when asked "did that actually land / where did my change go". NOT for an ordinary merge conflict (just merge the base in) and NOT for a PR that is simply still open.
---

# Re-land work a merge did not deliver

A merged PR badge is not evidence the work reached the default branch. Three
ways it silently does not:

- **A stacked PR merged before GitHub retargeted it.** Merge the base PR and the
  stacked one within the same minute and the stacked merge lands on the base's
  BRANCH, which is itself already merged and closed. Both PRs read "merged"; the
  second one's content is nowhere. Seen 2026-09-19: #244 merged at 15:37:09,
  #245 at 15:37:17, and none of #245 reached `main`.
- **A push onto a merged branch.** Git reports a fast-forward, GitHub shows
  nothing, the commit is in no PR (this is the variant already in `CLAUDE.md`).
- **A merge queue or admin merge that took a stale base.**

The orphan is usually also **too stale to merge as-is** — by the time you notice,
the default branch has moved, and merging the old branch would revert whatever
landed in between. Re-landing on a fresh branch is the fix, not a second merge.

## 1. Confirm it is actually orphaned

Ancestry first — it is the only claim that matters, and it is one command:

```bash
git fetch origin main                       # or PolyKybd for the firmware
git merge-base --is-ancestor <pr-head-sha> origin/main \
  && echo "ON MAIN" || echo "NOT ON MAIN"
```

Then confirm by **content**, because a badge and an ancestry check can both be
misread and a missing file cannot:

```bash
git cat-file -e origin/main:<a file the PR added> && echo present || echo ABSENT
git show origin/main:<a file the PR changed> | grep -c '<a symbol it added>'
```

If the head IS an ancestor and the files are there, stop — nothing is orphaned.

## 2. Measure the damage before re-merging anything

```bash
git log --oneline origin/main..origin/<orphan-branch>     # what is only there
git diff --stat origin/main origin/<orphan-branch>        # what a merge would DO
```

⚠️ **Read the second one carefully.** Large deletions of files the PR never
touched mean the branch predates work now on main, and merging it would revert
that work. That is the signal to re-land rather than merge.

## 3. Re-land on a branch cut from the CURRENT default

The orphaned PR's own diff is recoverable exactly, because its base head is on
main already:

```bash
git checkout -B <new-branch> origin/main
git diff <pr-base-head> <pr-head> | git apply --3way
```

`<pr-base-head>` is `base.sha` from the PR (for a stacked PR, the base PR's
head). The 3-way apply keeps whatever main gained in between — which is the
whole point of doing it this way rather than cherry-picking.

## 4. Verify the re-land is faithful

Two checks, and do both:

```bash
# 1. identical to what was reviewed, for the PR's own files
git diff <pr-head> -- <the PR's files>
```

⚠️ **Compare against the WORKING TREE, not `HEAD`.** `git apply` stages the
change but does not commit, so `git diff <sha> HEAD` still compares against the
branch point and reads as total content loss. This costs a minute of panic every
time; the form above (no second ref) is the right one.

Expect output only where main legitimately moved — a shared file like
`CLAUDE.md` that both sides appended to. Read those hunks; they should be
main's additions, not your deletions.

```bash
# 2. grep every note back by name — both yours and main's
grep -c '<a distinctive phrase from the orphaned PR>' CLAUDE.md
grep -c '<a distinctive phrase main gained meanwhile>' CLAUDE.md
```

Then run the suite. A re-land that drops a test is the failure this step exists
to catch.

## 5. Open the new PR

Title it as a re-land and **carry the evidence in the body**: the ancestry
command and its output, the `cat-file` showing the file absent from main, and
why the old branch cannot simply be merged. A reviewer's only real question is
"is this the same content on a current base", so answer it with the two
verifications from §4 rather than with prose.

Say explicitly that it is **no new code**, when that is true. It usually is.

## Output format

```
ORPHANED: <pr> — head <sha> is not an ancestor of origin/main
  absent from main: <file>, <symbol>, …
  branch is stale by: <N commits>, would revert <what>
RE-LANDED: <new-branch> ← git diff <base-head> <head>, 3-way onto <main-sha>
  faithful: <N files>, identical except <the legitimate drift>
  suite: <N tests>
PR: <url>
```

## Pitfalls

- **Do not merge the orphaned branch to "fix" it.** It is stale by construction;
  that is how you revert someone else's feature while fixing your own.
- **Do not reopen the merged PR.** It is closed and its base may no longer exist.
  A new PR against the current default is the honest record.
- ⚠️ **Never `git checkout -- <file>` to undo a local experiment while
  uncommitted work is in the tree** — it restores from HEAD and takes the
  uncommitted work with it. Use a `cp` backup for anything you intend to put
  back (this bit twice in one session; see the mutation-sweep note in
  `docs/testing.md`).
- **Stacked PRs are the common cause, so prevent the next one**: merge the base,
  wait for GitHub to retarget the stacked PR to the default branch (its `base.ref`
  changes), and only then merge it. Merging both inside a minute is what breaks.
- **Check the other direction too.** If the orphan branch received commits AFTER
  the base merged, they are orphaned as well and `git log origin/main..` is what
  lists them.
