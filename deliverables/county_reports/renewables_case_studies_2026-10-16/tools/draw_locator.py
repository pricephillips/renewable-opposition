"""Locator map in the style of the Wikimedia county maps: the state's counties
in cream with black outlines, the subject county in red. Drawn from
data/geo/counties_2024.topojson. Usage: draw_locator.py TOPOJSON STATEFIPS COUNTYFIPS OUT.png"""
import json, math, sys
from PIL import Image, ImageDraw
topo, st, cf, out = sys.argv[1:5]
t = json.load(open(topo))
sx, sy = t["transform"]["scale"]; tx, ty = t["transform"]["translate"]
arcs = []
for a in t["arcs"]:
    x = y = 0; pts = []
    for dx, dy in a:
        x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)
def ring(idx):
    pts = []
    for i in idx:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts
geoms = [g for g in t["objects"]["counties"]["geometries"] if str(g["id"]).zfill(5).startswith(st)]
polys = []
for g in geoms:
    rings = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
    for poly in rings:
        polys.append((str(g["id"]).zfill(5), [ring(r) for r in poly]))
lats = [p[1] for _, rs in polys for r in rs for p in r]; lons = [p[0] for _, rs in polys for r in rs for p in r]
k = math.cos(math.radians(sum(lats) / len(lats)))
minx, maxx, miny, maxy = min(lons) * k, max(lons) * k, min(lats), max(lats)
W = 1000; H = int(W * (maxy - miny) / (maxx - minx)); pad = 10
img = Image.new("RGB", (W + 2 * pad, H + 2 * pad), "white"); d = ImageDraw.Draw(img)
P = lambda p: (pad + (p[0] * k - minx) / (maxx - minx) * W, pad + (maxy - p[1]) / (maxy - miny) * H)
for fips, rs in polys:
    for r in rs[:1]:
        d.polygon([P(p) for p in r], fill=(220, 0, 0) if fips == cf else (254, 254, 233), outline=(0, 0, 0))
img.save(out); print(out, img.size)
