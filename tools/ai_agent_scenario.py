#!/usr/bin/env python3
"""The agent-prompt scenario and its keyboard layout — ONE definition.

tools/ai_agent_demo.py (stills + HID cost) and tools/ai_agent_gif.py (animation)
both read this, so the picture, the animation and the measured report counts
cannot describe different prompts.

Layout rules that came out of actually rendering it:

  * ⚠️ A ROW BELONGS TO ONE OPTION, across both halves. The halves sit ~20 cm
    apart but the eye still reads straight across them, so option 1 on the left
    home row and option 2 on the right home row read as ONE sentence spanning
    both. Tried it; unreadable. One option per physical row — a short option just
    stops part-way along it, a long one continues onto the other half.
  * One word per key. A 72x40 keycap holds ~6-8 characters at a legible size, so
    a sentence-length option cannot live on one key — it lives on a row, and the
    WHOLE ROW is the button (press any key of it to choose that option).
  * ⚠️ The bottom row is the thumb cluster, which is rotated and unevenly spaced,
    so a 4th option there reads visibly worse than options 1-3 on the letter
    rows. Four fits; three reads well.
"""

AGENT_KEY = "KC_HYPR"        # stand-in for the proposed KC_AGENT
CANCEL_KEY = "KC_ESC"

# Row 0, both halves — the question. ~12 words.
ROW_QUESTION = ["KC_1", "KC_2", "KC_3", "KC_4", "KC_5", "KC_NUBS",
                "KC_6", "KC_7", "KC_8", "KC_9", "KC_0", "KC_MINUS"]

# One option per row, each spanning both halves.
OPTION_ROWS = [
    ["KC_Q", "KC_W", "KC_E", "KC_R", "KC_T", "KC_GRAVE",
     "KC_Y", "KC_U", "KC_I", "KC_O", "KC_P", "KC_BSLS"],          # 1  upper row
    ["KC_A", "KC_S", "KC_D", "KC_F", "KC_G", "KC_QUOTE",
     "KC_H", "KC_J", "KC_K", "KC_L", "KC_EQUAL"],                 # 2  home row
    ["KC_Z", "KC_X", "KC_C", "KC_V", "KC_B",
     "KC_N", "KC_M", "KC_COMMA", "KC_SCLN"],                      # 3  lower row
    ["KC_LWIN", "KC_LALT", "KC_APP", "KC_SPACE", "KC_DEL",
     "KC_SLASH", "KC_DOT"],                                       # 4  thumb row
]

# Six parallel sessions for the overview frame — the Codex Micro's model, but
# shown only while you ask for it.
AGENT_TILES = ["KC_1", "KC_2", "KC_3", "KC_4", "KC_5", "KC_6"]
AGENTS = [("fw", "think"), ("docs", "ASK?"), ("rig", "done"),
          ("host", "think"), ("kicad", "idle"), ("web", "err")]
ASKING = 1

# Two rounds of a plausible session, shaped like a real coding agent's prompt:
# a sentence-length question and up to four sentence-length options.
ROUNDS = [
    {"who": "fw\nasks",
     "q": "Conflict in split_sync.c: both sides changed the retry logic. Resolve how?",
     "options": ["Keep ours, drop upstream backoff",
                 "Take upstream, keep our retry count",
                 "Show me both sides first",
                 "Skip file, continue merge"],
     "press": 1},
    {"who": "rig\nasks",
     "q": "HIL test failed on split72: no enumeration after the flash. What now?",
     "options": ["Re-run the HIL job",
                 "Fetch the rig diagnostics",
                 "Power-cycle and retry once",
                 "Stop and hand it back"],
     "press": 0},
]
