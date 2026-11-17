"""Write (or remove) the PolyKybd hooks in an agent's own config file.

`polyctl agents hooks install <vendor>` uses this. Each vendor gets a plan: the
files to change, with their text before and after, so the caller can show a diff
and ask before writing. Hooks the user wrote themselves are kept; only entries
whose command contains HOOK_MARK are replaced or removed.

Claude Code gets the short event set: no PreToolUse, since PermissionRequest and
Notification report the waiting state. PostToolUse stays, so the key turns back to
"working" once a permission was answered. Each hook call starts Python (about
0.27 s), so leaving PreToolUse out removes that delay before every tool call.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass

HOOK_MARK = "agents hook"

CLAUDE_EVENTS = ("SessionStart", "UserPromptSubmit", "PermissionRequest", "PostToolUse",
                 "Notification", "Stop", "SessionEnd")
# Events that need a matcher in Claude Code's settings ("*" = every tool).
CLAUDE_TOOL_EVENTS = ("PermissionRequest", "PostToolUse", "PreToolUse")
COPILOT_EVENTS = ("sessionStart", "userPromptSubmitted", "preToolUse", "postToolUse",
                  "agentStop", "errorOccurred", "sessionEnd")
# Gemini CLI (docs/hooks/reference.md): permission prompts arrive as a Notification
# with notification_type ToolPermission, so no BeforeTool hook is needed.
GEMINI_EVENTS = ("SessionStart", "BeforeAgent", "AfterTool", "AfterAgent", "Notification",
                 "SessionEnd")
# Qwen Code (docs/users/features/hooks.md) uses Claude Code's event names.
QWEN_EVENTS = ("SessionStart", "UserPromptSubmit", "PermissionRequest", "PostToolUse",
               "Notification", "Stop", "SessionEnd")
# OpenCode events the plugin passes on. Only session.idle is in the current docs;
# the permission and status names are the older ones, kept so either version works
# (hooks.interpret ignores an event it does not know).
OPENCODE_EVENTS = ("session.status", "session.idle", "session.error", "permission.asked",
                   "permission.updated", "permission.replied")
VENDORS = ("claude-code", "codex", "copilot", "gemini", "qwen", "opencode")


@dataclass
class FileChange:
    path: str
    before: str      # "" when the file does not exist
    after: str       # "" means delete the file


def polyctl_argv() -> list[str]:
    """How a hook starts polyctl: the console script if it is on PATH, else this
    Python with -m. Absolute, because an agent's hook shell can have another PATH."""
    found = shutil.which("polyctl")
    if found:
        return [os.path.abspath(found)]
    return [sys.executable, "-m", "polyhost.cli.polyctl"]


def _shell_command(argv: list[str], powershell: bool = False) -> str:
    def quote(arg):
        return f'"{arg}"' if (" " in arg or "\\" in arg) else arg
    text = " ".join(quote(a) for a in argv)
    # PowerShell runs a leading quoted string only with the call operator.
    return f"& {text}" if powershell and argv and quote(argv[0]) != argv[0] else text


def _is_ours(entry) -> bool:
    return HOOK_MARK in json.dumps(entry)


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


# ---- Claude Code ---------------------------------------------------------------

def plan_claude(home: str, install: bool = True, argv: list[str] | None = None,
                extra: list[str] = ()) -> list[FileChange]:
    path = os.path.join(home, ".claude", "settings.json")
    before = _read(path)
    data = json.loads(before) if before.strip() else {}
    hooks = data.setdefault("hooks", {})
    for event in list(hooks):
        kept = []
        for group in hooks[event]:
            inner = [h for h in group.get("hooks", []) if not _is_ours(h)]
            if inner:
                kept.append({**group, "hooks": inner})
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if install:
        command = _shell_command((argv or polyctl_argv()) + ["agents", "hook", "claude-code"]
                                 + list(extra))
        for event in CLAUDE_EVENTS:
            group = {"hooks": [{"type": "command", "command": command}]}
            if event in CLAUDE_TOOL_EVENTS:
                group = {"matcher": "*", **group}
            hooks.setdefault(event, []).append(group)
    if not hooks:
        del data["hooks"]
    after = json.dumps(data, indent=2) + "\n"
    return [FileChange(path, before, after)] if after != before else []


# ---- Codex ---------------------------------------------------------------------

def plan_codex(home: str, install: bool = True, argv: list[str] | None = None,
               extra: list[str] = ()) -> list[FileChange]:
    """`notify` in ~/.codex/config.toml. A notify line of the user's own is left
    alone (Codex takes one notify program): the plan is then empty and
    `codex_conflict()` says why."""
    path = os.path.join(home, ".codex", "config.toml")
    before = _read(path)
    lines = before.splitlines()
    ours = [i for i, l in enumerate(lines) if _codex_notify(l) and _codex_ours(l)]
    other = [i for i, l in enumerate(lines) if _codex_notify(l) and i not in ours]
    if other and install:
        return []
    lines = [l for i, l in enumerate(lines) if i not in ours]
    if install:
        args = (argv or polyctl_argv()) + ["agents", "hook", "codex"] + list(extra)
        lines.insert(0, "notify = " + json.dumps(args))
    after = "\n".join(lines) + ("\n" if lines else "")
    return [FileChange(path, before, after)] if after != before else []


def _codex_notify(line: str) -> bool:
    return line.strip().replace(" ", "").startswith("notify=")


def _codex_ours(line: str) -> bool:
    return '"agents", "hook"' in line


def codex_conflict(home: str) -> str:
    text = _read(os.path.join(home, ".codex", "config.toml"))
    for line in text.splitlines():
        if _codex_notify(line) and not _codex_ours(line):
            return ("~/.codex/config.toml already has its own notify program; Codex takes "
                    "only one, so it was left alone. Add the hook to that program, or "
                    "replace the line with: notify = " +
                    json.dumps(polyctl_argv() + ["agents", "hook", "codex"]))
    return ""


# ---- Copilot CLI ---------------------------------------------------------------

def plan_copilot(home: str, install: bool = True, argv: list[str] | None = None,
                 extra: list[str] = ()) -> list[FileChange]:
    """Its own file, ~/.copilot/hooks/polykybd.json, so no merge is needed."""
    path = os.path.join(home, ".copilot", "hooks", "polykybd.json")
    before = _read(path)
    if not install:
        return [FileChange(path, before, "")] if before else []
    base = (argv or polyctl_argv()) + ["agents", "hook", "copilot"] + list(extra)
    hooks = {e: [{"type": "command",
                  "powershell": _shell_command(base + ["--event", e], powershell=True),
                  "bash": _shell_command(base + ["--event", e]),
                  "timeoutSec": 5}] for e in COPILOT_EVENTS}
    after = json.dumps({"version": 1, "hooks": hooks}, indent=2) + "\n"
    return [FileChange(path, before, after)] if after != before else []


# ---- Gemini CLI and Qwen Code ----------------------------------------------------

def _plan_settings_hooks(path: str, vendor: str, events, timeout, install: bool,
                         argv, extra) -> list[FileChange]:
    """A `hooks` object in a settings.json, Claude Code's shape: event -> [{matcher,
    hooks: [{type, command, name, timeout}]}]. Other hooks and settings are kept."""
    before = _read(path)
    data = json.loads(before) if before.strip() else {}
    hooks = data.setdefault("hooks", {})
    for event in list(hooks):
        kept = []
        for group in hooks[event]:
            inner = [h for h in group.get("hooks", []) if not _is_ours(h)]
            if inner:
                kept.append({**group, "hooks": inner})
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if install:
        command = _shell_command((argv or polyctl_argv()) + ["agents", "hook", vendor]
                                 + list(extra))
        for event in events:
            hooks.setdefault(event, []).append(
                {"matcher": "*", "hooks": [{"type": "command", "name": "polykybd",
                                            "command": command, "timeout": timeout}]})
    if not hooks:
        del data["hooks"]
    after = json.dumps(data, indent=2) + "\n"
    if not before.strip() and not data:
        after = ""
    return [FileChange(path, before, after)] if after != before else []


def plan_gemini(home: str, install: bool = True, argv: list[str] | None = None,
                extra: list[str] = ()) -> list[FileChange]:
    """~/.gemini/settings.json; Gemini's hook timeout is in milliseconds."""
    return _plan_settings_hooks(os.path.join(home, ".gemini", "settings.json"), "gemini",
                                GEMINI_EVENTS, 5000, install, argv, extra)


def plan_qwen(home: str, install: bool = True, argv: list[str] | None = None,
              extra: list[str] = ()) -> list[FileChange]:
    """~/.qwen/settings.json; Qwen's hook timeout is in seconds."""
    return _plan_settings_hooks(os.path.join(home, ".qwen", "settings.json"), "qwen",
                                QWEN_EVENTS, 5, install, argv, extra)


# ---- OpenCode ------------------------------------------------------------------

OPENCODE_PLUGIN = """// PolyKybd agent keys. Written by PolyHost (polyctl agents hooks install opencode);
// remove it with: polyctl agents hooks uninstall opencode. Marker: agents hook
// Each event below goes as JSON on stdin to `polyctl agents hook opencode`, which
// never writes to stdout and always exits 0. A failed start is ignored.
import { spawn } from "node:child_process";

const ARGV = __ARGV__;
const EVENTS = new Set(__EVENTS__);

export const PolyKybd = async ({ directory }) => ({
  event: async ({ event }) => {
    if (!event || !EVENTS.has(event.type)) return;
    try {
      const child = spawn(ARGV[0], ARGV.slice(1),
                          { stdio: ["pipe", "ignore", "ignore"], windowsHide: true });
      child.on("error", () => {});
      child.stdin.on("error", () => {});
      child.stdin.end(JSON.stringify({ ...event, cwd: directory }));
    } catch (e) {}
  },
});
"""


def plan_opencode(home: str, install: bool = True, argv: list[str] | None = None,
                  extra: list[str] = ()) -> list[FileChange]:
    """Its own plugin file, ~/.config/opencode/plugins/polykybd.js (OpenCode has no
    shell hooks). On Windows OpenCode also reads ~/.config/opencode."""
    path = os.path.join(home, ".config", "opencode", "plugins", "polykybd.js")
    before = _read(path)
    if not install:
        return [FileChange(path, before, "")] if before else []
    args = (argv or polyctl_argv()) + ["agents", "hook", "opencode"] + list(extra)
    after = (OPENCODE_PLUGIN.replace("__ARGV__", json.dumps(args))
             .replace("__EVENTS__", json.dumps(list(OPENCODE_EVENTS))))
    return [FileChange(path, before, after)] if after != before else []


PLANNERS = {"claude-code": plan_claude, "codex": plan_codex, "copilot": plan_copilot,
            "gemini": plan_gemini, "qwen": plan_qwen, "opencode": plan_opencode}


def plan(vendor: str, home: str | None = None, install: bool = True,
         argv: list[str] | None = None, extra_args: list[str] = ()) -> list[FileChange]:
    """`extra_args` go after `agents hook <vendor>` in every command, e.g.
    ["--host", "desktop"] on a forwarder's machine."""
    if vendor not in PLANNERS:
        raise ValueError(f"no installer for {vendor!r}; supported: {', '.join(VENDORS)}")
    return PLANNERS[vendor](home or os.path.expanduser("~"), install, argv, extra_args)


def apply(changes: list[FileChange]) -> list[str]:
    """Write the changes. An existing file is first copied to <file>.polykybd.bak.
    Returns the paths written or removed."""
    done = []
    for change in changes:
        if change.before:
            with open(change.path + ".polykybd.bak", "w", encoding="utf-8") as fh:
                fh.write(change.before)
        if change.after:
            os.makedirs(os.path.dirname(change.path), exist_ok=True)
            with open(change.path, "w", encoding="utf-8") as fh:
                fh.write(change.after)
        elif os.path.exists(change.path):
            os.remove(change.path)
        done.append(change.path)
    return done


# ---- Status (the Integrations dialog) --------------------------------------------

STATE_INSTALLED = "installed"          # the hooks match what install would write
STATE_NOT_INSTALLED = "not-installed"  # no PolyKybd hook in the file
STATE_OUTDATED = "outdated"            # PolyKybd hooks of another path or version
STATE_CONFLICT = "conflict"            # Codex: a notify program of the user's own
STATE_ERROR = "error"                  # the file cannot be read or parsed

# The file each vendor's hooks are written to, below the home folder. The
# planners above use the same paths.
CONFIG_FILES = {
    "claude-code": (".claude", "settings.json"),
    "codex": (".codex", "config.toml"),
    "copilot": (".copilot", "hooks", "polykybd.json"),
    "gemini": (".gemini", "settings.json"),
    "qwen": (".qwen", "settings.json"),
    "opencode": (".config", "opencode", "plugins", "polykybd.js"),
}


@dataclass
class HookStatus:
    vendor: str
    path: str
    state: str
    detail: str = ""   # the conflict or error text

    @property
    def has_ours(self) -> bool:
        """Whether Remove has PolyKybd hooks to take out."""
        return self.state in (STATE_INSTALLED, STATE_OUTDATED)


def config_path(vendor: str, home: str | None = None) -> str:
    return os.path.join(home or os.path.expanduser("~"), *CONFIG_FILES[vendor])


def _contains_ours(text: str) -> bool:
    # A command string has "agents hook <vendor>"; Codex's notify line and the
    # OpenCode plugin have the argv as JSON: "agents", "hook".
    return HOOK_MARK in text or '"agents", "hook"' in text


def _strings(value):
    """Every string inside a JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _arg_after(argv: list[str], flag: str):
    try:
        return argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return None


def pinned_target(vendor: str, home: str | None = None) -> dict | None:
    """{"host", "authkey_file"} when the installed hooks were written with
    `--host` (a keyboard on another computer), else None: they then follow the
    forwarder on this computer, or report to this computer's host."""
    import re
    import shlex
    try:
        text = _read(config_path(vendor, home))
    except OSError:
        return None
    argvs = []
    # Codex's notify line and the OpenCode plugin: the argv as a JSON-style array.
    for array in re.findall(r"\[([^\[\]]*agents[^\[\]]*)\]", text):
        try:
            argv = json.loads("[" + array + "]")
        except ValueError:
            continue
        if isinstance(argv, list) and all(isinstance(a, str) for a in argv):
            argvs.append(argv)
    # The other agents: a shell command in a JSON string.
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    for command in _strings(data):
        if not _contains_ours(command):
            continue
        try:
            argvs.append(shlex.split(command.lstrip("& ")))
        except ValueError:
            continue
    for argv in argvs:
        if not ("agents" in argv and "hook" in argv):
            continue
        host = _arg_after(argv, "--host")
        if host:
            return {"host": host, "authkey_file": _arg_after(argv, "--authkey-file")}
    return None


def status(vendor: str, home: str | None = None,
           argv: list[str] | None = None) -> HookStatus:
    """The state of one vendor's hooks, read from its config file. Never raises
    for a broken file: the state is then STATE_ERROR."""
    home = home or os.path.expanduser("~")
    path = config_path(vendor, home)
    try:
        text = _read(path)
        if vendor == "codex":
            conflict = codex_conflict(home)
            if conflict:
                return HookStatus(vendor, path, STATE_CONFLICT, conflict)
        if not plan(vendor, home, True, argv):
            return HookStatus(vendor, path, STATE_INSTALLED)
    except (OSError, ValueError, TypeError, AttributeError) as e:
        # TypeError/AttributeError: valid JSON of another shape, e.g.
        # {"hooks": null}. One agent's broken file must not hide the others.
        return HookStatus(vendor, path, STATE_ERROR, str(e) or type(e).__name__)
    return HookStatus(vendor, path, STATE_OUTDATED if _contains_ours(text)
                      else STATE_NOT_INSTALLED)
