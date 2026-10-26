"""The ten control-group units, drawn for this overlay (not traced from the game).

Side views facing right, filled silhouettes on a 120x80 design grid (x right,
y down), rendered 4x supersampled. Each has the features that make the C&C
unit recognisable: the Mammoth's twin barrels, the Orca's engine pod, the
harvester's ore hopper. fetch_icons.py writes them as icons/_unit<N>.png.
"""
from PIL import Image, ImageDraw

K = 4                      # supersampling factor
GW, GH = 120, 80


def canvas():
    im = Image.new("RGBA", (GW * K, GH * K), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def S(pts):
    return [(x * K, y * K) for x, y in pts]


INK, CUT = (0, 0, 0, 255), (0, 0, 0, 0)


def poly(d, pts, fill=INK):
    d.polygon(S(pts), fill=fill)


def rect(d, x0, y0, x1, y1, fill=INK):
    d.rectangle([x0 * K, y0 * K, x1 * K - 1, y1 * K - 1], fill=fill)


def circ(d, cx, cy, r, fill=INK):
    d.ellipse([(cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K], fill=fill)


def line(d, pts, w, fill=INK):
    d.line(S(pts), fill=fill, width=int(w * K), joint="curve")


def wheel(d, cx, cy, r, hub=0.45):
    circ(d, cx, cy, r)
    circ(d, cx, cy, r * hub, CUT)


def tracks(d, x0, x1, y0, y1, n):
    """A track run: a rounded band with n road wheels cut out."""
    r = (y1 - y0) / 2
    d.rounded_rectangle([x0 * K, y0 * K, x1 * K, y1 * K], radius=r * K, fill=INK)
    step = (x1 - x0 - 2 * r) / (n - 1)
    for i in range(n):
        circ(d, x0 + r + i * step, (y0 + y1) / 2, r * 0.55, CUT)
        circ(d, x0 + r + i * step, (y0 + y1) / 2, r * 0.22)


def rifleman():
    im, d = canvas()
    circ(d, 62, 14, 7)                                   # head
    d.pieslice([53 * K, 3 * K, 72 * K, 21 * K], 180, 360, fill=INK)   # round helmet
    rect(d, 52, 11, 74, 13)                              # helmet rim
    poly(d, [(53, 22), (70, 22), (73, 48), (51, 48)])    # torso
    rect(d, 45, 25, 53, 34)                              # backpack
    poly(d, [(52, 48), (61, 48), (58, 78), (50, 78)])    # back leg
    poly(d, [(61, 48), (72, 48), (76, 78), (67, 78)])    # front leg
    line(d, [(60, 34), (100, 26)], 4.5)                  # rifle
    rect(d, 74, 29, 80, 38)                              # magazine
    line(d, [(64, 28), (78, 30)], 5)                     # arm to the rifle
    return im


def engineer():
    im, d = canvas()
    circ(d, 62, 15, 7)
    poly(d, [(52, 12), (72, 12), (70, 5), (62, 2), (54, 5)])     # hard hat
    rect(d, 50, 10, 76, 13)                              # brim
    poly(d, [(53, 23), (70, 23), (72, 50), (51, 50)])
    poly(d, [(36, 22), (52, 22), (52, 52), (36, 52)])    # big tool pack
    rect(d, 39, 15, 43, 22)                              # antenna stub
    poly(d, [(52, 50), (61, 50), (58, 78), (50, 78)])
    poly(d, [(61, 50), (72, 50), (75, 78), (66, 78)])
    line(d, [(66, 30), (88, 44)], 5)                     # arm
    line(d, [(86, 42), (98, 58)], 4)                     # wrench handle
    circ(d, 99, 60, 5)
    circ(d, 101, 62, 2.4, CUT)                           # wrench jaw
    return im


def buggy():
    im, d = canvas()
    poly(d, [(8, 52), (18, 42), (70, 40), (100, 46), (112, 52), (108, 60), (12, 60)])  # body
    line(d, [(36, 41), (46, 18), (72, 18), (80, 41)], 4)    # roll cage
    line(d, [(46, 18), (56, 41)], 3)
    rect(d, 60, 10, 66, 18)                              # gun mount
    line(d, [(63, 13), (94, 11)], 3.5)                   # machine gun
    wheel(d, 26, 62, 14)
    wheel(d, 94, 64, 12)
    return im


def apc():
    im, d = canvas()
    poly(d, [(6, 54), (14, 30), (82, 28), (112, 42), (112, 54)])  # sloped hull
    rect(d, 46, 18, 70, 29)                              # turret
    line(d, [(68, 22), (100, 20)], 3.5)                  # cannon
    for x in (24, 36):
        rect(d, x, 36, x + 7, 42, CUT)                   # vision ports
    tracks(d, 6, 112, 54, 74, 5)
    return im


def mammoth():
    im, d = canvas()
    poly(d, [(4, 48), (12, 34), (98, 32), (114, 40), (114, 50)])  # wide hull
    poly(d, [(30, 32), (36, 14), (78, 12), (86, 32)])     # big turret
    line(d, [(80, 17), (118, 15)], 4)                     # twin barrels
    line(d, [(80, 25), (118, 23)], 4)
    rect(d, 14, 22, 30, 32)                               # missile pod
    for y in (24, 28):
        rect(d, 16, y, 30, y + 2, CUT)
    tracks(d, 2, 116, 50, 74, 6)
    return im


def mlrs():
    im, d = canvas()
    poly(d, [(84, 34), (100, 34), (112, 46), (112, 60), (84, 60)])   # cab
    rect(d, 92, 38, 102, 46, CUT)                        # window
    rect(d, 8, 50, 86, 60)                               # flatbed
    poly(d, [(14, 48), (22, 20), (66, 8), (70, 18), (30, 48)])       # raised rocket pod
    for t in (0.25, 0.5, 0.75):                          # tubes
        x, y = 22 + 44 * t, 20 - 12 * t
        circ(d, x + 2, y + 6, 3.2, CUT)
    rect(d, 28, 40, 34, 50)                              # pod mount
    for cx in (24, 46, 98):
        wheel(d, cx, 64, 10)
    return im


def orca():
    im, d = canvas()
    poly(d, [(8, 34), (40, 26), (96, 28), (116, 36), (96, 44), (30, 44)])  # fuselage
    poly(d, [(84, 30), (100, 30), (110, 35), (96, 36)], CUT)     # canopy
    poly(d, [(8, 34), (2, 16), (12, 16), (22, 30)])      # tail fin
    d.rounded_rectangle([34 * K, 46 * K, 70 * K, 62 * K], radius=6 * K, fill=INK)  # engine pod
    rect(d, 46, 42, 56, 47)                              # pylon
    rect(d, 70, 51, 74, 57)
    line(d, [(36, 64), (44, 74), (60, 74), (68, 64)], 2.5, fill=INK)  # jet wash marks
    rect(d, 74, 50, 92, 54)                              # missile
    return im


def jet():
    im, d = canvas()
    poly(d, [(2, 40), (24, 34), (96, 32), (118, 38), (96, 44), (24, 46)])   # fuselage
    poly(d, [(86, 34), (104, 35), (96, 38), (84, 38)], CUT)     # canopy
    poly(d, [(40, 40), (70, 40), (46, 70), (34, 70)])    # wing (swept back, below)
    poly(d, [(6, 38), (2, 14), (14, 14), (26, 34)])      # tail fin
    poly(d, [(6, 44), (22, 44), (8, 54), (2, 54)])       # tailplane
    rect(d, 48, 52, 62, 56)                              # missile under the wing
    return im


def gunboat():
    im, d = canvas()
    poly(d, [(4, 44), (116, 44), (104, 62), (14, 62)])    # hull
    rect(d, 34, 30, 70, 44)                              # bridge
    rect(d, 40, 33, 64, 37, CUT)                         # bridge windows
    rect(d, 50, 16, 54, 30)                              # mast
    circ(d, 52, 13, 5)                                   # radar dome
    rect(d, 80, 34, 92, 44)                              # gun turret
    line(d, [(90, 37), (112, 30)], 3.5)                  # gun
    return im


def harvester():
    im, d = canvas()
    poly(d, [(6, 26), (68, 22), (82, 30), (82, 56), (6, 56)])   # ore hopper
    for x in (18, 34, 50):
        rect(d, x, 30, x + 8, 48, CUT)                   # hopper ribs
    poly(d, [(84, 30), (104, 30), (112, 42), (112, 56), (84, 56)])  # cab
    rect(d, 92, 34, 104, 42, CUT)
    poly(d, [(110, 50), (120, 58), (120, 68), (106, 66)])  # front scoop
    tracks(d, 4, 104, 56, 76, 5)
    return im


UNITS = {"1": rifleman, "2": engineer, "3": buggy, "4": apc, "5": mammoth,
         "6": mlrs, "7": orca, "8": jet, "9": gunboat, "0": harvester}
