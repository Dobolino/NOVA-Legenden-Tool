"""Line types that stay readable at legend size.

A line type is a repeating pattern (dash, gap, dot ...). In a legend the sample
line is short (5 to 12 mm). With the pattern lengths of the CAD templates
(19 to 32 mm) and their small factors, one dash shrinks below half a millimetre
and every type looks like a solid line. The rule here:

* at least ``MIN_PERIODS`` repetitions of the pattern on the sample line, so a
  reader sees the rhythm of the type;
* no dash shorter than ``MIN_DASH`` and no gap shorter than ``MIN_GAP`` mm on
  paper, so dashes, dots and gaps do not merge when printed or zoomed out.

When both cannot be met on a very short line the minimum sizes win: a type
must stay a type, even with fewer repetitions.
"""

from __future__ import annotations

import math

MIN_PERIODS = 2.5
MIN_DASH = 0.8          # mm on paper
MIN_GAP = 0.45          # mm on paper
LINE_WEIGHT = 0.35      # mm, sample lines in the legend

# Patterns of the legend line items, in mm at factor 1 (dash > 0, gap < 0, dot = 0).
PATTERNS: dict[str, list[float]] = {
    "solid": [],
    "dashed": [2.0, -1.0],
    "dotted": [0.0, -0.9],
    "dashdot": [2.0, -0.8, 0.0, -0.8],
}
DXF_NAMES = {"solid": "CONTINUOUS", "dashed": "NL_STRICH", "dotted": "NL_PUNKT", "dashdot": "NL_STRICHPUNKT"}
DESCRIPTIONS = {"dashed": "Strich __ __ __", "dotted": "Punkt . . . .", "dashdot": "Strichpunkt __ . __ ."}


def pattern_scale(pattern: list[float], length: float) -> float:
    """Factor for ``pattern`` on a sample line of ``length`` mm (see module text)."""
    period = sum(abs(v) for v in pattern)
    if not pattern or period <= 0 or length <= 0:
        return 1.0
    scale = length / (MIN_PERIODS * period)
    dashes = [v for v in pattern if v > 0]
    gaps = [-v for v in pattern if v < 0]
    if dashes:
        scale = max(scale, MIN_DASH / min(dashes))
    if gaps:
        scale = max(scale, MIN_GAP / min(gaps))
    return scale


def dash_array(style: str, length: float) -> list[float]:
    """SVG stroke-dasharray in mm for a legend line (empty = solid). A dot is drawn
    as a dash of one line width, as CAD programs plot it."""
    pattern = PATTERNS.get(style) or []
    if not pattern:
        return []
    k = pattern_scale(pattern, length)
    out = []
    for v in pattern:
        out.append(round(abs(v) * k if v != 0 else 0.01, 3))
    if len(out) % 2:
        out.append(out[-1])
    return out


def ensure_linetypes(doc) -> None:
    """The legend line types in a DXF document, with explicit patterns in mm."""
    for style, name in DXF_NAMES.items():
        pattern = PATTERNS[style]
        if not pattern or name in doc.linetypes:
            continue
        total = sum(abs(v) for v in pattern)
        doc.linetypes.add(name, pattern=[total, *pattern], description=DESCRIPTIONS.get(style, name))


def entity_length(entity) -> float:
    """Length of a curve in drawing units (0 when it has none)."""
    try:
        from ezdxf import path

        p = path.make_path(entity)
        pts = list(p.flattening(0.01))
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    except Exception:  # noqa: BLE001 - texts, hatches, points have no line type length
        return 0.0


def linetype_pattern(doc, name: str) -> list[float]:
    """Pattern elements (dash, gap, dot) of a line type of the document, [] for solid."""
    if not name or name.upper() in ("BYLAYER", "BYBLOCK", "CONTINUOUS"):
        return []
    try:
        lt = doc.linetypes.get(name)
    except Exception:  # noqa: BLE001
        return []
    if lt is None:
        return []
    try:
        return [float(v) for code, v in lt.pattern_tags.tags if code == 49]
    except Exception:  # noqa: BLE001 - complex line types: left as they are
        return []


def simplify_linetypes(doc) -> int:
    """Rewrite line types that only look complex (shape flags without a shape or text, as
    some DWG converters write them) as plain dash patterns, so every program draws the
    dashes. Real shape or text line types stay as they are."""
    changed = 0
    for lt in list(doc.linetypes):
        try:
            tags = list(lt.pattern_tags.tags)
        except Exception:  # noqa: BLE001
            continue
        elements = [float(v) for code, v in tags if code == 49]
        if not elements:
            continue
        shapes = [v for code, v in tags if code == 75]
        texts = [v for code, v in tags if code == 9]
        flags = [v for code, v in tags if code == 74]
        if texts or any(int(v) != 0 for v in shapes) or not any(int(v) != 0 for v in flags):
            continue
        total = sum(abs(v) for v in elements)
        try:
            lt.setup_pattern([total, *elements])
            changed += 1
        except Exception:  # noqa: BLE001 - keep the original definition
            continue
    return changed


def tune_entities(doc, entities, paper_scale: float, seen: set | None = None) -> int:
    """Set the line type factor of every patterned curve in ``entities`` (and inside
    their blocks) so it reads well when one drawing unit is ``paper_scale`` mm on
    paper. Returns how many curves were changed. Changes the document in memory."""
    seen = seen if seen is not None else set()
    global_scale = float(doc.header.get("$LTSCALE", 1.0) or 1.0)
    changed = 0
    for e in entities:
        kind = e.dxftype()
        if kind == "INSERT":
            name = e.dxf.name
            if name in seen:
                continue
            seen.add(name)
            try:
                block = doc.blocks.get(name)
            except Exception:  # noqa: BLE001
                block = None
            if block is not None:
                sx = abs(float(e.dxf.get("xscale", 1.0) or 1.0))
                changed += tune_entities(doc, list(block), paper_scale * sx, seen)
            continue
        if kind not in ("LINE", "LWPOLYLINE", "POLYLINE", "SPLINE", "ARC", "CIRCLE", "ELLIPSE"):
            continue
        name = e.dxf.get("linetype", "BYLAYER")
        if name.upper() == "BYLAYER":
            try:
                name = doc.layers.get(e.dxf.layer).dxf.linetype
            except Exception:  # noqa: BLE001
                name = "CONTINUOUS"
        pattern = linetype_pattern(doc, name)
        if not pattern:
            continue
        length_mm = entity_length(e) * paper_scale
        if length_mm <= 0:
            continue
        # factor on paper, then back to the entity factor of this drawing
        factor = pattern_scale(pattern, length_mm) / paper_scale / global_scale
        e.dxf.ltscale = round(factor, 6)
        changed += 1
    return changed
