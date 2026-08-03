# `overlay-mapping.poly.yaml` — reference

Which overlay set the keyboard loads for the focused window. This file documents
every key the matcher understands; the matcher itself is
`polyhost/handler/common.py` (`find_matching_entry`), shared by local window
tracking and the forwarder's remote path.

For the *contents* of an overlay PNG (the 10×9 grid, the modifier→channel map)
see [`overlay_specification.md`](overlay_specification.md); for building one from
a binding file see [`overlay_sources/README.md`](overlay_sources/README.md).

## Shape

```yaml
<app-name>[,<app-name>…]:
  overlay: <file> | [<file>, …]
  # optional constraints and sub-maps, all described below
```

The top-level key is one or more **application names**, comma-separated. Matching
is an exact dict lookup on the lowercased name, so every spelling you want to
catch must be listed:

- **Windows** — the executable name with the extension stripped and lowercased:
  `sublime_text.exe` → `sublime_text`, `Adobe Premiere Pro.exe` →
  `adobe premiere pro`. ⚠️ On Windows JetBrains ships `idea64.exe` /
  `pycharm64.exe` / `studio64.exe`, which are *not* the same names as their
  Linux launchers.
- **Linux / macOS** — the reported application name, lowercased.

Because it is an exact lookup, **one app name can appear in only one entry**. Two
entries keyed on `soffice` do not both apply; the later simply wins. Split by
window title (or OS) instead — see below.

## Keys

| Key | Type | Meaning |
|---|---|---|
| `overlay` | file or list | The overlay PNG(s) to load, relative to `res/overlays/`. |
| `remote` | bool | This entry is a forwarded window rather than a local one. |
| `title` | regex | Hard gate: `re.search` against the **whole** window title. |
| `titles-startswith` | sub-map | Keyed on the title's **first word**. |
| `titles-endswith` | sub-map | Keyed on the title's **last word**. |
| `titles-contains` | sub-map | Keyed on **any one word** of the title. |
| `url` | regex | Hard gate on the focused browser tab's URL. |
| `urls-contains` | sub-map | Keyed on a **substring** of the URL. |
| `os` | sub-map | Keyed on the OS running the focused app. |

A sub-map's values are full entries, so they may carry an `overlay` plus further
constraints of their own — the matcher recurses.

## Matching order

Most specific first; the first branch that yields a match wins:

1. **`os`** — the platform decides which keymap the app even has.
2. **`urls-contains`** — a tab's URL identifies a web app far better than its title.
3. `titles-startswith`, then `titles-endswith`, then `titles-contains`.
4. The entry's own `title` / `url` gates, then its own `overlay`.

Nothing matching a sub-map is not a failure: the entry's own `overlay` applies.
That is what makes a default-plus-refinements entry work.

## `os:` — per-platform artwork

An app's shortcuts are a property of the platform it runs on. Sublime Text binds
`Cmd+P` on macOS and `Ctrl+P` on Windows, so one app name needs two overlay sets:

```yaml
myapp:
  overlay: [myapp_template.mods.png, myapp_template.combo.mods.png]   # default
  os:
    macos:
      overlay: [myapp_mac_template.mods.png, …]
```

The macOS artwork typically needs the `extra` and `gui` overlay tiers, since
almost every Mac shortcut is a `Cmd+…` chord — see
[`overlay_specification.md`](overlay_specification.md) for the channel map.

**Accepted keys** (case-insensitive; anything else never matches):

| Key | Also accepted |
|---|---|
| `windows` | `win`, `win32` |
| `macos` | `mac`, `darwin`, `osx`, `os x` |
| `linux` | `bsd` |
| `linux_gnome` | `gnome`, `linux-gnome` |
| `linux_kde` | `kde`, `plasma` |

**Desktop environments fall back to the family.** Running GNOME tries
`linux_gnome` first and then `linux`, so a `gnome:` branch wins where one exists
and a plain `linux:` branch still catches every desktop. A `gnome:` branch does
**not** fire on KDE — GNOME and KDE bind Super differently, which is why the
firmware distinguishes them at all.

**An unknown OS falls back to the default overlay**, never to a branch. Same for
no `os:` key at all.

**Mobile is out of scope.** `OsType` has `ANDROID`/`IOS`, but they can never
reach this matcher — `get_host_os()` never returns them (the host app doesn't run
there) and a forwarder is another instance of this same app. An `android:` branch
would be dead config, so those names are deliberately unrecognised.

**Which OS?** The one running the **focused app**, not the one the keyboard is
plugged into: a forwarded window uses the forwarder's reported OS
(`RemoteHandler.forwarded_os`), so a Mac forwarding to a Windows keyboard host
still gets the Mac artwork. This mirrors `PolyCore._track_active_os`.

## Title sub-maps: word matching, not substring

All three title sub-maps match **whole words** of the title, split on whitespace.
A multi-word key like `LibreOffice Writer` can therefore never match — use the
distinguishing single word (`Writer`).

⚠️ **`titles-contains` only fires when the entry also declares
`titles-startswith` or `titles-endswith`.** The matcher only splits the title
into words in that case:

```python
words = title.split() if (title and (has_starts_with or has_ends_with)) else []
if words:
    ...
    if has_contains:      # unreachable when neither of the above is present
```

A `titles-contains`-only entry silently falls through to its own `overlay`. The
shipped browser entry is in exactly this state — its Miro / Outlook / Jira title
fallback does not currently run, despite the comment claiming it does. Prefer
`titles-endswith` (which also pins the match to the end of the title, so a
document merely *named* "Calc notes" cannot pull the Calc overlay).

## `urls-contains` needs the browser extension

URL constraints are only satisfiable when a URL is known for the focused window —
that means the browser extension, or the AppleScript fallback on macOS. See
[`browser-extension/README.md`](../../browser-extension/README.md). With no URL
available, a URL branch simply doesn't match and the entry degrades to its
title-matched or default overlay; it never guesses.

Ordering matters, because it is first-hit over the sub-map in file order: put
`atlassian.net/wiki` (Confluence) **above** `atlassian.net` (Jira), or the
broader key swallows the narrower one.

## Worked example

```yaml
# one process, three modules, told apart by the title's last word
soffice,soffice.bin,libreoffice,startcenter:
  overlay: [libreoffice_writer_template.mods.png, …]      # Start Center fallback
  titles-endswith:
    Writer:  { overlay: [libreoffice_writer_template.mods.png, …] }
    Calc:    { overlay: [libreoffice_calc_template.mods.png, …] }
    Impress: { overlay: [libreoffice_impress_template.mods.png, …] }
```
