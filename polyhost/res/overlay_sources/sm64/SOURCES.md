# Super Mario 64 PC ports overlay (sm64ex, sm64coopdx): sources and licences

Two sets from one folder: `sm64ex.yaml` and `sm64coopdx.yaml`. Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/sm64/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/sm64/sm64ex.yaml --preview /tmp/sm64ex_preview
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/sm64/sm64coopdx.yaml --preview /tmp/sm64coopdx_preview
```

All steps are deterministic. The six sm64coopdx action icons are fetched from an
unpinned branch, so a change there changes the PNG bytes.

## What the sets load for

| set | name | where it comes from |
|---|---|---|
| sm64ex | `sm64.us.f3dex2e`, `sm64.eu.f3dex2e`, `sm64.jp.f3dex2e`, `sm64.sh.f3dex2e` | `TARGET := sm64.$(VERSION)` plus `.f3dex2e` in the `Makefile`: the Linux executable for each ROM version |
| sm64ex | `sm64` | Windows: the host cuts `sm64.us.f3dex2e.exe` at the first dot |
| sm64coopdx | `sm64coopdx` | `EXE := $(BUILD_DIR)/sm64coopdx` (`.exe` on Windows, `sm64coopdx.app` on macOS) in the `Makefile` |

Names not checked on an install. Other ports built from sm64ex can use the same
executable name with other keys.

## Shortcuts

Both ports store a bind as a scancode. The default is the first entry of each
`configKey*` array in `src/pc/configfile.c`; the other entries are game-pad
buttons. Scancodes above `0x100` are the extended keys (`0x148` is the up arrow).

- sm64ex (<https://github.com/sm64pc/sm64ex>): branch `nightly`, commit
  `d7ca2c04364a6dd0dac58b47151e04e26887e6f0`, read 2026-11-14. The project has no
  release tags; its README names `nightly` as the branch that gets changes first.
- sm64coopdx (<https://github.com/coop-deluxe/sm64coopdx>): tag `v1.5.1`, read
  2026-11-14.

| key | scancode | array | control | sm64ex | sm64coopdx |
|---|---|---|---|---|---|
| L | `0x26` | `configKeyA` | A | yes | yes |
| , | `0x33` | `configKeyB` | B | yes | yes |
| I | `0x17` | `configKeyX` | X | | yes |
| M | `0x32` | `configKeyY` | Y | | yes |
| K | `0x25` | `configKeyZ` | Z | yes | yes |
| left Shift | `0x2A` | `configKeyL` | L | yes | yes |
| right Shift | `0x36` | `configKeyR` | R | yes | yes |
| Space | `0x39` | `configKeyStart` | Start | yes | yes |
| arrow keys | `0x148`, `0x150`, `0x14B`, `0x14D` | `configKeyCUp`, `CDown`, `CLeft`, `CRight` | C buttons | yes | yes |
| W, S, A, D | `0x11`, `0x1F`, `0x1E`, `0x20` | `configKeyStickUp`, `Down`, `Left`, `Right` | control stick | yes | yes |
| Home, End, Delete, Page Down | `0x147`, `0x14F`, `0x153`, `0x151` | `configKeyDUp`, `DDown`, `DLeft`, `DRight` | D-pad | | yes |
| Enter | `0x1C` | `configKeyChat` | Open chat | | yes |
| Tab | `0x0F` | `configKeyPlayerList` | Player list | | yes |
| `` ` `` and F1 | `0x29`, `0x3B` | `configKeyConsole` | Console | | yes |
| U / O | `0x16` / `0x18` | `configKeyPrevPage` / `configKeyNextPage` | Previous / next page | | yes |
| F12 | `0x58` | `configKeyDisconnect` | Disconnect | | yes |

The sm64ex set has 14 keys and the sm64coopdx set 27. These are all the default
keyboard binds of both ports. Nothing is left out.

## Icons

| file | source | licence |
|---|---|---|
| `chat.png`, `playerlist.png`, `console.png`, `prevpage.png`, `nextpage.png`, `disconnect.png` | Material Symbols (`google/material-design-icons`), names in `fetch_icons.py` | [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0) |
| `btna.png` … `btnz.png`, `start.png`, `c*.png`, `stick*.png`, `dpad*.png` | drawn by `pad_keys.n64_pad()` with `retroarch/fetch_icons.py` (`ring()`, `pill()`); text in Press Start 2P by CodeMan38 (`google/fonts`, `ofl/pressstart2p`, pinned commit) | the drawing is this repo's; the font is [SIL OFL 1.1](https://openfontlicense.org/open-font-license-official-text/) |
| `sm64ex.png`, `sm64coopdx.png` | the port names set in Russo One by Jovanny Lemonad (`google/fonts`, `ofl/russoone`, pinned commit), drawn by `pad_keys.wordmark()` | the font is SIL OFL 1.1 |

## The ESC marks

Neither repository has a licence file at its root at the commit read (the ports
are built from a decompilation of the game), and the game art belongs to
Nintendo. Only the default keys were read. No art is copied; each mark is the
port's name set in an open font.
