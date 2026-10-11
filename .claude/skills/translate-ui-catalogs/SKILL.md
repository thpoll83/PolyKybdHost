---
name: translate-ui-catalogs
description: Translate new or changed PolyKybdHost UI strings into all 19 shipped catalogs (polyhost/res/locale/*.po) — regenerate the template, list what is empty, have agents draft each language group against the existing catalog's terminology, merge with a placeholder/newline/tag/mnemonic check, run tests/i18n_test.py, and look at the dialog rendered in German and Arabic. Use after any host change that adds or rewords a string marked with _(), _f(), _nf(), N_() or M_(), when tests/i18n_test.py reports an untranslated template or a stale polyhost.pot, or when asked to "translate the new strings", "update the catalogs", "fill the .po files". NOT for marking strings in the first place (docs/i18n.md → Marking a string) and NOT for reviewing machine translations with a native speaker.
---

# Translate the host UI catalogs

Every user-visible host string ships in 20 languages, so any UI change owes 19
catalog updates. Missing ones fall back to English silently, except `M_()`
templates, which `tests/i18n_test.py` requires in every catalog. The mechanism is
[`docs/i18n.md`](../../../docs/i18n.md).

Done twice in the session that wrote this skill (2026-10-10): ~760 entries for the
first translation (#352) and 57 device-message templates (#357), plus one changed
dialog sentence.

## 1. Regenerate the template and the catalogs

```bash
cd /home/user/PolyKybdHost
.venv/bin/python scripts/i18n_strings.py unmarked   # must report 0 before you go on
.venv/bin/python scripts/i18n_strings.py update     # writes polyhost.pot, merges every .po
.venv/bin/python .claude/skills/translate-ui-catalogs/list_untranslated.py /tmp/tr/msgids.json
```

Babel needs `pip install -r tools/requirements.txt`. `update` runs with
`--no-fuzzy-matching --ignore-obsolete`, so a REWORDED msgid arrives empty and its
old translation is gone from the catalog. Save the old translations first (read
them with `babel.messages.pofile.read_po`) when the change is a small edit: adapting
the old text beats re-translating it.

## 2. Draft the translations

Under ~5 strings: write them yourself, one JSON per language. Otherwise fan out
agents in parallel, about five languages each. Groups that worked:
`de fr es pt_BR it` · `ja zh_CN zh_TW ko vi` · `ru uk pl cs nl` · `ar fa tr id`.

Each agent gets `msgids.json`, writes `/tmp/tr/<code>.json` (`{msgid: msgstr}`,
`ensure_ascii=False`), edits no `.po` file, and follows these rules:

- **Copy terminology from that language's existing `.po`**: grep it for firmware,
  keyboard, half, staged, macro. Match its register too. The German catalog uses
  impersonal infinitives and the Italian one `tu`, so asking for Sie/Lei produces a
  mismatch.
- Keep every `{placeholder}`, every `\n` (count and structure), every `<tag>`, and the
  `&` mnemonic count. Keep technical tokens verbatim (FW_UP_*, BOOTSEL, UF2, `.sig`,
  WinCompose, PolyKybd, quoted commands).
- A fragment inserted into another message (a `{reason}`, `{what}` or `{step}` value)
  is translated to fit that slot: no final period, the right grammatical case.
- The A / R keycap letters stay Latin; only the word in parentheses is translated.
- Arabic and Persian get no bidi control characters. `_f` isolates values itself.

## 3. Merge and check

```bash
.venv/bin/python .claude/skills/translate-ui-catalogs/merge_translations.py /tmp/tr
.venv/bin/python scripts/i18n_strings.py check
QT_QPA_PLATFORM=offscreen xvfb-run -a .venv/bin/python -m unittest tests.i18n_test
```

The merge fills only empty entries and skips any pair whose placeholders, newlines,
tags or mnemonics differ, naming it. Fix the skipped ones and run it again. Babel's
`write_po(width=None)` round-trips these catalogs byte-identically, so the diff
holds only the new entries plus shifted line references.

## 4. Look at it

Render the changed dialog offscreen in `de` (longest words) and `ar` (right to left)
and Read the PNG. The pattern is `prepare(code)` from `polyhost.gui.i18n_qt`, build
the widget, `grab().save(...)`. Run the script with `PYTHONPATH=$PWD`, without `-I`
(`-I` ignores `PYTHONPATH`). A string the scanner cannot see shows up here as English.

## Output

Report the count of entries filled per language, any skipped pair and why, the
`i18n_test` result, and the two screenshots.

## Pitfalls

- ⚠️ **A clean scanner is a floor.** `unmarked` sees only literals passed straight to
  a Qt text call. Text reaching a widget through a variable (device-layer status,
  downloader progress) stays English until it is an `M_()` template. Run with
  `POLYHOST_LANG=pseudo` to find the rest.
- ⚠️ **Babel extracts dict keys**: `_(texts["start"])` puts `"start"` in every
  catalog. Use namedtuple attributes.
- **Plural entries** (`_nf`) need one form per plural rule of the language. The merge
  script fills singular entries only; write plural ones by hand and let
  `tests/i18n_test.py` check the form count.
- ⚠️ **A check script can flag a token inside a word** ("ms" inside "claims"). Match
  technical tokens on word boundaries before "fixing" a translation.
- **Mark the translations as drafts.** They are machine-made; `docs/i18n.md` →
  *Translation status* says so, and an empty `msgstr` (English) beats a wrong one on
  a firmware-flash dialog.
