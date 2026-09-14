---
paths:
  - "polyhost/core/poly_core.py"
  - "polyhost/core/events.py"
  - "polyhost/core/decisions.py"
---
# Editing PolyCore

Full notes: `docs/architecture.md`.

- **`PolyCore` must stay importable without PyQt5 and without a display**, and must
  communicate ONLY through observer callbacks with JSON-serializable payloads.
  Worker-side code must never touch a Qt object. Guarded by
  `tests/core/import_guard_test.py`.
- **A settings change applies its device side effects through ONE hook** —
  `note_settings_changed(keys=None)`. Add the side effect there, never to a caller;
  there are two settings writers and the second copy is how a setting came to do
  nothing at all mid-session.
- **The reconnect probe is debounced (3 strikes)** because the keyboard goes deaf after
  a large overlay transfer. A single failed probe must not flap the connection state —
  that wipes the overlays and forces a resend, a self-sustaining oscillation.
- **A mode/value counts as pushed only when the device CONFIRMS it** — `worker.submit`
  only queues, so recording at submit time suppresses the retry that exists to fix the
  failure.
- ⚠️ `Observable.emit` **snapshots under the lock and fires outside it**, and a raising
  observer is caught, logged and left subscribed. Both are load-bearing.
