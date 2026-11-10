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

Requirements: PolyKybdHost from branch `ccr-821a0b53-8mu20l` (PolyKybdHost#763),
keyboard firmware with protocol 30 (qmk_firmware#424), and the setting turned on:

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
- It always exits 0, prints nothing to stdout and never blocks the agent. It sends
  only the session id, the event, the working directory and its parent process id.
  It never sends the prompt or tool arguments.
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
| SessionEnd | removed from the keyboard |

The payload must contain a session id in one of these fields: `session_id`,
`sessionId`, `sessionID`, `thread-id`, `conversation_id`. A payload without one is
ignored.

If your hook system has no event for a permission prompt (Antigravity, Copilot
CLI, Cursor), still hook PreToolUse and PostToolUse. The host shows "waiting" when a
PreToolUse has no PostToolUse after 5 s.

## The quick way

`polyctl agents hooks install claude-code` (or `codex`, `copilot`) writes the hooks
into the agent's own config file. It shows the diff and asks before it writes,
keeps hooks you wrote yourself, keeps a copy as `<file>.polykybd.bak`, and puts the
absolute path of `polyctl` into each command, so the agent's shell needs no PATH
entry. `--dry-run` only shows the diff; `polyctl agents hooks uninstall <vendor>`
removes them again. No PolyKybdHost needs to be running.

For Claude Code it writes a shorter set than the block below: no `PreToolUse`,
because `PermissionRequest` and `Notification` already report "waiting". Each hook
call starts Python (about 0.3 s), so this removes that delay before every tool call.

## Agents on a second computer (forwarder)

On a computer that runs the PolyKybdHost **forwarder** with `--report-rpc` (the
keyboard is on another computer), the hooks report over the same authenticated
network endpoint the forwarder uses:

```
polyctl agents hooks install claude-code --host <keyboard computer> [--authkey-file <its polykybd-winreport.authkey>]
```

- The keyboard computer must have `window_report_network_enabled` on, as for the
  forwarder itself.
- Its agents appear on the keys with this computer's name (`polyctl agents list`
  on the keyboard computer shows it in the `machine` field).
- A key press is sent back to this computer's forwarder in the reply to its next
  window report; while this computer has agents on the keys, the forwarder reports
  every second, so the window comes forward within about a second.
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

Gemini CLI, Antigravity, Copilot CLI, Cursor, OpenCode and Qwen Code each have
their own hook file. Use the format your own documentation gives, and for each
event in the table above run `polyctl agents hook <vendor>` with the hook JSON on
stdin. These formats were not tested with the keyboard yet.

- Gemini CLI: `settings.json`, `hooks`.
- Antigravity: `.agents/hooks.json` (project) or `~/.gemini/config/hooks.json`.
- Cursor: `.cursor/hooks.json` or `~/.cursor/hooks.json`.
- Qwen Code: `.qwen/settings.json`, `hooks`.
- OpenCode has no shell hooks. It needs a small plugin that, on the `event` handler,
  pipes `JSON.stringify(event)` into `polyctl agents hook opencode` for
  `permission.asked`, `permission.replied` and `session.idle`.

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

Without any hook, Claude Code, Gemini CLI and Codex running in a terminal are still
found by their window title (not on macOS), but then "waiting" and "done" look the
same.
