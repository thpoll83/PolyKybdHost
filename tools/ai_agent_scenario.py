#!/usr/bin/env python3
"""The agent-prompt scenario and its keyboard layout — ONE definition.

tools/ai_agent_demo.py (stills + HID cost) and tools/ai_agent_gif.py (animation)
both read this, so the picture, the animation and the measured report counts
cannot describe different prompts.

⚠️ Rows are addressed by MATRIX POSITION ("row,col"), not by keycode. Two reasons,
both found by rendering it the other way first: the layout is *physical* (a row of
caps is a line of text, whatever those keys happen to type), and `KC_ENTER` appears
**twice** in the base keymap — at (4,6) and (7,7) — so a keycode-keyed cell map
silently paints one cap with the other's text.

Layout rules that came out of actually rendering it:

  * ⚠️ A ROW OF CAPS IS ONE TEXT STRIP, TWO LINES PER CAP, and prose is broken at
    LETTER boundaries, not word boundaries. One word per cap looks tidy on a toy
    prompt and collapses on a real one: an agent question is 150-200 characters,
    and spending a whole 72x40 panel on "in" leaves nowhere for the rest. Flowed,
    a 12-cap row holds ~220 characters instead of ~12 words.
  * ⚠️ FILL EACH CAP BEFORE MOVING ON (cap-major), never line-0-across-the-row.
    A single wide display would do the latter, and it renders WRONG here: the caps
    are physically separate — and the halves ~20 cm apart — so the eye reads one
    cap's two lines as a pair. Line-major made the top row read "The upstr / M
    menu". Each cap is its own ~16-character chunk, read like a word.
  * ⚠️ A ROW BELONGS TO ONE OPTION, across both halves. The halves sit far apart
    but the eye still reads straight across them, so option 1 on the left home row
    and option 2 on the right home row read as ONE sentence. Tried it; unreadable.
    One option per physical row, and the whole row is the button.
  * ⚠️ NOTHING MAY SIT IN THE MIDDLE OF A ROW. The agent-name tile was on the AI
    key (6,1) — the right half's INNER edge — which is exactly where the eye
    crosses the gap, so it cut option 1 in half. It lives at (5,7), the far outer
    corner, mirroring Esc at (0,0).
  * ⚠️ The bottom row is the thumb cluster, rotated and unevenly spaced, so a 4th
    option there reads visibly worse than options 1-3 on the letter rows. Keep the
    4th option SHORT — it is nearly always the escape ("stop", "skip", "hand back").

Geometry facts this encodes (see qmk_firmware/CLAUDE.md § per-keycap rendering):
the upper rows carry panels at cols 0-6 only (col 7 is a routing phantom), the
bottom row is a full 8-wide row, the right half applies a `c--` display fold on
rows 5-8 so col 1 is its INNER edge, and (3,7) / (8,0) have no OLED at all.
"""


def _row(r, cols):
    return [f"{r},{c}" for c in cols]


CANCEL_POS = "0,0"          # Esc, left outer corner
WHO_POS = "5,7"             # which agent is asking — right OUTER corner, off the rows
AGENT_POS = "6,1"           # the AI key you press (KC_HYPR on the base layer)

# The question: the two number rows, inner columns only.
ROW_QUESTION = _row(0, range(1, 7)) + _row(5, range(1, 7))              # 12 caps

# One option per physical row, each spanning both halves.
OPTION_ROWS = [
    _row(1, range(1, 7)) + _row(6, range(1, 8)),                        # 13  upper
    _row(2, range(1, 7)) + _row(7, range(1, 8)),                        # 13  home
    _row(3, range(1, 7)) + _row(8, range(1, 8)),                        # 13  lower
    _row(4, range(1, 7)) + _row(9, range(0, 7)),                        # 13  thumbs
]

# Six parallel sessions for the overview frame — the Codex Micro's model, but
# shown only while you ask for it.
AGENT_TILES = _row(0, range(1, 7))
AGENTS = [("fw", "think"), ("docs", "ASK?"), ("rig", "done"),
          ("host", "think"), ("kicad", "idle"), ("web", "err")]
ASKING = 1

# Two rounds of a plausible session, shaped like a real coding agent's prompt: a
# sentence-length question and four sentence-length options. Row capacity measured
# with CapPainter.flow() is ~220 characters per 12-cap row; check_fits() below
# asserts nothing silently overflows.
ROUNDS = [
    {"who": "fw\nasks",
     "q": "The upstream merge added -Wunused-but-set-parameter to common_rules.mk. "
          "With -Werror that fails six DOOM menu callbacks in vendored m_menu.c. "
          "How should I resolve it?",
     "options": [
         "Demote it in the doom-only EXTRAFLAGS block in keyboards/polykybd/"
         "rules.mk, so our own sources keep the warning",
         "Patch the six m_menu.c callbacks to consume the ignored parameter, "
         "editing vendored third-party code",
         "Show me the failing output and that rules.mk block first",
         "Skip the DOOM pack, finish the merge without it",
     ],
     "press": 0},
    {"who": "rig\nasks",
     "q": "HIL on split72 went red: the master never enumerated after the flash "
          "and the console stayed silent. The same commit passed an hour ago. "
          "What do you want me to do?",
     "options": [
         "Check the rig is on current ctnd main first — a stale checkout runs the "
         "old settle and flakes exactly like this",
         "Re-run the job once; a boot-window race is the usual cause",
         "Power-cycle both halves over the RUN pin, then retry",
         "Stop and hand it back to me",
     ],
     "press": 0},
]


def prompt_cells(painter, q, options=(), *, q_chars=None, marker=True, lines=2):
    """{matrix_pos: 72x40 buffer} for one prompt frame, flowed across the rows.

    ``q_chars`` truncates the question to that many characters, which is how the
    animation streams it in: the strip fills like a terminal line, not word by
    word. Returns only the caps this frame paints — the caller decides what the
    rest of the board shows.
    """
    cells = {}
    text = q if q_chars is None else q[:q_chars]
    bufs, _ = painter.flow(text, len(ROW_QUESTION), lines=lines)
    cells.update(zip(ROW_QUESTION, bufs))
    for i, opt in enumerate(options):
        row = OPTION_ROWS[i]
        bufs, _ = painter.flow(opt, len(row),
                               marker=str(i + 1) if marker else None, lines=lines)
        cells.update(zip(row, bufs))
    return cells


def option_positions(index):
    """Every cap belonging to option ``index`` — the whole row is the button."""
    return set(OPTION_ROWS[index])


def check_fits(painter, lines=2):
    """Text that overflows its row. Silent truncation is the failure mode a mockup
    hides best, so both tools call this at startup and print what it returns."""
    bad = []
    for r, rnd in enumerate(ROUNDS):
        _, over = painter.flow(rnd["q"], len(ROW_QUESTION), lines=lines)
        if over:
            bad.append(f"round {r} question overflows by {len(over)} chars: {over!r}")
        for i, opt in enumerate(rnd["options"]):
            _, over = painter.flow(opt, len(OPTION_ROWS[i]),
                                   marker=str(i + 1), lines=lines)
            if over:
                bad.append(f"round {r} option {i + 1} overflows by "
                           f"{len(over)} chars: {over!r}")
    return bad
