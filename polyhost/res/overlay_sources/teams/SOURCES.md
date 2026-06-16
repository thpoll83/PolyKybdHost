# Microsoft Teams overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild byte-identical overlays.

## Shortcuts

Target: the **new Microsoft Teams** desktop app on **Windows**. Official reference:
- https://support.microsoft.com/en-us/office/keyboard-shortcuts-for-microsoft-teams-2e8e2a70-e8d8-4a19-949b-4c36dd5292d2
  (the support page `WebFetch`-403s; verified against multiple shortcut aggregators
  whose lists agree with it — UC Today, howtogeek, the per-shortcut MS Support help
  articles surfaced via WebSearch, June 2026.)

27 shortcuts placed across the representable channels:

- **Ctrl** (primary R): Ctrl+E Search/command bar, Ctrl+N New chat, Ctrl+, Settings,
  Ctrl+/ Show commands, Ctrl+. Keyboard shortcuts, Ctrl+O Attach file,
  Ctrl+= Zoom in, Ctrl+- Zoom out, Ctrl+0 Reset zoom,
  Ctrl+1..6 app-bar nav (Activity / Chat / Teams / Calendar / Calls / Files).
- **Ctrl+Shift** (combo R): Ctrl+Shift+M Mute toggle, Ctrl+Shift+O Camera toggle,
  Ctrl+Shift+E Share screen, Ctrl+Shift+A Accept video call,
  Ctrl+Shift+S Accept audio call, Ctrl+Shift+D Decline call,
  Ctrl+Shift+C Start audio call, Ctrl+Shift+U Start video call,
  Ctrl+Shift+K Raise hand, Ctrl+Shift+P Background blur,
  Ctrl+Shift+X Expand compose box.

### Teams-specific quirks worth noting

- **Ctrl+E = search / command bar** (the global search box; *not* "center" as in
  Word). The command bar also runs slash-commands.
- **Ctrl+. = keyboard-shortcuts panel** and **Ctrl+/ = show commands** (the two are
  often swapped in third-party cheat-sheets; this follows the MS Support page).
- **Ctrl+1..6 follow the app-bar order, not fixed apps.** As of the 2026 new Teams,
  Ctrl+N opens the *Nth app in the side rail*; the icons here use the **default**
  order (Activity / Chat / Teams / Calendar / Calls / Files). If a user re-orders
  their app bar these meanings shift — documented limitation, not a bug.
- Call controls are almost all **Ctrl+Shift** (the high-value mute/camera/share/
  raise-hand/accept/decline set), which maps cleanly to the combo file's R channel.

### Dropped / not included (flagged)

- **Reply (Alt+Shift+R), mark-as-unread, find-in-chat, filter** — these are either
  Alt+arrow / nav-area shortcuts, vary between classic and new Teams, or could not
  be confirmed as stable new-Teams defaults from the official material. **Not
  invented** — omitted rather than guessed.
- No Ctrl+Alt+Shift or Win/GUI Teams shortcuts exist in the target set, so nothing
  hit the un-representable channels (the generator reported 0 drops).

## Icons — all MIT

All 26 glyphs are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`, `assets/<Name>/SVG/ic_fluent_*_24_regular.svg`)
— the native style for a Microsoft app and license-compatible with the GPL-2.0 host.
Every Fluent asset name was **probed (raw fetch, 404 check)** before use on
2026-06-15. Mapping lives in `fetch_icons.py`; each binding's `source:` notes the glyph.

Note on a probe miss + substitution:
- **Calendar** — the folder is `Calendar LTR` (uppercase), not `Calendar Ltr`; the
  lowercase guess 404'd. Corrected to `Calendar LTR/ic_fluent_calendar_ltr_24_regular.svg`.

Weaker / interpretive matches worth knowing:
- **Accept video call** → "Video Person" (person-in-frame; distinct from the plain
  "Video" used for the camera toggle).
- **Accept audio call** → "Call" (same handset as the Calls nav item — acceptable,
  different cells/contexts).
- **Background blur** → "Blur" (gradient-dots glyph; reads as blur at keycap size).
- **Reset zoom** → "Full Screen Maximize" (corner brackets = fit/reset view).

## Program icon (ESC, all layers)

`program_icon: teams_logo.png` is a **generic, license-clean mark drawn in code**
(no Microsoft Teams logo): the same **'Office document'** style as the Word mark —
a 90° rotated trapezoid page with a letter knocked out (negative space) + text
lines on the right — but stamped with a **T** instead of a W, so Teams sits
visually with the other Office apps. Drawn by `_draw_teams_logo()` in
`fetch_icons.py` (white-on-transparent → `program_icon_mode: alpha`), fully
reproducible and carrying no trademark/licence risk. Drop a real Teams logo as
`icons/teams_logo.png` to override — the fetch script skips it if it already exists.

## Transformations

`bindings.yaml`: `mode: luma`, `threshold: 150`, `region: [36, 32]`,
`anchor: bottom-right`, `margin: 0`; program icon bottom-right `[46, 40]`,
`mode: alpha`. Ctrl+3 (`teams.png` = Fluent "People Team") and the program mark use
`mode: alpha`. Fluent `.svg` → cairosvg 96 px in `fetch_icons.py`. Committed `icons/`
freeze the render; pin the branch → a SHA for byte-exact reproducibility if needed.

## Mapping stanza

To add to `polyhost/res/overlay-mapping.poly.yaml` (NOT edited here):

```yaml
ms-teams,teams:
  overlay: [teams_template.mods.png, teams_template.combo.mods.png]
```

## Coverage audit additions (2026-06)

Added 3 high-confidence defaults that were missing (26 → 29): `Ctrl+Shift+F`
filter (Filter), `Ctrl+Shift+I` mark important (Important), `Alt+Shift+R` reply to
thread (Arrow Reply). All Fluent (MIT). (Lower-confidence call/compose variants —
e.g. Ctrl+Shift+B, Alt+Shift+C — were left out pending in-app confirmation.)
