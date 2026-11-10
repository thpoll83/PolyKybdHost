"""Map an agent's hook payload to a registry report.

One table for every vendor. Each vendor sends JSON with its own field names, so
`interpret()` reads the event name and the session id from the first field that
has them, normalises the event, and maps it to a state.

Sources for the event names (2026-11): Claude Code hooks, Codex hooks and its
`notify` program, Gemini CLI hooks, Antigravity `hooks.json`, Copilot CLI hooks,
Cursor hooks, OpenCode plugin events, Qwen Code hooks. A field this module does
not know is ignored, never an error: a hook must not fail the agent.

⚠️ No prompt text, tool arguments or file contents leave this module. Only the
session id, the state, the working directory and the process id are kept.
"""
from __future__ import annotations

import re

from polyhost.services.agents.model import ENDED, AgentState

_EVENT_FIELDS = ("hook_event_name", "hookEventName", "event", "event_name", "type")
_SESSION_FIELDS = ("session_id", "sessionId", "sessionID", "thread-id", "thread_id",
                   "conversation_id", "conversationId")
_CWD_FIELDS = ("cwd", "workspace", "project_dir", "workspace_root")

# normalised event -> (state or None for "fields only", registry event tag)
_EVENTS = {
    "sessionstart": (AgentState.IDLE, ""),
    "sessionend": (ENDED, ""),
    "userpromptsubmit": (AgentState.WORKING, "prompt"),
    "userpromptsubmitted": (AgentState.WORKING, "prompt"),
    "beforeagent": (AgentState.WORKING, "prompt"),
    "preinvocation": (AgentState.WORKING, "prompt"),
    "pretooluse": (AgentState.WORKING, "pretool"),
    "beforetool": (AgentState.WORKING, "pretool"),
    "beforeshellexecution": (AgentState.WORKING, "pretool"),
    "posttooluse": (AgentState.WORKING, "posttool"),
    "aftertool": (AgentState.WORKING, "posttool"),
    "aftershellexecution": (AgentState.WORKING, "posttool"),
    "afterfileedit": (AgentState.WORKING, "posttool"),
    "postinvocation": (AgentState.WORKING, "posttool"),
    "permissionrequest": (AgentState.WAITING, "posttool"),
    "permissionasked": (AgentState.WAITING, "posttool"),
    "permissionreplied": (AgentState.WORKING, "posttool"),
    "stop": (AgentState.DONE, "stop"),
    "afteragent": (AgentState.DONE, "stop"),
    "agentturncomplete": (AgentState.DONE, "stop"),
    "sessionidle": (AgentState.DONE, "stop"),
    "subagentstop": (None, ""),
    "precompact": (None, ""),
    "postcompact": (None, ""),
}


def normalise_event(name: str) -> str:
    return re.sub(r"[^a-z]", "", (name or "").lower())


def _first(payload: dict, fields) -> str:
    for name in fields:
        value = payload.get(name)
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return ""


def interpret(payload: dict) -> dict | None:
    """{"session_id", "state", "event", "cwd"} for a hook payload, or None when the
    payload names no session or an event that changes nothing."""
    if not isinstance(payload, dict):
        return None
    properties = payload.get("properties")
    if isinstance(properties, dict):
        # OpenCode plugin events carry their fields one level down.
        payload = {**properties, **{k: v for k, v in payload.items() if k != "properties"}}
    session = _first(payload, _SESSION_FIELDS)
    if not session:
        return None
    event = normalise_event(_first(payload, _EVENT_FIELDS))
    tag = ""
    if event == "notification":
        state, tag = _notification_state(payload)
    elif event in _EVENTS:
        state, tag = _EVENTS[event]
    else:
        return None
    if state is None and not tag:
        return None
    return {"session_id": session, "state": state, "event": tag,
            "cwd": _first(payload, _CWD_FIELDS)}


def _notification_state(payload: dict):
    """Claude Code: notification_type permission_prompt / idle_prompt.
    Gemini CLI: notification_type ToolPermission. Anything else that names a
    permission is read as waiting too."""
    kind = normalise_event(str(payload.get("notification_type")
                               or payload.get("notificationType") or ""))
    if kind in ("permissionprompt", "toolpermission", "elicitationdialog"):
        return AgentState.WAITING, "posttool"
    if kind == "idleprompt":
        return AgentState.DONE, "idle_prompt"
    message = str(payload.get("message") or "").lower()
    if "permission" in message or "approv" in message:
        return AgentState.WAITING, "posttool"
    return None, ""
