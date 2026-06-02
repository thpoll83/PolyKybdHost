## Summary
<!-- What does this PR change and why? -->


## Version bump label
<!-- The CI automatically bumps the version when this PR merges.
     Default (no label) = patch bump.  Add ONE label to override: -->

| Label | When to use |
|---|---|
| *(none)* | Bug fix, small tweak — patch bump `0.0.x` |
| `bump:minor` | New feature, backwards-compatible change — minor bump `0.x.0` |
| `bump:major` | Breaking change or major redesign — major bump `x.0.0` |
| `bump:protocol` | HID protocol change — increments `__protocol__` only (must also update firmware `PROTOCOL_VERSION`) |

> **Protocol changes** require a matching `bump:protocol` PR in
> [qmk_firmware](https://github.com/thpoll83/qmk_firmware) so both sides
> stay in sync.

## Testing
- [ ] Tested locally against real hardware
- [ ] Tested with mock device (if UI changes)
