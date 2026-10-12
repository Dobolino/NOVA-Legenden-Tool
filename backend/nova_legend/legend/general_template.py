"""The general part as an editable template: the server drawing with the changes of the
settings built in.

Texts changed in the settings replace the text in the drawing, hidden rows are removed,
rows keep the chosen order (each row moves as a whole: symbol, leaders, notes and text)
and rows added from the symbol library are drawn with the Nova symbol. The helper grid
NL_RASTER marks every row and three free rows at the end. The result can be edited in
Nova or AutoCAD and put back on the server as the new template.
"""

from __future__ import annotations

import ezdxf

from .general import RASTER_LAYER, GeneralPart, strip_raster

FREE_ROWS = 3


def build_template(raw: GeneralPart, final: GeneralPart, geometry_for):
    """``raw``: the drawing as read; ``final``: with the company's changes (apply_overrides).
    ``geometry_for(symbol_key)`` gives the SymbolGeometry of a library row. Returns an
    ezdxf document."""
    from ..render.svg import geometry_bounds
    from .export import _symbol_block

    doc = ezdxf.readfile(raw.dxf_path)
    strip_raster(doc)
    msp = doc.modelspace()
    db = doc.entitydb
    to_mm = raw.to_mm or 1.0
    drawn = {r["id"]: r for r in raw.rows if "y" in r}
    ys = sorted((r["y"] for r in drawn.values()), reverse=True)
    if len(ys) < 2:
        return doc
    steps = sorted(a - b for a, b in zip(ys, ys[1:]) if a - b > 1e-9)
    pitch = steps[len(steps) // 2] if steps else 1.0
    top = ys[0]

    def entities(row: dict) -> list:
        handles = list(row.get("all") or []) + ([row["th"]] if row.get("th") else [])
        return [db[h] for h in handles if h in db]

    kept = {r["id"] for r in final.rows}
    for rid, row in drawn.items():
        if rid not in kept:
            for e in entities(row):
                msp.delete_entity(e)

    sample = next((db[r["th"]] for r in drawn.values() if not r.get("heading") and r.get("th") in db), None)
    text_x = raw.text_x
    symbol_mid = text_x - (raw.symbol_area / to_mm) / 2 if raw.symbol_area else text_x - pitch
    blocks: dict = {}
    slots: list[float] = []
    for k, row in enumerate(final.rows):
        y = top - k * pitch
        slots.append(y)
        src = drawn.get(row["id"])
        if src is not None:
            dy = y - src["y"]
            for e in entities(src):
                if abs(dy) > 1e-9:
                    e.translate(0, dy, 0)
            text_entity = db.get(src.get("th")) if src.get("th") else None
            if text_entity is not None and row["text"] != src["text"]:
                _set_text(text_entity, row["text"])
            continue
        # a row from the symbol library: text like the other rows, symbol in the symbol column
        height = float(sample.dxf.height) if sample is not None and sample.dxftype() == "TEXT" else 2.5 / to_mm
        attribs = {"height": height, "insert": (text_x, y - height * 0.36)}
        if sample is not None:
            for key in ("layer", "style", "color"):
                if sample.dxf.hasattr(key):
                    attribs[key] = sample.dxf.get(key)
        msp.add_text(row["text"], dxfattribs=attribs)
        geo = geometry_for(row.get("symbol_key") or "")
        if geo is None or not geo.primitives:
            continue
        prim = {"key": row["symbol_key"], "length_mm": None, "width_mm": None, "hatch_off": False,
                "fill_off": False, "flat": False, "color": "#000000"}
        name = _symbol_block(doc, blocks, prim, geo)
        x0, y0, x1, y1 = geometry_bounds(geo)
        w, h = (x1 - x0) * 1000, (y1 - y0) * 1000
        s = pitch * 0.75 / max(w, h, 1e-6)
        bcx, bcy = (x0 + x1) / 2 * 1000, (y0 + y1) / 2 * 1000
        msp.add_blockref(name, (symbol_mid - bcx * s, y - bcy * s),
                         dxfattribs={"xscale": s, "yscale": s, "layer": sample.dxf.layer if sample is not None else "0"})
    _add_raster(doc, slots, pitch, raw, to_mm)
    return doc


def _set_text(entity, text: str) -> None:
    if entity.dxftype() == "MTEXT":
        entity.text = text
    else:
        entity.dxf.text = text


def _add_raster(doc, slots: list[float], pitch: float, raw: GeneralPart, to_mm: float) -> None:
    if RASTER_LAYER not in doc.layers:
        layer = doc.layers.add(RASTER_LAYER, color=9)
        layer.dxf.plot = 0
        layer.description = "Hilfsraster NOVA-Legenden: wird nicht gedruckt und nicht exportiert"
    msp = doc.modelspace()
    left = raw.ext_min[0] - 2 / to_mm
    right = raw.ext_max[0] + 2 / to_mm
    last = slots[-1] if slots else 0.0
    lines = [slots[0] + pitch / 2] + [y - pitch / 2 for y in slots]
    lines += [last - pitch / 2 - k * pitch for k in range(1, FREE_ROWS + 1)]
    for y in lines:
        msp.add_line((left, y), (right, y), dxfattribs={"layer": RASTER_LAYER})
    for x in (left, raw.text_x - 1 / to_mm, right):
        msp.add_line((x, lines[0]), (x, lines[-1]), dxfattribs={"layer": RASTER_LAYER})
    th = 2.5 / to_mm
    msp.add_mtext("Hilfsraster (Ebene NL_RASTER): Symbol links, Text rechts der Linie, beides zwischen denselben "
                  "zwei waagrechten Linien. Neue Zeilen unten in die freien Felder. Die Ebene wird nicht "
                  "gedruckt und nicht exportiert.",
                  dxfattribs={"layer": RASTER_LAYER, "char_height": th, "width": right - left,
                              "insert": (left, lines[0] + th * 9)})
