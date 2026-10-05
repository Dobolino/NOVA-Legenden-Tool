"""Write a placed legend as DXF (R2013, AC1027) and, with the ODA converter, as DWG.

Colours are true colours: header bar, background, border, lines and texts.
Every symbol becomes a block. A symbol without a hue of its own takes the
section colour; a real colour stays, and black lines on a coloured area stay
black. Layers: symbols and
lines on the legend layer of their category, texts on X_Text, frames and bars
on X_Geometrie (layer names of the existing edeco legend).
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..parser.geometry import flex_points, sample_arc, sample_ellipse, sample_spline
from ..render.svg import _hue, geometry_bounds, is_mixed, is_soft, own_paint
from .general import GeneralPart
from .linetypes import (DXF_NAMES, LINE_WEIGHT, PATTERNS, ensure_linetypes, pattern_scale, simplify_linetypes,
                        tune_entities)
from .model import tint

FONT_FILES = {"Arial": "arial.ttf", "Arial Bold": "arialbd.ttf", "Calibri": "calibri.ttf", "Verdana": "verdana.ttf"}
TEXT_LAYER = "X_Text"
CAP_HEIGHT = 0.716           # Arial: capital letter height / font size
FRAME_LAYER = "X_Geometrie"


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _text_style(doc, font: str, bold: bool) -> str:
    font = (font or "Arial").strip() or "Arial"
    name = "Arial Bold" if bold and font == "Arial" else font
    if name not in doc.styles:
        doc.styles.add(name, font=FONT_FILES.get(name, "arial.ttf"))
    return name


def _layer(doc, name: str) -> str:
    name = (name or "0").strip() or "0"
    name = re.sub(r'[<>/\\":;?*|=`]', "_", name)[:120]
    if name not in doc.layers:
        doc.layers.add(name)
    return name


def build_dxf(lay: dict, general: GeneralPart | None, geometry_for, font: str = "Arial"):
    """Return an ezdxf document of the placed legend. ``geometry_for(prim)`` gives the
    SymbolGeometry (metres) of a symbol primitive, or None."""
    import ezdxf

    doc = ezdxf.new("R2013", setup=True, units=4)     # millimetres
    doc.header["$INSUNITS"] = 4
    doc.header["$LTSCALE"] = 1.0
    if "Arial" not in doc.styles:
        doc.styles.add("Arial", font="arial.ttf")
    if "Arial Bold" not in doc.styles:
        doc.styles.add("Arial Bold", font="arialbd.ttf")
    msp = doc.modelspace()
    ensure_linetypes(doc)
    height = lay["height"]
    blocks: dict[str, str] = {}

    def Y(y: float) -> float:
        return round(height - y, 4)

    def draw(prims, dx=0.0, dy=0.0):
        for p in prims:
            t = p["t"]
            if t == "rect":
                if p.get("role") == "general":
                    continue
                pts = [(p["x"] + dx, Y(p["y"] + dy)), (p["x"] + dx + p["w"], Y(p["y"] + dy)),
                       (p["x"] + dx + p["w"], Y(p["y"] + dy + p["h"])), (p["x"] + dx, Y(p["y"] + dy + p["h"]))]
                layer = _layer(doc, FRAME_LAYER)
                if p.get("fill"):
                    h = msp.add_hatch(dxfattribs={"layer": layer})
                    h.rgb = _rgb(p["fill"])
                    h.paths.add_polyline_path(pts, is_closed=True)
                if p.get("stroke"):
                    pl = msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer, "const_width": 0.25})
                    pl.rgb = _rgb(p["stroke"])
            elif t == "text":
                if not p["text"]:
                    continue
                # CAD programs read a text height as the height of capital letters; the
                # layout (and the editor) uses the full font size. Convert, so the DXF text
                # has the same size as in the editor and stays inside its column.
                txt = msp.add_text(p["text"], height=round(p["size"] * CAP_HEIGHT, 4), dxfattribs={
                    "layer": _layer(doc, TEXT_LAYER),
                    "style": _text_style(doc, p.get("font") or font, bool(p.get("bold")))})
                txt.set_placement((p["x"] + dx, Y(p["y"] + dy)))
                txt.rgb = _rgb(p["color"])
            elif t == "line":
                # own line types with patterns in mm, scaled so the type reads on the short sample
                style = p["style"] if p.get("style") in PATTERNS else "solid"
                length = abs(p["x2"] - p["x1"])
                ln = msp.add_line((p["x1"] + dx, Y(p["y1"] + dy)), (p["x2"] + dx, Y(p["y2"] + dy)), dxfattribs={
                    "layer": _layer(doc, p.get("layer") or FRAME_LAYER), "linetype": DXF_NAMES[style],
                    "ltscale": round(pattern_scale(PATTERNS[style], length), 5), "lineweight": int(LINE_WEIGHT * 100)})
                ln.rgb = _rgb(p["color"])
            elif t == "half":
                cx, cy, r = p["cx"] + dx, Y(p["cy"] + dy), p["r"]
                c = msp.add_circle((cx, cy), r, dxfattribs={"layer": _layer(doc, FRAME_LAYER)})
                c.rgb = _rgb(p["color"])
                half = [(cx + r * math.sin(a), cy + r * math.cos(a)) for a in
                        [math.pi * i / 24 for i in range(25)]]
                h = msp.add_hatch(dxfattribs={"layer": _layer(doc, FRAME_LAYER)})
                h.rgb = _rgb(p["color"])
                h.paths.add_polyline_path(half, is_closed=True)
            elif t == "symbol":
                geo = geometry_for(p)
                if geo is None or not geo.primitives:
                    continue
                name = _symbol_block(doc, blocks, p, geo)
                if "ax" in p:          # anchor on the axis: the insertion point of the symbol
                    bcx, bcy = p["ax"], p["ay"]
                else:
                    x0, y0, x1, y1 = geometry_bounds(geo)
                    bcx, bcy = (x0 + x1) / 2 * 1000, (y0 + y1) / 2 * 1000
                s = p["scale"]
                rot = int(p.get("rot") or 0)
                mx = -1.0 if p.get("mirror") else 1.0       # mirrored: negative x scale
                # turn around the anchor: it stays on the axis of the column
                a = math.radians(rot)
                ox = (mx * bcx * math.cos(a) - bcy * math.sin(a)) * s
                oy = (mx * bcx * math.sin(a) + bcy * math.cos(a)) * s
                msp.add_blockref(name, (p["cx"] + dx - ox, Y(p["cy"] + dy) - oy), dxfattribs={
                    "xscale": mx * s, "yscale": s, "rotation": rot, "layer": _layer(doc, p.get("layer") or "0")})

    if general and general.kind == "project":
        g = next((p for p in lay["prims"] if p.get("role") == "general"), None)
        if g:
            draw(_scaled(general.prims, g.get("fit", 1.0)), g["x"], g["y"])
    if general and general.kind == "dxf" and general.rows:
        _import_general_rows(doc, msp, general, [p for p in lay["prims"] if p["t"] == "grow"], Y)
    elif general and general.kind == "dxf":
        g = next((p for p in lay["prims"] if p.get("role") == "general"), None)
        if g:
            _import_general(doc, msp, general, g["x"], Y(g["y"] + g["h"]), g.get("fit", 1.0))
    draw(lay["prims"])
    return doc


def _scaled(prims: list[dict], k: float) -> list[dict]:
    """Primitives of a general part from a template project, shrunk to a narrower sheet."""
    if k == 1.0:
        return prims
    out = []
    for p in prims:
        q = dict(p)
        for key in ("x", "y", "w", "h", "cx", "cy", "x1", "x2", "y1", "y2", "r", "size", "scale"):
            if isinstance(q.get(key), (int, float)):
                q[key] = q[key] * k
        out.append(q)
    return out


def _import_general(doc, msp, general: GeneralPart, x: float, y_bottom: float, fit: float = 1.0) -> None:
    import ezdxf
    from ezdxf.addons import Importer

    src = ezdxf.readfile(general.dxf_path)
    blk = doc.blocks.new("Allgemeinteil")
    imp = Importer(src, doc)
    imp.import_entities(src.modelspace(), target_layout=blk)
    imp.finalize()
    sc = general.scale * fit
    msp.add_blockref("Allgemeinteil", (x - general.ext_min[0] * sc, y_bottom - general.ext_min[1] * sc),
                     dxfattribs={"xscale": sc, "yscale": sc, "layer": _layer(doc, FRAME_LAYER)})


def _import_general_rows(doc, msp, general: GeneralPart, grows: list[dict], Y) -> None:
    """Every row graphic of the general part as its own block, placed where the layout
    put it (the texts are drawn by the layout like all other texts)."""
    import ezdxf
    from ezdxf.addons import Importer

    if not grows:
        return
    src = ezdxf.readfile(general.dxf_path)
    rows = {r["id"]: r for r in general.rows}
    imp = Importer(src, doc)
    names: dict[str, str] = {}
    for p in grows:
        r = rows.get(p["row"])
        if not r or r["id"] in names:
            continue
        name = f"Allgemeinteil_{r['id']}"
        blk = doc.blocks.new(name)
        ents = [src.entitydb[h] for h in r.get("handles", []) if h in src.entitydb]
        imp.import_entities(ents, target_layout=blk)
        names[r["id"]] = name
    imp.finalize()
    # line types of the rows: plain dash patterns, readable at the size the layout gives them
    simplify_linetypes(doc)
    seen: set = set()
    tuned: set = set()
    for p in grows:
        r = rows.get(p["row"])
        if not r or r["id"] not in names:
            continue
        if r["id"] not in tuned:
            blk = doc.blocks.get(names[r["id"]])
            win = _source_window(r, p)
            _clip_block(blk, r["src"], win)
            tune_entities(doc, list(blk), general.to_mm * p["k"], seen)
            tuned.add(r["id"])
        s = general.to_mm * p["k"]
        x0, y0, x1, y1 = _source_window(r, p)
        rot = int(p.get("rot") or 0) % 360
        cmx, cmy = (x0 + x1) / 2, (y0 + y1) / 2
        a = math.radians(rot)
        sx, sy = s * cmx, s * cmy
        rx = sx * math.cos(a) - sy * math.sin(a)
        ry = sx * math.sin(a) + sy * math.cos(a)
        # the centre of the graphic stays in the cell; the block turns around that centre
        ix = p["x"] + p["w"] / 2 - rx
        iy = Y(p["y"] + p["h"] / 2) - ry
        msp.add_blockref(names[r["id"]], (round(ix, 4), round(iy, 4)), dxfattribs={
            "xscale": s, "yscale": s, "rotation": rot, "layer": _layer(doc, FRAME_LAYER)})


def _source_window(row: dict, prim: dict) -> tuple[float, float, float, float]:
    """The part of the row graphic that the layout actually shows, in drawing units.

    A long stroke beside a symbol is cut at the tile. Without full_w the whole
    graphic is shown, which is how a plain line sample is placed."""
    x0, y0, x1, y1 = row["src"]
    full_w = float(prim.get("full_w") or prim.get("w") or 0)
    full_h = float(prim.get("full_h") or prim.get("h") or 0)
    src_w, src_h = x1 - x0, y1 - y0
    if full_w <= 0 or full_h <= 0 or src_w <= 0 or src_h <= 0:
        return x0, y0, x1, y1
    if abs(full_w - float(prim["w"])) < 1e-3 and abs(full_h - float(prim["h"])) < 1e-3:
        return x0, y0, x1, y1
    fx, fy = float(prim.get("fx") or 0), float(prim.get("fy") or 0)
    ww = src_w * (float(prim["w"]) / full_w)
    hh = src_h * (float(prim["h"]) / full_h)
    wx0 = x0 + fx * src_w
    wy0 = y0 + fy * src_h
    return wx0, wy0, wx0 + ww, wy0 + hh


def _clip_seg(a, b, box):
    """Cohen–Sutherland. None when the segment misses the box."""
    x0, y0, x1, y1 = box
    def code(x, y):
        c = 0
        if x < x0:
            c |= 1
        elif x > x1:
            c |= 2
        if y < y0:
            c |= 4
        elif y > y1:
            c |= 8
        return c
    ax, ay = a
    bx, by = b
    ca, cb = code(ax, ay), code(bx, by)
    for _ in range(12):
        if not ca and not cb:
            return (ax, ay), (bx, by)
        if ca & cb:
            return None
        c = ca or cb
        if c & 8:
            t = (y1 - ay) / (by - ay) if by != ay else 0
            x, y = ax + (bx - ax) * t, y1
        elif c & 4:
            t = (y0 - ay) / (by - ay) if by != ay else 0
            x, y = ax + (bx - ax) * t, y0
        elif c & 2:
            t = (x1 - ax) / (bx - ax) if bx != ax else 0
            x, y = x1, ay + (by - ay) * t
        else:
            t = (x0 - ax) / (bx - ax) if bx != ax else 0
            x, y = x0, ay + (by - ay) * t
        if c == ca:
            ax, ay, ca = x, y, code(x, y)
        else:
            bx, by, cb = x, y, code(x, y)
    return None


def _line_segments(entity):
    kind = entity.dxftype()
    if kind == "LINE":
        return [((entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y))]
    if kind == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in entity.get_points("xy")]
        if len(pts) < 2:
            return []
        if entity.closed:
            pts = [*pts, pts[0]]
        return list(zip(pts, pts[1:]))
    return None


def _bbox_hits(entity, box) -> bool:
    from ezdxf import bbox

    ext = bbox.extents([entity], fast=True)
    if not ext.has_data:
        return True
    x0, y0, x1, y1 = box
    return not (ext.extmax.x < x0 or ext.extmin.x > x1 or ext.extmax.y < y0 or ext.extmin.y > y1)


def _replace_with_lines(block, entity, segments):
    attribs = {}
    for key in ("layer", "color", "linetype", "lineweight", "ltscale"):
        if entity.dxf.hasattr(key):
            attribs[key] = entity.dxf.get(key)
    true_color = entity.dxf.true_color if entity.dxf.hasattr("true_color") else None
    block.delete_entity(entity)
    for a, b in segments:
        if abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9:
            continue
        ln = block.add_line(a, b, dxfattribs=attribs)
        if true_color is not None:
            ln.dxf.true_color = true_color


def _clip_one(block, entity, win):
    if entity.dxftype() == "INSERT":
        try:
            kids = list(entity.virtual_entities())
        except Exception:  # noqa: BLE001 - keep the insert when it cannot be opened
            kids = None
        if kids:
            block.delete_entity(entity)
            for kid in kids:
                block.add_entity(kid)
                _clip_one(block, kid, win)
            return
        if not _bbox_hits(entity, win):
            block.delete_entity(entity)
        return
    segs = _line_segments(entity)
    if segs is None:
        if not _bbox_hits(entity, win):
            block.delete_entity(entity)
        return
    clipped = [c for a, b in segs if (c := _clip_seg(a, b, win))]
    if len(clipped) == len(segs) and all(
        abs(a[0] - c[0][0]) < 1e-6 and abs(a[1] - c[0][1]) < 1e-6 and abs(b[0] - c[1][0]) < 1e-6 and abs(b[1] - c[1][1]) < 1e-6
        for (a, b), c in zip(segs, clipped)):
        return
    _replace_with_lines(block, entity, clipped)


def _clip_block(block, src, win) -> None:
    """Drop what the layout crops away, so a long stroke does not run into the text."""
    if not block:
        return
    sx0, sy0, sx1, sy1 = src
    x0, y0, x1, y1 = win
    if x0 <= sx0 + 1e-4 and y0 <= sy0 + 1e-4 and x1 >= sx1 - 1e-4 and y1 >= sy1 - 1e-4:
        return
    for entity in list(block):
        _clip_one(block, entity, win)


def _symbol_block(doc, cache: dict, prim: dict, geo) -> str:
    layer_color = prim.get("color") or "#000000"
    flat = bool(prim.get("flat"))
    key = (f"{prim['key']}|{prim.get('length_mm') or ''}|{prim.get('width_mm') or ''}|"
           f"{int(bool(prim.get('hatch_off')))}{int(bool(prim.get('fill_off')))}{int(flat)}|{layer_color}")
    if key in cache:
        return cache[key]
    base = re.sub(r"[^A-Za-z0-9_\-]", "_", str(prim["key"]))[:60] or "Symbol"
    name = f"{base}_{len(cache) + 1}"
    blk = doc.blocks.new(name)
    mixed = False if flat else is_mixed(geo)
    monochrome = flat or not any(_hue(p.color) for p in geo.primitives)

    def colored(entity, color: str):
        entity.rgb = _rgb(color)
        return entity

    for p in geo.primitives:
        d = p.data
        pts: list = []
        closed = False
        line = own_paint(p.color, mixed, False, layer_color, monochrome)
        fill = own_paint(p.color, mixed, True, layer_color, monochrome)
        if p.kind == "hatch":
            fill = tint(fill, 0.65)       # the preview shows hatches at 35 % opacity
        # a hidden fill: hatches vanish, filled outlines keep their line
        drop_fill = bool(p.filled) and bool(prim.get("hatch_off") if is_soft(p, mixed) else prim.get("fill_off"))
        if drop_fill and p.kind == "hatch":
            continue
        if p.kind == "line":
            colored(blk.add_line(_mm(d["start"]), _mm(d["end"])), line)
            continue
        if p.kind == "arc" and d.get("full"):
            if p.filled and not drop_fill:
                h = colored(blk.add_hatch(), fill)
                h.paths.add_polyline_path([_mm(q) for q in sample_arc(d, 48)], is_closed=True)
            colored(blk.add_circle(_mm(d["center"]), d["radius"] * 1000), line)
            continue
        if p.kind == "arc":
            pts = sample_arc(d)
        elif p.kind == "ellipse_arc":
            pts = sample_ellipse(d)
            closed = abs(abs(d["sweep"]) - 2 * math.pi) < 1e-6
        elif p.kind in ("polygon", "hatch"):
            pts, closed = flex_points(d), True
        elif p.kind == "polyline":
            pts = flex_points(d)
        elif p.kind == "spline":
            pts = sample_spline(d)
        elif p.kind == "text":
            t = blk.add_text(d["text"], height=d["height"] * 1000, rotation=d.get("rotation", 0.0),
                             dxfattribs={"style": "Arial"})
            t.set_placement(_mm(d["position"]))
            colored(t, fill if p.filled else line)
            continue
        if len(pts) < 2:
            continue
        mm = [_mm(q) for q in pts]
        if p.filled and len(mm) >= 3 and not drop_fill:
            h = colored(blk.add_hatch(), fill)
            h.paths.add_polyline_path(mm, is_closed=True)
        colored(blk.add_lwpolyline(mm, close=closed), line)
    cache[key] = name
    return name


def _mm(p) -> tuple[float, float]:
    return round(p[0] * 1000, 4), round(p[1] * 1000, 4)


def dxf_to_dwg(dxf: Path, oda_exe: str | None, out_dir: Path) -> Path:
    """Convert with the ODA File Converter. Same message as the import when it is missing."""
    from ..importer.dwg import ConverterMissing, MISSING_MESSAGE

    if not oda_exe or not Path(oda_exe).exists():
        raise ConverterMissing(MISSING_MESSAGE)
    in_dir = Path(tempfile.mkdtemp(prefix="nl_dxf_in_"))
    try:
        shutil.copy2(dxf, in_dir / dxf.name)
        flags = 0x08000000 if sys.platform == "win32" else 0
        proc = subprocess.run([oda_exe, str(in_dir), str(out_dir), "ACAD2013", "DWG", "0", "1", dxf.name],
                              capture_output=True, timeout=300, creationflags=flags)  # noqa: S603
        target = out_dir / (dxf.stem + ".dwg")
        if not target.exists():
            raise RuntimeError(f"ODA File Converter hat keine DWG-Datei erzeugt (Rückgabewert {proc.returncode}).")
        return target
    finally:
        shutil.rmtree(in_dir, ignore_errors=True)
