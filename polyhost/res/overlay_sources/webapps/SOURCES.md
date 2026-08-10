# Browser-hosted app overlays — sources & licenses

Five overlay sets sharing one icon folder: **GitHub**, **GitLab**, **Confluence
Cloud**, **Google Docs**, **Notion**.

They are grouped because they share a large command vocabulary — search, edit,
comment, submit, and the rich-text run of bold / italic / link / lists /
headings. Five copies of the same ~30 PNGs would be noise; the per-app split
lives in the five `*.yaml` binding files.

## Shortcuts

Every set is from the vendor's **own** documentation:

| Set | Source |
|---|---|
| GitHub | <https://docs.github.com/en/get-started/accessibility/keyboard-shortcuts> |
| GitLab | <https://docs.gitlab.com/ee/user/shortcuts.html> |
| Confluence Cloud | <https://support.atlassian.com/confluence-cloud/docs/keyboard-shortcuts-markdown-and-autocomplete/> |
| Google Docs | <https://support.google.com/docs/answer/179738> |
| Notion | <https://www.notion.com/help/keyboard-shortcuts> |

### Deliberately excluded: the `g`-then-`x` chords

GitHub and GitLab both navigate with two-key sequences — GitHub's `g c` (code),
`g i` (issues), `g p` (pull requests); GitLab's `g p`, `g i`, `g m`. **None are
shown.** An overlay cell depicts what one keypress does, and the firmware has no
pending-chord state, so painting "issues" on `i` would be wrong for every press
that isn't preceded by `g`. Same rule as the Sublime `Ctrl+K` chords.

Confluence's `Win+Alt+C` (create page) is excluded too: the GUI/Win modifier
combination is not one of the nine representable modifier variants.

### Notes on specific bindings

- **Confluence headings are `Ctrl+Alt+1..6`**, not `Ctrl+1..6`. A widely-copied
  cheat sheet claims the latter; Atlassian's own page says `Ctrl+Alt`, which is
  what shipped.
- **Google Docs `Ctrl+Alt+Shift+A`** (open discussion thread) is one of only two
  bindings in this whole batch that lands on the third (`extra`) overlay layer.
- **GitHub `S` and `/`** both focus search, and GitLab is the same; both keys
  carry the icon rather than picking one arbitrarily.
- **Notion is wired twice** — a native mapping entry for the desktop app and a
  `urls-contains: notion.so` entry under the browser — since it is commonly run
  either way.
- Notion headings (`Ctrl+Shift+1/2/3`) are **omitted**: Notion's official
  shortcut page does not list them, and this batch's rule is that an unsourced
  binding does not ship.

## Icons

| File(s) | Source | License |
|---|---|---|
| all shortcut icons except `numberlist` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `numberlist` | [Google Material Symbols](https://fonts.google.com/icons) (`format_list_numbered`) | Apache-2.0 |
| `gh.png`, `gl.png`, `cf.png`, `gd.png`, `nt.png` (ESC program marks) | Custom-drawn, `../program_marks.py` | GPL-3.0-or-later (this repo) |

**None of the program marks are the real logos.** The GitHub Invertocat, the
GitLab tanuki, the Atlassian/Confluence mark, the Google Docs mark and the
Notion mark are all trademarks we may not redistribute; each ESC cell shows a
drawn tile with an initial (G, GL, C, D, N) instead.

Fluent ships **no ordered-list glyph** — every `Text Number List *` name 404s,
and its nearest match `Text Number Format` draws "ABC 123", which reads as
alphanumeric *formatting*, not a numbered list. That is the gap Material Symbols
is kept for; it is rendered at `weight=300` per the house note in
`../material_symbols.py`.

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are both GPL-3.0-compatible
(Apache-2.0 is GPLv3-compatible but *not* GPLv2 — usable only since the 2026-06
relicense).

## Mapping

The four browser-only sets hang off the existing browser entry's
`urls-contains:` block (`github.com`, `gitlab.com`, `atlassian.net/wiki`,
`docs.google.com/document`) — the same mechanism Miro, Jira and web Outlook
already use. That needs the browser extension (or the macOS AppleScript
fallback) for URL detection; see `browser-extension/README.md`.

## Regenerate

```bash
python polyhost/res/overlay_sources/webapps/fetch_icons.py
for m in github gitlab confluence googledocs notion; do
  python scripts/generate_app_overlays.py \
      polyhost/res/overlay_sources/webapps/$m.yaml --preview /tmp/${m}_preview
done
```

## Program marks

**GitHub (`gh.png`) and GitLab (`gl.png`) use the REAL logos**, rendered from
**Simple Icons** (`simple-icons/simple-icons`, `icons/github.svg`,
`icons/gitlab.svg`) whose artwork is **CC0-1.0** — so redistributing a rendered
copy in this GPL-3.0-or-later repo is fine. CC0 grants no *trademark* rights;
the basis for using them is **nominative use** — each mark identifies the very
service its overlay set is for, unmodified, no endorsement implied. Both are
plain monochrome silhouettes, which is exactly what survives the 1-bit 72x40
downscale. See `../brand_marks.py`.

**Google Docs (`gd.png`) is a labelled document frame** instead: Google's logo
is not ours to ship, and Docs *is* a document, so it gets the Fluent `Document`
glyph (MIT) with the module name inside — same builder as the LibreOffice marks
(`../doc_mark.py`), which asserts nothing touches the page outline. It is a
**full-cell** mark (`program_icon_region: [72, 40]`, authored 1:1) because a
5px-tall label does not survive being rescaled; the cost is that it covers the
firmware-drawn `Esc` legend.

**Confluence (`cf.png`) and Notion (`nt.png`) keep the drawn letter tiles**
(`../program_marks.py`) — the generic-document treatment was tried for them and
rejected: as page/wiki apps they came out near-identical to Google Docs, with
only a four-letter label to tell them apart at keycap size.

### Notion

`nt.png` is a framed **serif N with a 2px extruded shade** (`../rect_mark.py`,
`serif=True, shade=2`). Notion's brand letter genuinely is a serif, and the
extrude — right + bottom edges only, offset down-right — is the 1-bit stand-in
for the logo's depth. Drawing all four offset edges would read as a second box
rather than as a shadow.
