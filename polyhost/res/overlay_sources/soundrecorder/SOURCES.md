# Windows Sound Recorder overlay — sources

Windows 11 renamed **Voice Recorder** to **Sound Recorder**; the mapping matches
both names, and the app is the same one.

## Shortcuts

⚠️ **Microsoft publishes no shortcut table for this app.** The old *"Keyboard
shortcuts in apps"* page that carried the Voice Recorder table has been folded
into the general Windows shortcuts page and the per-app tables are gone (checked
2026-09-14); the app's own FAQ page documents features, not keys.

So the **`notepad` rule** applies: every binding drawn here is one that **two
independent references agree on**.

* <https://keycombiner.com/collections/voice-recorder/>
* <https://www.makeuseof.com/windows-11-voice-recorder-keyboard-shortcuts/>

Both list: `Ctrl+R` new recording, `Ctrl+M` marker, `Delete` delete recording,
`Space` play/pause, `Backspace` go back, `F2` rename, `Left`/`Right` seek,
`Shift+Left`/`Shift+Right` seek further, `Home`/`End` to the ends.

## ⚠️ This overlay is mostly BARE KEYS, on purpose

The calc overlay skips unmodified keys because *"the keycap already shows the
character"*. That is true of a digit or a `+` and **false of a transport
control**: a keycap reading `Home` does not say *"jump to the start of the
recording"*, and `Space` does not say *"play"*. These are exactly the keys worth
relabelling — the same reason Photos' `F5` is drawn.

## What is NOT drawn, and why

| left off | why |
|---|---|
| `Esc` stop recording | one reference only, **and** the program mark owns ESC on every overlay in this repo |
| bare `O` (show in folder), bare `S` (share) | one reference only, and a bare letter as a global shortcut is unusual enough to want confirming against the app before it goes on a keycap |

## Icons

All Microsoft Fluent UI System Icons (MIT), <https://github.com/microsoft/fluentui-system-icons>.

The seek family is **three distinct pairs**, ordered by size so the picture
itself says which jump is bigger:

| keys | distance | glyph |
|---|---|---|
| `Left` / `Right` | one step | a single arrow |
| `Shift+Left` / `Shift+Right` | further | a double triangle |
| `Home` / `End` | the ends | a triangle against a bar |

⚠️ **NOT `Skip Back 10` / `Skip Forward 10`**, which is what the first cut used:
those glyphs have the **number 10 drawn inside them**, and the documented jump is
not ten seconds — one reference says five and the other only says "further". A
glyph that states a wrong number is the *"a wrong icon is worse than no icon,
because the user believes it"* rule in its most literal form. Seen on the
rendered sheet; invisible from the folder names.

## Program mark

Named by the mapping entry's `icon:` (`mdi:microphone`), not baked and not from
`app_icons.yaml`. Sound Recorder is a Win11 packaged app, so its process is
`ApplicationFrameHost.exe` and a process-name lookup could never resolve — see
`ICON_APP` in `handler/common.py`.

## Reproducing

```bash
python polyhost/res/overlay_sources/soundrecorder/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/soundrecorder/bindings.yaml --preview /tmp/sr
```

Verified byte-identical on a re-run.
