"""Render a SymbolGeometry as a standalone SVG string.

Coordinates are metres at plot scale (0.005 = 5 mm). The SVG uses mm as
user unit and flips the Y axis (Nova: Y up, SVG: Y down).
"""

from __future__ import annotations

import html
import math

from ..parser.geometry import (SymbolGeometry, flex_points, sample_arc,
                               sample_ellipse, sample_spline)

MM = 1000.0  # metres -> millimetres


def _pt(p: tuple[float, float] | list[float]) -> str:
    return f"{p[0] * MM:.4f},{-p[1] * MM:.4f}"


def _path(points: list, closed: bool) -> str:
    if not points:
        return ""
    d = "M" + " L".join(_pt(p) for p in points)
    return d + (" Z" if closed else "")


def geometry_bounds(geo: SymbolGeometry) -> tuple[float, float, float, float]:
    """Bounds in metres from the actual primitives (bbox field may be missing)."""
    xs: list[float] = []
    ys: list[float] = []

    def add(pts):
        for x, y in pts:
            xs.append(x)
            ys.append(y)

    for p in geo.primitives:
        d = p.data
        if p.kind == "line":
            add([d["start"], d["end"]])
        elif p.kind == "arc":
            add(sample_arc(d, 32))
        elif p.kind == "ellipse_arc":
            add(sample_ellipse(d, 32))
        elif p.kind in ("polygon", "polyline", "hatch"):
            add(flex_points(d))
        elif p.kind == "spline":
            add(sample_spline(d, 24))
        elif p.kind == "text":
            x, y = d["position"]
            w = d["height"] * 0.6 * max(len(d["text"]), 1) * d.get("width_factor", 1.0)
            a = math.radians(d.get("rotation", 0.0))
            ux, uy = math.cos(a), math.sin(a)      # text direction
            vx, vy = -uy, ux                       # text up direction
            h = d["height"]
            add([(x, y), (x + ux * w, y + uy * w), (x + vx * h, y + vy * h),
                 (x + ux * w + vx * h, y + uy * w + vy * h)])
    for v in geo.points.values():
        add([(v[0], v[1])])
    if not xs:
        if geo.bbox:
            return tuple(geo.bbox)  # type: ignore[return-value]
        return (-0.0025, -0.0025, 0.0025, 0.0025)
    return min(xs), min(ys), max(xs), max(ys)


# Colours in the SVG. The page defines the CSS variables; the fallbacks keep
# standalone files readable.
LAYER_FILL = "var(--sym-layer, #b9c0c9)"   # layer colour next to explicit black lines
BACKGROUND = "var(--sym-bg, #ffffff)"      # white masking areas


def is_layer_grey(color: str | None) -> bool:
    """A neutral grey in the Nova drawing. It follows the plan layer, like a part
    without its own colour. Black stays black, white stays a mask, a real hue stays."""
    if not color or len(color) != 7 or not color.startswith("#"):
        return False
    try:
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return False
    if max(r, g, b) - min(r, g, b) > 24:
        return False
    if max(r, g, b) <= 48 or min(r, g, b) >= 242:
        return False
    return True


def _explicit(color: str | None) -> bool:
    """A colour the symbol chose itself. Grey and empty follow the plan layer."""
    return bool(color) and not is_layer_grey(color)


def _hue(color: str | None) -> bool:
    """A real colour, not black, white or grey. Those follow the plan layer when
    the whole symbol has no colour of its own."""
    if not _explicit(color) or not color:
        return False
    low = color.lower()
    if low in ("#000000", "#ffffff"):
        return False
    try:
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    except ValueError:
        return False
    return max(r, g, b) - min(r, g, b) > 24 or (max(r, g, b) > 48 and min(r, g, b) < 242)


def is_soft(p, mixed: bool) -> bool:
    """A soft fill: a hatch, or an area without own colour next to coloured lines
    (drawn as a light tone). Everything else that is filled is a solid fill."""
    return p.kind == "hatch" or (bool(p.filled) and mixed and not _explicit(p.color))


def has_fill(geo: SymbolGeometry) -> bool:
    """True if the symbol has filled areas or hatches (the fill can be hidden)."""
    return any(p.filled for p in geo.primitives)


def _paint(color: str | None, mixed: bool) -> str:
    """CSS colour for a primitive.

    Nova draws parts without their own colour in the layer colour. When a
    symbol also has explicitly coloured parts (the "Füllung" symbols: black
    lines on a layer-coloured area) the layer colour becomes a light tone,
    otherwise everything uses the text colour of the page.
    """
    if color is None:
        return LAYER_FILL if mixed else "currentColor"
    if color == "#000000":
        return "currentColor"
    if color == "#ffffff":
        return BACKGROUND
    return color


# Legend colours. As in Nova, a part without its own colour is drawn in the colour of
# its layer: in the legend the colour of the section (plan colour of the category's
# layer). An explicit colour of the symbol stays, black included.
OWN_BLACK = "#000000"
LAYER_TINT = 0.45            # an area without own colour next to coloured lines: lighter layer colour


def _tint(color: str, share: float) -> str:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(c + (255 - c) * share) for c in (r, g, b))


def own_paint(color: str | None, mixed: bool, filled: bool, layer: str = OWN_BLACK,
              monochrome: bool = False) -> str:
    """Hex colour of a primitive in the legend (DXF export).

    An explicit hue stays. A part without own colour, a neutral grey, and every
    part of a symbol that has no hue of its own, take ``layer``. White stays a
    mask. An area without own colour next to a coloured line takes a lighter
    tone, so the line on it stays visible.
    """
    if color and color.lower() == "#ffffff":
        return color
    # black stays black next to a real colour; a symbol without any hue takes the plan colour
    if monochrome or not _explicit(color):
        return _tint(layer, LAYER_TINT) if (mixed and filled and not monochrome) else layer
    return color


def is_mixed(geo: SymbolGeometry) -> bool:
    return any(_explicit(p.color) for p in geo.primitives) and any(not _explicit(p.color) for p in geo.primitives)


def render_svg(geo: SymbolGeometry, size_px: int | None = 96, show_points: bool = True,
               stroke_mm: float = 0.18, title: str | None = None, show_fill: bool = True,
               own_colors: bool = False, show_soft: bool | None = None,
               force_color: bool = False) -> str:
    """``show_fill`` False hides the fills; with ``show_soft`` given, it decides on its
    own for hatches and light areas and ``show_fill`` only for solid fills."""
    soft_shown = show_fill if show_soft is None else show_soft
    x0, y0, x1, y1 = geometry_bounds(geo)   # full symbol, also when the fill is hidden
    pad = max(x1 - x0, y1 - y0, 0.002) * 0.12
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    w, h = (x1 - x0) * MM, (y1 - y0) * MM
    # Large symbols (e.g. an 11 m PV array at 1:50) keep visible lines
    stroke_mm = max(stroke_mm, 0.012 * max(w, h))
    # force_color: one colour for the whole symbol (the section colour, or a chosen one).
    # White stays a mask. Otherwise a real hue in the drawing stays.
    mixed = False if force_color else is_mixed(geo)
    monochrome = force_color or not any(_hue(p.color) for p in geo.primitives)
    parts: list[str] = []
    for p in geo.primitives:
        if p.filled and not (soft_shown if is_soft(p, mixed) else show_fill):
            continue
        d = p.data
        if own_colors:
            # explicit colours as hex; parts without own colour follow the page:
            # currentColor = section colour, --sym-layer = its lighter tone
            if p.color and p.color.lower() == "#ffffff":
                paint = line = BACKGROUND
            elif monochrome or not _explicit(p.color):
                line = "currentColor"
                paint = "var(--sym-layer, #b9c0c9)" if (mixed and p.filled and not monochrome) else "currentColor"
            else:
                paint = line = p.color
            stroke = f' stroke="{line}"'
        else:
            paint = _paint(p.color, mixed)
            stroke = f' stroke="{paint}"' if paint != "currentColor" else ""
        fill = paint if p.filled else "none"
        attrs = f' fill="{fill}"{stroke}'
        if p.kind == "hatch":
            attrs += ' fill-opacity="0.35"'
        if p.kind == "line":
            parts.append(f'<path d="M{_pt(d["start"])} L{_pt(d["end"])}"{stroke}/>')
        elif p.kind == "arc":
            if d.get("full"):
                cx, cy = d["center"]
                parts.append(f'<circle cx="{cx * MM:.4f}" cy="{-cy * MM:.4f}" '
                             f'r="{d["radius"] * MM:.4f}"{attrs}/>')
            else:
                parts.append(f'<path d="{_path(sample_arc(d), False)}"{attrs}/>')
        elif p.kind == "ellipse_arc":
            closed = abs(abs(d["sweep"]) - 2 * math.pi) < 1e-6
            parts.append(f'<path d="{_path(sample_ellipse(d), closed)}"{attrs}/>')
        elif p.kind in ("polygon", "hatch"):
            parts.append(f'<path d="{_path(flex_points(d), True)}"{attrs}/>')
        elif p.kind == "polyline":
            parts.append(f'<path d="{_path(flex_points(d), False)}"{attrs}/>')
        elif p.kind == "spline":
            parts.append(f'<path d="{_path(sample_spline(d), False)}"{stroke}/>')
        elif p.kind == "text":
            x, y = d["position"]
            size = d["height"] * MM
            rot = -d["rotation"]
            parts.append(
                f'<text x="{x * MM:.4f}" y="{-y * MM:.4f}" font-size="{size:.3f}" '
                f'font-family="Arial, sans-serif" stroke="none" fill="{paint}" '
                f'transform="rotate({rot:.3f} {x * MM:.4f} {-y * MM:.4f})">'
                f'{html.escape(d["text"])}</text>')
    if show_points:
        r = max(w, h) * 0.025
        for name, v in geo.points.items():
            color = "#d9480f" if name.startswith("NP") else "#1971c2"
            parts.append(f'<circle cx="{v[0] * MM:.4f}" cy="{-v[1] * MM:.4f}" r="{r:.4f}" '
                         f'fill="{color}" stroke="none"><title>{html.escape(name)}</title></circle>')
    title_tag = f"<title>{html.escape(title)}</title>" if title else ""
    size_attr = f'width="{size_px}" height="{size_px}" ' if size_px else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" {size_attr}'
        f'viewBox="{x0 * MM:.4f} {-y1 * MM:.4f} {w:.4f} {h:.4f}" '
        f'preserveAspectRatio="xMidYMid meet">{title_tag}'
        f'<g fill="none" stroke="currentColor" stroke-width="{stroke_mm:.3f}" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        + "".join(parts) + "</g></svg>"
    )
