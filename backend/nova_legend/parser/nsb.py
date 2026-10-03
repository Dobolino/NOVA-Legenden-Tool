"""Read symbol drawings from a bundled Nova symbol library (Lib/<name>.nsb).

A few catalogue items (e.g. 10-220 "Leerdose Gr.I, UP") have no geometry of
their own but point to a symbol in a library inside the dataset
(``Lib="BT_EB" Content="10"``). The library is an OLE file like a plan: its
stream ``Elements`` holds one record per drawing element, in plan
coordinates (mm). A symbol is the run of records from its frame record to
its reference point WP.

Decoded record classes (verified on BT_EB 10 and 20 against the layout of
the neighbouring switch 10-10: circle radius 2.5 mm, centre 2.5 mm above
WP, NP0 in the centre). Every element must lie inside the symbol frame:

    0x0082  symbol frame (layer X_SymbolRahmen): starts a symbol, not drawn
    0x0093  line: x1, y1, x2, y2
    0x0008  ellipse arc: centre (x, y, z), axis a (x, y, z), axis b (x, y, z),
            start and end angle (equal = full)
    0x0068  named point (WP, NP0, CP1 ...)

The cut contour (0x0069) is skipped. A symbol with any other element class,
or whose values do not fit (non-finite, far from WP, outside its frame), is
dropped: the program then shows its
usual placeholder instead of a wrong drawing.
"""

from __future__ import annotations

import io
import math
import re
import struct

from .geometry import Primitive, SymbolGeometry

_RECORD = re.compile(rb"\x66(..)(.)\x00{2,4}\x01?\x33\x03\x00\x00\x00\x02", re.S)
_EMPTY_NAME = b"\xff\xfe\xff\x00"
_NAME = re.compile(rb"\xff\xfe\xff([\x01-\x40])")
FRAME, LINE, ELLIPSE, POINT = 0x82, 0x93, 0x08, 0x68
CUT = 0x69             # cut contour (layer X_CUT): masks the wall, not drawn
MAX_MM = 60.0          # every element of a symbol lies within this distance of WP


def _doubles(data: bytes, offset: int, n: int) -> list[float] | None:
    if offset < 0 or offset + 8 * n > len(data):
        return None
    vals = list(struct.unpack_from(f"<{n}d", data, offset))
    return vals if all(math.isfinite(v) for v in vals) else None


def _utf16_after(data: bytes, start: int, limit: int = 400) -> tuple[str, int] | None:
    """First non-empty length-prefixed UTF-16 string after ``start``: (text, end offset)."""
    for m in _NAME.finditer(data, start, min(len(data), start + limit)):
        n = m.group(1)[0]
        end = m.end() + 2 * n
        try:
            return data[m.end():end].decode("utf-16-le"), end
        except UnicodeDecodeError:
            continue
    return None


def _symbols_raw(elements: bytes) -> dict[str, dict]:
    symbols: dict[str, dict] = {}
    current: dict | None = None
    for m in _RECORD.finditer(elements):
        cls = struct.unpack("<H", m.group(1))[0]
        name_end = elements.find(_EMPTY_NAME, m.end(), m.end() + 80)
        if cls == FRAME:
            named = _utf16_after(elements, m.end() + 40)
            frame = _doubles(elements, name_end + 5, 4) if name_end > 0 else None
            current = {"name": named[0] if named else "", "lines": [], "ellipses": [], "points": {},
                       "frame": frame, "unknown": set()}
            if current["name"]:
                symbols[current["name"]] = current
        elif current is None:
            continue
        elif cls == LINE and name_end > 0:
            vals = _doubles(elements, name_end + 5, 4)
            if vals:
                current["lines"].append(vals)
        elif cls == ELLIPSE and name_end > 0:
            vals = _doubles(elements, name_end + 6, 11)
            if vals:
                current["ellipses"].append(vals)
        elif cls == POINT:
            named = _utf16_after(elements, m.end() + 20)
            if named:
                vals = _doubles(elements, named[1] + 9, 2)
                if vals:
                    current["points"][named[0]] = vals
        elif cls != CUT:
            # an element this reader cannot draw (polyline, hatch ...): the symbol
            # would be incomplete, so it is not used at all
            current["unknown"].add(cls)
    return symbols


def _geometry(raw: dict) -> SymbolGeometry | None:
    wp = raw["points"].get("WP")
    if not wp or raw["unknown"] or not (raw["lines"] or raw["ellipses"]):
        return None
    ox, oy = wp

    def rel(x: float, y: float) -> tuple[float, float]:
        return (x - ox) / 1000.0, (y - oy) / 1000.0

    def near(*mm: float) -> bool:
        return all(abs(v) <= MAX_MM for v in mm)

    frame = raw.get("frame")
    if not frame:
        return None
    fx0, fy0, fx1, fy1 = min(frame[0], frame[2]), min(frame[1], frame[3]), max(frame[0], frame[2]), max(frame[1], frame[3])

    def inside(x: float, y: float) -> bool:
        """Absolute mm point within the symbol frame (small tolerance)."""
        return fx0 - 0.01 <= x <= fx1 + 0.01 and fy0 - 0.01 <= y <= fy1 + 0.01

    if not inside(ox, oy):
        return None

    geo = SymbolGeometry(groups=["nsb"])
    for x1, y1, x2, y2 in raw["lines"]:
        if not near(x1 - ox, y1 - oy, x2 - ox, y2 - oy) or not (inside(x1, y1) and inside(x2, y2)):
            return None
        geo.primitives.append(Primitive("line", "", False, {"start": rel(x1, y1), "end": rel(x2, y2)}))
    for cx, cy, _cz, ax, ay, _az, bx, by, _bz, t0, t1 in raw["ellipses"]:
        if not near(cx - ox, cy - oy, ax, ay, bx, by) or math.hypot(ax, ay) <= 0:
            return None
        reach = max(math.hypot(ax, ay), math.hypot(bx, by))
        if not (inside(cx - reach, cy - reach) and inside(cx + reach, cy + reach)):
            return None
        center = rel(cx, cy)
        full = abs(t1 - t0) < 1e-9
        ra, rb = math.hypot(ax, ay), math.hypot(bx, by)
        if full and abs(ra - rb) < 1e-6 and abs(ax * bx + ay * by) < 1e-6:
            r = ra / 1000.0
            start = (center[0] + r, center[1])
            geo.primitives.append(Primitive("arc", "", False, {"center": center, "start": start, "end": start,
                                                               "radius": r, "clockwise": False, "full": True}))
        else:
            sweep = 2 * math.pi if full else t1 - t0
            geo.primitives.append(Primitive("ellipse_arc", "", False, {
                "matrix": [ax / 1000.0, bx / 1000.0, ay / 1000.0, by / 1000.0], "center": center,
                "start": t0, "sweep": sweep}))
    for name, (x, y) in raw["points"].items():
        if near(x - ox, y - oy):
            px, py = rel(x, y)
            geo.points[name] = [px, py, 0.0]
    return geo


def read_nsb(data: bytes) -> dict[str, SymbolGeometry]:
    """Symbol name -> drawing (metres at paper scale, WP at the origin)."""
    import olefile

    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
        try:
            elements = ole.openstream("Elements").read()
        finally:
            ole.close()
    except Exception:  # noqa: BLE001 - an unreadable library gives no drawings
        return {}
    out = {}
    for name, raw in _symbols_raw(elements).items():
        geo = _geometry(raw)
        if geo is not None:
            out[name] = geo
    return out
