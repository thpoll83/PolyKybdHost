# Hosted / packaged Windows apps — which get an overlay, and why

A batch of six was requested on 2026-09-14 (Sticky Notes, Camera, Weather, Maps,
Voice Recorder, Mail), plus a question about Photos. **Three shipped, two were
declined on evidence, and two of the six are retired apps that no longer run.**
This file is the record, so the declined ones are not re-proposed and the
retired ones are not re-discovered.

## Verdict

| app | outcome | why |
|---|---|---|
| **Sticky Notes** | ✅ shipped, 24 bindings | Microsoft publishes a complete table, both sections |
| **Photos** | ✅ shipped, 21 bindings | two independent references agree; `F5` also witnessed by our own UIA harvest |
| **Voice / Sound Recorder** | ✅ shipped, 12 bindings | two independent references agree |
| **Camera** | ❌ declined | has essentially ONE shortcut — `Enter` is the shutter. That is not an overlay |
| **Weather** | ❌ declined | no app shortcut set at all; the only "shortcuts" documented are Windows-level, and the one named (`Win+H`) is a GUI chord, which this overlay format drops by construction |
| **Maps** | ⚠️ retired | deprecated 2025-04-08, removed from the Store by July 2025, a final update made it non-functional, and it is not preinstalled from Win11 24H2 |
| **Mail** | ⚠️ retired | support ended 2024-12-31; the app no longer sends or receives. Superseded by **new Outlook**, which is a different process and already has an `outlook` entry |

Sources for the two retirements: Microsoft's
[deprecated features list](https://learn.microsoft.com/en-us/windows/whats-new/deprecated-features-resources)
and
[Windows Mail, Calendar and People are becoming new Outlook](https://support.microsoft.com/en-us/outlook/windows-mail-calendar-and-people-are-becoming-new-outlook).

## ⚠️ Microsoft's per-app shortcut tables are GONE

The support page *"Keyboard shortcuts in apps"*
(`139014e7-177b-d1f3-eb2e-7298b2599a34`) used to carry tables for Photos, Maps,
Voice Recorder, Movies & TV, Groove, Paint and Calculator. **The URL still
resolves and those sections are simply absent** — it now redirects to the general
Windows shortcuts page. Checked 2026-09-14.

That is why Photos and Sound Recorder fall back to the `notepad` rule (two
independent references must agree) while Sticky Notes did not have to: Sticky
Notes is documented under *Office* support, which still carries its table.

**The stronger source, when the hardware is to hand, is the app itself:**

```
python tools/shortcut_probe.py --focused --json shortcuts.json
```

That reads `AcceleratorKey` off the live UI Automation tree — the same mechanism
the daemon uses — and is first-party evidence in a way a shortcut article is not.
Worth running against Photos and Sound Recorder to confirm or correct what the
two references claim.

## The host-process problem

Three of these apps do not run in a process named after themselves, and the
executable name is therefore not the app:

| app | process | how it is identified |
|---|---|---|
| Calculator | `ApplicationFrameHost.exe` | `titles-startswith` / `title:` branch |
| Sound Recorder | `ApplicationFrameHost.exe` | `titles-startswith: Sound` branch |
| **Sticky Notes** | **`ONENOTE.EXE`** | `title: "^Sticky Notes"` |
| Photos | `Photos.exe` | ordinary entry — it really is its own process |

Every hosted entry also carries **`icon:`** (`ICON_APP`, `handler/common.py`),
because the program mark cannot be resolved from a host-process name. For Sticky
Notes that is not merely a gap but a **wrong icon prevented**: `app_icons.yaml`
maps `onenote` to `mdi:microsoft-onenote`, so without it a Sticky Notes window
would draw a OneNote logo.

⚠️ **The parent `applicationframehost` entry must keep an overlay of its own.**
`find_matching_entry` returns `None` immediately for an entry carrying neither
`overlay:` nor `remote:` — *before* it looks at any sub-map — so a parent reduced
to title branches alone would make every branch unreachable. Calculator is the
parent; its `^Calculator` regex is also what stops an unnamed hosted app (Clock,
Weather) being handed calculator keycaps.

## Adding another hosted app

1. Confirm it still exists and is not retired.
2. Get its shortcuts from Microsoft's own docs, or from
   `tools/shortcut_probe.py --focused` against the running app. Two independent
   secondary references are the fallback, never one.
3. Build the overlay under `polyhost/res/overlay_sources/<app>/` as usual.
4. Add a **title branch** under `applicationframehost` (not a new top-level key —
   the process name is the host for every one of them) carrying `title:`,
   `icon:` and `overlay:`.
5. Check the routing, including that the apps you did **not** name still fall
   through unmatched.
