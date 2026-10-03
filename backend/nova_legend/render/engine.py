"""Simplified preview for parametric Nova symbols (GraphicItem Type="Engine").

Nova draws these symbols itself from parameters, e.g.

    2DNeutral;Typ=0;A=*L;B=*;A1=0,05;B1=0,05;Fill=1|4|5|8
    Verteiler;H=*H;B=*L;T=*B;AP=1;Darstellung=3

``*L`` means "take attribute L of the part" (size in mm). The preview here
builds a SymbolGeometry with the real proportions:

* 2DNeutral Typ 0 rectangle, Typ 1 ellipse, Typ 2 wall luminaire (rectangle
  with wall line), other types a plain rectangle
* A1/B1 inner frame (share of the size), Lines/Grid inner lines,
  Fill = filled sectors (8 triangles around the centre)
* Verteiler: box B x T with Darstellung 1 cross, 2 diagonal, 3 diagonal
  filled, 4 filled, 5 empty
* Langfeldleuchte (linear luminaires, sheet graphic of sheets 140, T5, T8):
  box L x B; DArt 0 (standard) with one line per tube (AnzR) along the
  length, DArt 1 plain box, DArt 2 (suspended) box with a line across;
  MitSicherheitsleuchte=True adds a filled square at one end

Inner symbols from Nova libraries (Symbol=L_1|geoSL) are not drawn. The
result is marked as a simplified preview (groups == ["engine"]).
"""

from __future__ import annotations

import math

from ..parser.geometry import Primitive, SymbolGeometry

PLAN_SCALE = 50            # preview scale 1:50 (paper metres = mm / 1000 / 50)
DEFAULT_MM = 600.0
ENGINE_GROUP = "engine"


def _num(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _size(expr: str | None, attrs: dict[str, str], fallback_key: str) -> float:
    """'*L' -> attribute L, '*' -> attribute fallback_key, '600' -> 600 (mm)."""
    value = None
    if expr:
        expr = expr.strip()
        if expr.startswith("*"):
            key = expr[1:].rstrip("*") or fallback_key
            value = _num(attrs.get(key))
        else:
            value = _num(expr)
    if not value or value <= 0:
        value = _num(attrs.get(fallback_key))
    if not value or value <= 0:
        value = DEFAULT_MM
    return value / 1000.0 / PLAN_SCALE


def _attr(expr: str | None, attrs: dict[str, str]) -> str | None:
    """'*Ctx1' -> attribute Ctx1, a plain value stays."""
    if expr and expr.strip().startswith("*"):
        return attrs.get(expr.strip()[1:])
    return expr


def _params(content: str) -> tuple[str, dict[str, str]]:
    parts = content.split(";")
    params = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip()] = v.strip()
    return parts[0].strip(), params


def _rect(w: float, h: float, inset_x: float = 0.0, inset_y: float = 0.0) -> list[tuple[float, float]]:
    x0, y0 = -w / 2 + inset_x, -h / 2 + inset_y
    x1, y1 = w / 2 - inset_x, h / 2 - inset_y
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _polygon(points, filled=False) -> Primitive:
    return Primitive("polygon", ENGINE_GROUP, filled,
                     {"points": points, "segments": [None] * len(points), "closed": True})


def _line(a, b) -> Primitive:
    return Primitive("line", ENGINE_GROUP, False, {"start": list(a), "end": list(b)})


def _ellipse(w: float, h: float, filled=False) -> Primitive:
    return Primitive("ellipse_arc", ENGINE_GROUP, filled,
                     {"matrix": [w / 2, 0.0, 0.0, h / 2], "center": [0.0, 0.0],
                      "start": 0.0, "sweep": 2 * math.pi})


def _sector(w: float, h: float, k: int) -> Primitive:
    """Triangle k (1..8) between centre and the rectangle border, 45° steps from east."""
    border = [(w / 2, 0), (w / 2, h / 2), (0, h / 2), (-w / 2, h / 2),
              (-w / 2, 0), (-w / 2, -h / 2), (0, -h / 2), (w / 2, -h / 2)]
    a, b = border[(k - 1) % 8], border[k % 8]
    return _polygon([(0.0, 0.0), a, b], filled=True)


def engine_geometry(content: str | None, attrs: dict[str, str]) -> SymbolGeometry | None:
    if not content:
        return None
    kind, p = _params(content)
    geo = SymbolGeometry(groups=[ENGINE_GROUP])
    prims = geo.primitives

    if kind == "Verteiler":
        w = _size(p.get("B"), attrs, "B")
        h = _size(p.get("T"), attrs, "T")
        box = _rect(w, h)
        mode = p.get("Darstellung", "5").strip("*")
        if mode == "4":
            prims.append(_polygon(box, filled=True))
        elif mode == "3":
            prims.append(_polygon([box[0], box[1], box[2]], filled=True))
        prims.append(_polygon(box))
        if mode in ("1", "2", "3"):
            prims.append(_line(box[0], box[2]))
        if mode == "1":
            prims.append(_line(box[1], box[3]))
    elif kind == "Langfeldleuchte":
        w = _size(p.get("L"), attrs, "L")
        h = _size(p.get("B"), attrs, "B")
        box = _rect(w, h)
        prims.append(_polygon(box))
        dart = (p.get("DArt") or "0").strip()
        if dart == "0":
            tubes = max(1, min(4, int(_num(_attr(p.get("AnzR"), attrs)) or 1)))
            for i in range(1, tubes + 1):
                y = -h / 2 + h * i / (tubes + 1)
                prims.append(_line((-w / 2, y), (w / 2, y)))
        elif dart == "2":
            prims.append(_line((0.0, -h / 2), (0.0, h / 2)))
        if (p.get("MitSicherheitsleuchte") or "").strip().lower() == "true":
            side = min(h, w) * 0.8
            x0 = w / 2 - side - h * 0.1
            prims.append(_polygon([(x0, -side / 2), (x0 + side, -side / 2), (x0 + side, side / 2), (x0, side / 2)],
                                  filled=True))
    elif kind in ("2DNeutral", "BauteileGrundriss"):
        typ = p.get("Typ", "0")
        w = _size(p.get("A") or p.get("L"), attrs, "L")
        h = _size(p.get("B"), attrs, "B")
        if typ == "1":
            for k in _fill_list(p.get("Fill")):
                prims.append(_sector(w, h, k))
            prims.append(_ellipse(w, h))
        else:
            box = _rect(w, h)
            for k in _fill_list(p.get("Fill")):
                prims.append(_sector(w, h, k))
            prims.append(_polygon(box))
            if typ == "2":
                # wall luminaire: filled strip on the wall side (bottom)
                y0, y1 = -h / 2, -h / 2 + h * 0.12
                prims.append(_polygon([(-w / 2, y0), (w / 2, y0), (w / 2, y1), (-w / 2, y1)], filled=True))
            lines = int(_num(p.get("Lines")) or 0)
            grid = p.get("Grid")
            if grid:
                lines = max(lines, int(_num(grid.split("|")[1]) or 0) if "|" in grid else 0)
            for i in range(1, lines + 1):
                y = -h / 2 + h * i / (lines + 1)
                prims.append(_line((-w / 2, y), (w / 2, y)))
        a1 = _num(p.get("A1")) or 0.0
        b1 = _num(p.get("B1")) or 0.0
        if a1 > 0 or b1 > 0:
            iw, ih = w * a1 if a1 < 1 else a1 / 1000 / PLAN_SCALE, h * b1 if b1 < 1 else b1 / 1000 / PLAN_SCALE
            if typ == "1":
                prims.append(_ellipse(w - 2 * iw, h - 2 * ih))
            else:
                prims.append(_polygon(_rect(w, h, iw, ih)))
    else:
        return None

    geo.points["WP"] = [0.0, 0.0, 0.0]
    return geo


def _fill_list(text: str | None) -> list[int]:
    out = []
    for part in (text or "").split("|"):
        n = _num(part)
        if n and 1 <= n <= 8:
            out.append(int(n))
    return out


def is_engine_preview(geo: SymbolGeometry | None) -> bool:
    return bool(geo and geo.groups == [ENGINE_GROUP])
