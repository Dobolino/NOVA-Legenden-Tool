"""Parser for the textual 2D geometry stored in Graphic/GraphicItem@Geometry.

The geometry is a nested bracket notation. Numbers inside one bracket are
separated by ';' (coordinates) or '|' (point lists). Example (a switch):

    ((1)(("")()(0)((3)(((Line)((x1;y1)(x2;y2))))...(((Arc)((cx;cy)(sx;sy)(ex;ey)(0)))))
         ((0))((0))((0))))
    ((2)(("NP0")(0;0.0025;0))(("WP")(0;0;0)))
    ((1)(("CP1")(0;0.0025;0)(0)))
    (-0.0025;0;0.0025;0.005;1)

Top level blocks:
    1. groups    -> list of (name, ?, flag, curves, fills, hatches, texts)
    2. points    -> named connection points (NP0, NP1, WP ...)
    3. cpoints   -> named construction points (CP1 ...) with an extra value
    4. bbox      -> xmin;ymin;xmax;ymax;flag

All coordinates are in metres at plot scale 1:1 (0.005 = 5 mm).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any

Sexp = list | str  # nested list of atoms


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def parse_sexp(text: str, strict: bool = True) -> list:
    """Turn the bracket notation into nested Python lists.

    Quoted strings ("...") become Python strings wrapped in a 1-tuple marker
    so they can be told apart from bare atoms. Bare atoms stay str.
    """
    stack: list[list] = [[]]
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "(":
            new: list = []
            stack[-1].append(new)
            stack.append(new)
            i += 1
        elif ch == ")":
            if len(stack) == 1:
                raise ValueError(f"Unbalanced ')' at {i}")
            stack.pop()
            i += 1
        elif ch == '"':
            # Quoted string; a doubled quote "" inside is an escaped quote
            j = i + 1
            buf = []
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"' and not (j + 2 < n and text[j + 2] == ")"):
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(text[j])
                j += 1
            stack[-1].append(Quoted("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in '()"':
                j += 1
            stack[-1].append(text[i:j])
            i = j
    if len(stack) != 1 and strict:
        raise ValueError("Unbalanced '(' in geometry")
    # strict=False: a truncated text keeps what was read (open lists are closed)
    return stack[0]


class Quoted(str):
    """Marker type for quoted strings in the bracket notation."""


def _nums(atom: Any) -> list[float]:
    """'0.1;0.2' -> [0.1, 0.2]. Accepts a list holding one atom."""
    if isinstance(atom, list):
        if not atom:
            return []
        atom = atom[0]
    return [float(x) for x in str(atom).split(";") if x != ""]


def _points(atom: Any) -> list[tuple[float, float]]:
    """'3|x;y|x;y|x;y' -> [(x,y), ...]."""
    if isinstance(atom, list):
        atom = atom[0]
    parts = str(atom).split("|")
    count = int(parts[0])
    pts = []
    for p in parts[1:1 + count]:
        x, y = p.split(";")[:2]
        pts.append((float(x), float(y)))
    return pts


# ---------------------------------------------------------------------------
# Primitive model
# ---------------------------------------------------------------------------

@dataclass
class Primitive:
    kind: str                      # line, arc, ellipse_arc, polyline, polygon, spline, hatch, text
    layer: str                     # sub group name, e.g. X_Geometrie
    filled: bool = False
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SymbolGeometry:
    primitives: list[Primitive] = field(default_factory=list)
    points: dict[str, list[float]] = field(default_factory=dict)
    cpoints: dict[str, list[float]] = field(default_factory=dict)
    bbox: list[float] | None = None
    groups: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "primitives": [p.to_dict() for p in self.primitives],
            "points": self.points,
            "cpoints": self.cpoints,
            "bbox": self.bbox,
            "groups": self.groups,
            "warnings": self.warnings,
        }

    def stats(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for p in self.primitives:
            out[p.kind] = out.get(p.kind, 0) + 1
        return out


# ---------------------------------------------------------------------------
# Interpreters for each block
# ---------------------------------------------------------------------------

def _arc(data: list) -> dict:
    """Arc: (center)(start)(end)(dir). start == end means full circle."""
    c, s, e = _nums(data[0]), _nums(data[1]), _nums(data[2])
    direction = int(float(data[3][0])) if len(data) > 3 and data[3] else 0
    r = math.hypot(s[0] - c[0], s[1] - c[1])
    full = abs(s[0] - e[0]) < 1e-12 and abs(s[1] - e[1]) < 1e-12
    return {"center": c[:2], "start": s[:2], "end": e[:2], "radius": r,
            "clockwise": direction == 1, "full": full}


def _elliptic_arc(data: list) -> dict:
    """EllipticArc: ((m11;m21;m12;m22)(cx;cy))(sweep)(start).

    Point(t) = center + M * (cos t, sin t), t from start to start+sweep.
    """
    frame = data[0]
    m = _nums(frame[0])
    c = _nums(frame[1])
    sweep = float(data[1][0]) if len(data) > 1 else 2 * math.pi
    start = float(data[2][0]) if len(data) > 2 else 0.0
    return {"matrix": m, "center": c[:2], "sweep": sweep, "start": start}


def _segments(seg_block: list, count: int) -> list[dict | None]:
    """Segment list of a Flex polygon/polyline.

    ``()`` alone means all straight segments. Otherwise ``((k)(seg)...)``
    where an empty seg is straight and ``(Arc)(...)`` is a circular arc.
    """
    if not seg_block:
        return [None] * count
    k = int(seg_block[0][0]) if seg_block and isinstance(seg_block[0], list) and seg_block[0] else 0
    segs: list[dict | None] = []
    i = 1
    while i < len(seg_block):
        item = seg_block[i]
        if isinstance(item, list) and item and isinstance(item[0], str) and item[0] == "Arc":
            segs.append({"type": "arc", **_arc(seg_block[i + 1])})
            i += 2
        elif isinstance(item, list) and len(item) == 0:
            segs.append(None)
            i += 1
        elif isinstance(item, list) and item and isinstance(item[0], list) and item[0] == ["Arc"]:
            segs.append({"type": "arc", **_arc(item[1])})
            i += 1
        else:
            segs.append(None)
            i += 1
    while len(segs) < max(k, count):
        segs.append(None)
    return segs


def _flex(data: list, closed: bool) -> dict:
    pts = _points(data[0])
    n_seg = len(pts) if closed else max(len(pts) - 1, 0)
    segs = _segments(data[1] if len(data) > 1 else [], n_seg)
    return {"points": pts, "segments": segs, "closed": closed}


def _spline(data: list) -> dict:
    degree = int(float(data[0][0]))
    ctrl = _points(data[1])
    knots_raw = str(data[2][0]).split("|") if len(data) > 2 and data[2] else []
    knots = [float(x) for x in knots_raw[1:]] if knots_raw else []
    weights: list[float] = []
    if len(data) > 3 and data[3]:
        w_raw = str(data[3][0]).split("|")
        weights = [float(x) for x in w_raw[1:]]
    return {"degree": degree, "control": ctrl, "knots": knots, "weights": weights}


def _curve(elem: list, layer: str, filled: bool, warnings: list[str]) -> Primitive | None:
    """One curve element: [[type], data]."""
    if not elem or not isinstance(elem[0], list) or not elem[0]:
        warnings.append(f"empty curve element in {layer}")
        return None
    kind = elem[0][0]
    data = elem[1] if len(elem) > 1 else []
    try:
        if kind == "Line":
            a, b = _nums(data[0]), _nums(data[1])
            return Primitive("line", layer, filled, {"start": a[:2], "end": b[:2]})
        if kind == "Arc":
            return Primitive("arc", layer, filled, _arc(data))
        if kind == "EllipticArc":
            return Primitive("ellipse_arc", layer, filled, _elliptic_arc(data))
        if kind == "FlexPolygon":
            return Primitive("polygon", layer, filled, _flex(data, closed=True))
        if kind == "FlexPolyline":
            return Primitive("polyline", layer, filled, _flex(data, closed=False))
        if kind == "Spline":
            return Primitive("spline", layer, filled, _spline(data))
    except (ValueError, IndexError, TypeError) as exc:
        warnings.append(f"could not read {kind} in {layer}: {exc}")
        return None
    warnings.append(f"unknown curve type {kind!r} in {layer}")
    return None


def _text(elem: list, layer: str, warnings: list[str]) -> Primitive | None:
    """Text element: [[matrix, pos], [font, a, b], content]."""
    try:
        frame, font, content = elem[0], elem[1], elem[2]
        m = _nums(frame[0])
        pos = _nums(frame[1])
        # The 2x2 matrix is stored column by column: text x axis = (m0, m2),
        # text y axis = (m1, m3). Verified on "T23" in 90-105 (vertical text).
        height = math.hypot(m[1], m[3]) if len(m) >= 4 else 0.0025
        width_factor = (math.hypot(m[0], m[2]) / height) if height else 1.0
        rotation = math.degrees(math.atan2(m[2], m[0]))
        font_name = str(font[0][0]) if font and font[0] else "Arial"
        flags = [str(f[0]) if f else "" for f in font[1:]]
        text = str(content[0]) if content else ""
        return Primitive("text", layer, False, {
            "text": text, "position": pos[:2], "height": height,
            "width_factor": width_factor, "rotation": rotation,
            "matrix": m, "font": font_name, "font_flags": flags,
        })
    except (ValueError, IndexError, TypeError) as exc:
        warnings.append(f"could not read text in {layer}: {exc}")
        return None


def _block_items(block: list) -> list:
    """((n)(item)(item)...) -> [item, ...] (each item unwrapped once)."""
    if not block:
        return []
    items = []
    for entry in block[1:]:
        # Each entry is wrapped: (((Line)(...))) -> [[['Line'], [...]]]
        if isinstance(entry, list) and len(entry) == 1 and isinstance(entry[0], list):
            items.append(entry[0])
        else:
            items.append(entry)
    return items


def parse_geometry(text: str) -> SymbolGeometry:
    """Parse a Geometry attribute into a SymbolGeometry."""
    geo = SymbolGeometry()
    try:
        top = parse_sexp(text)
    except ValueError:
        # Some Trimble datasets contain truncated geometry texts (e.g.
        # Niederspannung.CH KNX_01_B). Keep the complete part.
        top = parse_sexp(text, strict=False)
        geo.warnings.append("geometry text truncated (partly read)")
    if len(top) < 1:
        geo.warnings.append("empty geometry")
        return geo

    groups_block = top[0]
    for group in groups_block[1:]:
        # group: [name, ?, flag, curves, fills, hatches, texts]
        name = str(group[0][0]) if group and group[0] else ""
        layer = name
        geo.groups.append(name)
        curves = group[3] if len(group) > 3 else []
        fills = group[4] if len(group) > 4 else []
        reserved = group[5] if len(group) > 5 else []  # hatch areas
        texts = group[6] if len(group) > 6 else []
        for elem in _block_items(curves):
            prim = _curve(elem, layer, False, geo.warnings)
            if prim:
                geo.primitives.append(prim)
        for elem in _block_items(fills):
            prim = _curve(elem, layer, True, geo.warnings)
            if prim:
                geo.primitives.append(prim)
        for elem in (reserved[1:] if reserved else []):
            # Hatch: [[pattern], [points, segments], ...more loops]
            try:
                pattern = str(elem[0][0]) if elem and elem[0] else ""
                for loop in elem[1:]:
                    data = _flex(loop, closed=True)
                    data["pattern"] = pattern
                    geo.primitives.append(Primitive("hatch", layer, True, data))
            except (ValueError, IndexError, TypeError) as exc:
                geo.warnings.append(f"could not read hatch in {layer}: {exc}")
        for elem in _block_items(texts):
            prim = _text(elem, layer, geo.warnings)
            if prim:
                geo.primitives.append(prim)
        if len(group) > 7:
            geo.warnings.append(f"group {layer} has {len(group)} fields")

    if len(top) > 1:
        for entry in top[1][1:]:
            geo.points[str(entry[0][0])] = _nums(entry[1])
    if len(top) > 2:
        for entry in top[2][1:]:
            geo.cpoints[str(entry[0][0])] = _nums(entry[1])
    if len(top) > 3 and top[3]:
        nums = _nums(top[3])
        geo.bbox = nums[:4] if len(nums) >= 4 else None
    return geo


# ---------------------------------------------------------------------------
# Sampling helpers (used by renderer, matcher and DXF export)
# ---------------------------------------------------------------------------

def arc_angles(arc: dict) -> tuple[float, float]:
    """Return (start_angle, end_angle) in radians, counter clockwise order."""
    cx, cy = arc["center"]
    a0 = math.atan2(arc["start"][1] - cy, arc["start"][0] - cx)
    a1 = math.atan2(arc["end"][1] - cy, arc["end"][0] - cx)
    if arc.get("full"):
        return 0.0, 2 * math.pi
    if arc.get("clockwise"):
        a0, a1 = a1, a0
    while a1 <= a0:
        a1 += 2 * math.pi
    return a0, a1


def sample_arc(arc: dict, steps_per_circle: int = 64) -> list[tuple[float, float]]:
    """Points along an arc, in the direction it was drawn."""
    cx, cy = arc["center"]
    r = arc["radius"]
    a0, a1 = arc_angles(arc)
    n = max(4, int(steps_per_circle * (a1 - a0) / (2 * math.pi)))
    pts = [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
            cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    if arc.get("clockwise") and not arc.get("full"):
        pts.reverse()
    return pts


def sample_ellipse(e: dict, steps: int = 64) -> list[tuple[float, float]]:
    m, (cx, cy) = e["matrix"], e["center"]
    t0, sw = e["start"], e["sweep"]
    n = max(4, int(steps * abs(sw) / (2 * math.pi)))
    pts = []
    for i in range(n + 1):
        t = t0 + sw * i / n
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + m[0] * c + m[2] * s, cy + m[1] * c + m[3] * s))
    return pts


def sample_spline(sp: dict, steps: int = 48) -> list[tuple[float, float]]:
    """Evaluate a (rational) B-spline with de Boor's algorithm."""
    p = sp["degree"]
    ctrl = sp["control"]
    knots = sp["knots"]
    w = sp["weights"] or [1.0] * len(ctrl)
    if len(knots) != len(ctrl) + p + 1:
        return list(ctrl)  # fall back to control polygon
    lo, hi = knots[p], knots[len(ctrl)]
    out = []
    for i in range(steps + 1):
        t = lo + (hi - lo) * i / steps
        k = p
        while k < len(ctrl) - 1 and not (knots[k] <= t < knots[k + 1]):
            k += 1
        d = [(ctrl[j][0] * w[j], ctrl[j][1] * w[j], w[j]) for j in range(k - p, k + 1)]
        for r in range(1, p + 1):
            for j in range(p, r - 1, -1):
                denom = knots[j + 1 + k - r] - knots[j + k - p]
                a = 0.0 if denom == 0 else (t - knots[j + k - p]) / denom
                d[j] = tuple((1 - a) * d[j - 1][q] + a * d[j][q] for q in range(3))
        x, y, ww = d[p]
        out.append((x / ww, y / ww) if ww else (x, y))
    return out


def flex_points(flex: dict) -> list[tuple[float, float]]:
    """Expand a Flex polygon/polyline (with arc segments) to a point list."""
    pts = flex["points"]
    if not pts:
        return []
    out = [pts[0]]
    n_seg = len(pts) if flex["closed"] else len(pts) - 1
    for i in range(n_seg):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        seg = flex["segments"][i] if i < len(flex["segments"]) else None
        if seg and seg.get("type") == "arc":
            arc_pts = sample_arc(seg, 48)
            # Orient the sampled arc from a to b
            if math.dist(arc_pts[0], a) > math.dist(arc_pts[-1], a):
                arc_pts.reverse()
            out.extend(arc_pts[1:-1])
        out.append(b)
    return out
