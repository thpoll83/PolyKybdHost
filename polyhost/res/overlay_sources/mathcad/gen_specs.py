#!/usr/bin/env python3
"""Write the PTC Mathcad Prime overlay spec from one table.

The keys are from PTC's "Keyboard Shortcuts" PDF for PTC Mathcad Prime
12.0.1.0 (the same keys as 11.0.1.0). Mathcad Prime is a Windows program, so
there is one set. The PDF lists the US / English key first and German, French,
Italian, Spanish and Russian variants under it; this set draws the English
keys. Shifted characters are drawn on the US key that types them
(Ctrl+Shift+$ on Ctrl+Shift+4). See SOURCES.md for the keys left out.

    python polyhost/res/overlay_sources/mathcad/gen_specs.py
    python scripts/generate_app_overlays.py polyhost/res/overlay_sources/mathcad/bindings.yaml
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))

from polyhost.res.overlay_sources import chord_table  # noqa: E402

PLATFORMS = ("windows",)


def k(win):
    return {"windows": win}


ROWS = [
    "regions",
    ("area", "Area", k("CS+A")),
    ("chart", "Chart component", k("C+1")),
    ("excel", "Excel component", k("CS+E")),
    ("include", "Include worksheet", k("CS+W")),
    ("mathregion", "Math region", k("CS+M")),
    ("object", "Object", k("CS+O")),
    ("solveblock", "Solve block", k("C+7")),
    ("table", "Insert table", k("C+6")),
    ("textbox", "Text box", k("C+T")),
    ("recalcpage", "Recalculate to this page", k("+F5")),
    ("separateh", "Separate horizontally", k("C+F8")),
    ("separatev", "Separate vertically", k("C+F3")),
    "math and text",
    ("greek", "Greek letter", k("C+G")),
    (None, "Subscript", k("C+-")),
    (None, "Bold", k("C+B")),
    (None, "Italic", k("C+I")),
    (None, "Underline", k("C+U")),
    ("labels", "Toggle label", k("C+Q")),
    ("infinity", "Infinity", k("CS+Z")),
    "plots",
    ("xyplot", "XY plot", k("C+2")),
    ("plot3d", "3D plot", k("C+3")),
    ("polarplot", "Polar plot", k("C+4")),
    ("contourplot", "Contour plot", k("C+5")),
    "algebra",
    ("sqrt", "Square root", k("+KC_BACKSLASH")),
    ("abs", "Absolute value", k("S+KC_BACKSLASH")),
    ("power", "Exponent", k("S+6")),
    ("inlinediv", "In-line division", k("C+/")),
    ("breakadd", "Break after +", k("CS+=")),
    ("breaksub", "Break after -", k("CS+-")),
    ("breakmul", "Break after *", k("CS+8")),
    ("breakdiv", "Break after /", k("CS+/")),
    ("breaktoggle", "Toggle equation break", k("CS+Enter")),
    "calculus",
    ("circconv", "Circular convolution", k("CS+V")),
    ("gradient", "Gradient", k("CS+G")),
    ("derivative", "Derivative", k("CS+D")),
    ("partial", "Partial derivative", k("C+D")),
    ("integral", "Integral", k("CS+I")),
    ("linconv", "Linear convolution", k("CS+L")),
    ("prime", "Prime", k("C+'")),
    ("product", "Product", k("CS+3")),
    ("sum", "Summation", k("CS+4")),
    "comparison and logic",
    ("equalto", "Equal to", k("C+=")),
    ("ge", "Greater or equal", k("C+0")),
    ("le", "Less or equal", k("C+9")),
    ("element", "Element of", k("C+F7")),
    ("xor", "Exclusive or", k("CS+5")),
    ("and", "Logical and", k("CS+7")),
    ("not", "Logical not", k("CS+1")),
    ("or", "Logical or", k("CS+2")),
    "definition and engineering",
    ("definition", "Definition", k("S+KC_SEMICOLON")),
    ("globaldef", "Global definition", k("CS+`")),
    ("conjugate", "Complex conjugate", k("CS+9")),
    ("scaling", "Scaling", k("CS+U")),
    ("polar", "Polar", k("CS+P")),
    ("symbolic", "Symbolic evaluation", k("C+.")),
    ("limit", "Limit", k("C+L")),
    "vectors and matrices",
    ("cross", "Cross product", k("C+8")),
    ("matrix", "Matrix", k("C+M")),
    ("matrixcol", "Matrix column", k("CS+C")),
    ("matrixrow", "Matrix row", k("CS+R")),
    ("transpose", "Transpose", k("CS+T")),
    ("norm", "Norm", k("CS+KC_BACKSLASH")),
    ("vectorize", "Vectorize", k("CS+6")),
    ("insertcol", "Insert column", k("S+Space")),
    "programming",
    ("program", "Program", k("+]")),
    ("localdef", "Local definition", k("S+[")),
    ("kw_if", "If", k("S+]")),
    ("kw_else", "Else", k("CS+]")),
    ("kw_elseif", "Else if", k("C+KC_SEMICOLON")),
    ("kw_alsoif", "Also if", k("CS+0")),
    ("kw_while", "While loop", k("C+]")),
    ("kw_for", "For loop", k("CS+'")),
    ("kw_break", "Break", k("CS+[")),
    ("kw_continue", "Continue", k("CS+KC_SEMICOLON")),
    ("kw_return", "Return", k("C+KC_BACKSLASH")),
    ("kw_try", "Try / on error", k("C+[")),
    ("tooperator", "Keyword to operator", k("C+J")),
    "general",
    (None, "Help", k("+F1")),
    ("functions", "Functions", k("+F2")),
    ("pagebreak", "Page break", k("C+Enter")),
    ("gotopage", "Go to page", k("CA+G")),
    ("calcsheet", "Calculate worksheet", k("C+F5")),
    ("link", "Link", k("C+K")),
    (None, "New", k("C+N")),
    (None, "Open", k("C+O")),
    (None, "Save", k("C+S")),
    (None, "Print", k("C+P")),
    (None, "Close", k("C+W")),
]

HEADER = """\
# PTC Mathcad Prime shortcut overlays for PolyKybd (Windows).
# GENERATED by gen_specs.py from its table -- edit the table, not this file.
#
# Shortcuts: PTC, "Keyboard Shortcuts", PTC Mathcad Prime 12.0.1.0 (PDF).
# English / US keys. See SOURCES.md.
#
# Regenerate:
#   python polyhost/res/overlay_sources/mathcad/fetch_icons.py
#   python polyhost/res/overlay_sources/mathcad/gen_specs.py
#   python scripts/generate_app_overlays.py \\
#       polyhost/res/overlay_sources/mathcad/bindings.yaml --preview /tmp/mathcad_preview
app: mathcad
match: [mathcadprime]
output: mathcad_template
icon_dir: icons
fit: contain
anchor: bottom-right
region: [36, 32]
margin: 0
mode: auto     # one rule per icon file: see HOUSE_LUMA_THRESHOLD in scripts/generate_app_overlays.py
threshold: 150

program_icon: mathcad.png
program_icon_mode: alpha
program_icon_anchor: right
program_icon_region: [37, 32]
program_icon_margin: 0

bindings:
"""

# No label here folds onto a shared concept it should not draw.
NOT_SHARED: set[str] = set()


def main() -> int:
    chord_table.write(HERE / "bindings.yaml", HEADER, ROWS, NOT_SHARED, PLATFORMS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
