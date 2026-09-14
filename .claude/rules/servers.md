---
paths:
  - "polyhost/server/control_server.py"
  - "polyhost/server/window_report_server.py"
  - "polyhost/server/mpc_listener.py"
  - "polyhost/server/protocol.py"
---
# The three listener servers

- ⚠️ **When a bug is found in one server, grep the other two before designing
  anything.** The `ControlServer.stop()` deadlock was diagnosed from stack traces
  across three sessions while `window_report_server.py` carried the identical fix,
  comment and rationale in prose.
- **Waking a blocked `accept()` uses a bounded RAW connect, never an authed
  `mpc.Client`** — the authkey challenge is blocking and un-timeoutable, and only a
  thread inside `accept()` answers it. If the loop has already exited, `stop()` blocks
  forever on the main thread.
- ⚠️ **`wake_address()` exists because a wildcard `0.0.0.0` bind is not connectable** —
  the network server overrides it to dial loopback.
- ⚠️ **The surfaces stay separate — that separation is the security boundary.** The
  network endpoint serves exactly ONE method, carries no registry and holds no
  `PolyCore` reference, so it can never reach device control, flash or bootloader.
