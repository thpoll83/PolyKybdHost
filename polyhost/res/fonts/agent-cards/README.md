# Fallback fonts for the agent cards

`services/agents/card.py` draws a card's text in Pillow's bundled font (Aileron),
which has only ASCII. A character it does not have is drawn with the first font
listed in `card.FALLBACK_FONTS` that has it. Each file is xz-compressed
(`xz -9e`); the card code reads it into memory once.

| file | font | size | covers | license |
|---|---|---|---|---|
| `Galmuri11.ttf.xz` | Galmuri11 2.40.3 by Lee Minseo, npm package `galmuri`, unchanged (`dist/Galmuri11.ttf`, SHA-256 `2c709890…b4b4f`) | 12 px | European Latin (Latin-1, Latin Extended-A), Greek, Cyrillic, all 11,172 Hangul syllables, Hiragana, Katakana, 6,477 CJK ideographs | SIL OFL 1.1, `OFL-Galmuri.txt` |
| `WenQuanYiZenHeiMono-cjk.ttf.xz` | WenQuanYi Zen Hei Mono (face 1 of `wqy-zenhei.ttc`, Debian package `fonts-wqy-zenhei` 0.9.45), **changed**: cut to the 3,939 characters of GB2312, Big5 level 1 and CJK punctuation that Galmuri11 does not have; no hinting, no OpenType layout tables | 12 px | the rest of common simplified and traditional Chinese | GPL-2 with a font embedding exception, and the M+ FONTS license, `LICENSE-WenQuanYi.txt` |
| `NotoSansDevanagari.ttf.xz` | Noto Sans Devanagari, google/fonts `ofl/notosansdevanagari`, unchanged (SHA-256 `14ec4af4…9853e`) | 13 px | Devanagari (Hindi, Marathi, Nepali), shaped by raqm | SIL OFL 1.1, `OFL-NotoSansDevanagari.txt` |
| `NotoSansThai.ttf.xz` | Noto Sans Thai, google/fonts `ofl/notosansthai`, unchanged (SHA-256 `5a1c559b…c9ef8`) | 13 px | Thai | SIL OFL 1.1, `OFL-NotoSansThai.txt` |
| `NotoSansArmenian.ttf.xz` | Noto Sans Armenian, google/fonts `ofl/notosansarmenian`, unchanged (SHA-256 `0870908d…fef71`) | 13 px | Armenian | SIL OFL 1.1, `OFL-NotoSansArmenian.txt` |
| `NotoSansHebrew.ttf.xz` | Noto Sans Hebrew, google/fonts `ofl/notosanshebrew`, unchanged (SHA-256 `7ef36a2c…2de88`) | 13 px | Hebrew | SIL OFL 1.1, `OFL-NotoSansHebrew.txt` |
| `NotoSansArabic.ttf.xz` | Noto Sans Arabic, google/fonts `ofl/notosansarabic`, unchanged (SHA-256 `63111b5b…e869e`) | 13 px | Arabic, Persian, Urdu | SIL OFL 1.1, `OFL-NotoSansArabic.txt` |

WenQuanYi Zen Hei is GPL-2 only. The file is a separate data file that the host
reads at run time, not part of the host's GPL-3 code.

Right to left: a title whose first letter is Hebrew or Arabic (`card.is_rtl`) has
its font runs drawn from right to left; raqm orders the characters inside each
run, so a Latin word or a number in it stays left to right. An Arabic word split
by a line break gets a zero-width joiner on both sides, so its letters keep their
joined forms.

Not covered yet (boxes), added on demand: Georgian, Bengali, Tamil and the other
Indic scripts, Ethiopic, Khmer, Lao, Myanmar, Sinhala, Tibetan.

To add a script: add a font with that script here, compressed the same way, with
its license, and add an entry to `card.FALLBACK_FONTS`. Prefer a font drawn on a
pixel grid at about 12 px. For a script that needs shaping (Indic, Thai), an
outline font with OpenType tables at 13 px reads better than a pixel font
without them. Check the result with a rendered card before adding it.
