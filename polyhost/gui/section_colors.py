"""The colours of the coloured dialogs' sections (Settings, Integrations, Tutorials).

Each section has one colour: the band behind its title, a light tint of it behind
the section, the stripe of its sidebar entry, and its on/off switches.

The scheme is a rainbow in spectrum order: red, orange, yellow, green, teal,
blue, violet, pink. It was chosen by look (2026-11-17) over schemes whose
neighbours were further apart for colour-blind readers: in spectrum order two
neighbours are close (validator, deutan distance 1.5), so the colour is never
the only way to tell sections apart. The sidebar entry and the band name each one.

There are two sets of the same hues. Light mode uses darker colours, dark mode
lighter ones, so each has at least 3:1 contrast against the window colour of its
theme (#f0f0f0 light, #505050 dark, gui/theme.py). The one exception is yellow in
light mode: 2.0:1, the floor the tray icon colours use, because a darker yellow
turns olive. The title text on its band
is near-black at 7.2:1, and the stripe stays visible.

A section added after the eighth takes the neutral grey, or shares a hue; a new
hue needs the scheme checked again in both themes.
"""

# (name, light, dark), in slot order.
SLOTS = (
    ("red",    "#d15c56", "#ee857e"),
    ("orange", "#cb6620", "#e88e59"),
    ("yellow", "#c5aa00", "#efd551"),   # 2.0:1 in light mode, see above
    ("green",  "#25984d", "#5cb572"),
    ("teal",   "#17959b", "#0eb4bb"),
    ("blue",   "#2f8adc", "#60aaf3"),
    ("violet", "#8e71d6", "#ae96f1"),
    ("pink",   "#bf5da2", "#dd86c1"),
)

# The lowest contrast a slot may have against its theme's window colour.
MIN_CONTRAST = 3.0
MIN_CONTRAST_EXCEPTIONS = {("yellow", "light"): 2.0}

# Developer and Other: settings most users never open, so no hue of their own.
NEUTRAL = ("grey", "#6b7280", "#c0c4cc")

# Section id -> slot name. A section not listed is neutral.
SECTION_SLOTS = {
    "general": "red",
    "icons": "orange",
    "games": "yellow",
    "brightness": "green",
    "keyboard": "teal",
    "connections": "blue",
    "privacy": "violet",
    "agents": "pink",
}

# The alpha (0-255) of the light tint: the section's background and the selected
# sidebar entry. The sidebar's hover tint is weaker.
TINT_ALPHA = 80
HOVER_ALPHA = 35

_BY_NAME = {name: (light, dark) for name, light, dark in SLOTS + (NEUTRAL,)}


def section_color(section_id, dark):
    """The hex colour of ``section_id`` for the dark or the light theme."""
    light_hex, dark_hex = _BY_NAME[SECTION_SLOTS.get(section_id, NEUTRAL[0])]
    return dark_hex if dark else light_hex


def tint(hexcolor, alpha=TINT_ALPHA):
    """``hexcolor`` as an ``rgba()`` style sheet colour with ``alpha`` (0-255)."""
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _luminance(hexcolor):
    out = []
    for i in (1, 3, 5):
        c = int(hexcolor[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    """The WCAG contrast ratio of two hex colours."""
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def title_ink(hexcolor):
    """White or near-black, whichever reads better on a band of ``hexcolor``.
    The light theme's darker colours take white, the dark theme's lighter ones
    near-black."""
    return max(("#ffffff", "#1e1e1e"), key=lambda ink: contrast(ink, hexcolor))


def slot_color(index, dark):
    """The colour of the ``index``-th sidebar entry of a dialog whose entries
    take the slots in sidebar order (Integrations, Tutorials). Neighbours keep
    the validated distances. Past the last slot the colour is neutral."""
    if 0 <= index < len(SLOTS):
        _name, light_hex, dark_hex = SLOTS[index]
    else:
        _name, light_hex, dark_hex = NEUTRAL
    return dark_hex if dark else light_hex
