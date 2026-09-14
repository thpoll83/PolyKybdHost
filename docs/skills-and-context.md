# Mirrored skills, and what actually costs context

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## Mirrored skills (`qmk_firmware` ↔ `PolyKybdHost`)

Nine skills exist in **both** repos and are kept **byte-identical**:
`add-gated-hid-command`, `check-mirrored-artifacts`, `cross-repo-pr-sweep`,
`mutation-test-suite`, `polykybd-github-release`, `prune-claude-md`,
`session-retro`, `triage-pr-review`, `update-polykybd-docs`. A skill loads only from the repos a session has attached,
so one that describes cross-repo work is unreachable from a session opened on the
other repo alone — which is what happened to `mutation-test-suite`, extended to
cover Python/unittest suites while living only in the firmware repo.

⚠️ **They had already drifted, and every difference was pure loss — not repo-specific
tailoring.** Measured 2026-09-07 before harmonising: `session-retro` lacked the whole
open-PR-sweep section on the host side, `update-polykybd-docs` lacked its Images
section there, and `polykybd-github-release` was missing the shallow-clone warning on
the host side and the corrected WinCompose `status.txt` ordering on the firmware side —
i.e. each copy was the newer one for a different note. Nothing anywhere flagged it,
because a skill has no build, no test and no reviewer.

**So the rule is copy, never fork**: edit one, `cp` it to the other, and check with

```bash
for s in add-gated-hid-command check-mirrored-artifacts cross-repo-pr-sweep \
         mutation-test-suite polykybd-github-release prune-claude-md \
         session-retro triage-pr-review update-polykybd-docs; do
    cmp -s /home/user/qmk_firmware/.claude/skills/$s/SKILL.md \
           /home/user/PolyKybdHost/.claude/skills/$s/SKILL.md \
      && echo "$s: ok" || echo "$s: DRIFTED"
done
```

A firmware-specific section in the host's copy (or the reverse) costs a reader one
skipped paragraph; a fork costs a note that only one repo ever sees. Take the first.
If a skill ever genuinely needs to differ per repo, split the differing part into a
separate skill rather than forking the shared one.

### Where shared content can live, and what actually costs context

⚠️ **A shared `CLAUDE-SHARED.md` imported by both repos would NOT reduce context.**
Claude Code's memory docs say it twice: *"imported files still load and enter the
context window at launch"*, and *"Splitting into `@path` imports helps organization
but doesn't reduce context, since imported files load at launch."* The same is true
of a `.claude/rules/` file with no `paths:` frontmatter. So single-sourcing the text
fixes **drift** and buys nothing in tokens — worth knowing before the idea is
proposed again, because it is an obvious-looking saving that is not one.

- **The prize is small in any case — measured 2026-09-10.** Across the three
  sections headed *"(all PolyKybd repos)"*, only **2,975 B** is byte-identical
  between `qmk_firmware` and `PolyKybdHost`: the docstring-coverage rule, the
  verify-an-AI-finding rule and the green-board rule. Everything else under those
  headings has diverged into genuinely repo-specific material (qmk's
  inherited-upstream scanner note means nothing in the host repo; the host's
  Sourcery `nosemgrep` note means nothing in the firmware), and the two branching
  rules are the same rules written twice in different words.
- ⚠️ **A shared file also has nowhere safe to live.** It must sit inside a repo to
  be version-controlled, and then a session that attached only the OTHER repo cannot
  resolve it — the same silent absence that left `mutation-test-suite` unreachable
  from host-only sessions and the five `keyboards/**/.claude/skills/` skills
  invisible. The docs add a second silent failure: an import resolving outside the
  working directory raises a one-time approval dialog, and *"If you decline, the
  imports stay disabled and the dialog doesn't appear again."*
- ✅ **What DOES reduce context**, in increasing order of saving: a `docs/*.md` file
  read on demand; a **path-scoped rule** (`.claude/rules/*.md` with `paths:`
  frontmatter), which loads only when Claude reads a matching file; and a **skill**,
  which costs nothing at all until it is invoked. The docs are explicit — *"If an
  entry is a multi-step procedure or only matters for one part of the codebase, move
  it to a skill or a path-scoped rule instead."* **No path-scoped rule exists in
  either repo yet**, and it is the obvious home for anything that only matters while
  editing one directory.
- **Block-level HTML comments are STRIPPED before injection**, so `<!-- … -->` in a
  CLAUDE.md costs nothing — usable for maintainer notes, or as machine-readable
  fences round a block that is meant to stay identical across repos.
- ⚠️ **Both files are still past the documented target of "under 200 lines", and
  that is the standing argument for EXTRACTION over adding.** Measured 2026-09-10,
  before and after a deliberate pass: qmk **6,178 -> 2,296 lines (485 -> 176 KB)**,
  host **3,198 -> 1,623 (266 -> 136 KB)**. Nothing was deleted — eighteen subsystems
  moved WHOLE into `docs/` (host) or `keyboards/polykybd/*.md` (firmware), plus the
  reviewer forensics into the `triage-pr-review` skill, each leaving a pointer that
  carries only the rules binding code outside its own file. The notes are
  measurements nobody can re-derive, so the trade is size against re-derivability;
  extraction settles it without giving anything up. `/doctor` proposes trims, and
  `claudeMdExcludes` skips a file wholesale if one is ever in the way.
- ⚠️ **A move RE-BASES every relative path in the moved text, and a LINK is the half
  that breaks silently.** Same hardcoded-`../`-depth trap the five relocated skills
  hit, except prose is worse than a script: nothing runs it, so nothing fails.
  Measured this pass — moving the font-pack notes from the repo root to
  `keyboards/polykybd/` turned `](../AdafruitGFX/CLAUDE.md)` into a link at
  `keyboards/AdafruitGFX/`. Check the files you touched, never the tree (an upstream
  fork has thousands of `.md`):
  ```bash
  python3 - <<'EOF'
  import pathlib, re
  for f in list(pathlib.Path("keyboards/polykybd").glob("*.md")) + [pathlib.Path("CLAUDE.md")]:
      for m in re.finditer(r'\]\(([^)#][^)]*)\)', f.read_text()):
          t = m.group(1)
          if not t.startswith(("http", "#")) and not (f.parent / t).exists():
              print(f, "->", t, "=>", (f.parent / t).resolve())
  EOF
  ```
  ⚠️ A path into a **sibling repo** resolves outside the checkout and always reports
  missing in a session that did not attach it — read the RESOLVED path, not the
  exists() bit.


