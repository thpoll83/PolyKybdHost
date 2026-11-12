# PolyKybd agent keys: setup instructions for an AI coding agent

Give this file to the agent (Claude Code, Codex, Gemini CLI, Antigravity, Copilot
CLI, Cursor, OpenCode, Qwen Code) and ask it to set itself up. It is written for the
agent to follow.

## What this does

The PolyKybd keyboard shows the state of each agent session on the number row. The
host app (PolyKybdHost) learns the state from the agent's **hooks**: on each
lifecycle event the agent runs one command, and that command reports the event to
the host. Hooks are used, not MCP, because an MCP tool runs only when the model
calls it. While the agent waits for a permission answer, the model is not running,
so an MCP tool cannot report "waiting".

Requirements: PolyKybdHost 1.22.2 or later, keyboard firmware 1.13.0 or later
(protocol 31), and the setting turned on:

```
polyctl settings set agents_enabled true
```

Then unplug and replug the keyboard once.

## The command

```
polyctl agents hook <vendor>
```

- `<vendor>` is one of: `claude-code`, `codex`, `gemini`, `antigravity`, `copilot`,
  `cursor`, `opencode`, `qwen`, `aider`.
- It reads the hook's JSON from **stdin**, or from its **last argument** when the
  agent passes the JSON as an argument (Codex `notify` does).
- It always exits 0, prints nothing to stdout and gives up after 4 s, so it never
  blocks the agent. It sends only the session id, the event, the state, the working
  directory, the surface (`cli`) and the agent's process id; for Claude Code also the
  session's title (the text the terminal tab shows, which can describe your work); and
  through a forwarder also this computer's name. It never sends the prompt, the
  transcript or tool arguments.
- If `polyctl` is not on `PATH` (a checkout without `pip install -e .`), use
  `<path-to-PolyKybdHost>/.venv/bin/python -m polyhost.cli.polyctl agents hook <vendor>`,
  or `.venv\Scripts\python.exe` on Windows.

## Which events to hook

Run the command on every event of this list that your hook system has. The host
maps the names itself; it ignores case, `-`, `_` and `.`.

| Event (any of these names) | Shown as |
|---|---|
| SessionStart | idle |
| UserPromptSubmit, UserPromptSubmitted, BeforeAgent | working |
| PreToolUse, BeforeTool, BeforeShellExecution | working |
| PostToolUse, AfterTool, AfterShellExecution, AfterFileEdit | working |
| PermissionRequest, `permission.asked` | **waiting** (red, blinking) |
| Notification with `notification_type` `permission_prompt` or `ToolPermission` | **waiting** |
| Notification with `notification_type` `idle_prompt` | done |
| Stop, AfterAgent, `agent-turn-complete`, `session.idle` | done (green) |
| SessionEnd | removed from the keyboard when the user ended the session (`/exit`, `/clear`, logout); for any other reason (an editor or the desktop app restarting the process) the key stays as idle |

The payload must contain a session id in one of these fields: `session_id`,
`sessionId`, `sessionID`, `thread-id`, `conversation_id`. A payload without one is
ignored.

If your hook system has no event for a permission prompt (Antigravity, Copilot
CLI, Cursor), still hook PreToolUse and PostToolUse. The host shows "waiting" when a
PreToolUse has no PostToolUse after 5 s.

## The quick way

`polyctl agents hooks install claude-code` (or `codex`, `copilot`, `gemini`, `qwen`,
`opencode`) writes the hooks
into the agent's own config file. It shows the diff and asks before it writes,
keeps hooks you wrote yourself, keeps a copy as `<file>.polykybd.bak`, and puts the
absolute path of `polyctl` into each command, so the agent's shell needs no PATH
entry. `--dry-run` only shows the diff; `polyctl agents hooks uninstall <vendor>`
removes them again. No PolyKybdHost needs to be running.

For Claude Code it writes a shorter set than the block below: no `PreToolUse`,
because `PermissionRequest` and `Notification` already report "waiting". Each hook
call starts Python (about 0.3 s), so this removes that delay before every tool call.

## Agents on a second computer (forwarder)

On a computer that runs the PolyKybdHost **forwarder** (the keyboard is on another
computer), first pair the forwarder with the keyboard computer, once:

1. On the keyboard computer: tray > AI Agents > "Pair a Forwarder…" (or
   `polyctl forwarder pairing-code`) shows a code. It is the key of the network
   endpoint: anyone with it can send reports to that computer.
2. On the forwarder's computer: forwarder tray > "Pair with the Keyboard Computer…"
   (or `polyctl forwarder pair <code>`), then restart the forwarder.

A paired forwarder uses the authenticated connection (`--report-rpc`) with that key,
without command-line flags. Without the key it would be refused with "digest sent
was rejected". `--report-rpc` and `--report-authkey-file` still work and take
priority over the pairing.

Then install the hooks as on any computer (forwarder tray > "Set Up Agent Hooks", or):

```
polyctl agents hooks install claude-code
```

Each hook call reads the forwarder's current target from
`polykybd-agents-target.json` in the config folder, and reports over the same
authenticated network endpoint the forwarder uses. The forwarder rewrites that file
whenever its target changes (for example through `--host-file`), so the hooks follow
it. `--host <keyboard computer> [--authkey-file <file>]` on the install fixes the
hooks to one computer instead.

- The forwarder must be paired (or run with `--report-rpc`). Otherwise it uses its
  plain TCP relay, which has no reply channel and no key, writes no target, and the
  hooks find no host.
- The keyboard computer needs three settings on: `window_report_network_enabled`
  (as for the forwarder itself), `agents_enabled`, and `agents_remote_enabled`,
  which is off by default (Settings > AI agents > "Agents from other computers").
  With it off, the endpoint refuses `agents.report` and relays no raise.
- Its agents appear on the keys with this computer's name (`polyctl agents list`
  on the keyboard computer shows it in the `machine` field).
- A key press on one of its agents brings forward, on the keyboard computer, the
  remote-desktop viewer that shows this computer: NoMachine, Remote Desktop, VNC
  (RealVNC, TigerVNC, TightVNC, UltraVNC), Remmina, Parsec, AnyDesk, TeamViewer,
  RustDesk and every app the overlay mapping marks `remote: true`. The viewer
  whose title names this computer is taken; with no such title, the viewer, when
  only one is open.
- To also bring the agent's own window forward on this computer, turn on
  `agents_raise_here` here (forwarder Settings > AI agents > "Raise agent windows
  on this computer", off by default). The press then reaches this computer's
  forwarder in the reply to its next window report; while this computer has agents
  on the keys, the forwarder reports every second, so the window comes forward
  within about a second.
- The forwarder and the hooks must run on the same computer: both name it with its
  host name.

## Claude Code (tested format)

Merge this into `~/.claude/settings.json` (all projects) or `.claude/settings.json`
(one project). Keep any hooks that are already there; add to their lists.

```json
{
  "hooks": {
    "SessionStart":      [{"hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}],
    "UserPromptSubmit":  [{"hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}],
    "PreToolUse":        [{"matcher": "*", "hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}],
    "PostToolUse":       [{"matcher": "*", "hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}],
    "PermissionRequest": [{"matcher": "*", "hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}],
    "Notification":      [{"hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}],
    "Stop":              [{"hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}],
    "SessionEnd":        [{"hooks": [{"type": "command", "command": "polyctl agents hook claude-code"}]}]
  }
}
```

## Codex CLI

In `~/.codex/config.toml`:

```toml
notify = ["polyctl", "agents", "hook", "codex"]
```

`notify` reports only "turn finished". If your Codex version has hooks
(`~/.codex/hooks.json`), hook the events from the table above in the format your
version documents, with the command `polyctl agents hook codex`; that adds
"working" and "waiting".

## Copilot CLI

`~/.copilot/hooks/polykybd.json` (all repositories) or `.github/hooks/polykybd.json`
(one repository). Copilot's hook JSON may not name the event, so each command
names it with `--event`. Without a session id the folder is the session: one key
per folder. Copilot has no event for a permission prompt; the host shows
"waiting" when a `preToolUse` has no `postToolUse` after 5 s.

```json
{
  "version": 1,
  "hooks": {
    "sessionStart":        [{"type": "command", "powershell": "polyctl agents hook copilot --event sessionStart", "bash": "polyctl agents hook copilot --event sessionStart", "timeoutSec": 5}],
    "userPromptSubmitted": [{"type": "command", "powershell": "polyctl agents hook copilot --event userPromptSubmitted", "bash": "polyctl agents hook copilot --event userPromptSubmitted", "timeoutSec": 5}],
    "preToolUse":          [{"type": "command", "powershell": "polyctl agents hook copilot --event preToolUse", "bash": "polyctl agents hook copilot --event preToolUse", "timeoutSec": 5}],
    "postToolUse":         [{"type": "command", "powershell": "polyctl agents hook copilot --event postToolUse", "bash": "polyctl agents hook copilot --event postToolUse", "timeoutSec": 5}],
    "agentStop":           [{"type": "command", "powershell": "polyctl agents hook copilot --event agentStop", "bash": "polyctl agents hook copilot --event agentStop", "timeoutSec": 5}],
    "errorOccurred":       [{"type": "command", "powershell": "polyctl agents hook copilot --event errorOccurred", "bash": "polyctl agents hook copilot --event errorOccurred", "timeoutSec": 5}],
    "sessionEnd":          [{"type": "command", "powershell": "polyctl agents hook copilot --event sessionEnd", "bash": "polyctl agents hook copilot --event sessionEnd", "timeoutSec": 5}]
  }
}
```

## Other agents

`polyctl agents hooks install <vendor>` (or the tray's Set Up Hooks menu) also
writes the hooks for these, keeping any hooks of your own. Their formats were not
tested with the keyboard yet.

- Gemini CLI (`gemini`): `~/.gemini/settings.json`, `hooks`, for SessionStart,
  BeforeAgent, AfterTool, AfterAgent, Notification and SessionEnd. A tool permission
  prompt arrives as a Notification of type `ToolPermission`.
- Qwen Code (`qwen`): `~/.qwen/settings.json`, `hooks`, with Claude Code's events.
- OpenCode (`opencode`) has no shell hooks: the installer writes the plugin
  `~/.config/opencode/plugins/polykybd.js`, which pipes `session.status`,
  `session.idle`, `session.error` and the permission events as JSON into
  `polyctl agents hook opencode`.

Antigravity (`.agents/hooks.json` or `~/.gemini/config/hooks.json`) and Cursor
(`.cursor/hooks.json` or `~/.cursor/hooks.json`) have no installer: for each event
in the table above run `polyctl agents hook <vendor>` with the hook JSON on stdin.

## Check that it works

1. Run `polyctl agents list`. It shows `agent keys: on; keyboard active`.
2. Send one prompt in the agent. `polyctl agents list` now shows the session with
   state `working`, then `done` when the turn ends.
3. The key shows the session's title: for Claude Code the hook reads it from the
   session transcript (`transcript_path`), the same text the terminal tab shows as
   `✳ <title>`, and sends only that line. Before the first title exists, and for
   other agents, it shows the working directory's name; agents that would show the
   same text are numbered ("agent 1", "agent 2").
4. To show your own text on the key instead:
   `polyctl agents label <vendor> <session_id> "<text>"` (the session id is in the
   list).

Without any hook, an agent running in a terminal is still found by its window
title (not on macOS): Claude Code, Codex, Gemini CLI, Qwen Code, OpenCode, Copilot
CLI, Kimi Code, Grok Build and Mistral Vibe. What the title shows differs:

- Gemini CLI, Qwen Code and Grok Build show working and waiting.
- Claude Code shows working, but "waiting" and "done" look the same (`✳`).
- Codex shows waiting (`[ ! ] Action Required`); otherwise only with the shell
  integration's Codex option.
- OpenCode, Copilot CLI, Kimi Code and Mistral Vibe show only that they run
  (idle), Vibe also working.
- Kimi Code's title stops naming it once the session has a title.

A hook gives the real state. Formats: `res/overlay_sources/aicli/SOURCES.md`.
