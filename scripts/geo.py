"""County geometry helpers over data/geo/counties_2024.topojson.

Pure Python, no GIS dependencies. Everything here reads the reference
geometry; nothing writes a file.

- ``neighbors(fips)``: counties that share a boundary arc, across state lines.
- ``centroid(fips)``: area-weighted centroid of the county's largest ring set.
- ``county_at(lat, lon)``: the county whose polygon contains the point, or "".
- ``name(fips)``: the Census county name.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPOJSON = ROOT / "data" / "geo" / "counties_2024.topojson"


@lru_cache(maxsize=1)
def _topology(path: str = str(TOPOJSON)) -> dict:
    t = json.loads(Path(path).read_text(encoding="utf-8"))
    sx, sy = t["transform"]["scale"]
    tx, ty = t["transform"]["translate"]
    arcs = []
    for arc in t["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    counties = {}
    for g in t["objects"]["counties"]["geometries"]:
        fid = str(g.get("id") or "")
        if len(fid) != 5:
            continue
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        rings = [[_ring(arcs, r) for r in poly] for poly in polys]
        arc_ids = {i if i >= 0 else ~i for poly in polys for r in poly for i in r}
        xs = [p[0] for poly in rings for p in poly[0]]
        ys = [p[1] for poly in rings for p in poly[0]]
        counties[fid] = {
            "name": (g.get("properties") or {}).get("name", ""),
            "rings": rings,
            "arcs": arc_ids,
            "bbox": (min(xs), min(ys), max(xs), max(ys)),
        }
    by_arc: dict[int, set[str]] = {}
    for fid, c in counties.items():
        for a in c["arcs"]:
            by_arc.setdefault(a, set()).add(fid)
    return {"counties": counties, "by_arc": by_arc}


def _ring(arcs: list, idx: list[int]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for i in idx:
        pts = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        out.extend(pts if not out else pts[1:])
    return out


def _inside(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    hit = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def known(fips: str) -> bool:
    return fips in _topology()["counties"]


def all_counties() -> list[str]:
    """Every 2024 county (and county equivalent) in the boundary file."""
    return sorted(_topology()["counties"])


def name(fips: str) -> str:
    c = _topology()["counties"].get(fips)
    return c["name"] if c else ""


def neighbors(fips: str) -> list[str]:
    topo = _topology()
    c = topo["counties"].get(fips)
    if not c:
        return []
    out = set()
    for a in c["arcs"]:
        out |= topo["by_arc"].get(a, set())
    out.discard(fips)
    return sorted(out)


def centroid(fips: str) -> tuple[float, float] | None:
    """(lat, lon) of the area-weighted centroid of the county's outer rings."""
    c = _topology()["counties"].get(fips)
    if not c:
        return None
    a_sum = cx = cy = 0.0
    for poly in c["rings"]:
        ring = poly[0]
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            cross = x0 * y1 - x1 * y0
            a_sum += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
    if a_sum == 0:
        x0, y0, x1, y1 = c["bbox"]
        return ((y0 + y1) / 2, (x0 + x1) / 2)
    return (cy / (3 * a_sum), cx / (3 * a_sum))


def county_at(lat: float, lon: float) -> str:
    """FIPS of the county containing the point, or "" (offshore, or a gap in
    the simplified 5m boundaries)."""
    for fid, c in _topology()["counties"].items():
        x0, y0, x1, y1 = c["bbox"]
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poly in c["rings"]:
            if _inside(lon, lat, poly[0]) and not any(_inside(lon, lat, h) for h in poly[1:]):
                return fid
    return ""
