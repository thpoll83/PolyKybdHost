"""Propose additions to res/shortcut_lexicon/*.yaml from translation catalogs.

Only catalog entries whose English msgid is a SPECIFIC command count (SPECIFIC
below): generic words such as "Left", "Window", "About" or "Select" translate to
words that would put wrong icons on unrelated labels. A translation is proposed
when it appears in >= MIN catalogs, is never the translation of an English
phrase of another concept (any msgid, specific or not), is not on the exclusion
list (terms the drafting agents left out on purpose), and is not already listed.
Compact-script (Chinese/Japanese) phrases need >= 3 characters, or >= 2 and
>= 10 catalogs.

Prints the proposals; with --write, appends them to the YAML files.

Getting the catalogs (Ubuntu 24.04; the .deb files are unpacked, not installed,
because container images often drop /usr/share/locale on install):

    mkdir -p cat/deb cat/x && cd cat/deb
    apt-get download libkf5configwidgets-data libkf5xmlgui-data
    for l in ar cs de es fa fr id it ja ko nl pl pt ru tr uk vi zh-hans zh-hant; do
        apt-get download language-pack-gnome-$l-base; done
    for f in *.deb; do dpkg-deb -x "$f" ../x; done

Then run with `cat/x` as the first argument.

    python tools/shortcut_lexicon_fill_gaps.py cat/x [--write]
"""
import gettext
import glob
import os
import re
import sys
from collections import Counter, defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import yaml  # noqa: E402
from polyhost.services import shortcut_icons as si  # noqa: E402

ROOT = sys.argv[1]
WRITE = "--write" in sys.argv
MIN = 3

LANG_DIRS = {
    "ar": ["ar"], "cs": ["cs"], "de": ["de"], "es": ["es"], "fa": ["fa"],
    "fr": ["fr"], "id": ["id"], "it": ["it"], "ja": ["ja"], "ko": ["ko"],
    "nl": ["nl"], "pl": ["pl"], "pt": ["pt", "pt_BR"], "ru": ["ru"], "tr": ["tr"],
    "uk": ["uk"], "vi": ["vi"], "zh_CN": ["zh_CN"], "zh_TW": ["zh_TW", "zh_HK"],
}

SPECIFIC = {
    "save": "save", "save as": "save as", "save a copy": "save as", "save all": "save as",
    "open": "open", "open file": "open", "open recent": "open",
    "new": "new", "new file": "new", "new document": "new",
    "print": "print", "print preview": "print",
    "reload": "reload", "refresh": "reload",
    "cut": "cut", "copy": "copy", "paste": "paste", "paste special": "paste",
    "undo": "undo", "redo": "redo", "delete": "delete",
    "select all": "select all",
    "find": "find", "search": "find", "find next": "find next",
    "find previous": "find next", "replace": "replace", "find and replace": "replace",
    "go to line": "go to",
    "fullscreen": "fullscreen", "full screen": "fullscreen", "maximize": "fullscreen",
    "minimize": "minimize", "hide": "hide", "hide others": "hide",
    "new window": "window",
    "zoom in": "zoom in", "zoom out": "zoom out", "normal size": "zoom reset",
    "actual size": "zoom reset", "reset zoom": "zoom reset", "original size": "zoom reset",
    "increase indent": "indent", "decrease indent": "outdent", "unindent": "outdent",
    "settings": "settings", "preferences": "settings",
    "help": "help", "keyboard shortcuts": "help", "documentation": "help",
    "close": "close", "close tab": "close", "close window": "close",
    "close document": "close", "quit": "quit", "exit": "quit",
    "word wrap": "wrap text", "line wrap": "wrap text", "wrap text": "wrap text",
    "bookmark": "bookmark", "read only": "lock",
    "toggle comment": "comment", "uncomment": "comment",
    "change case": "change case", "to uppercase": "change case", "to lowercase": "change case",
    "bold": "bold", "italic": "italic", "underline": "underline",
    "superscript": "superscript", "subscript": "subscript",
    "format painter": "paint", "copy link": "share",
}

EXCLUDE = {
    "de": {"wiederherstellen", "markieren", "info", "über"},
    "nl": {"links", "rechts", "over", "help", "info", "open", "stop", "superscript", "subscript"},
    "fr": {"styles", "style", "agrandir"},
    "it": {"ripristina", "ingrandisci", "rientro", "riduci", "informazioni"},
    "es": {"reducir"},
    "pt": {"aumentar", "diminuir", "sobre", "reduzir", "restaurar"},
    "pl": {"zakładka", "style"},
    "cs": {"zpět", "konec", "záložka"},
    "ru": {"свернуть", "развернуть", "восстановить", "предварительный просмотр"},
    "uk": {"повернути", "вставлення", "попередній перегляд", "згорнути", "розгорнути"},
    "tr": {"değiştir", "git", "küçült"},
    "id": {"batalkan", "ganti"},
    "vi": {"cập nhật", "phóng to", "thu nhỏ", "in"},
    "ar": {"بعد", "قرب", "أعد", "أنه", "حدث", "تكبير", "تصغير", "إعادة", "إلغاء", "تكرار", "نمط"},
    "fa": {"دوباره", "باز", "سبک", "زیرنویس"},
    "ja": {"移動", "更新", "配置", "重複"},
    "zh_CN": {"恢复", "还原", "取消", "换行", "目录"},
    "zh_TW": {"重複", "內容", "取消", "加入"},
    "ko": {"이동", "정렬", "맞춤", "정보", "되돌리기", "메모"},
}

ENGLISH = {phrase: concept for phrase, concept in si._PHRASES}
_MNEMONIC_TAIL = re.compile(r"\s*\(\s*[_&]?[a-z0-9]\s*\)$", re.I)
_ASCII = re.compile(r"^[a-z]+$")


def norm(text):
    return si.normalize(_MNEMONIC_TAIL.sub("", text))


def main():
    total = 0
    for lang, dirs in LANG_DIRS.items():
        spec = defaultdict(Counter)
        any_concept = defaultdict(set)
        for d in dirs:
            for path in glob.glob(os.path.join(ROOT, "usr/share/locale*", d, "LC_MESSAGES", "*.mo")):
                try:
                    with open(path, "rb") as fh:
                        cat = gettext.GNUTranslations(fh)._catalog
                except Exception:
                    continue
                for key, value in cat.items():
                    if not isinstance(key, str) or not isinstance(value, str) or not value:
                        continue
                    msgid = norm(key.split("\x04", 1)[-1])
                    tr = norm(value)
                    if not tr or tr == msgid:
                        continue
                    if msgid in ENGLISH:
                        any_concept[tr].add(ENGLISH[msgid])
                    if msgid in SPECIFIC:
                        spec[SPECIFIC[msgid]][tr] += 1
        path = os.path.join(REPO, "polyhost/res/shortcut_lexicon", f"{lang}.yaml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        ours = yaml.safe_load(text)["concepts"]
        listed = {si.normalize(p) for ps in ours.values() for p in ps}
        adds = defaultdict(list)
        for concept, counter in spec.items():
            for tr, n in counter.items():
                if n < MIN or tr in listed or tr in EXCLUDE.get(lang, ()):
                    continue
                if any_concept[tr] - {concept}:
                    continue
                if _ASCII.match(tr) and len(tr) < 3:
                    continue
                if si._is_compact(tr) and not (len(tr) >= 3 or (len(tr) >= 2 and n >= 10)):
                    continue
                adds[concept].append((tr, n))
        n_lang = sum(len(v) for v in adds.values())
        total += n_lang
        print(f"== {lang}: {n_lang}")
        for concept in si.LEXICON:
            if adds.get(concept):
                print(f"  {concept}: " + ", ".join(f"{t} ({n})" for t, n in sorted(adds[concept], key=lambda x: -x[1])))
        if WRITE and adds:
            lines = text.split("\n")
            for concept, items in adds.items():
                new = [t for t, _ in sorted(items, key=lambda x: -x[1])]
                key = f"  {concept}: ["
                for i, line in enumerate(lines):
                    if line.startswith(key) and line.endswith("]"):
                        lines[i] = line[:-1] + ", " + ", ".join(new) + "]"
                        break
                else:
                    # concept absent: insert in LEXICON order
                    order = list(si.LEXICON)
                    after = [c for c in order[:order.index(concept)] if c in ours]
                    if after:
                        prev = f"  {after[-1]}: ["
                        idx = next(i for i, l in enumerate(lines) if l.startswith(prev)) + 1
                    else:
                        idx = lines.index("concepts:") + 1
                    lines.insert(idx, f"  {concept}: [{', '.join(new)}]")
                    ours[concept] = new
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines))
    print("total", total)


if __name__ == "__main__":
    main()
