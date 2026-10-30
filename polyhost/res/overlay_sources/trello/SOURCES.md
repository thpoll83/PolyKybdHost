# Trello overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `trello_template` (1 file), `_mac` (2 files) | a browser tab on trello.com `/b/`, `/c/` or `/u/`, or a window title ending in "\| Trello" when no URL is known |

Trello's desktop apps were retired, so the set is only under the browser entries
(Chrome and the other Chromium browsers, Firefox and Safari, through the shared
`&web_urls` maps). The title form "<board> | Trello" was not checked in a
browser.

## Shortcut reference

<https://trello.com/shortcuts>, read 2026-10-30 with headless Chromium (the
page renders its list with JavaScript, so a plain fetch returns no shortcuts).
Atlassian's help article
<https://support.atlassian.com/trello/docs/keyboard-shortcuts-in-trello/> lists
a subset and agrees with it. Trello writes "Control (Windows) or Command (Mac)",
so the Ctrl bindings use `CMDCTRL`.

| Key | Action |
|---|---|
| J / K (and the arrows) | select the next / previous card |
| ] | show or hide the board menu |
| B | open the boards menu |
| / | focus the search box |
| C | archive the card |
| D | due date |
| - | add a checklist (card open) |
| E | quick edit |
| Enter | open the card |
| Ctrl/Cmd+Enter | save the text being written |
| F | card filter |
| L | labels |
| 1 … 0 | apply or remove the green, yellow, orange, red, purple, blue, sky, lime, pink, black label |
| ; | show or hide label names |
| M | add or remove members |
| N | insert a card after the selected one |
| , / . | move the card to the bottom of the left / right list |
| < / > (Shift+, / Shift+.) | move the card to the top of the left / right list |
| Q | "cards assigned to me" filter |
| S | watch the card |
| Space | assign or unassign yourself |
| T | edit the title |
| V | vote (Voting Power-Up) |
| X | clear all filters |
| ? (Shift+/) | shortcuts page |
| Z / Shift+Z | undo / redo |
| R | repeat the last action on another card |
| Ctrl/Cmd+C, X, V | copy, cut (move), paste a card while hovering |

Left out: Esc (it shows the program mark), the arrows (they keep their
legends), `@` (only while writing a comment), Shift+Enter (only while creating
a card), Shift+click and Shift+scroll (mouse).

## Icons

Microsoft Fluent UI System Icons (MIT,
<https://github.com/microsoft/fluentui-system-icons>) by default; Material
Symbols (Apache-2.0, <https://github.com/google/material-design-icons>) where
`fetch_icons.py` names `ms:<name>`. Copy, Cut, Paste, Undo and Redo are drawn
by the shared concept renderer.

| File | Source | Licence |
|---|---|---|
| `next.png`, `prev.png` | Material `keyboard_arrow_down`, `keyboard_arrow_up` | Apache-2.0 |
| `boardmenu.png` | Fluent `Panel Right` | MIT |
| `boards.png` | Fluent `Board` | MIT |
| `search.png` | Fluent `Search` | MIT |
| `archive.png` | Fluent `Archive` | MIT |
| `due.png` | Fluent `Calendar Clock` | MIT |
| `checklist.png` | Material `checklist` | Apache-2.0 |
| `quickedit.png` | Fluent `Edit` | MIT |
| `open.png` | Material `open_in_full` | Apache-2.0 |
| `save.png` | Material `send` | Apache-2.0 |
| `filter.png`, `clearfilter.png` | Fluent `Filter`, `Filter Dismiss` | MIT |
| `labels.png`, `labelnames.png` | Fluent `Tag`, `Tag Multiple` | MIT |
| `members.png` | Fluent `People Add` | MIT |
| `newcard.png` | Material `note_add` | Apache-2.0 |
| `movebottomleft.png`, `movebottomright.png` | Fluent `Arrow Left`, `Arrow Right` | MIT |
| `movetopleft.png`, `movetopright.png` | Fluent `Arrow Previous`, `Arrow Next` | MIT |
| `mycards.png` | Material `person_search` | Apache-2.0 |
| `watch.png` | Fluent `Eye` | MIT |
| `assignself.png` | Material `how_to_reg` | Apache-2.0 |
| `title.png` | Fluent `Rename` | MIT |
| `vote.png` | Fluent `Thumb Like` | MIT |
| `shortcuts.png` | Fluent `Keyboard` | MIT |
| `repeat.png` | Material `repeat` | Apache-2.0 |
| `label_0.png` … `label_9.png` | drawn by `fetch_icons.label_icons()`: a tag over the colour's short name in Liberation Sans Bold, 1-bit at 40×40 | (this repo) |
| `trello.png` (ESC) | Simple Icons `trello` | CC0-1.0 artwork; nominative use, see `../brand_marks.py` |

The label icons are drawn at their final size and bound with `region: [40, 40]`,
so the generator places them 1:1.
