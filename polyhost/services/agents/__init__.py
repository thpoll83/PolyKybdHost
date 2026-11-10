"""AI agent sessions on the number row (docs/agent-registry-plan.md).

Qt-free. The registry holds every agent session the adapters report (hooks,
window titles). The controller maps one page of up to 10 agents onto the
keyboard's number row over HID cmd 45/46 (firmware protocol v30+).
"""
