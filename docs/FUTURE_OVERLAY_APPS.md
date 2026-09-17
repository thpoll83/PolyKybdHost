# Future overlay apps — extending shortcut-overlay coverage

A follow-up task, deliberately **separate** from the generic-icon work in
[`generic-icons-plan.md`](generic-icons-plan.md). That plan makes a keycap mark
appear for an app nobody configured. This one is the opposite direction: pick the
apps worth a **hand-built, per-shortcut overlay** and build them with the
`generate-app-overlays` skill.

The two do not compete. A template overlay draws a real icon on every shortcut
key; the generic path draws one program mark on ESC. Template wins wherever it
exists, so this list only ever improves the result.

## What we already cover — measure it, don't guess

As of 2026-09-17: **45 entries** in `polyhost/res/overlay-mapping.poly.yaml`
(many carrying several aliases — `chrome` alone folds 10 browser executables) and
**37 reproducible source folders** under `polyhost/res/overlay_sources/`.

```bash
python3 - <<'PY'
import yaml, pathlib
d = yaml.safe_load(pathlib.Path("polyhost/res/overlay-mapping.poly.yaml").read_text())
print("%d mapping entries" % len(d))
for k in d: print("  " + k.split(",")[0])
PY
ls polyhost/res/overlay_sources/
```

⚠️ **Run that before building a candidate list.** The mapping keys are
executable names with aliases folded in, so a bare eyeball of the directory
listing under-counts: `jetbrains/` is one folder covering CLion, PyCharm, IDEA
and three more, and `webapps/` covers several sites at once.

## The approach

1. **Get a candidate list of applications.** Any ranking of widely-used desktop
   software does; a third-party shortcut site's app index is also fine, because
   a list of ~90 software *names* is not where anyone's investment sits, and you
   could rebuild it from a download chart. Subtract what the inventory above
   already covers — the remainder is usually far smaller than the raw list
   suggests.
2. **Source the shortcuts from PRIMARY sources**, preferring machine-readable
   ones: Notepad++ `shortcuts.xml`, VS Code `keybindings.json`, JetBrains keymap
   XML, the app's own documented shortcut reference. This is independent
   creation from the authoritative source, so the result is ours outright. The
   `generate-app-overlays` skill covers the whole loop and its sourcing rules.
3. **Check completeness against the VENDOR'S own reference**, not against a
   third-party shortcut database.

⚠️ **Step 3 is the one that is easy to get backwards, and it matters for two
independent reasons.**

- **Accuracy.** Every third-party shortcut site is *derived* from the same vendor
  documentation you would be parsing. KeyCombiner's author says plainly that he
  builds his database by parsing software documentation pages with regular
  expressions. So auditing your reading of the primary source against a secondary
  one inherits that secondary source's gaps as your own, one hop downstream of
  the truth.
- **Licensing.** Using a third-party database as a systematic completeness oracle
  across dozens of apps is *extraction* of its contents even when no row is
  copied, because what you take is the verification and completeness it invested
  in. Art 7(5) of Directive 96/9/EC prohibits "repeated and systematic extraction
  … of insubstantial parts" that conflicts with normal exploitation, and Art
  7(2)(a) defines extraction to include **temporary** transfer, so not storing the
  comparison does not help. *Innoweb v Wegener* (C-202/12) decided a
  store-nothing, query-in-real-time architecture and found re-utilisation anyway.

## Third-party shortcut databases — surveyed 2026-09-16/17

Recorded so a later session does not repeat the search. **None is currently
usable as a bulk source**, and the reason differs per entry.

| source | licence | apps | platforms | note |
|---|---|---|---|---|
| [hotkys](https://github.com/solomkinmv/hotkys) | MIT | ~66 | macOS only | machine-readable (`shift+cmd+e`), maps onto `shortcut_source.parse_accel` |
| [ShortcutMapper](https://github.com/waldobronchart/ShortcutMapper) | MIT | ~20 | `keys_win` + `keys_mac` | Adobe / JetBrains / 3D only; keys as prose (`"Ctrl + A"`) |
| [KeyCombiner](https://keycombiner.com/collections/) | none stated | 90+ | Win + macOS + Linux | **best candidate — ask** (below) |
| [DefKey](https://defkey.com/) | forbids it | 3650 | all | terms: shareable "as long as you don't create a database" |

The two MIT sets are usable today and are **complementary rather than
redundant**: hotkys covers macOS, where `shortcut_source`'s Accessibility backend
is not built at all, and ShortcutMapper covers the heavyweight custom-drawn UIs
that expose accelerators to UIA badly.

### Sources we CAN use today

Three, and the third is the one that matters most.

**1. The application's own keybinding file — always try this first.** It is
authoritative, machine-readable, and carries no third-party licence question at
all, because it ships with software the user already has. The
`generate-app-overlays` skill treats this as the primary route:

| app family | file |
|---|---|
| VS Code | `keybindings.json` (and the built-in defaults) |
| JetBrains IDEs | keymap `*.xml` |
| Notepad++ | `shortcuts.xml` |
| anything else | the vendor's own documented shortcut reference |

**2. [hotkys](https://github.com/solomkinmv/hotkys) — MIT, ~66 apps, macOS.**
Data lives in `shortcuts-disco-site/shortcuts-data/*.json`, one file per app,
against a committed `schema/shortcut.schema.json`. Shape is
app → `keymaps` → `sections` → `shortcuts`, each shortcut carrying a `key` such
as `shift+cmd+e` with modifiers drawn from `ctrl`, `shift`, `opt`, `cmd`.

That format maps directly onto `polyhost/services/shortcut_source/model.py` —
`parse_accel` already turns modifier tokens plus a base key into an `Accel`, so
this is a parser adaptation rather than a new model. It is worth more than 66
apps suggests, because **macOS is the platform where our own harvest returns
nothing**: `shortcut_source/__init__.py` records the Accessibility backend
(`AXMenuItemCmdChar`) as NOT built.

**3. [ShortcutMapper](https://github.com/waldobronchart/ShortcutMapper) — MIT,
~20 apps, Windows + macOS.** Data in `sources/<app>/intermediate/*.json`, with
`keys_win` and `keys_mac` as separate fields, so it is per-platform. Keys are
prose (`"Ctrl + A"`), needing a small tokeniser rather than a lookup. Coverage is
Adobe, JetBrains, Blender, Maya, Houdini, Unity, Nuke, SketchUp — precisely the
heavyweight custom-drawn UIs that expose accelerators to UIA badly, so it too
covers a gap rather than duplicating the harvest.

⚠️ **MIT is permissive, not public domain — the copyright notice has to travel
with the data.** That is already this repo's convention for art: every
`overlay_sources/<app>/` folder carries a `SOURCES.md` recording each asset's URL
and licence. Vendored shortcut data gets the same treatment, plus the upstream
`LICENSE` text alongside whatever JSON is copied in. Do not paraphrase a licence
into a one-line credit.

### KeyCombiner is worth one message

Its [terms](https://keycombiner.com/terms-and-conditions/) carry **no IP clause,
no scraping prohibition and no derivative-database prohibition** — the opposite
of DefKey. It is run by one person in Vienna, governed by Austrian law, and the
FAQ points at a public GitHub repo for questions.

⚠️ **"Public collections" is a visibility setting, not a licence.** The site says
it "provides a growing database of public shortcut collections for everyone to
explore", and the action it grants is copying a shortcut into your own collection
*inside KeyCombiner*. Same shape as a public GitHub repo with no LICENSE file:
readable and forkable on the platform, all rights reserved everywhere else.
Silence in the terms does not help either, because the database right applies by
operation of law rather than by contract.

So the permission has to come from him. That is one message, and the position is
good: PolyKybd does not compete with him (he sells a screen overlay and a
practice trainer; we put legends on keycaps), and he already made the collections
public and built copying into the product.

## Cost, so it is priced honestly

Per app this is real work — the skill's own guidance is to enumerate the whole
Ctrl row plus the notable Shift/Alt/F-key bindings in one coverage pass, because
users notice missing ones and dripping them in piecemeal is what frustrates. Then
each shortcut needs a legible 72×40 1-bit icon. Budget a session per app, plus
maintenance as the app changes its bindings.

⚠️ **Note the tension with the no-configuration goal.** A hand-built per-app
shortcut table is a per-app configuration file, which is what the generic-icon
work set out to remove. The honest distinction: the app→slug icon map was cut
because the **OS already provides** an icon, so the map was duplicating something
free. No OS provides shortcuts on Linux, and macOS is unimplemented, so a table
there fills a real hole rather than duplicating a free source. Build it where the
OS gives nothing; do not rebuild what the OS already answers.
