# Code review conventions — the long form

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## Code review conventions (all PolyKybd repos)

- **Docstring coverage: ignore CodeRabbit's "Docstring Coverage … threshold 80%" pre-merge check.** That 80% target is a CodeRabbit default, **not** a project policy — the check is non-blocking and we deliberately do not chase it. Do **not** add docstrings to existing functions just to satisfy it (out-of-scope churn). Document new code where a docstring genuinely helps a reader, and no more.

- **Verify an AI reviewer's finding against the code before acting on it — several
  arrive confidently wrong.** Of 7 CodeRabbit findings on one PR (2026-08-01), 3
  were false and **two were refuted by their own evidence**: a "PACK_VERSION 3
  needs a matching host change" (the host never parses the PlyX version — it
  checks magic + slot fit and defers the ABI/RAM contract to the firmware loader
  by design); a "the unpacker is not defined" whose own analysis script had
  returned 159 bytes of output, i.e. it reasoned without the code (the decoder
  was 90 lines above in the same file); and an `int8_t` "signed-overflow UB" that
  the StackOverflow answer it quoted explicitly contradicts (a sub-`int` operand
  promotes to `int`, so the narrowing back is *implementation-defined*, not UB —
  though a real non-termination hazard did lurk nearby, so the fix was taken for
  a different stated reason). **The rule is verify, not dismiss:** the same review
  round produced one genuinely valuable finding (a bulk repair loop running inline
  in `raw_hid_receive()`, worth seconds of blocked main loop) that was adopted.
  Reply to the false ones with the evidence so they are not re-raised.

- ⚠️ **A green board is NOT evidence a reviewer read your code, and every bot here
  has a way of going quiet that looks like a clean pass.** The standing check, in
  full, is `pull_request_read` `get_reviews` plus the summary comment's body:
  - a review counts only when its **`commit_id` equals the PR head sha** AND its
    **body is not a refusal notice** (a quota / diff-too-large refusal is a real
    review object carrying the head sha, so the sha alone reads as reviewed);
  - **and the absence of a review object proves nothing either** — a CLEAN
    CodeRabbit pass creates none, it edits its summary comment to say *"No
    actionable comments were generated"*. So read the summary body's `📥 Commits`
    range alongside `get_reviews`.
  - **No check run answers this question.** A green `Sourcery review` /
    `Greptile Review` / CodeRabbit status has accompanied a PR that nothing read,
    measured, more than once.
  - ⚠️ **A check run's CONCLUSION can say `success` while its TITLE reports an
    open alert.** On #255 `CodeQL` read `completed / success / "1 new alert"`
    with an error-severity finding outstanding; a rollup that reads only the
    conclusion calls that commit green. **The alert count is in the title —
    read it, not the conclusion.**
  - ⚠️ **Sourcery stops reviewing mid-PR** with `conclusion: skipped`,
    `"⏭️ Auto re-review limit reached"`, after enough pushes. It is an honest
    state and easy to miss in a list of green rows: from that point every
    further push is unreviewed by it. On a long PR, expect to lose Sourcery
    partway and ask CodeRabbit by hand for the pushes that matter.
  **The full field guide — which bot goes quiet in which disguise, the sticky
  walkthrough, the Merge Risk sha, the false `✅ Addressed in <sha>` attribution,
  the quota shapes and the rate-limit arithmetic — is the `triage-pr-review`
  skill**, mirrored in both repos. Load it when you are actually triaging a PR;
  it is ~51 KB that does not belong in every session's context.

- ⚠️ **A review pinned to a MERGE COMMIT reviews the BASE, not your diff — and the
  `commit_id`-vs-head check above does NOT catch it.** That check finds a review of
  an older version of *this branch*; this is a review of somebody else's code that
  reached the branch through a `Merge remote-tracking branch 'origin/main'`. On
  host#248 (2026-09-22) Greptile's header read *"should not merge until
  recovery-copy naming prevents one preserved corrupt settings file from
  overwriting another"* at confidence 4/5, last-reviewed commit `ec2710fc` — a merge
  commit — while `polyhost/settings.py` was **not among the PR's changed files at
  all**. The finding was real code and a real (if narrow) bug; it simply belonged to
  `main` rather than to the PR it was blocking. **Read `pull_request_read`
  `get_files` before acting on a finding**, not the sha alone: a severity label on a
  file your branch never touched is an argument about a different PR.

- ⚠️ **An image is INVISIBLE to the reviewers, so *"that asset is not present in the
  repository"* on a `.png` is structurally false — every time.** CodeRabbit names the
  filter outright in its own comment (`⛔ Files ignored due to path filters (1) …
  is excluded by `!**/*.png``), and Sourcery behaves the same way: on docs#79
  (2026-09-14) it raised the missing-asset finding against
  `tray-menu-forwarder.png` while the commit adding it, `Bin 0 -> 15878 bytes`, sat
  in the same PR and the build emitted its WebP. The reviewer sees a markdown
  reference and no file, and reports the only thing that shape can mean. **Reply
  with the adding commit and that path-filter line**; never "fix" it by re-adding an
  image that is already there.
- **A reviewer's CONCLUSION can be sound while its EVIDENCE is invented — and the
  evidence is worth correcting separately.** The existing rule above says verify and
  decline the false ones. The 2026-08-23 round on PolyKybd#35 sharpened it: **3 of 4
  findings had a defensible conclusion resting on a claim that was simply not true of
  the repo.** (1) *"the netlist shows LED1 uses `WS2812B-Mini`/`C527089`"* — real
  identifiers, read out of a **2024 generated netlist** describing a design two board
  revisions old. (2) *"a later BOM exporter reading `MPN` will produce a wrong
  manufacturer id"* — there **is no `MPN` column** in the BOMs that repo generates; the
  exporter reads `Value`, which was already correct. (3) *"omits the standard footprint
  header"* — it had been added two commits earlier. Only the fourth (an exposed pad
  drawn 5× too tall) was right as stated, and that one was genuinely valuable.
  - **Take the conclusion when it stands on its own merits** — the stale-netlist finding
    led to a real improvement (a library footprint should not restate what the schematic
    instantiates) even though its evidence was junk. Say so explicitly: *"fixed, but for
    a different reason"*.
  - ⚠️ **Reply with the counter-evidence anyway, because CodeRabbit stores a learning
    from the thread.** It did: after being shown the 2024 timestamps and the BOM
    history it recorded *"`*.kicad_sch` files are the authoritative current schematic
    sources… do not use `poly_kb.net`, `poly_kb.xml`… these artifacts are stale"*. That
    is a durable repo-wide fix bought with one reply. Declining silently buys nothing.
  - ⚠️ **The mirror case: a finding can be right about the code and STILL wrong to
    fix, when the code's contract is parity with something else.** Greptile's #200
    finding was correct in every particular — `oled_preview.Renderer.bbox()`
    measures a substituted `'!'` for a missing glyph in a `HINT_SMALL` run while
    `draw()` skips it. Applying the one-line fix would have been wrong anyway: that
    asymmetry is the FIRMWARE's (`kdisp_gfx_text_bbox_in` substitutes with no
    `small` guard; `kdisp_write_gfx_char_half` returns 0), and the module exists to
    mirror the C, not to be internally consistent. "Verify the finding" is not
    enough here — the finding verified fine; what needed checking was whether the
    **remedy** violated a contract the reviewer could not see.
    - **The response that leaves something behind is to pin BOTH halves as a
      test**, with the reasoning in the docstring, so the next reader (or the next
      bot) does not re-raise it — and to say on the thread where the real fix
      belongs. Declining without that just resets the clock.
    - ✅ **And that is what closed it: the real fix landed upstream (qmk#252,
      2026-09-01), so the pin has been INVERTED here.** `Renderer.bbox()` now skips
      an unresolvable glyph in a `HINT_SMALL` run instead of substituting `'!'`,
      matching `kdisp_gfx_text_bbox_in`; the test that pinned the old behaviour is
      `test_small_skips_a_missing_glyph_instead_of_substituting_bang`, ported from
      the C's own new case. **The lesson is unchanged and this is its payoff** —
      declining a correct finding on parity grounds only holds while somebody
      carries it to the end the contract points at. ⚠️ It also means a parity pin
      is a LIABILITY the moment the other side moves: nothing here would have
      failed, so the divergence would simply have flipped direction in silence.
      When you pin one, name the upstream change that would invalidate it.

- **When two reviewers disagree about the same code, WRITE THE TEST — it
  adjudicates, and it is faster than arguing.** On PR #154 (2026-08-07) Sourcery
  asked for a regression test on a parser input shape while CodeRabbit claimed
  that shape silently returned an empty result. Writing the test settled it in
  seconds: CodeRabbit was right, and the docstring had been advertising a shape
  the code dropped. The general form is worth internalising — a "testing
  suggestion" from one reviewer is often the cheapest way to check a
  *correctness* claim from another, and unlike a code-reading argument it leaves
  a permanent guard behind. It also inverts nicely: a test that passes
  immediately is evidence the finding was wrong, which is exactly the evidence
  to paste in the reply.

- **A guard that ENUMERATES its siblings will go stale — delete it rather than
  add the missing term, and distrust a test that documents the workaround.**
  `find_matching_entry` (`handler/common.py`) split the window title only
  `if title and (has_starts_with or has_ends_with)`, while the *third* word-based
  matcher below it, `has_contains`, was never added to that list. So
  `titles-contains` could not match unless the entry happened to declare a
  sibling key it did not need — and the shipped browser entry's Miro / web-Outlook
  / Jira overlays, which route purely on `titles-contains`, **had never once
  rendered** since they were added (#156, 2026-08-11). Two things to carry over:
  - **The fix is to drop the gate** (`words = title.split() if title else []`),
    not to add `or has_contains`. Every branch under it already checks its own
    `has_*` flag, so the gate's only job was to restate them and stay in sync —
    exactly what it failed at, and one more term re-arms the same trap for
    whoever adds a fourth matcher.
  - ⚠️ **The test suite was green throughout, because the test encoded the
    workaround as the contract**: it built its fixture as
    `entry(sw={"x": {}}, contains={...})` with the comment *"has both starts_with
    and contains so the title is split into words"*. That dummy `titles-startswith`
    is the only reason it passed. A fixture carrying an unexplained extra key to
    make the feature under test work is a **bug report**, not setup — chase it.
- **Sourcery's `dangerous-subprocess-use-audit` (opengrep) fires on ANY
  non-literal argv and will hold the check red forever — resolve it with a
  `# nosemgrep` marker plus a written audit, not by contorting the code.** It is
  an *audit* rule: it asks a human to confirm where the argv came from, which is
  the whole remedy. A `subprocess.run(list, ...)` with the default
  `shell=False` has no shell to inject through, and the rule's suggested
  `shlex.quote` escapes for a **shell string** — applied to an argv element it
  just corrupts the value. ⚠️ **The marker only applies to the line IMMEDIATELY
  following it**, so putting it at the top of an explanatory comment block (where
  it reads best) silently does nothing and the check stays red — cost an extra
  push on #154. Record the reasoning above the block, the marker directly above
  the call. Leaving the check red instead is the worse option: an always-red
  check is one people learn to scroll past, and the next real finding rides in
  behind it.

