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
| `gh.png`, `gl.png` (ESC program marks) | [Simple Icons](https://github.com/simple-icons/simple-icons) via `../brand_marks.py` | CC0-1.0 (artwork) |
| `gd.png` (ESC program mark) | Custom-drawn, `../doc_mark.py` | GPL-3.0-or-later (this repo) |
| `nt.png` (ESC program mark) | Custom-drawn, `../rect_mark.py` | GPL-3.0-or-later (this repo) |
| `cf.png` (ESC program mark) | Custom-drawn, `../geo_marks.py` | GPL-3.0-or-later (this repo) |

**GitHub and GitLab get their real marks; the other three do not.** The
Invertocat and the tanuki are published as plain monochrome artwork that Simple
Icons redistributes under CC0, and they read cleanly as a 1-bit silhouette — CC0
settles the *copyright*, and using them here is nominative (the mark denotes the
very app the overlay set is for). The Google Docs and Notion marks come with no
such release, so they are drawn substitutes; Atlassian's Confluence mark is a
trademark too, but its *construction* — a mirrored J rotated into a pair of
hooks — is a shape we can draw ourselves (`../geo_marks.py`).

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

**Confluence (`cf.png`) and Notion (`nt.png`) do NOT use the document frame** —
the generic-document treatment was tried for them and rejected: as page/wiki
apps they came out near-identical to Google Docs, with only a four-letter label
to tell them apart at keycap size.

### Confluence

`cf.png` is two thickened, vertically-mirrored **J**s rotated 70° and 250° CCW
(`../geo_marks.py`). It replaced a drawn "C" letter tile.

Two things are worth knowing before tuning it.

**The `gap` is signed, and the sign is what moves the space.** Each hook is
displaced along its own rotation axis; flipping the sign is the equivalent of
padding the glyph box on the left rather than the right before rotating, since
the rotation turns that padding into a displacement along the rotated x-axis.
Each of the two configurations is *individually* 180°-symmetric, which makes it
tempting to conclude they collapse into one image — they do **not** (verified by
hash), because the 180° rotation swaps the two hooks as well as their positions.
An earlier revision of this file claimed otherwise; it was wrong.

**The face decides the mark.** Ten sans faces were rendered as the finished
mark and compared side by side; measured on a 200px J (hook overhang past the
stem, and box width/height):

| face | w/h | overhang | reads as |
|---|---|---|---|
| Rubik | 0.82 | 0.07 | barely hooks — two thick slabs |
| DejaVu Sans | 0.37 | 0.43 | a straight stem — two *bars*, not hooks |
| **Lato** | **0.48** | **0.60** | **the pick** |
| FreeSans | 0.62 | 0.67 | hook curls right over — too curvy |

**Lato is not a system font**, so `geo_marks` fetches `Lato-Bold.ttf` from
google/fonts (OFL) at draw time, the way `brand_marks` fetches its SVGs. That
only matters when *regenerating*: `ensure_confluence` leaves a committed
`cf.png` alone, so a normal fetch-script run touches no network for it. With no
network it falls back to `_SANS` (a preference order, not a chain of equals) and
prints a warning that the mark **will** differ from the committed one — treat
that output as a candidate, not a reship. No Black weight exists in any of
these, so the stroke is grown by dilating Bold.

**The J is trimmed at the top before it is rotated** (`trim`, default 3),
thinning the hook's outer bar while leaving the stem. The unit is **final
output pixels**: the mark is drawn 8x supersampled, so a row of the drawing is
an eighth of an output pixel and trimming three of *those* would be invisible.

### Notion

`nt.png` is a framed **serif N with a 2px extruded shade** (`../rect_mark.py`,
`serif=True, shade=2`). Notion's brand letter genuinely is a serif, and the
extrude — right + bottom edges only, offset down-right — is the 1-bit stand-in
for the logo's depth. Drawing all four offset edges would read as a second box
rather than as a shadow.
