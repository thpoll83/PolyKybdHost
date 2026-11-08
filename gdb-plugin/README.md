# PolyKybd state reporter (GDB script)

Writes GDB's state into the terminal's window title, so PolyKybdHost shows the
keys that work at that moment:

| title | GDB is | keycaps |
|---|---|---|
| `gdb ⏸ <program>` | at the `(gdb)` prompt | the GDB set: the one-letter commands (b, c, n, s, p, …), the TUI keys, Ctrl+C, Ctrl+D |
| `gdb ▶ <program>` | running the program | only Ctrl+C (interrupt) and the GDB mark; every other key goes to the program |

`<program>` is the base name of the file GDB loaded, or nothing when no file is
loaded. On start the script saves the terminal's title (`CSI 22;2t`), and when
GDB exits it restores it (`CSI 23;2t`, GDB 12 and later). Terminals without a
title stack ignore both.

GDB 8.0 or later with Python support (most Linux distributions, MSYS2 and
Homebrew build it with Python). Tested with GDB 15.1 on Linux, in a
pseudo-terminal; macOS and Windows builds are untested.

## Install

PolyKybdHost does it: tray → Updates → "Set up the terminal and editors…",
tick GDB, Install. Or `polyctl editor-plugins install --editor gdb`. That copies
`polykybd.py` to `~/.config/gdb/polykybd/` (`$XDG_CONFIG_HOME/gdb/polykybd/`
when that is set) and adds this block to the init file GDB reads, after saving
a copy of the file. GDB 11 and later read one config-folder file if it exists,
else `~/.gdbinit`:

- macOS: `~/Library/Preferences/gdb/gdbinit` (GDB ignores `XDG_CONFIG_HOME` and
  `~/.config` there);
- elsewhere: `$XDG_CONFIG_HOME/gdb/gdbinit` when that variable is set, else
  `~/.config/gdb/gdbinit`.

GDB 10 and earlier read only `~/.gdbinit`. When none of these exists, the block
goes into `~/.gdbinit`.

```
# >>> PolyKybd editor integration >>>
python
import os as _pk_os
_pk_file = "/home/me/.config/gdb/polykybd/polykybd.py"
if _pk_os.path.isfile(_pk_file):
    gdb.execute("source " + _pk_file)
end
# <<< PolyKybd editor integration <<<
```

By hand: put `source /path/to/polykybd.py` in your GDB init file.

## What it sends

Nothing over the network. Its only output is the title escape sequence
(`OSC 2`) and the two title-stack sequences, written to GDB's terminal and only
when that is a terminal (not in batch mode or with output to a pipe).
