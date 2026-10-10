---
name: probe-linux-shortcut-harvest
description: Diagnose why a Linux application shows no (or too few, or stale) shortcut icons on the keycaps — or no ESC program mark — by walking the AT-SPI harvest from the bus up: is the accessibility flag on, is the app on the bus at all, what raw GetKeyBinding strings it exposes, what the parser accepted, and whether its menus change later (welcome page vs document). Use when the user reports "app X shows no shortcut icons / no app image on ESC on Linux", "Kate/a Qt/KDE app shows nothing", "a GTK4 app shows nothing", "Ctrl+S is missing", "the icons are from the wrong state of the app", or pastes a `No shortcut icons for '<app>'` log line. NOT for Windows/macOS harvests (UI Automation / AX), NOT for choosing which icon a label gets (that is shortcut_hints.yaml / NAME_SYNONYMS curation), and NOT for designing an ESC mark (add-program-mark).
---

# Probe a Linux app's shortcut harvest

The keycap shortcut icons come from AT-SPI: the host walks the focused app's
accessibility tree, reads each menu item's `GetKeyBinding()` string, parses it
into a key, and matches the item's label to an icon concept. A missing icon
can fail at any of five layers, and **each layer has its own tool**. Walk them
in order and stop at the first one that fails; guessing from the top layer is
how a "wrong parser" theory gets chased while the app was never on the bus.

Background and the measurements behind each step:
[`docs/generic-icons-plan.md`](../../../docs/generic-icons-plan.md) §A.3 (the
formats, the Qt flag) and §E15 (the title-triggered re-harvest).

Everything below runs **on the user's desktop**, not in the cloud container
(no session bus there). Hand the commands over and read back the output.

## 0. Start from the host log

```bash
polyctl logs paths            # where the logs are (works with the host stopped)
grep -E "Shortcut icons for|No shortcut icons for|Accessibility flag|Turned on the session" <daemon log>
```

| Log line | Means | Go to |
|---|---|---|
| `No shortcut icons for 'x' (<backend reason>)` | PyGObject / typelib / bus missing | the reason names the package; `docs/generic-icons-plan.md` E13/E14 |
| `No shortcut icons for 'x' (the app exposes no accelerators)` | on the bus, nothing parsed | step 2, then 3 |
| no line for the app at all | the harvest never ran for that name | step 1 (is it on the bus, under which name?) |
| `Shortcut icons for 'x': N shortcut(s) harvested -> …` + `no icon (<why>)` | harvest fine; curation | read the `why` (below) |
| icons from the wrong STATE (welcome page vs document) | menus changed after the harvest | step 4 |

The `no icon (why)` reasons are phrased as the fix: `no icon concept matched the
label` is curation (`res/shortcut_hints.yaml`, `NAME_SYNONYMS`), and `the keyboard
has no keycap for that key` and `a bare keypress on a key that types a
character` are by design. There is no per-app cap on the number of icons.

## 1. Is the app on the bus?

```bash
python3 tools/shortcut_probe.py --list
```

Not listed → it never registered.

- **A Qt/KDE app** registers only while the session's accessibility flag is
  on, and Plasma leaves it off. Check it:
  ```bash
  gdbus call --session --dest org.a11y.Bus --object-path /org/a11y/bus \
    --method org.freedesktop.DBus.Properties.Get org.a11y.Status IsEnabled
  ```
  The host flips it once per process (`shortcut_enable_accessibility`, logged
  as `Turned on the session's accessibility flag` or `Accessibility flag:
  already on`). To prove the cause for one app, start it forced on:
  `QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1 kate -n &`.
- ⚠️ **`kate &` while a Kate runs starts NOTHING** — it hands off to the
  running instance and exits, so the new environment never reached a process.
  Use `kate -n` (other KDE apps: check for a `--new-instance`-style flag, or
  quit the running one first).
- **GTK3** needs `libatk-adaptor`; **GTK4** registers by itself.
- Listed under an unexpected name? The harvest matches on the name the window
  tracker reports (Kate is `org.kde.kate` via the KWin script); compare the
  `--list` name against the log's `'<app>'`.

## 2. What does the parser accept?

```bash
python3 tools/shortcut_probe.py --app kate
```

Lists the shortcuts `pick_binding()` accepted, with the key each maps to. A
healthy classic-menubar app gives dozens. Zero here while step 1 listed the
app → step 3 decides between "exposes nothing" and "exposes a format we
reject".

## 3. What does the app actually expose?

```bash
python3 tools/atspi_raw_dump.py kate
python3 tools/atspi_raw_dump.py kate --all-nodes | grep -i save
```

Prints the role histogram and every non-empty `GetKeyBinding` string,
unfiltered. Read the FORMAT:

| Raw string | Toolkit | Parser path |
|---|---|---|
| `m;<Alt>f:m;<Control>s` | GTK3 | `parse_accel` |
| `<VoidSymbol>` everywhere | GTK4 < 4.18 | nothing to read — the upstream stub, by design here |
| `S;;<Control>s` | GTK 4.18–4.20 | `parse_accel` |
| `S;;Control+S` | GTK 4.22+ (ARIA) | `parse_aria_accel` |
| `Ctrl+S` (no `;`, no `<`) | Qt | `_pick_qt_binding`; an `Alt+<letter in label>` is a mnemonic |

A string in none of these shapes is a new format: add it to `model.py` with a
test in `tests/services/shortcut_binding_pick_test.py`, the way the ARIA and
Qt forms were added.

`--all-nodes` also lists menu items WITHOUT a binding, which separates "the
item is in the tree but has no shortcut" from "the item is absent". Kate's
welcome page has no Save/Undo/Copy at all — absent, not unbound.

## 4. Do the menus change later?

```bash
python3 tools/atspi_event_probe.py kate --seconds 60
# meanwhile: open a document, type, save, close
```

Prints each `children-changed`, accessible-name and `window:activate` event
and a summary. The host re-harvests on a **window title** change (Qt sent no
`children-changed` when its menus were rebuilt), behind a 3 s floor, a backoff
on unchanged answers and one re-read per new pid. If an app's menus change
WITHOUT its title changing, the summary is the evidence for a different
trigger; run it before designing one.

## Output

Report, per app: the layer that failed, the command output that shows it, and
the fix — a package to install, the flag, a parser branch with its test, a
curation entry, or "by design" with the reason.

## Pitfalls

- **The probe tools read the bus of the session they run in.** Run them as the
  desktop user, in a terminal of that session; over ssh without the session
  bus they report "accessibility bus unreachable".
- **A zero from `shortcut_probe.py` does not mean the app exposes nothing** —
  it is post-parser. Only `atspi_raw_dump.py` answers that.
- **Do not trust one instance's numbers for another.** A KDE app reuses its
  running instance, and two Kates reported 97 and 59 shortcuts on the same
  welcome page (unexplained, `docs/FUTURE_WORK.md`). Start a fresh instance
  with `-n` before comparing.
- **Never debug the parser from a log alone.** The log shows what was
  accepted; ask for the raw dump before theorising about formats.
