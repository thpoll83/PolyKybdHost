# Notifications on the keyboard: plan

**Status:** concept (2026-11-28), not built. Written after the MCP server
([`mcp-server-plan.md`](mcp-server-plan.md)) and the agent keys
([`agent-registry-plan.md`](agent-registry-plan.md)) to decide how they fit together,
and whether the agent keys can become a general notification area.

## Goal

The keyboard tells the user that something needs them, whatever the source: an AI
agent waits for a permission, a build finished, the assistant was asked to "tell me
when the tests pass", a firmware update is ready. Today only AI agents can do this,
through the agent keys. This plan makes the agent registry one source of a general
notification area, and adds two more sources: an MCP `notify` tool and
`polyctl notify` for scripts.

## The three features and their jobs

| Feature | Who starts it | What it is for | Needs the model to act |
|---|---|---|---|
| Agent keys (hooks) | the agent's own events | the STATE of every running agent: working, waiting, done | no |
| MCP server | the user, through the assistant | change the keyboard on request: language, keys, overlays, drawings | yes |
| Overlays and drawn keys | the window matcher, or the user's own sets | what each key shows for the focused app, or always (`"*"`) | no |

- **The agent keys stay the status channel.** A hook fires on the agent's events
  whether or not the model remembers an instruction, and it reports "waiting for
  permission", which no MCP tool can: the model is blocked on that prompt, and the
  tool call would itself need permission.
- **The MCP server adds what hooks cannot know.** A hook knows the lifecycle of a
  turn (started, tool call, waiting, stopped). It does not know what the model
  learned: "the tests failed", "the deploy is done", "the file you asked about
  changed". Only the model can say that, and only by calling a tool.
- **Drawn keys are the long-lived indicator.** A notification goes away when it is
  seen. A drawing (`draw_key`, `"*"` set) stays until it is removed, for things such
  as "this key is my test command" or a status the user wants to keep in view.

Together, for one request such as "run the tests and tell me how it went":

1. The hook marks the agent's key `working` (amber). The user can switch apps.
2. The agent needs a permission: the hook marks the key `waiting` (red, blinking).
3. The tests finish. The model calls `notify("tests: 3 failed", level: attention)`.
   The key rings and the notification card says what happened.
4. The turn ends: the hook marks the key `done` (green). The user presses the AI key,
   sees both cards, presses the agent's key and its window comes to the front.

## A general notification area

### The model

A notification is a registry entry like an agent, with a source instead of a vendor:

| Field | Meaning |
|---|---|
| `source` | `agent:<vendor>` (the agent keys), `mcp`, `polyctl`, `host` |
| `id` | stable per source: a later post with the same id replaces the entry |
| `text` | one short line, at most the status line's 128 px, ASCII as in cmd 49 TEXT; the card shows what fits |
| `level` | `info` (no ring), `attention` (ring 3 times, like a finished agent), `urgent` (blinks red until seen, like `waiting`) |
| `expires` | seconds, or until seen. A seen `info` entry goes away; agents keep their own states |
| `action` | what pressing its key does: raise the window that posted it (agents, and an MCP client whose window is known), or nothing |

The agent registry (`services/agents/registry.py`) already has the entry, the slot
assignment over pages of 10 keys, the cards, the LED states and the "seen" logic. A
notification becomes an entry in the same registry with its own mark on the card,
so the number row shows agents and notifications side by side, in arrival order.
An agent is the source whose state comes from hooks. Nothing else in the registry
needs to know the difference.

### What the user sees

- **Outside AI mode**: a number-row LED per entry, as today (amber, red, green). A
  new `attention` entry rings its key; an `urgent` one blinks red, and the AI key
  ripples every 4 s while it is unseen, as for a waiting agent.
- **In AI mode** (the AI key; renamed in the UI to the notification key if this is
  built): each number key shows a card. An agent's card as today; a notification's
  card shows the source mark (MCP, terminal, host) and its text. Pressing the key
  runs its action and marks it seen.
- **The status display** shows the newest unseen notification's text for a few
  seconds. Today cmd 49 TEXT works only inside a tutorial session (the keyboard's 10 s
  watchdog), so this needs a firmware change (phase N2).

### Sources

| Source | How it posts | Notes |
|---|---|---|
| AI agents | hooks, title scanner, cloud relay (unchanged) | the agent keys of today |
| MCP | tool `notify(text, level, id?, expires?)`, `clear_notification(id)` | any MCP client: Claude Code, Claude Desktop, ChatGPT desktop, Cursor |
| Hookless agents | MCP tool `report_state(state)` (the "MCP shim" of the registry plan) | gives identity, `working` and `done`; never `waiting` |
| Scripts | `polyctl notify "build done" --level attention` | `make && polyctl notify ...`, a CI watcher, a cron job |
| Host | the host's own events: a firmware or host update, a font pack that failed to flash | today these are tray balloons, which macOS does not show |

### Rules

- **Local only.** Notifications come from this computer (and the forwarder and the
  cloud relay, which already feed the registry). No network listener is added.
- **Opt-in per source.** `notify_sources` setting: agents (as `agents_enabled` today),
  MCP (also needs `mcp_enabled`), scripts, host. Off by default except host.
- **Rate limit per source.** At most 10 posts a minute and 10 entries per source;
  the oldest unseen entry of that source is dropped. Prompt injection could make an
  assistant post many times; the limit keeps the number row usable.
- **What a keycap shows, everyone near the desk sees.** The text is short, the user
  chose the source, and the tray can turn a source off.
- **No new data leaves the host.** Notification text is never sent to telemetry or
  a log bundle (the log line names the source and level only).

## The MCP additions

| Tool | Control method | Kind |
|---|---|---|
| `notify(text, level="attention", id?, expires?)` | `notify.post` | write |
| `clear_notification(id)` | `notify.clear` | write |
| `list_notifications()` | `notify.list` (only entries this client posted) | read |
| `report_state(state, title?)` | `agents.report` with the MCP client as vendor `mcp:<client name>` | write |

- The new methods go on the allow-list and the frozen test changes with them.
  `agents.report` is allowed for MCP connections only with a `mcp:` vendor, so an
  assistant cannot fake a Claude Code hook.
- The client name comes from MCP `initialize` (`clientInfo.name`); the host does not
  trust it for anything but the card's label.
- `notify` returns the entry's id and the key it got, so the assistant can clear it.

## Build order

1. **N1, host only, no firmware change.**
   - Generalize the registry entry (`source`, `level`, `expires`, `action`).
   - Notification cards in the existing card renderer.
   - `notify.*` control methods, `polyctl notify`, and the MCP tools above.
   - Host events as a source, replacing balloons that never reach macOS users.
   - Uses only what the keyboard has: cmd 45/46 (cards, LEDs, events) and cmd 47
     (the ring).
2. **N2, firmware.** A status-line notice outside tutorials: a new cmd 49 op or a
   cmd 45 op that shows one line for a given time, version-gated, with the
   protocol increase on both sides (`add-gated-hid-command`). RAM: one 59-byte line,
   about the size of cmd 49 TEXT.
3. **N3, later.** More sources only when someone asks: a webhook through the cloud
   relay (CI on GitHub), calendar reminders. Each is a new source with its own opt-in.

## Tests

- Registry: a notification and an agent share pages and slots; replace by id;
  expiry; rate limit per source; seen clears `info`.
- MCP: `notify` refused while `mcp_enabled` is off; `report_state` cannot use a
  non-`mcp:` vendor; frozen allow-list updated.
- Mock keyboard: a posted notification produces a card upload (cmd 46) and a ring
  (cmd 47) on a keyboard with the agent keys, and nothing on one without them.

## Open questions

1. Does the AI key become the notification key in the UI and docs, or does the
   notification area get its own key (another custom keycode)?
2. Should a drawn `"*"` key be able to show a notification count (a small badge)?
   That would join overlays and notifications, but it needs a redraw per change.
3. Which host events are worth a notification and not just a log line: firmware
   update, font-pack flash failure, keyboard reconnect after a crash?
4. Should `polyctl notify` work from another computer through the forwarder, as
   `agents.report` does behind its opt-in (HOST-6)?
