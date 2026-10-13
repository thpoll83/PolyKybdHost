# SoundCraft overlay: sources and licences

SoundCraft (<https://github.com/storytold/soundcraft>, one of the ArtCraft
"Crafting Apps", <https://getartcraft.com/apps/soundcraft>) is an open-source,
Pro-Tools-style DAW in Rust/egui, licensed **MIT OR Apache-2.0**. PolyKybdHost is
GPL-3.0-or-later, and both licences are GPLv3-compatible.

## Shortcuts

Everything here was read from the app's source at commit
**`c0cb99340891d306e216582db465f3594b89dc1d`**. That source is SoundCraft's own
keymap, not Avid's. Paths are relative to the repo root.

How a key is resolved (`crates/ui-egui/src/shortcuts.rs`): `handle()` tries
`fixed()` (`:101`) first, then the engine command registry (`command_for`,
first match in `command_specs()` order, `crates/engine/src/cmd/mod.rs:105`),
then `menus.rs::UI_COMMANDS`.

**Modifiers.** The registry stores macOS strings. `mods_match` (`shortcuts.rs:45`)
treats `Cmd` as Cmd on macOS and Ctrl elsewhere, so `Cmd` is written `CMDCTRL`
here. A registry `Ctrl` is the Mac **Control** key, which has no key off macOS
(`!want.ctrl`), so those chords are `only: [macos]`. The exception is
`PC_CTRL_CHORDS` (`shortcuts.rs:388`): `fixed()` maps Ctrl+Up/Down and
Ctrl+Shift+Up/Down to real Ctrl on every OS (`:191`, `:204`), so they stay
literal `CTRL`.

| Group | Source |
|---|---|
| File: New/Open/Close/Save/Save As, Import Audio/MIDI/Video, Bounce Mix, Export Clips, Print Score, Quit | `crates/engine/src/cmd/file.rs:11-195` |
| Edit: undo/redo, cut/copy/paste/clear, Cut/Clear Clip Gain, Repeat to Fill, Select All, selection keys, Duplicate, Repeat, Shift, Insert Silence, Separate, Heal, Trim, Mute, Copy to New Playlist, Strip Silence, Fades, Snap to Grid (Shift+F4), Consolidate | `crates/engine/src/cmd/edit.rs:12-187` |
| Copy/Move to Target or New Playlist | `crates/engine/src/cmd/edit_more.rs:177-204` |
| Zoom in/out, presets, Zoom to Selection, Fill Window | `crates/engine/src/cmd/view.rs:10-41` |
| Track New/Group/Duplicate/Folder/Commit/Bounce/Input Only/Scroll To/Clear Clip Indicators | `crates/engine/src/cmd/track.rs:10-116` |
| Clip Edit/Time Lock, Back/Front, Group/Ungroup, Rename, Sync Point, Quantize to Grid, Elastic, Capture | `crates/engine/src/cmd/clip.rs:9-166` |
| MIDI Quantize/Transpose/Duration, All Notes Off | `crates/engine/src/cmd/event.rs:28-82` |
| Mute/Solo/Record/Input (Shift+M/S/R/I), automation Thin/Write/Copy to Send | `crates/engine/src/cmd/mix.rs:12-172` |
| Loop Record, QuickPunch, Pre/Post-Roll, Loop Playback, TrackPunch, Session Setup | `crates/engine/src/cmd/options.rs:21-72` |
| Play Edit (Alt+[), Home/End | `crates/engine/src/cmd/transport.rs:22-24` |
| Target-playlist keys | `crates/engine/src/cmd/track_more.rs:152-170` |
| Regroup, Clear Clips, Identify Beat, Import Session Data | `clip_more.rs:13`, `clip_list.rs:12`, `event_more.rs:135`, `setup_more.rs:118` (all under `crates/engine/src/cmd/`) |
| Window keys (Cmd+1/3/4/5/9, Cmd+W, Cmd+Alt+M/J, Alt+6/7/'/=/I/J, Shift+K, Cmd+Ctrl+W/S/=) | `crates/ui-egui/src/menus.rs:9-61` (`UI_COMMANDS`) |
| Cmd+= Mix/Edit, Shift(+Alt)+=/- grid/nudge value, F12 record, F1-F4 and Alt+1-4 edit modes, \` cycle mode, F5-F10 tools, - nudge, Cmd+Alt+[ ] waveform zoom, Cmd+Alt+0-5 rating, Cmd+Ctrl+1-5 zoom presets, Ctrl(+Alt)(+Shift)+Up/Down track height, Ctrl+Shift+Up/Down clip gain, R/T zoom | `crates/ui-egui/src/shortcuts.rs:101-224` (`fixed`) |
| Single keys (Commands Keyboard Focus): A S D G F , . M / 0 O [ ] B X C V Z N 1-5 P ; L ' E, Shift+Z/P/; | `crates/ui-egui/src/shortcuts.rs:292-338` (`commands_focus`) |

Commands Keyboard Focus is the default (`crates/model/src/session.rs:287`,
`keyboard_focus: "commands"`). It works in the **Edit window only**, so the single
letters do nothing in the Mix window.

### Conflicts resolved by the code's own order

- **Cmd+Alt+L** is registered twice: `edit.move_selection_left` (`edit.rs:71`) and
  `clip.loop` (`clip.rs:68`). `command_for` takes the first, which is **Move Edit
  Left**, so that is what is drawn. Loop... has no reachable key.
- **Space / Ctrl+Space / Shift+Space** (play, record, half speed) and **Enter**
  (new memory location) are handled by the code, but those keys have no overlay
  cell.

### Skipped

- **No cell:** Space, Shift+Space, Cmd+Space, Enter, Tab chords (Tab to
  transient, Alt/Ctrl+Tab back), keypad Plus/Minus nudge, `Period n Period` (recall
  memory location; keypad workflow), Escape (the program-mark cell).
- **Shift+/** (Link Timeline and Edit Selection, `options.rs:25`): egui-winit 0.36
  resolves the *logical* key first, so Shift+/ arrives as `Key::Questionmark` and
  never equals the registry's parsed `Key::Slash`. The binding cannot fire on a
  US layout, so it is left off. (The code works around the same issue for
  Shift+; and Shift+=, but not here.)
- **Alt+-** also reaches `edit.nudge` (`shortcuts.rs:165`, no Alt check), but this
  looks incidental, so it is not drawn. Plain `-` is drawn, because the main-row
  key really does nudge back.
- **Cmd+Alt+L "Loop..."**: shadowed, see above.

## macOS

From one spec (`CMDCTRL`), the generator writes `soundcraft_template_mac.*`.
Everything that is Cmd on macOS is Ctrl on Windows/Linux. No action is remapped.
The macOS-only rows are the registry's Control chords: Cmd+Ctrl+I/X/B/D/G/W/S/=/1-5,
Ctrl+Shift+P/;, Ctrl+Alt+L (Time Lock) and Ctrl+Alt+Shift+Left (Toggle Recent
Playlist). These are drawn as `GUI+CTRL` / `CTRL+…` with `only: [macos]`.
Off macOS, Search, Score Editor and Hide Floating are reached from the Window
menu, as the code comment at `shortcuts.rs:51` says.

macOS reserves Cmd+H (Hide), Cmd+M (Minimize) and Cmd+Q (Quit). SoundCraft binds
Cmd+H to Heal Separation and Cmd+M to Mute Clips, and the overlay draws what
SoundCraft documents. If winit's default app menu takes the chord first, Cmd+H may
hide the app instead. This is unverified on hardware.

## Icons

| File(s) | Source | Licence |
|---|---|---|
| Most glyphs (see the `FLUENT` map in `fetch_icons.py`) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `follow, selector, scrubber, inputmon, midikeyboard, recinputonly, quantize, looprecord, consolidate, sendback, bringfront, insertsilence, heal, stripsilence, identifybeat, automation, thin, copytosend, narrowmix, trackpunch, quickpunch, score, heightup, heightdown, gainup, gaindown, cleargain, extendup, extenddown, duplicate` | [Material Symbols](https://fonts.google.com/icons) (`ms:`, weight 300) | Apache-2.0 |
| `open, save, saveas, import, export, undo, redo, cut, copy, paste, selectall, group, ungroup, zoom, zoomin, zoomout, zoomfit, hand, newsequence` | byte-identical copies of `../premiere/icons/` (Fluent) | MIT |
| `blade, trim, snap, rippleedit` | `../nle_glyphs.py` (custom-drawn) | GPL-3.0-or-later |
| `fadein, fadeout, crossfade` | drawn in `fetch_icons.py::_fade` (a clip block plus its ramp) | GPL-3.0-or-later |
| `zoompreset1-5` (Fluent Search plus a digit), `rating0-5` (Fluent Star plus a digit) | `../number_badge.py` composites | MIT + GPL-3.0-or-later |
| `soundcraft.png` (ESC program mark) | SoundCraft's own icon, `assets/app-icon/soundcraft.ico` @ `c0cb9934`, 64 px frame | **MIT OR Apache-2.0** |

The app-icon directory has no LICENSE file of its own. Its licence comes from
`assets/app-icon/README.md` ("Provenance and licence: drawn from scratch … MIT OR
Apache-2.0, like the code"), from `ATTRIBUTION.md` (rows for `icon.svg` and
`soundcraft.ico`: "SoundCraft contributors, original, MIT OR Apache-2.0") and from
the repo `LICENSE-MIT` / `LICENSE-APACHE`. It is not the ArtCraft brand mark:
`docs/brand/` is trademarked and excluded by `NOTICE`, and nothing from there is
used. The README calls the nightingale a **placeholder** until the owner redraws
it. If it changes upstream, delete `icons/soundcraft.png`, bump `SOUNDCRAFT_SHA`
and re-run.

### Program-mark sweep

The program mark was picked by rendering the candidates at keycap size, not by
reasoning from the source. I compared frames 32/40/48/64/128/256 against
luma t90-130 and bright t140-225, in regions [37,32] and [42,40]:

- **bright** lights the pale bird body and its engraving hatch, which turns into
  a noisy blob.
- **luma t130+** lights the teal field (luma ~127), which also gives a blob.
- **luma t110** keeps only the ink linework: the head outline, the open bill and
  the eye. That reads as a singing bird.

Frames 64 and above converge, so 64 was taken. Settings: `program_icon_mode: luma`,
`threshold: 110`, `region: [42, 40]`, `anchor: bottom-right`, `margin: 0`.

## Regenerate

```bash
python polyhost/res/overlay_sources/soundcraft/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/soundcraft/bindings.yaml --preview /tmp/soundcraft_preview
```
