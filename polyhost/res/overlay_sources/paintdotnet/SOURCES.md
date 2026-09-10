# paint.net overlay -- sources & provenance

Reproducible record for the paint.net keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/paintdotnet/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/paintdotnet/bindings.yaml --preview /tmp/paintdotnet_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

Shortcuts come from **paint.net's own documentation**, so this is the documented
set rather than a third-party summary:

- https://www.getpaint.net/doc/latest/KeyboardMouseCommands.html

⚠️ **The plain-letter tool row is the point of this overlay.** paint.net picks a
tool with a bare keystroke -- `B` brush, `P` pencil, `E` eraser, `F` fill, `G`
gradient, `K` colour picker, `L` clone stamp, `R` recolor, `T` text, `S` select,
`M` move, `Z` zoom, `H` pan, `O` line/curve -- which is the class of shortcut
nobody memorises, and it fills the no-modifier layer that most overlays leave
empty.

⚠️ **The four brush-width keys had to be DRAWN, and finding that out needed the
preview.** `[` / `]` / `Ctrl+[` / `Ctrl+]` all pointed at Fluent's
`Line Horizontal 1` and rendered as the same plain bar -- as did `O`
(line/curve), so five cells carried one picture. Every one of them drew a
perfectly valid glyph, so nothing in the generator could see it. They are now a
bar whose thickness states the direction over the signed step (`-1` `+1` `-5`
`+5`), and `O` uses Fluent's diagonal `Line`.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: the gradient ramp, the clone stamp and the four brush-width composites.

⚠️ **The program mark is never the app's real logo.** Every one of these logos is
proprietary trademark art, so the ESC cell carries a licence-clean substitute --
usually the shared letter tile (`../program_marks.py`). It exists to say *which
overlay set is loaded*, not to identify the vendor.

| icon | art | licence |
|---|---|---|
| `rectselect.png` | Fluent `Select Object` | MIT |
| `movesel.png` | Fluent `Drag` | MIT |
| `zoomtool.png` | Fluent `Search` | MIT |
| `pan.png` | Fluent `Hand Right` | MIT |
| `brush.png` | Fluent `Paint Brush` | MIT |
| `pencil.png` | Fluent `Pen` | MIT |
| `eraser.png` | Fluent `Eraser` | MIT |
| `bucket.png` | Fluent `Paint Bucket` | MIT |
| `gradient.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `picker.png` | Fluent `Eyedropper` | MIT |
| `clonestamp.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `recolor.png` | Fluent `Color Line` | MIT |
| `text.png` | Fluent `Text T` | MIT |
| `linecurve.png` | Fluent `Line` | MIT |
| `swapcolors.png` | Fluent `Arrow Swap` | MIT |
| `brushdec1.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `brushinc1.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `toolswin.png` | Fluent `Options` | MIT |
| `historywin.png` | Fluent `History` | MIT |
| `layerswin.png` | Fluent `Layer Diagonal` | MIT |
| `colorswin.png` | Fluent `Color` | MIT |
| `layerprops.png` | Fluent `Options` | MIT |
| `new.png` | Fluent `Document Add` | MIT |
| `open.png` | Fluent `Folder Open` | MIT |
| `save.png` | Fluent `Save` | MIT |
| `close.png` | Fluent `Document Dismiss` | MIT |
| `print.png` | Fluent `Print` | MIT |
| `undo.png` | Fluent `Arrow Undo` | MIT |
| `redo.png` | Fluent `Arrow Redo` | MIT |
| `cut.png` | Fluent `Cut` | MIT |
| `copy.png` | Fluent `Copy` | MIT |
| `paste.png` | Fluent `Clipboard Paste` | MIT |
| `selectall.png` | Fluent `Select All On` | MIT |
| `deselect.png` | Fluent `Select All Off` | MIT |
| `invertsel.png` | Fluent `Border All` | MIT |
| `zoomin.png` | Fluent `Zoom In` | MIT |
| `zoomout.png` | Fluent `Zoom Out` | MIT |
| `zoomwindow.png` | Fluent `Zoom Fit` | MIT |
| `actualsize.png` | Fluent `Ratio One To One` | MIT |
| `resize.png` | Fluent `Resize Image` | MIT |
| `rotatecw.png` | Fluent `Rotate Right` | MIT |
| `rotateccw.png` | Fluent `Rotate Left` | MIT |
| `mergedown.png` | Fluent `Arrow Between Down` | MIT |
| `levels.png` | Fluent `Data Histogram` | MIT |
| `repeateffect.png` | Fluent `Arrow Repeat All` | MIT |
| `layervis.png` | Fluent `Eye` | MIT |
| `nextimage.png` | Fluent `Arrow Right` | MIT |
| `previmage.png` | Fluent `Arrow Left` | MIT |
| `brushdec5.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `brushinc5.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |
| `layerabove.png` | Fluent `Arrow Up` | MIT |
| `layerbelow.png` | Fluent `Arrow Down` | MIT |
| `saveas.png` | Fluent `Save Edit` | MIT |
| `copymerged.png` | Fluent `Layer Diagonal` | MIT |
| `pastelayer.png` | Fluent `Layer Diagonal Add` | MIT |
| `crop.png` | Fluent `Crop` | MIT |
| `newlayer.png` | Fluent `Layer Diagonal Add` | MIT |
| `duplayer.png` | Fluent `Document Multiple` | MIT |
| `canvas.png` | Fluent `Slide Size` | MIT |
| `flatten.png` | Fluent `Layer` | MIT |
| `zoomsel.png` | Fluent `Crop Interim` | MIT |
| `rotatezoom.png` | Fluent `Arrow Rotate Clockwise` | MIT |
| `autolevel.png` | Fluent `Wand` | MIT |
| `blackwhite.png` | Fluent `Circle Half Fill` | MIT |
| `brightness.png` | Fluent `Brightness High` | MIT |
| `curves.png` | Fluent `Data Line` | MIT |
| `huesat.png` | Fluent `Color` | MIT |
| `invertcolors.png` | Fluent `Color Background` | MIT |
| `posterize.png` | Fluent `Filter` | MIT |
| `sepia.png` | Fluent `Weather Sunny` | MIT |
| `saveall.png` | Fluent `Save Multiple` | MIT |
| `pasteimage.png` | Fluent `Image Copy` | MIT |
| `invertalpha.png` | Fluent `Scan Type` | MIT |
| `toplayer.png` | Fluent `Arrow Upload` | MIT |
| `bottomlayer.png` | Fluent `Arrow Download` | MIT |
| `paintdotnet.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |

69 of 76 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
