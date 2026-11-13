# Agent registry and the AI key: plan

Status: prototype on branch `ccr-821a0b53-8mu20l` in PolyKybdHost and qmk_firmware,
protocol 31 (30 is Caps Word / Auto Shift, qmk#425). Not tested on a keyboard. Written 2026-11-10 against host 1.21.4 and
firmware 1.11.3 (protocol 29).

## What the prototype has

- Host: `polyhost/services/agents/` (registry, hook mapping, title scanner, card
  renderer, controller, window raise), `PolyKybd.ai_*` behind the `agent_keys` gate,
  the emulated firmware, `PolyCore`'s `agents` periodic, control methods
  `agents.list/report/label/forget`, and `polyctl agents list|report|label|forget|hook`.
- Firmware: `KC_AI`, AI mode (hold or tap), swallowing, the event ring, cmd 45 and 46,
  card drawing, number-row LEDs.
- Changes from the plan below: the card upload is its own command, **cmd 46**, not an
  op of cmd 45, because a 60-byte segment plus an op byte does not fit the 62-byte
  payload. The 12 cards (10 number keys, `-`, `+`) borrow pool slots from the MRU
  cache instead of reserving any (`OverlayMRUCache.allocate_aside`): a switch
  evicts a card first and the host uploads it again on its next pass, so the
  600-image limit per switch is unchanged.
- Added after the first hardware test: in AI mode `-` starts dictation (the OS
  shortcut, Win+H on Windows, setting `agents_dictation_shortcut` elsewhere) and `+`
  raises the next agent that waits, cycling, from any page. Both have host-drawn
  cards; `+` shows how many agents wait and blinks red while one does. ESC shows
  "Next" and pages only when there is more than one page.
- Not in the prototype: a tray menu (turn it on with
  `polyctl settings set agents_enabled true`, then reconnect the keyboard),
  `polyctl agents pin`, `hooks install`, the forwarder relay, the MCP shim, a HIL test.

To try it, add a hook to each agent that runs `polyctl agents hook <vendor>`. For
Claude Code, in `~/.claude/settings.json`, every event (`SessionStart`,
`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Notification`, `PermissionRequest`,
`Stop`, `SessionEnd`) gets
`{"hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}`.
For Codex, `notify = ["polyctl", "agents", "hook", "codex"]` in `~/.codex/config.toml`.
Without hooks, Claude Code, Gemini CLI and Codex in a terminal are found by their
window titles (not on macOS).

This plan replaces the AI key set that has been open since September:
qmk_firmware#276, PolyKybdHost#216 and polykybd-docs#72. Those PRs drive one key for
one agent. This plan drives a row of keys for many agents. Parts of them are reused
(see [Reuse from the open AI key PRs](#reuse-from-the-open-ai-key-prs)). polykybd-ctnd#95
(HOST-5) stays valid on its own.

## What the user sees

1. **Outside AI mode**, the number row `1`..`0` (10 keys) keeps its normal legends
   and keycodes. Its RGB LEDs show the state of up to 10 agents, one agent per key.
   A key with no agent keeps the running RGB effect.
2. **The AI key** (`KC_AI`, a custom keycode the user binds in the layout editor; the
   maintainer puts it top right) switches the board into AI mode. In AI mode:
   - each number key shows an agent card on its OLED: the vendor's mark, a state mark
     and a short text line (the headline) that names the agent;
   - pressing a number key brings that agent's window to the front, and the board
     leaves AI mode;
   - ESC becomes the pager when there are more than 10 agents. Each press shows the
     next page of 10. The LEDs follow the page.
3. **The page stays selected after AI mode ends.** The number row LEDs keep showing
   the page last chosen, until the user picks another page or that page empties.

### Hold or tap

Hold-only does not work with this layout. The AI key is on the right half, and keys
`6`..`0` are also on the right half, so one hand cannot hold AI and press `8`.

What the prototype does (firmware `ai_mode.h`):

- **Tap** the AI key: a one-shot Hyper (Ctrl+Shift+Alt+GUI on the next key), for
  global shortcuts. A tap never shows the cards.
- **Hold** it past the tapping term, or press another key while it is down: AI mode
  turns on. Released after a key was pressed in the mode, the mode ends.
- **Long press and release** with nothing pressed: AI mode stays on until a number
  key, `-`, `+`, any other key (swallowed), or a timeout (10 s, open, see
  [Open questions](#open-questions)). That keeps one hand free for `6`..`0`.

ESC (the pager) does not end AI mode in either case.

### The agent card (72×40, 1 bit)

```
┌────────────────────────────────────┐
│ [vendor mark 24×24]   [state mark] │   rows 0..25
│                                    │
│ polykybd-docs                      │   rows 28..39: headline, one line
└────────────────────────────────────┘
```

- Vendor mark: the ESC program mark for that vendor's app (`services/app_icons.py`,
  Simple Icons), scaled to the left part of the card. A vendor with no mark gets its
  name in text.
- State mark: the same set for every vendor (see the state table). The state is also
  on the LED, but the mark covers split42 (no RGB matrix) and colour blindness.
- Headline: one line in the smallest resident face, cut to what fits in 72 px. Source
  order: a label the user set (`polyctl agents label`), the topic from the terminal
  title (Claude Code writes `✳ <topic>`), the session's working directory name.

The host renders the card as an image (Python, the same path as other overlays) and
uploads it. The firmware draws no text and no layout for it. Measure every card
layout with `tools/oled_preview.py`: 0 pixels outside 72×40.

## States

| State | Meaning | LED | Mark |
|---|---|---|---|
| `working` | a turn is running | amber, breathing | turning arrows |
| `waiting` | the agent waits for the user: a permission prompt or a question | red, blinking | `!` |
| `done` | a turn finished and the user has not looked since | green, steady | check |
| `idle` | finished and seen, or no turn yet | dim green, then off | none |
| `stale` | no event for a long time, the process may be gone | dim white | `?` |
| (empty) | no agent on this key | RGB effect unchanged | normal legend |

- `done` becomes `idle` when the user raises that agent, from the key or by focusing
  its window (the host sees the focus change).
- Only `waiting` blinks, as in #276.
- When a page that is not shown has an agent in `waiting`, the ESC LED blinks red in
  AI mode. Outside AI mode ESC is not touched (open question: show it there too).

## The registry (host)

A Qt-free module, `polyhost/services/agents/registry.py`, owned by `PolyCore`.

### The entry

| Field | Content |
|---|---|
| `key` | `(vendor, session_id)`. Vendor is a short id: `claude-code`, `codex`, `gemini`, `antigravity`, `copilot`, `opencode`, `qwen`, `cursor`, `aider` |
| `state` | one of the states above |
| `since` | time of the last state change |
| `last_event` | time of the last event from any adapter |
| `headline` | see the card |
| `label` | user-set text, optional |
| `cwd` | working directory, when an adapter knows it |
| `surface` | `cli`, `desktop`, `ide`, `web` |
| `machine` | `local` or the forwarder's name |
| `pid` | the agent's process id, when known |
| `window` | a window handle the raise can use, when known |
| `slot` | the key position: page × 10 + key index |

The registry keeps no prompt text, no tool arguments and no file contents. It is not
part of telemetry, the log bundle or the problem report (the payload allow-list in
`build_payload()` stays as it is).

### Session identity

- Claude Code, Codex and OpenCode send a session id in the hook payload. Use it.
- A Claude Code session moved between the web and the CLI keeps its session id, so
  both surfaces merge into one entry. The `surface` field lists the last surface seen.
- For an adapter without a session id, build one from the agent's process id and its
  working directory. The hook adapter runs as a child of the agent, so its parent
  process id is the agent.

### Slots

- **An agent keeps its key for as long as it exists.** The user learns positions, so
  agents do not move when their state changes. A new agent takes the first free slot.
- A finished or `stale` entry is removed after a grace period, and its slot becomes
  free. The value is open.
- `polyctl agents pin <id> <slot>` puts an agent on a chosen key and keeps it there.
- More than 10 agents fill page 2, page 3 and so on.

## Adapters (inputs)

Each adapter turns its source into `(key, state, fields)` and calls
`registry.report()`. One adapter per source. Hook payloads differ per vendor, so the
mapping is a table per vendor in one adapter module, as #216's
`contrib/ai-hooks/polykybd_ai_hook.py` already does for Claude Code and Codex.

| Adapter | Source | Covers | Misses |
|---|---|---|---|
| Hooks | a command each agent runs on its events, which calls `polyctl agents report` | Claude Code, Codex, Gemini CLI, Antigravity, Copilot CLI, Qwen Code, Cursor | vendors without a waiting event (below) |
| OpenCode plugin | a small JS plugin subscribed to `permission.asked` and `session.idle` | OpenCode | |
| HTTP hook | a local endpoint for agents whose hooks can POST (Copilot CLI, Qwen Code) | no script needed | |
| Aider | `--notifications-command` | waiting for input | `working`, and done vs waiting |
| Window titles | all window titles every few seconds, with #572's title patterns | any CLI in a terminal, without setup | waiting vs done (both `✳`), native Wayland |
| MCP shim (later) | an MCP server each agent connects to | identity and cwd for any MCP client | `waiting`: the model does not run during a permission prompt |

### Waiting for approval without an event

Antigravity, Copilot CLI and Cursor have `PreToolUse` and `PostToolUse` but no event
for a permission prompt (as far as their docs showed on 2026-11-09). The adapter
reports `waiting` when a `PreToolUse` has no matching `PostToolUse` after a delay.
A long shell command looks the same, so this is a heuristic, and the state is
`waiting?` in `polyctl agents list`. The delay value is open.

### Out of scope for the first version

- Cloud agents other than Claude Code. Claude Code cloud sessions (claude.ai/code)
  report through the relay since 2026-11-13: see `docs/agent-keys-agent-setup.md` →
  *Claude Code cloud sessions*.
- Chat apps without hooks: claude.ai, Claude Desktop chat, ChatGPT.
- The MCP shim. It is added only if Antigravity or another agent has no other way in.

## Raising an agent

Reuse `WindowRaiser` from #216 (`services/ai_link.py`, pywinctl enumerate and
activate). The target is the entry's `window`, or else a window matched by `pid` or
by title.

Limits that stay:

- A terminal tab or an Antigravity agent panel is not a window. Raising the window
  does not select the tab or panel.
- A web session is a browser tab. The raise brings the browser forward and stops.
- Native Wayland has no client window activation. The press is recorded and nothing
  is raised; the tray says so.
- An agent on a forwarder machine is raised there, through the reply channel #216
  built (`AiRelayFollower`). HOST-5 applies: messages on that connection are
  authenticated only at the handshake, so a forged reply can raise a window on the
  forwarder machine or show an agent that does not exist.

## Firmware

### New state, RAM only, synced to the slave

| Field | Size | Set by |
|---|---|---|
| `ai_mode` | bool | the AI key (master), synced |
| `ai_led[10]` | 3 bits each: the state of each number key | the host |
| `ai_esc_attention` | bool | the host |
| `ai_slot[10]` | pool slot of each card, `0xFFFF` = no card | the host |

None of it is persisted. A light that survived a reboot would describe an agent that
may be gone. The host re-sends everything on reconnect. Add a `static_assert` on the
sync struct size against `RPC_M2S_BUFFER_SIZE`.

### Keys

- `KC_AI` is appended at the end of the `QK_KB_*` range, as in #276. It is bound in no
  keymap.
- `KC_AI` acts on the press edge. Its release edge is read only to end hold mode, and
  fires nothing.
- In AI mode the master swallows the press AND the release of `1`..`0` and ESC. A key
  that was already down when AI mode started keeps its normal release (gate the
  swallow on ownership, the intl layer rule). The key positions come from the keymap
  (find `KC_1`..`KC_0` and `KC_ESC` on the base layer), so a remap moves them.
- Call `clear_keyboard()` when AI mode starts.
- Each swallowed press is written to an event ring: `seq` (u8), `key` (0..9, or 10 for
  ESC). The ring size is open.

### Drawing

- In AI mode, `render_key()` for a number key draws pool slot `ai_slot[i]` without the
  legend (the v25 no-legend path) instead of the normal legend and overlay.
  `to_static_text()` must give the same answer for the same key.
- A number key with no card in AI mode is blank, and its press is swallowed and
  reported (the host ignores it).
- `request_disp_refresh()` on both halves when AI mode starts and ends.

### LEDs

- `ai_rgb_paint()` from `rgb_matrix_indicators_kb`, as in #276, for the 10 number keys
  and ESC. The fade curve in #276's `base/ai_light.h` is reused for `idle`.
- If the user keeps the RGB matrix off, the light borrows it while any key is not
  empty, and returns it after (the #276 borrow).

### Protocol

One new command, `45` AI (the next free id after 44), with sub-ops. The protocol
version is whatever is next when it merges (31 today). Write it down only after the
firmware bump commit exists: #276 lost 17 to #278 in the same way.

| Op | Request | Reply |
|---|---|---|
| `0` QUERY | | `ai_mode`, page events pending, ring `seq` |
| `1` SET_KEYS | `ai_led[10]` packed, `ai_esc_attention`, `ai_slot[10]` (u16 each) | ACK |
| `2` READ_EVENTS | `seq` last read | up to N events after it, newest `seq` |

- The range is closed: an unknown op or state NACKs.
- Card images go over the existing overlay upload (RLE, cmds `0x10`/`0x11`) into pool
  slots the host chooses. No new upload path.
- **Press back to the host:** the firmware writes the event to the ring, increments `G`
  (`poly_state_touch()`), and prints `ai ev <seq>` on the console. The host reads
  op 2 when it sees the console line (250 ms) or when `G` moves (1 s). The console
  announces and op 2 defines, as `PROTOCOL_HISTORY.md` requires. A press during a
  flash is announced only by `G`.
- An `A` block value or similar is not needed: `ai_mode` is in op 0.

## Host

- `services/agents/registry.py`, `services/agents/adapters/*.py`: Qt-free, unit-tested.
- `services/agents/card.py`: renders a card (vendor mark, state mark, headline) to a
  72×40 1-bit image. Golden tests against rendered cards.
- `PolyCore`: owns the registry; pushes op 1 when a shown key changes; uploads cards
  for the shown page; reads op 2 on the console line or a `G` change; acts on presses
  (raise, page change).
- Pool slots: the cards borrow slots from the MRU cache (decided after the first
  hardware test; the prototype first reserved 12, which lowered the per-switch limit
  to 588). A switch evicts a card before any app image; a card never evicts the
  newest switch's images.
- Control methods `M_AGENTS_LIST`, `M_AGENTS_REPORT`, `M_AGENTS_LABEL`,
  `M_AGENTS_PIN`, `M_AGENTS_FORGET`, mirrored in `RemoteCore`.
- `polyctl agents list | report | label | pin | forget | hooks install <vendor>`.
  `hooks install` writes the hook entry into the vendor's config file
  (`~/.claude/settings.json`, `~/.codex/hooks.json`, `.agents/hooks.json`, …) and
  shows the diff before writing.
- Tray: an Agents submenu, gated on protocol and on `agents_enabled`. All strings
  through `_()`.
- `agents_enabled` defaults to off, as `ai_key_enabled` did in #216.
- Forwarder: relays registry reports from its machine. Its settings allow-list
  (`FORWARDER_SETTING_KEYS`) gets the new keys.
- Gating: `FEATURE_MIN_PROTOCOL`, both accessors, `CMD_MIN_PROTOCOL` in
  `device/mock_firmware.py`, the `CALLS` entry. The `add-gated-hid-command` skill.

## Reuse from the open AI key PRs

| From | Part | Use |
|---|---|---|
| host#216 | `contrib/ai-hooks/polykybd_ai_hook.py` (`decide_state`) | becomes the hook adapter; add a table per vendor |
| host#216 | `WindowRaiser` (handle-based cycle, pywinctl) | the raise |
| host#216 | `AiRelayFollower`, `raise_seq` on the `window.report` reply | the forwarder raise |
| host#216 | the keycode browser's PolyKybd tab | assigning `KC_AI` |
| qmk#276 | `KC_AI` keycode, keymap-derived key position | the AI key |
| qmk#276 | `ai_rgb_paint`, the RGB borrow, `base/ai_light.h` fade | the LEDs |
| qmk#276 | `HINT_SMALL` state marks | the split42 and no-image fallback |

Not reused: #276's cmd 40 (now the idle timeout), its `PROTOCOL_VERSION` 18, the
single `ai_state`, and the console line as the only press channel.

After this plan is accepted, close qmk#276, host#216 and docs#72 with a link here.

## Build order

1. Registry and two adapters (Claude Code hooks, window titles), with
   `polyctl agents list` only. Run it against real sessions: Claude Code in several
   terminals, Codex, Antigravity. Check identity merging and the `waiting` heuristic
   before any keyboard work.
2. Firmware cmd 45 with LEDs only (op 0, op 1 without slots). The number row shows
   states; no AI mode yet.
3. AI mode: `KC_AI`, swallowing, the event ring, op 2, raise on press.
4. Cards: `card.py`, slot reservation, upload.
5. Pager.
6. Adapters for the other vendors, `polyctl agents hooks install`.
7. Docs page, after the firmware and host releases that contain it.

## Tests

- Host: registry (identity, merge, slots, expiry), each adapter's mapping table with
  recorded payloads, card rendering (golden images, 0 pixels outside), the protocol
  sweep tests.
- Firmware: a unit suite for the event ring and the swallow ownership; `ai_light`
  stays.
- HIL: cmd 45 ops and NACKs, LED state round trip. The rig cannot press keys
  (GPIO key-matrix simulation is open work in polykybd-ctnd), so AI mode, the pager and
  the raise need a hardware round. Ask for `TIER_EXTENDED` (split link).

## Open questions

These are values or choices for the maintainer. None is in code yet.

1. Tap-latch timeout for AI mode.
2. Grace period before a finished or `stale` agent leaves its slot, and the time
   without events after which an agent counts as `stale`.
3. Delay for the `PreToolUse` without `PostToolUse` heuristic.
4. Event ring size, and the number of events op 2 returns.
5. Pool slots reserved for cards (10 or 11), which lowers the app overlay limit.
6. ESC attention blink outside AI mode: yes or no.
7. Whether a press in AI mode ends AI mode in hold mode too, or only in tap mode.
8. split42: its number row is shorter. Which keys carry agents there, or is split42
   left out of the first version.
