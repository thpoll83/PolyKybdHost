"""Compare res/shortcut_lexicon/*.yaml with real translation catalogs (.mo).

For each language: every catalog entry whose English msgid normalizes EXACTLY to an
English LEXICON phrase gives (concept, translated label). Translations are
normalized the same way the host normalizes labels.

Writes a JSON report: per language, per concept
  confirmed   our phrases seen in catalogs for this concept (with counts)
  elsewhere   our phrases seen in catalogs ONLY for other concepts
  unseen      our phrases not seen in any matching catalog entry
  candidates  catalog translations (count >= MIN) that we do not list
plus, per translated phrase, every concept it was seen for (ambiguity).

Getting the catalogs (Ubuntu 24.04; the .deb files are unpacked, not installed,
because container images often drop /usr/share/locale on install):

    mkdir -p cat/deb cat/x && cd cat/deb
    apt-get download libkf5configwidgets-data libkf5xmlgui-data
    for l in ar cs de es fa fr id it ja ko nl pl pt ru tr uk vi zh-hans zh-hant; do
        apt-get download language-pack-gnome-$l-base; done
    for f in *.deb; do dpkg-deb -x "$f" ../x; done

Then run with `cat/x` as the first argument.

    python tools/shortcut_lexicon_verify.py cat/x report.json [MIN]
"""
import gettext
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import yaml  # noqa: E402
from polyhost.services import shortcut_icons as si  # noqa: E402

ROOT = sys.argv[1]           # extracted .deb tree
OUT = sys.argv[2]
MIN = int(sys.argv[3]) if len(sys.argv) > 3 else 2

LANG_DIRS = {
    "ar": ["ar"], "cs": ["cs"], "de": ["de"], "es": ["es"], "fa": ["fa"],
    "fr": ["fr"], "id": ["id"], "it": ["it"], "ja": ["ja"], "ko": ["ko"],
    "nl": ["nl"], "pl": ["pl"], "pt": ["pt", "pt_BR"], "ru": ["ru"], "tr": ["tr"],
    "uk": ["uk"], "vi": ["vi"], "zh_CN": ["zh_CN"], "zh_TW": ["zh_TW", "zh_HK"],
}

ENGLISH = {phrase: concept for phrase, concept in si._PHRASES}
# GTK/KDE mnemonic forms the host normalizer does not strip: "(_S)" is removed by
# the parenthetical rule already; KDE uses "&" which normalize() strips.
_MNEMONIC_TAIL = re.compile(r"\s*\(\s*[_&]?[a-z0-9]\s*\)$", re.I)


def norm(text):
    return si.normalize(_MNEMONIC_TAIL.sub("", text))


def catalogs(lang):
    files = []
    for d in LANG_DIRS[lang]:
        for base in ("usr/share/locale-langpack", "usr/share/locale"):
            files += glob.glob(os.path.join(ROOT, base, d, "LC_MESSAGES", "*.mo"))
    return files


def main():
    report = {}
    for lang in LANG_DIRS:
        seen = defaultdict(Counter)          # concept -> Counter(translation)
        where = defaultdict(set)             # translation -> {concepts}
        sources = defaultdict(set)           # (concept, translation) -> {mo names}
        for path in catalogs(lang):
            try:
                with open(path, "rb") as fh:
                    cat = gettext.GNUTranslations(fh)._catalog
            except Exception:
                continue
            name = os.path.basename(path)[:-3]
            for key, value in cat.items():
                if not isinstance(key, str) or not isinstance(value, str) or not value:
                    continue
                msgid = key.split("\x04", 1)[-1]
                concept = ENGLISH.get(norm(msgid))
                if concept is None:
                    continue
                tr = norm(value)
                if not tr or tr == norm(msgid):
                    continue
                seen[concept][tr] += 1
                where[tr].add(concept)
                sources[(concept, tr)].add(name)
        with open(os.path.join(REPO, "polyhost/res/shortcut_lexicon", f"{lang}.yaml"),
                  encoding="utf-8") as fh:
            ours = {c: [si.normalize(p) for p in ps]
                    for c, ps in (yaml.safe_load(fh)["concepts"] or {}).items()}
        per = {}
        for concept in si.LEXICON:
            mine = ours.get(concept, [])
            conf, elsewhere, unseen = {}, {}, []
            for p in mine:
                if seen[concept].get(p):
                    conf[p] = seen[concept][p]
                elif p in where:
                    elsewhere[p] = sorted(where[p])
                else:
                    unseen.append(p)
            cands = {t: {"n": n, "also": sorted(where[t] - {concept}),
                         "src": sorted(sources[(concept, t)])[:4]}
                     for t, n in seen[concept].most_common()
                     if n >= MIN and t not in mine}
            ambiguous = {p: {"own": seen[concept].get(p, 0),
                             **{o: seen[o][p] for o in sorted(where[p] - {concept})}}
                         for p in mine if where.get(p, {concept}) - {concept}}
            per[concept] = {"confirmed": conf, "elsewhere": elsewhere,
                            "ambiguous": ambiguous,
                            "unseen": unseen, "candidates": cands}
        report[lang] = {"catalogs": len(catalogs(lang)), "concepts": per}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    for lang, data in report.items():
        c = data["concepts"]
        n_conf = sum(len(v["confirmed"]) for v in c.values())
        n_else = sum(len(v["elsewhere"]) for v in c.values())
        n_un = sum(len(v["unseen"]) for v in c.values())
        n_cand = sum(len(v["candidates"]) for v in c.values())
        print(f"{lang:6} catalogs={data['catalogs']:4} confirmed={n_conf:3} "
              f"elsewhere={n_else:3} unseen={n_un:3} candidates={n_cand:3}")


if __name__ == "__main__":
    main()
