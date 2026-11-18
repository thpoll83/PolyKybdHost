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

WenQuanYi Zen Hei is GPL-2 only. The file is a separate data file that the host
reads at run time, not part of the host's GPL-3 code.

Not covered yet (boxes): Georgian, Armenian, Hebrew, Arabic, Bengali, Tamil and
other Indic scripts. Hebrew and Arabic also need right-to-left handling, which
`card._runs` does not do.

To add a script: add a font with that script here, compressed the same way, with
its license, and add an entry to `card.FALLBACK_FONTS`. Prefer a font drawn on a
pixel grid at about 12 px. For a script that needs shaping (Indic, Thai), an
outline font with OpenType tables at 13 px reads better than a pixel font
without them. Check the result with a rendered card before adding it.
