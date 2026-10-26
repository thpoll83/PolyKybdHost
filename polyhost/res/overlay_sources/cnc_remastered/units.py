"""The ten control-group units, drawn for this overlay (not traced from the game).

Side views facing right, filled silhouettes on a 120x80 design grid (x right,
y down), rendered 4x supersampled. Each has the features that make the C&C
unit recognisable: the Mammoth's twin barrels, the Orca's engine pod, the
harvester's ore hopper. fetch_icons.py writes them as icons/_unit<N>.png.
"""
import math

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


def treaded_wheel(d, cx, cy, r):
    """A tyre with tread notches, a rim and a hub."""
    circ(d, cx, cy, r)
    for i in range(10):
        a = i * math.pi / 5
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
        circ(d, x, y, r * 0.16, CUT)
    circ(d, cx, cy, r * 0.55, CUT)
    circ(d, cx, cy, r * 0.32)


def rifleman():
    """Kneeling to aim: helmet with goggles, webbing vest, rifle with scope."""
    im, d = canvas()
    d.pieslice([46 * K, 2 * K, 70 * K, 26 * K], 180, 360, fill=INK)  # helmet dome
    rect(d, 44, 13, 72, 16)                              # helmet rim
    rect(d, 52, 6, 64, 10, CUT)                          # goggles strap gap
    rect(d, 54, 6, 62, 10)                               # goggles
    poly(d, [(50, 16), (66, 16), (66, 26), (50, 26)])    # face / neck
    rect(d, 58, 18, 63, 21, CUT)                         # eye shade
    poly(d, [(44, 26), (70, 26), (74, 52), (42, 52)])    # torso
    for x in (46, 55, 64):                               # vest pouches
        rect(d, x, 40, x + 6, 47, CUT)
    rect(d, 42, 34, 74, 36, CUT)                         # webbing strap
    rect(d, 34, 28, 44, 48)                              # pack
    rect(d, 34, 36, 44, 38, CUT)
    poly(d, [(42, 52), (60, 52), (56, 66), (40, 66)])    # thigh (kneeling)
    poly(d, [(40, 62), (50, 62), (50, 78), (36, 78)])    # shin, foot back
    poly(d, [(58, 52), (74, 52), (86, 66), (74, 68)])    # front thigh
    poly(d, [(74, 62), (86, 64), (88, 78), (76, 78)])    # front shin
    rect(d, 74, 75, 94, 78)                              # boot
    line(d, [(56, 32), (78, 30)], 6)                     # arms to the rifle
    poly(d, [(64, 24), (118, 20), (118, 24), (66, 30)])  # rifle barrel + body
    poly(d, [(58, 26), (68, 24), (70, 36), (60, 38)])    # stock at the shoulder
    rect(d, 80, 15, 96, 19)                              # scope
    rect(d, 84, 24, 90, 34)                              # magazine
    return im


def engineer():
    """Bulky suit, visor helmet, radio pack with antenna, toolbox in hand."""
    im, d = canvas()
    circ(d, 62, 14, 11)                                  # helmet
    poly(d, [(60, 10), (74, 10), (74, 18), (62, 20)], CUT)  # visor
    poly(d, [(64, 12), (72, 12), (72, 16), (64, 17)])    # visor glint frame
    poly(d, [(46, 25), (76, 25), (80, 54), (44, 54)])    # bulky suit
    rect(d, 44, 46, 80, 49, CUT)                         # belt
    rect(d, 58, 46, 64, 49)                              # buckle
    for y in (30, 37):                                   # chest panel lines
        rect(d, 52, y, 70, y + 2, CUT)
    rect(d, 30, 24, 46, 52)                              # radio pack
    rect(d, 33, 30, 43, 33, CUT)
    rect(d, 33, 38, 43, 41, CUT)
    line(d, [(34, 24), (28, 2)], 2.5)                    # antenna
    circ(d, 28, 3, 2.5)
    poly(d, [(46, 54), (60, 54), (58, 76), (46, 76)])    # legs
    poly(d, [(62, 54), (78, 54), (80, 76), (66, 76)])
    rect(d, 42, 74, 60, 79)                              # boots
    rect(d, 64, 74, 84, 79)
    line(d, [(74, 30), (90, 48)], 7)                     # arm
    rect(d, 82, 52, 112, 70)                             # toolbox
    rect(d, 92, 46, 102, 52)                             # handle
    rect(d, 94, 48, 100, 52, CUT)
    rect(d, 82, 58, 112, 60, CUT)                        # lid line
    return im


def buggy():
    """Low armoured buggy: wedge nose, roll cage, shielded machine gun, big tyres."""
    im, d = canvas()
    poly(d, [(4, 50), (12, 40), (40, 36), (78, 36), (104, 42), (118, 48), (114, 56), (6, 58)])
    rect(d, 20, 44, 34, 47, CUT)                          # side panel lines
    rect(d, 44, 44, 70, 47, CUT)
    poly(d, [(84, 42), (100, 44), (100, 47), (84, 46)], CUT)   # headlight slot
    rect(d, 2, 40, 10, 46)                                # exhaust
    rect(d, 0, 36, 6, 40)
    line(d, [(30, 37), (40, 14), (70, 14), (82, 37)], 4)  # roll cage
    line(d, [(40, 14), (50, 37)], 3)
    circ(d, 58, 28, 5)                                    # driver's helmet
    rect(d, 60, 4, 72, 14)                                # gun shield
    rect(d, 64, 14, 68, 18)                               # gun post
    line(d, [(68, 8), (100, 6)], 3.5)                     # machine gun
    rect(d, 94, 3, 98, 9)                                 # muzzle brake
    treaded_wheel(d, 26, 62, 15)
    treaded_wheel(d, 96, 63, 14)
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
    """Rocket launcher: a 3x2 box of tubes raised on a six-wheel truck, cab."""
    im, d = canvas()
    poly(d, [(86, 30), (102, 30), (114, 42), (114, 60), (86, 60)])   # cab
    poly(d, [(92, 34), (101, 34), (108, 42), (92, 42)], CUT)         # windscreen
    rect(d, 86, 48, 114, 50, CUT)                         # bumper line
    rect(d, 4, 50, 88, 60)                                # chassis
    rect(d, 8, 52, 80, 54, CUT)
    rect(d, 26, 36, 40, 50)                               # elevation mount
    # The pod is drawn flat on its own layer, then tilted 25 degrees.
    pod = Image.new("RGBA", (64 * K, 30 * K), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pod)
    pd.rectangle([0, 0, 64 * K - 1, 30 * K - 1], fill=INK)
    for row in range(2):
        for col in range(3):
            cx, cy = (50 - col * 14) * K, (8 + row * 14) * K
            r = 5 * K
            pd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CUT)
            r = 2 * K
            pd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK)
    pod = pod.rotate(25, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(pod, (8 * K, 2 * K))
    for cx in (20, 44, 100):
        treaded_wheel(d, cx, 64, 11)
    return im


def orca():
    """Orca seen from above: pointed nose, side nacelles on stub wings, twin tail."""
    im, d = canvas()
    poly(d, [(10, 34), (30, 30), (84, 30), (118, 40), (84, 50), (30, 50)])  # fuselage
    poly(d, [(88, 36), (104, 39), (104, 41), (88, 44)], CUT)        # canopy
    rect(d, 40, 39, 74, 41, CUT)                          # spine line
    rect(d, 44, 14, 66, 66)                               # stub wing
    for y0 in (2, 60):                                    # engine nacelles
        d.rounded_rectangle([34 * K, y0 * K, 76 * K, (y0 + 18) * K], radius=7 * K, fill=INK)
        rect(d, 64, y0 + 4, 74, y0 + 14, CUT)             # intake
        rect(d, 66, y0 + 6, 72, y0 + 12)
    for y0 in (22, 54):                                   # missile pods under the wing
        rect(d, 70, y0, 88, y0 + 4)
    poly(d, [(10, 34), (2, 22), (12, 22), (24, 32)])      # twin tail
    poly(d, [(10, 46), (2, 58), (12, 58), (24, 48)])
    return im


def jet():
    """A-10 seen from above: straight wing, two engines on the back, twin tails."""
    im, d = canvas()
    poly(d, [(4, 37), (20, 34), (102, 34), (118, 40), (102, 46), (20, 46), (4, 43)])  # fuselage
    poly(d, [(92, 37), (104, 39), (104, 41), (92, 43)], CUT)        # canopy
    poly(d, [(54, 2), (70, 2), (74, 78), (50, 78)])       # straight wing
    for y in (10, 22, 58, 70):                            # bombs under the wing
        rect(d, 74, y - 2, 86, y + 2)
    for y0 in (22, 46):                                   # engines beside the tail
        d.rounded_rectangle([20 * K, y0 * K, 44 * K, (y0 + 12) * K], radius=5 * K, fill=INK)
        rect(d, 38, y0 + 3, 44, y0 + 9, CUT)
    rect(d, 2, 18, 20, 62)                                # tailplane
    for y0 in (14, 58):                                   # twin fins
        rect(d, 0, y0, 14, y0 + 8)
    return im


def gunboat():
    """Gunboat: portholes, stepped bridge, radar array, deck gun, missile box, wave."""
    im, d = canvas()
    poly(d, [(2, 42), (118, 38), (108, 60), (12, 60)])    # hull
    for x in (22, 36, 50, 64, 78):
        circ(d, x, 50, 3, CUT)                            # portholes
    rect(d, 10, 44, 104, 46, CUT)                         # deck line
    rect(d, 30, 26, 70, 42)                               # superstructure
    rect(d, 38, 18, 62, 26)                               # bridge
    rect(d, 42, 20, 58, 23, CUT)                          # bridge windows
    rect(d, 48, 6, 52, 18)                                # mast
    rect(d, 40, 6, 60, 9)                                 # radar array
    poly(d, [(50, 0), (54, 0), (52, 6)])
    rect(d, 12, 32, 26, 42)                               # missile box
    rect(d, 14, 34, 24, 36, CUT)
    rect(d, 80, 30, 94, 40)                               # gun turret
    line(d, [(92, 33), (116, 26)], 3.5)                   # gun
    line(d, [(0, 66), (20, 62), (40, 66), (60, 62), (80, 66), (100, 62), (120, 66)], 3)
    return im


def harvester():
    """Harvester: ribbed ore hopper on tracks, cab, exhaust stacks, front scoop."""
    im, d = canvas()
    poly(d, [(6, 24), (70, 18), (82, 26), (82, 56), (6, 56)])   # hopper
    for x in (14, 28, 42, 56):
        rect(d, x, 28, x + 8, 50, CUT)                    # hopper ribs
        rect(d, x + 3, 28, x + 5, 50)
    rect(d, 6, 22, 70, 25, CUT)                           # hopper rim line
    rect(d, 10, 8, 16, 22)                                # exhaust stacks
    rect(d, 20, 12, 26, 22)
    poly(d, [(84, 28), (102, 28), (112, 40), (112, 56), (84, 56)])  # cab
    poly(d, [(90, 32), (100, 32), (106, 40), (90, 40)], CUT)
    rect(d, 84, 46, 112, 48, CUT)
    poly(d, [(108, 48), (118, 50), (120, 66), (110, 72), (106, 60)])  # front scoop
    for y in (54, 60, 66):
        rect(d, 114, y, 120, y + 2, CUT)                  # scoop teeth gaps
    tracks(d, 4, 106, 56, 78, 6)
    return im


UNITS = {"1": rifleman, "2": engineer, "3": buggy, "4": apc, "5": mammoth,
         "6": mlrs, "7": orca, "8": jet, "9": gunboat, "0": harvester}
