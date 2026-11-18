# Fallback fonts for the agent cards

`services/agents/card.py` draws a card's text in Pillow's bundled font (Aileron).
A character that font does not have is drawn with the first font listed in
`card.FALLBACK_FONTS` that has it.

| file | font | size | covers | license |
|---|---|---|---|---|
| `Galmuri11.ttf.xz` | Galmuri11 2.40.3 by Lee Minseo, from the npm package `galmuri` | 12 px | all 11,172 Hangul syllables, Hiragana, Katakana, 6,477 CJK ideographs, Cyrillic | SIL OFL 1.1 (`OFL-Galmuri.txt`) |

The file is the unchanged `dist/Galmuri11.ttf` (SHA-256
`2c709890595668f7bdb6df408420fda957dde0288e95b31a1cc17a2ab98b4b4f`), compressed
with `xz -9e`. The card code reads it into memory once.

To add a script (Hebrew, Arabic, Thai, Devanagari, …): add a pixel font with that
script here, compressed the same way, with its license, and add an entry to
`card.FALLBACK_FONTS`. Choose a font drawn on a pixel grid at about 12 px: an
outline font such as Noto comes out ragged at that size in 1 bit.
