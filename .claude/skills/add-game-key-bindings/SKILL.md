---
name: add-game-key-bindings
description: Make a game overlay's icons follow the player's OWN key bindings (or the installed language's hotkeys) by reading the game's binding file and moving each icon with `build.remap`. Use when asked "can we read the key assignment from a file", "the icons should follow my rebinds", "the German/French install uses other keys", "do the same for <game>" after UT2004/Warcraft III/OpenRA, or when an overlay's default keys are wrong for a localized install. Covers finding the binding file and the default-key source, naming every binding's `command:`, checking the defaults against the game's own files, the reader hook (`bindings(files)` or a spec-level `bindings: <name>` source), `BINDINGS_COMPLETE`, `undrawn:`, the cache key, tests and a run on the user's real files. NOT for drawing icons from the game's art (evaluate-game-asset-reader) and NOT for building a new overlay set (generate-app-overlays).
---

# Make a game overlay follow the player's key bindings

A game overlay ships with the game's default keys. When the player rebinds a key,
or plays a localized install whose hotkeys differ, the icon sits on the wrong key.
`polyhost/services/game_assets/build.py` can move each icon to the player's key at
build time (`remap`). This skill wires one game into that.

Done four times on 2026-11-14/15 (PolyKybdHost#869, #874):

| Game | Binding source | Hook | Complete? |
|---|---|---|---|
| UT2004 | `System/User.ini` `[Engine.Input]` (`Key=Command`) | reader `bindings(files)` (`unreal2/bindings.py`) | yes: the file lists every key |
| Warcraft III | the installed language's `EscMenuMainPanel.fdf`, `GlobalStrings.fdf`, `CommandStrings.txt` in the MPQs, then `CustomKeys.txt` | reader `bindings(files)` (`warcraft3/reader.py`, no art) | no |
| OpenRA (3 mods) | `Keys:` in `settings.yaml` in the support folder | spec `bindings: openra` → `openra_keys.py` | no: only changed keys are written |
| C&C Generals | `Data\<Language>\CommandMap.ini` (in `<Language>ZH.big`) | `command:` names only, no reader yet | - |

## 1. Find the two sources

1. **The default keys** the shipped overlay draws: the game's own data files
   (`generate-app-overlays` → *Research the shortcuts*). Defaults often differ per
   language; note which language the shipped set uses.
2. **The player's keys**: a user config (User.ini, settings.yaml, CustomKeys.txt,
   a hotkey profile) and/or the installed language's data files. Read the game's
   source or a file the user sends to learn the exact format and where it lives on
   Windows, macOS, Linux, Wine and Flatpak. Get a real file before writing the
   parser (`evaluate-game-asset-reader` → *Get real files*).

Decide **complete or not**: does a command MISSING from the player's data mean
"unbound" (UT2004's User.ini lists every key) or "unknown, keep the default"
(OpenRA writes only changes; Warcraft III's files cover only some keys)? Getting
this wrong either blanks every icon the parser did not find or leaves unbound
keys drawn.

## 2. Name every binding's command

In the overlay spec, give each binding `command:` with the game's own name, exactly
as the binding file writes it (`SwitchWeapon 4`, `CmdMove`, `QuitButton`,
`AttackMove`, `ControlGroupCreate01`). Comparison ignores case and runs of
spaces. A generator script that writes mod copies (`openra/gen_mods.py`) must carry
the names too.

Then **check every default key against the game's files** with a throwaway script:
for each binding, the game's default for its command must equal the spec's
`key` + `mods`. The OpenRA check compared 93 keys per mod; the UT2004 one compared
the spec with the real `DefUser.ini`. Fix the spec, not the check.

When the game binds a command to more keys than the overlay labels (UT2004's arrow
keys and `,`/`.` next to WASD), list them under `undrawn: [UP, COMMA]`: they count
as default keys, so the stock file moves nothing, and no icon is drawn on them.

## 3. The reader hook

- **The game already has a reader** whose `find()` locates the same install:
  add `bindings(files) -> {command: [token, ...]} | None` to its `reader.py`,
  and put the binding file in `files` (an OPTIONAL entry of `data_files`) so
  `fingerprint(files)` keys the cache on it.
- **The bindings live apart from the files the art reader finds** (OpenRA's
  support folder): write `game_assets/<name>_keys.py` with `find() -> Path|None`,
  `bindings(path)` and `BINDINGS_COMPLETE`, and add `bindings: <name>` to the
  spec's `game_assets:` block. `build.bindings_source` adds that path to the cache
  key.
- **No art at all** (Warcraft III): a reader whose `draw()` raises and whose spec
  has `icons: {}` is fine; `build.build` still patches the shipped overlay.

Tokens are the generator's key names with modifiers: `"S"`, `"ALT+Q"`,
`"CTRL+SHIFT+1"` (`build.key_token`). Map the game's key names to those in a
table and drop keys with no keycap cell (keypad, mouse, Meta); a command bound
only to such keys gives `[]`. Set `BINDINGS_COMPLETE = False` at module level
when a missing command means "unknown".

A new reader needs its folder setting (`readers.py` registry, `__init__.py` with
`Setting`), the extractor list in `scripts/i18n_strings.py`, and the 19
translations (`translate-ui-catalogs`).

## 4. Tests and checks

- Parser tests on synthetic files in the real format: sections outside the one
  that holds keys are ignored, an empty value is unbound, unknown keys are
  dropped, a byte order mark is handled, an oversized file is refused.
- A `build.build` test on a synthetic install: the stock bindings change no cell;
  a rebind moves the icon and blanks the old key; ESC keeps the program mark; a
  command missing from the data keeps or clears its key as `BINDINGS_COMPLETE`
  says; a changed binding file yields a new cache file; an unreadable one logs a
  warning and leaves the defaults.
- `mutation-test-suite`: 7 to 8 mutations per reader were each caught this time.
- Run `reader_compare.py` (`evaluate-game-asset-reader`) on the user's real files
  twice: the stock config (only the art keys may change) and a copy with two or
  three keys rebound.

## Pitfalls

- ⚠️ **A key moved between overlay files keeps its default.** The primary file
  holds plain, Ctrl, Alt and Shift; the `.combo` file the two-modifier keys.
  `remap` runs per file, so it leaves a command alone when its old and new keys
  are in different files. Say so in `SOURCES.md`.
- ⚠️ **The remap needs the reader's `find()` to succeed.** No art files, no
  build, no remap (OpenRA needs its content anyway; a key-only reader's `find()`
  should require only the binding source).
- **Never draw on ESC**: `remap` drops it as a target; keep it that way.
- **Point `find()` at the developer's machine in tests only through a mock**: a
  developer's own settings file would otherwise move icons in unrelated tests
  (`game_assets_ra_test` patches `openra_keys.find`).
