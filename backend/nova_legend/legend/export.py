"""Write a placed legend as DXF (R2013, AC1027) and, with the ODA converter, as DWG.

Colours are true colours: header bar, background, border, lines and texts.
Every symbol becomes a block whose entities keep the colours of the Nova
drawing (black where the symbol has no own colour); the section colour does
not recolour symbols. Layers: symbols and
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
from ..render.svg import geometry_bounds, is_mixed, is_soft, own_paint
from .general import GeneralPart
from .model import tint

LINETYPES = {"solid": "CONTINUOUS", "dashed": "DASHED", "dotted": "DOT", "dashdot": "DASHDOT"}
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
                ln = msp.add_line((p["x1"] + dx, Y(p["y1"] + dy)), (p["x2"] + dx, Y(p["y2"] + dy)), dxfattribs={
                    "layer": _layer(doc, p.get("layer") or FRAME_LAYER), "linetype": LINETYPES.get(p["style"], "CONTINUOUS"),
                    "ltscale": 0.25, "lineweight": 35})
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
    for p in grows:
        r = rows.get(p["row"])
        if not r or r["id"] not in names:
            continue
        s = general.to_mm * p["k"]
        x0, y0 = r["src"][0], r["src"][1]
        msp.add_blockref(names[r["id"]], (round(p["x"] - x0 * s, 4), round(Y(p["y"] + p["h"]) - y0 * s, 4)),
                         dxfattribs={"xscale": s, "yscale": s, "layer": _layer(doc, FRAME_LAYER)})


def _symbol_block(doc, cache: dict, prim: dict, geo) -> str:
    layer_color = prim.get("color") or "#000000"
    key = (f"{prim['key']}|{prim.get('length_mm') or ''}|{prim.get('width_mm') or ''}|"
           f"{int(bool(prim.get('hatch_off')))}{int(bool(prim.get('fill_off')))}|{layer_color}")
    if key in cache:
        return cache[key]
    base = re.sub(r"[^A-Za-z0-9_\-]", "_", str(prim["key"]))[:60] or "Symbol"
    name = f"{base}_{len(cache) + 1}"
    blk = doc.blocks.new(name)
    mixed = is_mixed(geo)

    def colored(entity, color: str):
        entity.rgb = _rgb(color)
        return entity

    for p in geo.primitives:
        d = p.data
        pts: list = []
        closed = False
        line = own_paint(p.color, mixed, False, layer_color)
        fill = own_paint(p.color, mixed, True, layer_color)
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
