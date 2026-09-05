# The AI key

One key on the keyboard wears an agent's status and calls you back to it.

* The **light** under the key: green when the agent is quiet, amber while it is
  working, blinking red when it is waiting on you. The keycap spells the same word
  out, so it still reads on a split42 (no RGB matrix) and without colour vision.
* **Pressing** it raises the agent's window — and pressing it again walks to the next
  matching window, so several sessions at once still works.

Nothing here is specific to one AI tool. The host exposes two commands and anything
that can run a command can drive them.

## Set it up

1. Tell the host which window the key should raise. The pattern is a
   case-insensitive part of the window title, or a regex written as `/.../`:

   ```
   polyctl ai target "Claude Code"
   polyctl ai status            # what it matches right now
   ```

2. Point your agent at the hook adapter. It reads whichever shape your tool sends
   and never fails the tool it is hooked into.

   **Claude Code** — in `~/.claude/settings.json`:

   ```json
   {
     "hooks": {
       "UserPromptSubmit": [{"hooks": [{"type": "command",
          "command": "python3 ~/polykybd/contrib/ai-hooks/polykybd_ai_hook.py"}]}],
       "Notification":     [{"hooks": [{"type": "command",
          "command": "python3 ~/polykybd/contrib/ai-hooks/polykybd_ai_hook.py"}]}],
       "Stop":             [{"hooks": [{"type": "command",
          "command": "python3 ~/polykybd/contrib/ai-hooks/polykybd_ai_hook.py"}]}]
     }
   }
   ```

   `Notification` is the one that turns the key red — it is what fires when Claude
   Code wants a permission answer or your input.

   **OpenAI Codex CLI** — in `~/.codex/config.toml`:

   ```toml
   notify = ["python3", "/home/you/polykybd/contrib/ai-hooks/polykybd_ai_hook.py"]
   ```

   ⚠️ Codex's `notify` has exactly ONE event, `agent-turn-complete`, so it can turn
   the light green when a turn ends but cannot say "working" or "waiting on you" on
   its own. Drive those from wherever you start the agent:

   ```sh
   polyctl ai state working && codex ... ; polyctl ai state idle
   ```

   **Anything else** — one command per state, no adapter needed:

   ```
   polyctl ai state working
   polyctl ai state attention
   polyctl ai state idle
   polyctl ai state off        # hand the LED back to your normal lighting
   ```

   The words `busy`, `running`, `done`, `ready`, `waiting`, `ask` and `input` work
   too, so a hook can use its own vocabulary.

## What is where

| Piece | Where |
|---|---|
| The key, its light and the press | firmware, `keyboards/polykybd/poly_keymap.c` (`KC_AI`) |
| The status command | firmware HID cmd 40, protocol v17+ |
| Reading the press | host, `polyhost/services/ai_link.py` (the firmware console) |
| The commands | `polyctl ai state|target|status` |

## Notes

* The status lives in the keyboard's RAM only. A keyboard reboot clears it, and the
  host re-pushes what it last knew on reconnect.
* Firmware older than protocol v17 ignores the status (`polyctl ai status` says so),
  but the key press still works — it travels on the console, which any firmware
  carrying the key prints.
* A press during a firmware or font-pack flash is lost: the console is not drained
  while an upload is streaming. Press it again.
* Raising a window needs a window manager that lets a client do it. Native Wayland
  does not, and the key says so rather than doing nothing quietly.
