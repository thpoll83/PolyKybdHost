## Summary
<!-- What does this PR change and why? -->


## Version bump label
<!-- The CI automatically bumps the version when this PR merges.
     Default (no label) = patch bump.  Add ONE label to override: -->

| Label | When to use |
|---|---|
| *(none)* | **The default since 1.0.** Bug fix, diagnostic, developer tool or small addition, even one that bumps the protocol — patch bump `x.y.Z` |
| `bump:minor` | A feature an owner would call new, the kind that names a release — minor bump `x.Y.0`. When unsure, leave it off |
| `bump:major` | Breaking change or major redesign — major bump `X.0.0` |
| `bump:protocol` | Only when the PR does NOT already edit `__protocol__` in source — increments it after merge. Omit it when the source bumps it, or it is bumped twice |

> **Protocol changes** need a matching `PROTOCOL_VERSION` change in
> [qmk_firmware](https://github.com/thpoll83/qmk_firmware) so both sides stay in sync.

## Testing
- [ ] Tested locally against real hardware
- [ ] Tested with mock device (if UI changes)
