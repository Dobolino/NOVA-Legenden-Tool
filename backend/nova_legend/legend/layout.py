"""Place a legend document on its fixed grid.

One source of truth for the editor view and the DXF export. Output is a list
of drawing primitives in millimetres, x to the right, y downwards, on a sheet
of at most 200 mm width:

    rect      x, y, w, h, fill, stroke, role (header / background / border / general)
    text      x, y (baseline), size, text, bold, color
    symbol    id, key, family_key, length_mm, width_mm, cx, cy, scale, rot, w, h, layer
    line      x1, y1, x2, y2, color, style
    half      cx, cy, r, color            (AP note: half filled circle)
    hit       kind (item / block / section / general), block, id, x, y, w, h

Rules: sections span the full width with a coloured header bar; the area
behind the entries is paper unless the section switches a background on.
Entries fill 2 or 3 columns top to bottom. In every column of a section all
symbol centres sit on one vertical axis and all texts start on one vertical
text line right of the widest symbol. Symbol and text of a row share the same
horizontal middle. Text wraps inside its column; a row grows with its text or
symbol, so nothing overlaps the next entry or column. Symbols turn in steps of
90 degrees around their centre; texts stay horizontal.
"""

from __future__ import annotations

import math

LINE_FACTOR = 1.3            # line height relative to the text size
_NARROW = set("il.,;:|!'`Iíìj()[]/\\ ")
_WIDE = set("MWmw@%")


def text_width(text: str, size: float, bold: bool = False) -> float:
    """Approximate Arial width in mm."""
    w = 0.0
    for ch in text:
        if ch in _NARROW:
            w += 0.28
        elif ch in _WIDE:
            w += 0.83
        elif ch.isupper() or ch.isdigit():
            w += 0.64 if ch.isupper() else 0.56
        else:
            w += 0.52
    return w * size * (1.07 if bold else 1.0)


def wrap(text: str, size: float, width: float, bold: bool = False) -> list[str]:
    """Split a text into lines that fit ``width``. Long words are cut."""
    if width <= size:
        width = size
    lines: list[str] = []
    for para in (text or "").split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for word in words:
            cand = f"{cur} {word}" if cur else word
            if text_width(cand, size, bold) <= width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            cur = word
            while text_width(cur, size, bold) > width and len(cur) > 1:
                cut = len(cur)
                while cut > 1 and text_width(cur[:cut], size, bold) > width:
                    cut -= 1
                lines.append(cur[:cut])
                cur = cur[cut:]
        lines.append(cur)
    return lines or [""]


def symbol_scale(size: tuple[float, float] | None, style: dict, engine: bool) -> float:
    """Common scale, limited so a symbol fits its row height and symbol cell.
    ``size`` is the drawing size at scale 1 as it stands on the sheet (after turning)."""
    s = style["symbol_scale"] * (50.0 / style["plan_scale"] if engine else 1.0)
    if not size or size[0] <= 0 or size[1] <= 0:
        return s
    w, h = size
    max_h = style["row"] * 1.25
    max_w = (style["text_offset"] - 1.2) * 2 if not engine else style["text_offset"] * 4
    return round(min(s, max_h / h, max_w / w), 4)


def _turned(size, rotation: int):
    if size and rotation in (90, 270):
        return (size[1], size[0], size[2])
    return size


def _symbol_box(item: dict, size, style: dict) -> tuple[float, float, float]:
    """(width, height, scale) of the symbol cell of an entry on the sheet."""
    kind = item["kind"]
    if kind == "symbol":
        size = _turned(size, item.get("rotation", 0))
        if size:
            scale = symbol_scale((size[0], size[1]), style, bool(size[2]))
            return size[0] * scale, size[1] * scale, scale
        side = 5.0 * style["symbol_scale"]
        return side, side, 1.0
    if kind == "line":
        return min(item["line_length"], style["text_offset"] * 2 - 2.4), 1.0, 1.0
    if kind == "note":
        return 3.6, 3.6, 1.0
    return 0.0, 0.0, 1.0


def layout(doc: dict, sizes: dict | None = None, general: dict | None = None,
           only_block: str | None = None, include_general: bool = True) -> dict:
    """Place everything. ``sizes`` maps an item id to (width, height, engine) of its drawing
    at scale 1. ``general`` is {"w", "h"} of the locked part in mm (already fitted)."""
    sizes = sizes or {}
    style = doc["style"]
    ts = style["text_size"]
    row = style["row"]
    margin = style["margin"]
    gap = max(0.0, float(style.get("section_gap") or 0.0))
    width = min(style["width"], 200.0)
    inner = width - 2 * margin
    cols = 3 if style["columns"] >= 3 else 2
    prims: list[dict] = []
    y = margin

    if general and include_general and general.get("h"):
        gw, gh = min(general["w"], inner), general["h"]
        prims.append({"t": "rect", "x": margin, "y": y, "w": gw, "h": gh, "fill": None, "stroke": None,
                      "role": "general"})
        prims.append({"t": "hit", "kind": "general", "block": None, "id": "general",
                      "x": margin, "y": y, "w": gw, "h": gh})
        y += gh + row

    title = doc.get("title") or {}
    text = str(title.get("text", "")).strip()
    if text and not only_block:
        tts = ts * float(title.get("scale") or 1.0)
        for line in wrap(text, tts, inner, True):
            prims.append({"t": "text", "x": margin, "y": y + tts, "size": tts, "text": line, "bold": True,
                          "color": "#000000"})
            y += tts * LINE_FACTOR
        y += row * 0.5

    first = True
    for block in doc["blocks"]:
        if only_block and block["id"] != only_block:
            continue
        if not first:
            y += gap
        first = False
        y = _block(block, style, sizes, prims, margin, y, inner, cols, ts, row)

    height = math.ceil((y + margin) * 10) / 10
    return {"width": width, "height": max(height, 2 * margin + row), "prims": prims}


def _block(block, style, sizes, prims, x0, y, inner, cols, ts, row) -> float:
    st = block["style"]
    pad = st["padding"]
    off = style["text_offset"]
    hts = ts * float(block.get("title_scale") or 1.0)
    head_h = max(hts * LINE_FACTOR + 1.6, hts * 2.0)
    top = y
    body: list[dict] = []
    colw = (inner - 2 * pad) / cols
    items = [it for it in block["items"] if not it.get("hidden")]
    boxes = {it["id"]: _symbol_box(it, sizes.get(it["id"]), style) for it in items}
    # one symbol axis and one text line for the section
    widest = max((boxes[it["id"]][0] for it in items), default=0.0)
    axis = max(off * 0.4, widest / 2 + 0.3)
    text_x = max(off, axis + widest / 2 + 1.2)
    per_col = math.ceil(len(items) / cols) if items else 0
    col_heights = []
    for c in range(cols):
        cx0 = x0 + pad + c * colw
        cy = top + head_h + pad
        for item in items[c * per_col:(c + 1) * per_col]:
            cy += _entry(item, boxes[item["id"]], body, block, cx0, cy, colw, ts, row, axis, text_x, st)
        col_heights.append(cy - (top + head_h + pad))
    body_h = max(col_heights or [0.0]) if items else row
    total_h = head_h + pad + body_h + pad
    if st.get("background_on"):
        prims.append({"t": "rect", "x": x0, "y": top, "w": inner, "h": total_h, "fill": st["background"],
                      "stroke": None, "role": "background", "block": block["id"]})
    prims.append({"t": "hit", "kind": "section", "block": block["id"], "id": block["id"],
                  "x": x0, "y": top, "w": inner, "h": total_h})
    prims.append({"t": "rect", "x": x0, "y": top, "w": inner, "h": head_h, "fill": st["header"],
                  "stroke": None, "role": "header", "block": block["id"]})
    title_lines = wrap(block["title"] or "", hts, inner - 2 * pad - 1, True)[:1]
    prims.append({"t": "text", "x": x0 + pad + 0.5, "y": top + head_h / 2 + hts * 0.36, "size": hts,
                  "text": title_lines[0], "bold": True, "color": st["header_text"]})
    prims.extend(body)
    if st["border_on"]:
        prims.append({"t": "rect", "x": x0, "y": top, "w": inner, "h": total_h, "fill": None,
                      "stroke": st["border"], "role": "border", "block": block["id"]})
    prims.append({"t": "hit", "kind": "block", "block": block["id"], "id": block["id"],
                  "x": x0, "y": top, "w": inner, "h": head_h})
    return top + total_h


def _entry(item, box, out, block, cx0, cy, colw, ts, row, axis, text_x, st) -> float:
    """Draw one entry at the top of its slot, return the slot height."""
    kind = item["kind"]
    sym_w, sym_h, scale = box
    its = ts * float(item.get("text_scale") or 1.0)
    lh = its * LINE_FACTOR
    tx = cx0 + text_x
    lines = wrap(item["text"], its, cx0 + colw - tx - 0.8)
    text_h = len(lines) * lh
    h = max(row, text_h + max(0.0, row - ts * LINE_FACTOR), sym_h + 0.8)
    mid = cy + h / 2
    sx = cx0 + axis
    if kind == "symbol":
        out.append({"t": "symbol", "id": item["id"], "key": item["symbol_key"], "family_key": item["family_key"],
                    "length_mm": item["length_mm"], "width_mm": item["width_mm"],
                    "cx": round(sx, 3), "cy": round(mid, 3), "scale": scale, "rot": item.get("rotation", 0),
                    "w": round(sym_w, 3), "h": round(sym_h, 3), "layer": block.get("layer") or ""})
    elif kind == "line":
        out.append({"t": "line", "x1": round(sx - sym_w / 2, 3), "x2": round(sx + sym_w / 2, 3),
                    "y1": round(mid, 3), "y2": round(mid, 3), "color": st["symbol"], "style": item["line_style"],
                    "layer": block.get("layer") or ""})
    elif kind == "note":
        out.append({"t": "half", "cx": round(sx, 3), "cy": round(mid, 3), "r": 1.8, "color": st["symbol"]})
    # baseline so the middle of the text block sits on the middle of the row
    base = mid - (len(lines) - 1) * lh / 2 + its * 0.32
    for i, line in enumerate(lines):
        out.append({"t": "text", "x": round(tx, 3), "y": round(base + i * lh, 3), "size": round(its, 3),
                    "text": line, "bold": False, "color": st["text"], "item": item["id"]})
    out.append({"t": "hit", "kind": "item", "block": block["id"], "id": item["id"],
                "x": cx0, "y": cy, "w": colw, "h": h})
    return h
