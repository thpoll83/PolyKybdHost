"""The colours of the Settings dialog's sections.

Each section has one colour: the frame around the section and the stripe of its
entry in the sidebar, so the sidebar entry and its section read as one thing.
The colour is decoration only: the sidebar entry and the section title carry the
name, and all text stays in the palette's text colours.

There are two schemes. Light mode uses darker colours, dark mode lighter ones of
the same hues, so each one has at least 3:1 contrast against the window colour of
its theme (#f0f0f0 light, #505050 dark, gui/theme.py).

The hue order was chosen with the dataviz skill's validator
(`validate_palette.js`), in both modes: neighbouring hues keep a colour-blind
(deutan, protan, tritan) OKLab distance of at least 8.6 and a normal-vision
distance of at least 15.1. Sections take the slots in sidebar order. The last
two slots (magenta, green) are free for new sections. A section added after
them shares a slot or takes the neutral grey; never invent a new hue without
re-running the validator on the whole order.
"""

# (name, light, dark), in slot order.
SLOTS = (
    ("teal",    "#0e8a62", "#4fd8a8"),
    ("orange",  "#c8521f", "#ff9a66"),
    ("blue",    "#2a6fc9", "#7fb2ff"),
    ("gold",    "#a87400", "#f5c542"),
    ("violet",  "#6a4fd8", "#b9a2ff"),
    ("red",     "#c93b3a", "#ff7d7a"),
    ("cyan",    "#0b7f9e", "#55d0f0"),
    ("brown",   "#9a5b1e", "#e6a465"),
    ("magenta", "#b8457a", "#ff8fc0"),   # free
    ("green",   "#3d7f12", "#9bdc5a"),   # free
)

# Developer and Other: settings most users never open, so no hue of their own.
NEUTRAL = ("grey", "#6b7280", "#c0c4cc")

# Section id -> slot name. A section not listed is neutral.
SECTION_SLOTS = {
    "general": "teal",
    "icons": "orange",
    "games": "blue",
    "brightness": "gold",
    "keyboard": "violet",
    "connections": "red",
    "privacy": "cyan",
    "agents": "brown",
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
