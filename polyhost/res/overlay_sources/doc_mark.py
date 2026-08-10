#!/usr/bin/env python3
"""Shared **document-framed program marks**: the Fluent `Document` glyph (MIT)
as the page frame, with a per-app motif and the app name placed INSIDE it.

Used by any overlay set whose app is a document/page (LibreOffice modules,
Google Docs, ...). Peer of `program_marks.py` (letter tiles) — reach for this
one when the app IS a document and the name is worth spelling out.

Placement is geometric, not eyeballed. The glyph is parsed into polygons
(svgpathtools -> shapely): an outer page ring, the page interior as a hole,
and the corner fold as a second hole. The area content may occupy is then

    safe = interior.buffer(-CLEAR).difference(fold.buffer(+CLEAR))

so nothing can land on or beside the outline, and the layout reads the
**per-row** x-spans of `safe` — which is what makes the cut corner work: the
top rows really are narrower. `build()` returns (label, touching, outside)
and the caller asserts the last two are 0.

⚠️ The page keeps Fluent's NATIVE aspect ratio (page_h 39.6 rasterises to
exactly 32x40 = 0.800; at 40 the antialiased edge crosses the threshold on one
side and yields 33px, i.e. 0.825 — visibly wider for no reason). At that ratio the measured
interior is ~26 px, so "IMPRESS" (25 px in the 3x5 pixel font, plus
clearance) does not fit and the label is "IMPR". Stretching the page to fit
it was tried and rejected — a distorted document reads worse than an
abbreviation.

Marks are authored 1:1 at 72x40 and placed with `program_icon_region:
[72, 40]`, so the generator never rescales them and every pixel is
deliberate — the same trick the Explorer mark uses.

    pip install shapely svgpathtools cairosvg
"""
import json, pathlib, urllib.request
import numpy as np
from svgpathtools import svgstr2paths
from shapely.geometry import Polygon
from shapely.affinity import scale as shscale, translate as shtrans
from PIL import Image, ImageDraw
F = json.loads((pathlib.Path(__file__).resolve().parent / "px3x5.json").read_text())
WID = {c: len(g[0]) for c, g in F.items()}
CELL_W, CELL_H, CLEAR = 72, 40, 1.2
FL=("https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/"
    "Document/SVG/ic_fluent_document_24_regular.svg")
_c = pathlib.Path(__file__).resolve().parent / "_assets" / "fluent_document.svg"
if not _c.exists():
    _c.write_bytes(urllib.request.urlopen(urllib.request.Request(FL,
        headers={"User-Agent":"polykybd"}), timeout=30).read())
paths,_ = svgstr2paths(_c.read_text())
rings=[]
for p in paths:
    for sub in p.continuous_subpaths():
        pts=[(sub.point(t).real, sub.point(t).imag) for t in np.linspace(0,1,600)]
        g=Polygon(pts)
        if g.is_valid and g.area>0.5: rings.append(g)
rings.sort(key=lambda g:-g.area); outer,interior,fold = rings[0],rings[1],rings[2]
def fit(page_h, stretch):
    s = page_h/(outer.bounds[3]-outer.bounds[1])
    g3=[shscale(g, s*stretch, s, origin=(outer.bounds[0],outer.bounds[1])) for g in (outer,interior,fold)]
    dx,dy = -g3[0].bounds[0], -g3[0].bounds[1]
    g3=[shtrans(g,dx,dy) for g in g3]
    ox=(CELL_W-(g3[0].bounds[2]-g3[0].bounds[0]))/2; oy=(CELL_H-(g3[0].bounds[3]-g3[0].bounds[1]))/2
    return [shtrans(g,ox,oy) for g in g3]
def mask_of(geom):
    m=Image.new("L",(CELL_W,CELL_H),0); d=ImageDraw.Draw(m)
    for g in (geom.geoms if hasattr(geom,"geoms") else [geom]):
        if g.is_empty: continue
        d.polygon(list(g.exterior.coords), fill=255)
        for h in g.interiors: d.polygon(list(h.coords), fill=0)
    return np.array(m)>127
def word_w(w): return sum(WID[c] for c in w)+len(w)-1
def draw_word(px,w,x,y):
    for c in w:
        for ry,row in enumerate(F[c]):
            for rx,ch in enumerate(row):
                if ch=="#": px[y+ry,x+rx]=1
        x+=WID[c]+1
def m_writer(px,lo,hi,t,b):
    for k,y in enumerate((t+2,t+5,t+8)):
        if y<=b: px[y, lo+1:(hi if k<2 else hi-3)]=1
def m_calc(px,lo,hi,t,b):
    y0,y1=t+1,min(b,t+10)
    px[y0,lo+1:hi]=1; px[y1,lo+1:hi]=1; px[y0:y1+1,lo+1]=1; px[y0:y1+1,hi-1]=1
    px[(y0+y1)//2,lo+1:hi]=1; px[y0:y1+1,(lo+hi)//2]=1
def m_impress(px,lo,hi,t,b):
    y0,y1=t+1,min(b-2,t+8)
    px[y0,lo+1:hi]=1; px[y1,lo+1:hi]=1; px[y0:y1+1,lo+1]=1; px[y0:y1+1,hi-1]=1
    px[min(b,y1+3), lo+3:hi-2]=1
MOTIF={"writer":m_writer,"calc":m_calc,"impress":m_impress}
def build(app, words, page_h=39.6, stretch=1.0, save=None):
    o,i,f = fit(page_h,stretch)
    ink=o.difference(i).difference(f)
    safe=i.buffer(-CLEAR).difference(f.buffer(CLEAR))
    ink_m,safe_m = mask_of(ink),mask_of(safe)
    px=np.zeros((CELL_H,CELL_W),np.uint8); px[ink_m]=1
    rows=[(y,np.nonzero(safe_m[y])[0]) for y in range(CELL_H)]
    rows=[(y,xs) for y,xs in rows if xs.size]
    if not rows: return None
    y0,y1=rows[0][0],rows[-1][0]; chosen=None
    for w in words:
        need=word_w(w)
        for top in range(y1-4,y0-1,-1):
            band=[xs for y,xs in rows if top<=y<=top+4]
            if len(band)<5: continue
            lo,hi=max(x.min() for x in band),min(x.max() for x in band)
            if hi-lo+1>=need: chosen=(w,top,lo+(hi-lo+1-need)//2); break
        if chosen: break
    if not chosen: return None
    w,ly,lx=chosen; draw_word(px,w,lx,ly)
    mtop,mbot=y0+1,ly-3
    band=[xs for y,xs in rows if mtop<=y<=mbot]
    if band:
        lo,hi=max(x.min() for x in band),min(x.max() for x in band)
        MOTIF[app](px,lo,hi,mtop,mbot)
    content=px.astype(bool)&~ink_m
    grow=np.zeros_like(ink_m)
    for dy in(-1,0,1):
        for dx in(-1,0,1): grow|=np.roll(np.roll(ink_m,dy,0),dx,1)
    if save:
        a=Image.fromarray(px*255,"L"); Image.merge("RGBA",(a,)*3+(a,)).save(save)
    return w,int((content&grow).sum()),int((content&~safe_m).sum()),int(px.sum())
