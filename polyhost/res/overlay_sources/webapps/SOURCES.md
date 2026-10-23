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
| Confluence Cloud | the in-app shortcut dialog (`?`), transcribed 2026-10-13: General, Formatting, Navigation and Tables tabs for pages; Whiteboards tab for `confluence_whiteboard.yaml` |
| Google Docs | <https://support.google.com/docs/answer/179738> |
| Notion | <https://www.notion.com/help/keyboard-shortcuts> |
| Jira Cloud | the in-app shortcut dialog (`?`), transcribed 2026-10-13 |
| Bitbucket Cloud | the in-app shortcut dialog (`?`), transcribed 2026-10-13: "Within A Pull Request", "Diff View" and "Global" |
| Outlook on the web | Microsoft's "Keyboard shortcuts for Outlook", tab "Outlook on the web", <https://support.microsoft.com/en-us/office/keyboard-shortcuts-for-outlook-3cdeb221-7ae5-4c1d-8c1d-9e63216c1efd>, transcribed 2026-10-16 |

Jira and Bitbucket also live in this folder. Their earlier hand-drawn `jira_*`
and `bb_*` art was replaced with Fluent in 2026-10; only the two ESC marks
(`jira_mark.png`, `bitbucket_mark.png`) are still the reclaimed drawings.

Jira is exactly its in-app `?` dialog (Jira Cloud, transcribed 2026-10-13):
Global, Navigating issues, Issue actions and Board. The first pass from the
support pages was wrong in places: `W` (watch) and `1 2 3` are not Jira keys,
and `D` is "change status", not development status.

Bitbucket is exactly its in-app `?` dialog for a pull request. A first pass taken
from the support page and older notes was wrong in places and was replaced
wholesale: `R` is "mark file as read/unread" (not "request changes"), `U` is
"go to the pull requests list", Shift+E hides the enhanced word diff, and
`1 2 3`, `F`, `S` and Shift+L are not pull request keys at all.

Confluence is exactly its in-app `?` dialog (Windows/Linux, transcribed
2026-10-13). Pages and whiteboards get separate sets: a whiteboard binds bare
S/T/E/L/H/V to drawing tools, and the mapping routes a `/whiteboard/` URL on
`atlassian.net/wiki` to `confluence_whiteboard_template`. The dialog binds three
chords twice, once in page view and once in the editor; the page set shows the
editor's meaning:

| Chord | Shown (editor) | Not shown (page view) |
|---|---|---|
| `Ctrl+Shift+I` | Table | Open details panel |
| `Ctrl+Shift+D` | Insert markup | Create live doc |
| `Ctrl+Alt+E` | Align center | Select comment |

Also left out: `Ctrl+Alt+[` / `]` (each is both "resize table" and "insert
row"), the arrow-key table edits, and Alt+F9 / Alt+F10 / Shift+F10 (toolbar
focus). Undo and redo are not in the page dialog, so the page set no longer
draws them; the whiteboard set does (`Ctrl+Z`, `Ctrl+Shift+Z`). Strikethrough
(`Ctrl+Shift+S`) is not in the dialog either and was dropped.

### Outlook on the web

`web_outlook.yaml` had 8 keys of reclaimed hand-drawn art (`owa_*`). In 2026-10
it moved to Fluent and to 45 keys, all from the "Outlook on the web" tab of
Microsoft's page (the default shortcut set). Only the ESC mark (`owa_mark.png`)
is still the reclaimed drawing.

- **Ctrl+U** is "mark unread" in the message list and "underline" in the
  editor. Bare `U` already shows Mark unread, so Ctrl+U shows Underline.
- **Ctrl+Shift+3** is "Go to Copilot" on the current page and is drawn with
  Fluent `Sparkle` (Fluent has no Copilot glyph).
- **Shift+N / Shift+E / Shift+L** are People-module keys (new contact, edit
  contact, new contact list). The page lists them only under People.
- Left out: the arrow, Home/End and PageUp/PageDown navigation, Tab/F6 focus
  moves, Alt+. / Alt+H / Alt+V ribbon focus, Shift+F5 (browser refresh), and
  the calendar's Alt+Up/Down and Alt+PageUp/PageDown, whose page rows name the
  opposite direction from the arrow on the key.
- **macOS**: the page gives Windows chords only. Single keys and the standard
  editor chords (Cmd+S/K/B/I/U/X/C/V/Z/A) are drawn. Ctrl+R and Ctrl+Enter keep
  their earlier `CMDCTRL` binding. Every other Ctrl or Alt chord is
  `except: [macos]`, because there is no confirmed Mac chord and the Cmd form
  collides with the browser (⌘Q quits, ⌘⇧R reloads, ⌘Y opens history).
  `Insert` (Flag) is left off too: Mac keyboards have no Insert key.

### Deliberately excluded: the `g`-then-`x` chords

GitHub and GitLab both navigate with two-key sequences — GitHub's `g c` (code),
`g i` (issues), `g p` (pull requests); GitLab's `g p`, `g i`, `g m`. **None are
shown.** An overlay cell depicts what one keypress does, and the firmware has no
pending-chord state, so painting "issues" on `i` would be wrong for every press
that isn't preceded by `g`. Same rule as the Sublime `Ctrl+K` chords.

Confluence's Meta chords are excluded too: `Meta+Alt+C` (create page),
`Meta+Alt+T` (view attachments) and `Ctrl+Meta+.` (Rovo chat). Meta is the
Windows key there, which the OS claims for its own chords.

### Notes on specific bindings

- **Confluence headings are `Ctrl+Alt+1..6`**, not `Ctrl+1..6`. A widely-copied
  cheat sheet claims the latter; the in-app dialog says `Ctrl+Alt`, with
  `Ctrl+Alt+0` for a paragraph.
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

## macOS

All five specs serve Windows/Linux **and** macOS from one file each. The
generator writes a second `<output>_mac.*` set, in which `CMDCTRL` resolves to
Cmd. Every one of these apps is a Cmd-for-Ctrl app, so almost every Ctrl chord
became `CMDCTRL`. Chords with no Ctrl (GitHub `t`/`s`/`/`, GitLab `j`/`k`,
Confluence `e`, Notion `Tab`) are the same on every platform and were left
alone. Confluence Quick search is the exception: `Alt+Shift+Z` and `Ctrl+Alt+Q`
on Windows/Linux (the dialog lists both) and `Ctrl+Option+Z` on the Mac
(Atlassian's page, via search snippets), so it is three lines with disjoint
`only:`. Atlassian's page (via search snippets, 2026-10-13) gives `⌘⌥` for the
`Ctrl+Alt` navigation chords, so they stay `CMDCTRL`. It gives plain Ctrl on the
Mac for `Ctrl+[` (sidebar), `Ctrl+]` (comments panel) and `Ctrl+.` / `Ctrl+,`
(next/previous comment), so those four are `CTRL`. Whiteboard fullscreen is
`Shift+F` on Windows/Linux and `⌘F` on the Mac.

| Set | macOS source | Result |
|---|---|---|
| GitHub | [`github/docs` → `content/get-started/accessibility/keyboard-shortcuts.md`](https://github.com/github/docs/blob/main/content/get-started/accessibility/keyboard-shortcuts.md). This is the source of the docs page above, and it gives a "Command … (Mac) or Ctrl … (Windows/Linux)" row for every chord. | 5 → `CMDCTRL` |
| GitLab | [`gitlab-org/gitlab` → `doc/user/shortcuts.md`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/doc/user/shortcuts.md). This is the source of the docs page, with its "macOS shortcut / Windows shortcut" columns. | 2 → `CMDCTRL` |
| Confluence Cloud | The Atlassian page above (Mac = ⌘ for Ctrl, ⌥ for Alt, via search snippets; the page itself was unreachable). The editor's own keymap source, [`@atlaskit/editor-common` 126.1.3 `keymaps/index.js`](https://www.npmjs.com/package/@atlaskit/editor-common), declares each chord as `Mod-…`, which it renders as Ctrl on Windows and Cmd on Mac. | pages 40, whiteboards 19 → `CMDCTRL` |
| Google Docs | [Answer 179738, Mac tab](https://support.google.com/docs/answer/179738?hl=en&co=GENIE.Platform%3DDesktop), read through search snippets because the page was unreachable from the build container. | 36 → `CMDCTRL`, 2 remapped |
| Notion | The [Notion help page](https://www.notion.com/help/keyboard-shortcuts) writes every chord as `cmd/ctrl + …`, read through search snippets. | 20 → `CMDCTRL` |

**Remapped on macOS** (written twice under disjoint `only:` lists):

| Set | Action | Windows/Linux | macOS | Why |
|---|---|---|---|---|
| Google Docs | Find and replace | `Ctrl+H` | `⌘⇧H` | Google's Mac column. ⌘H is the system Hide. |
| Google Docs | Strikethrough | `Alt+Shift+5` | `⌘⇧X` | Google's Mac column. |

Nothing was dropped on macOS.

**Notes and uncertainties**

- **Confluence `Ctrl+Shift+I` (Table)**: the in-app dialog confirms the Windows
  chord (Formatting tab), and also binds it to "Open details panel" in page
  view (General tab). A search snippet of Atlassian's page gives `⌘+Shift+I`.
- **Confluence `Ctrl+Shift+M`** is labelled "Code", the dialog's own word. In the
  Atlaskit editor, `Mod-Shift-m` is *inline code*. The Mac form is `⌘⇧M`.
- **Browser-reserved chords.** These are drawn on macOS exactly as their Ctrl
  twins already are on Windows:
  - Notion ⌘N (New page), ⌘⇧N (New window) and ⌘L (Copy page URL) are taken
    by the browser (new window, incognito window, address bar) when Notion runs
    in a tab. They are correct in the Notion **desktop app**, which the same
    set also serves.
  - ⌘P (Print / Search) and ⌘O (Open) are intercepted by the web apps
    themselves.
- **No macOS system-reserved chord is drawn** in these five sets: no ⌘H, ⌘M,
  ⌘Q, ⌘Tab, ⌘Space, ⌃Space, ⌃-arrows or ⌘⇧3/4/5. Notion's ⌘⇧↑/↓ (move
  block) uses Cmd, not the Mission-Control ⌃ arrows.

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

**The J is trimmed at its top** (`trim`, default 3) — the free end of the stem —
so the stem shortens and the hook keeps its full curl.

Two things about that step are easy to get backwards. The cut must happen
**before** `ImageOps.flip`: after the flip the hook sits at the top, so trimming
there takes the hook off instead, which is the opposite end (shipped once that
way). And the unit is **final output pixels** — the mark is drawn 8x
supersampled, so a row of the drawing is an eighth of an output pixel and
trimming three of *those* would be invisible.

**Each hook is then nudged 2px back towards the centre in x only** (`converge`,
same final-pixel unit), tightening the pair horizontally without disturbing the
diagonal the gap runs along, and **the upper hook drops 2px** (`drop`), closing
the pair vertically from one side. Both are applied by the sign of that hook's
own offset rather than as fixed ±/rotation angle, so `converge` stays *inwards*
whichever way `gap` goes and `drop` follows whichever hook is actually on top.

⚠️ **`drop` is at its ceiling at 2.** At 3 the hooks touch and flood into a
single blob. Check that with a **connected-component count** (must stay 2), not
by eye or by ink: the merge costs about one pixel of ink, so a size comparison
reads as unchanged right through the failure.

### Notion

`nt.png` is a framed **serif N with a 2px extruded shade** (`../rect_mark.py`,
`serif=True, shade=2, shade_dir="tl"`). Notion's brand letter genuinely is a
serif, and the extrude is the 1-bit stand-in for the logo's depth.

Two deliberate choices, both of which have been queried:

- **The shade goes to the TOP-LEFT** (`shade_dir="tl"`). It was right+bottom
  first and was changed on request; an automated review later read the stale
  version of this paragraph and proposed "fixing" the code back to `"br"`. The
  code is correct — this text was the thing that was wrong.
- **Two adjacent edges only.** Drawing all four offset edges reads as a second
  box rather than as a shadow.

## Google Sheets, Slides, Gmail and Calendar

`gen_google_specs.py` writes `googlesheets.yaml`, `googleslides.yaml`,
`gmail.yaml` and `googlecalendar.yaml` from one table per app. Each row has a
Windows/Linux key and a macOS key. A row whose Mac key is the Windows key with
Ctrl replaced by Cmd becomes one `CMDCTRL` binding; every other row is written
twice, under `except: [macos]` and `only: [macos]`.

| Set | Source (read 2026-10-22 with headless Chromium) | Bindings, Windows/Linux and macOS |
|---|---|---|
| Google Sheets | <https://support.google.com/docs/answer/181110>, PC and Mac tables | 80, 79 |
| Google Slides | <https://support.google.com/docs/answer/1696717>, PC and Mac tables | 83, 80 |
| Gmail | <https://support.google.com/mail/answer/6594> (one table, "⌘/Ctrl") | 60, 60 |
| Google Calendar | <https://support.google.com/calendar/answer/37034> | 28, 28 |

Linux gets the PC keys. The ChromeOS tables are not used.

### Left out

- Bare letters, digits and Shift+letter keys in Sheets and Slides: the
  comment keys `j`, `k`, `r`, `e`, `u` and the presenting and video keys of
  Slides act only in one mode. Gmail's 34 single keys are drawn (`c` compose,
  `e` archive, `r` reply, `j`/`k` older and newer, `/` search, ...). They work
  only after the user turns "Keyboard shortcuts on" in Gmail's settings; with
  shortcuts off the keys type nothing outside a text field, so a cell that does
  nothing is the cost. Gmail's keys that need Shift on a US layout (`!` spam,
  `#` delete, `_`, `:`, `~`, `*`, `+`, `?`) are left out. Google Calendar's single keys are on by default and act whenever no
  text field has focus, so its set has them: `j`/`n` and `k`/`p` (next and
  previous range), `r`, `t`, `/`, `s`, `g`, the views `1`..`5` and `d`, `w`,
  `m`, `x`, `a`, and `c`, `e`, Backspace, Delete and `z`. Calendar's `+` (add a
  calendar) is left out, because the key that types `+` depends on the layout,
  and Esc (back to the grid) shows the program mark.
- Two-key sequences ("holding Ctrl+Alt, press n then c", Gmail's `g` then `i`):
  an overlay cell shows what one key press does.
- The menu keys (Alt+F, Alt+E, ...): Chrome and other browsers use different
  modifiers for them (Alt in Chrome, Alt+Shift elsewhere).
- Keys with plain arrows, Home, End, Page Up/Down, Tab, Enter or Esc alone, and
  the Mac rows that need Fn.
- Input-tools keys (only in non-Latin documents) and the second key of a row
  that lists two (Sheets Bold ⌘2, Strikethrough ⌘5, ...).
- Slides: Ctrl+Up/Down move a slide in the filmstrip and move an object in the
  canvas. The set shows the object meaning (Bring forward, Send backward, and
  with Shift Bring to front, Send to back). Alt+Left/Right (rotate by 15°) is
  left out because the browser uses it for Back and Forward. Ctrl+Shift+, and
  Ctrl+Shift+. are drawn as font size; in the video player they change the
  playback rate.
- Gmail ⌘M (spelling suggestions) on macOS: ⌘M minimizes the window there.

### Icons and program marks

- Fluent UI System Icons (MIT) and Material Symbols (Apache-2.0), the `GOOGLE`
  dict in `fetch_icons.py`. `narrower.png` is `shorter.png` (Fluent `Arrow
  Minimize Vertical`) turned 90°, because Fluent has no horizontal one.
- Google Calendar's day, week and month views reuse the Outlook web set's
  `calday.png`, `calweek.png` and `calmonth.png`.
- `gs.png` and `gsl.png` are labelled document frames from `../doc_mark.py`,
  like Google Docs' `gd.png`, with the calc and impress motifs.
- `gmail.png` and `gcal.png` are the Gmail and Google Calendar marks from
  Simple Icons (CC0-1.0 artwork), used to name the application
  (`../brand_marks.py`), as the Google Meet set does.

## draw.io, Excalidraw, Linear and Overleaf

Four specs, written by hand: `drawio.yaml`, `excalidraw.yaml`, `linear.yaml` and
`overleaf.yaml`. Each uses `CMDCTRL`, so one spec gives a Windows/Linux set and a
macOS set. Their icons are in `fetch_icons.py` → `DIAGRAM_ETC`, and the ESC marks
are the apps' own logos from Simple Icons (`diagramsdotnet`, `excalidraw`,
`linear`, `overleaf`; artwork CC0-1.0, nominative use, see `../brand_marks.py`).

| Set | Keys (Windows/Linux, macOS) | Source |
|---|---|---|
| `drawio_template` | 76, 76 | draw.io's `Actions.js` (shortcut of each action), the key bindings in `EditorUi.js`, and the shortcut sheet `app.diagrams.net/shortcuts.svg` (jgraph/drawio, branch `dev`, read 2026-10-22) |
| `excalidraw_template` | 62, 62 | Excalidraw's help dialog, `packages/excalidraw/components/HelpDialog.tsx` and `actions/shortcuts.ts` (branch `master`, read 2026-10-22) |
| `linear_template` | 41, 43 | the modifier shortcuts and single keys named in Linear's docs (`linear.app/docs/*.md`, all pages listed in `linear.app/llms.txt`, read 2026-10-22); Linear has no shortcut page of its own |
| `overleaf_template` | 21, 21 | Overleaf's page `docs.overleaf.com/navigating-in-the-editor/keyboard-shortcuts` and the editor key map `services/web/frontend/js/features/source-editor/extensions/shortcuts.ts` (overleaf/overleaf, branch `main`) |

App names:

- draw.io desktop 32.5.5, Linux package `drawio-amd64-32.5.5.deb`, run under
  Xvfb on 2026-10-22: process `drawio`, WM_CLASS `draw-io`, title "Untitled
  Diagram - draw.io". Windows `draw.io.exe` and macOS "draw.io" come from the
  product name in its `package.json` and were not checked on an install. The host
  keeps a Windows process name up to its first dot, so `draw.io.exe` is looked up
  as `draw`, which the mapping entry lists.
- Linear desktop: Windows `Linear.exe` and macOS "Linear" were not checked. Linear
  has no Linux desktop app.
- Excalidraw and Overleaf exist only in a browser.

Routing: each site is a `urls-contains` entry with a `url` gate on its own host
(`diagrams.net` / `draw.io`, `excalidraw.com`, `linear.app`,
`overleaf.com/project`), so a search page whose URL names the site does not
match. Title fallbacks: "draw.io", "Excalidraw" and "Online LaTeX Editor" (an
Overleaf tab is "<project> - Overleaf, Online LaTeX Editor" or "<project> -
Online LaTeX Editor Overleaf"). Linear has none: its tab titles are issue names.

Choices and keys left out:

- **Tool letters.** draw.io (A, S, D, F, C add text, note, rectangle, ellipse,
  line; X freehand) and Excalidraw (H, V, R, D, O, A, L, P, T, N, E, F, K, B, I, Q,
  W, S, G, and Shift+H/V/F) draw their bare tool keys, as the Miro set does: on a
  drawing canvas the canvas has the focus, not a text field. Excalidraw's digit
  alternatives (1 to 0) are left out.
- **Linear:** the single keys named in its docs are drawn (C create issue, A assign,
  I assign to me, X and Shift+X select, S status, Shift+S subscribe, F filter, /
  search, J/K next and previous, H snooze, T collapse, Shift+M milestone,
  Shift+P project): they act when no text field has focus. Its two-key
  sequences (G then I, O then I) and the triage digits 1, 2, 3 (triage view
  only) are left out.
- **draw.io:** Ctrl+Shift+Numpad +/- (font size; Ctrl+Shift+[ and ] are drawn
  instead), plain Delete, Backspace, Home, Enter, F2, Tab, arrows and the mouse
  actions. Alt+Shift+Y (synchronize) is left out because it acts only in some
  storage back ends. Ctrl+0 is "Custom zoom" in the key bindings, though the
  action list names it "Fit page width"; the set follows the key bindings.
  Ctrl+Shift+P (Format panel) is drawn although Firefox keeps it for a new
  private window, so in Firefox it does not reach the page; it has no other key,
  and it works in the Chromium browsers and the desktop app.
- **Excalidraw:** Send to back and Bring to front are Cmd+Option+[ and ] on macOS
  and Ctrl+Shift+[ and ] elsewhere, so those two keys are written per platform.
  PgUp/PgDn, Space and Enter are left out. The command palette is drawn on
  Ctrl+/ only: its other key, Ctrl+Shift+P, opens a private window in Firefox,
  and Excalidraw's own help dialog hides it there.
- **Browser keys.** A page cannot take the keys a browser reserves for windows
  and tabs (Ctrl+N, Ctrl+T, Ctrl+W, Ctrl+Shift+N/T/W, Ctrl+Tab, and Firefox's
  Ctrl+Shift+P). None of these sets draws one except the two Ctrl+Shift+P keys
  above. Other browser keys, such as Ctrl+Shift+I and Ctrl+Shift+A, are not
  reserved: a page that handles them first and cancels the event keeps them.
- **Linear:** Cmd/Ctrl+B and Cmd/Ctrl+I also mean bold and italic in Linear's text
  editor; the set draws their view meaning (board or list layout, details
  sidebar). Cmd/Ctrl+Shift+S (unsubscribe, and strikethrough in the editor) is
  left out because the docs give it both meanings. Cmd+Option+C (copy as
  Markdown) and Cmd+Shift+U (upload files) are documented for macOS only.
  Cmd/Ctrl+Delete (delete issue) is left out because the docs do not say whether
  it means Delete or Backspace on Windows.
- **Overleaf:** Tab and Shift+Tab (indent), the multi-cursor keys
  (Ctrl+Alt+arrows) and the cursor movement keys are left out. Ctrl+U,
  Ctrl+Shift+U and Ctrl+Space use Ctrl on macOS as well, as the source binds them.
