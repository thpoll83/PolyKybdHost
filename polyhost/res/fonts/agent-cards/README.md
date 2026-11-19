# Fonts for the agent cards

`services/agents/card.py` draws a card's text in Pillow's bundled font (Aileron),
which has only ASCII. A character it does not have is drawn with the first font
in `card.FALLBACK_FONTS` that has it.

Bundled here (xz-compressed with `xz -9e`, read into memory once):

| file | font | size | covers | license |
|---|---|---|---|---|
| `Galmuri11.ttf.xz` | Galmuri11 2.40.3 by Lee Minseo, npm package `galmuri`, unchanged (`dist/Galmuri11.ttf`, SHA-256 `2c709890…b4b4f`) | 12 px | European Latin (Latin-1, Latin Extended-A), Greek, Cyrillic, all 11,172 Hangul syllables, Hiragana, Katakana, 6,477 CJK ideographs | SIL OFL 1.1, `OFL-Galmuri.txt` |

Downloaded the first time a title needs one (setting `agents_download_fonts`, on
by default, only while the agent keys are on), into `font_downloader`'s cache:

| font | size | from | covers | license |
|---|---|---|---|---|
| WenQuanYi Zen Hei Mono, cut to the 3,939 GB2312 / Big5 level 1 characters Galmuri11 lacks (1.3 MB) | 12 px | `https://www.polykybd.org/fonts/agent-cards/` (polykybd-docs `public/fonts/agent-cards/`, with its source and license) | the rest of common simplified and traditional Chinese | GPL-2 with a font embedding exception |
| Noto Sans Devanagari | 13 px | `noto-fonts.yaml` | Hindi, Marathi, Nepali (shaped by raqm) | SIL OFL 1.1 |
| Noto Sans Thai | 13 px | `noto-fonts.yaml` | Thai | SIL OFL 1.1 |
| Noto Sans Armenian | 13 px | `noto-fonts.yaml` | Armenian | SIL OFL 1.1 |
| Noto Sans Hebrew | 13 px | `noto-fonts.yaml` | Hebrew | SIL OFL 1.1 |
| Noto Sans Arabic | 13 px | `noto-fonts.yaml` | Arabic, Persian, Urdu | SIL OFL 1.1 |

Each downloaded entry has the Unicode `ranges` it is downloaded for. The card
shows boxes until the font is there, then it is drawn again.

Right to left: a title whose first letter is Hebrew or Arabic (`card.is_rtl`) has
its font runs drawn from right to left; raqm orders the characters inside each
run, so a Latin word or a number in it stays left to right. A card has no
brackets (`model.no_brackets`), so the host mirrors none itself; raqm still
mirrors a character such as `«` in a right-to-left run. An Arabic word split
by a line break gets a zero-width joiner on both sides where its letters join
(`card._joins`, by the Unicode joining types in `card._JOINS_NEXT` and
`_JOINS_PREVIOUS`), so they keep their joined forms.

Not covered yet (boxes), added on demand: Georgian, Bengali, Tamil and the other
Indic scripts, Ethiopic, Khmer, Lao, Myanmar, Sinhala, Tibetan. Several have a
Noto font in `noto-fonts.yaml` already.

To add a script: add a `FallbackFont` with its `noto-fonts.yaml` name, or with a
`url` and a `filename` (its file name in the cache, unique among the fonts there),
its size and its Unicode ranges. Prefer a font drawn on a pixel grid at about 12 px; for a
script that needs shaping (Indic, Thai), an outline font with OpenType tables at
13 px reads better than a pixel font without them. Check the result with a
rendered card before adding it.
