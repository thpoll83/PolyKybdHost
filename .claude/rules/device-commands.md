---
paths:
  - "polyhost/device/poly_kybd.py"
  - "polyhost/device/command_ids.py"
  - "polyhost/device/cmd_composer.py"
---
# Adding or changing a device command

Full notes: `docs/protocol-gate.md` · `docs/device-features.md`. The
`add-gated-hid-command` skill drives the whole cross-repo job.

- ⚠️ **Every new device-facing command MUST be version-gated.** `FEATURE_MIN_PROTOCOL`
  entry + `self.supports()` on BOTH accessors + the GUI gate + `polyctl` + a bump of
  `__protocol__` and the firmware `PROTOCOL_VERSION` in the same change. An ungated
  command connects and then NACKs at runtime instead of cleanly disabling — the gate
  that has been forgotten twice.
- ⚠️ **`GlyphSize` is a CLOSED range; `GlyphScript` is OPEN.** Deliberate, and the one
  way they differ: an unknown script degrades to the normal legend (so new faces need
  no protocol bump), an unknown size would persist as a setting that silently renders
  small. Never "make them consistent".
- **A wire-format change to an EXISTING command is ENCODED, not blocked** — branch on
  `self.protocol_version` (the plain-overlay packed header is the only precedent).
- ⚠️ **`parse_id_version_block` finds the font-pack block POSITIONALLY.** Anything new
  in the GET_ID reply goes AFTER it, or every deployed host re-flashes all bundles.
