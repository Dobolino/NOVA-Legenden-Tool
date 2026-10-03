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
    grid      block, x, y, w, h, row, cols, colw, axis, text   (placeholders of a section body)

Rules: sections span the full width with a coloured header bar; the area
behind the entries is paper unless the section switches a background on.
Entries fill 2 or 3 columns top to bottom. In every column of a section all
symbol centres sit on one vertical axis and all texts start on one vertical
text line right of the widest symbol. Every entry takes a whole number of grid
rows, so the entries sit exactly in the grid placeholders of their section.
Symbol and text of a row share the same
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


SYMBOL_CLEARANCE = 0.5       # mm free above and below a symbol inside its grid rows
TEXT_CLEARANCE = 0.4
TILE_FACTOR = 3.6            # symbol tile side = text size × this × symbol scale


def symbol_tile(style: dict) -> float:
    """Side of the shared symbol tile in mm. It grows with the text size."""
    ts = max(float(style.get("text_size") or 2.5), 1.0)
    sc = max(float(style.get("symbol_scale") or 1.0), 0.2)
    return round(ts * TILE_FACTOR * sc, 3)


def entry_slot(style: dict, tile: float) -> float:
    """Row height. The tile sets it; a chosen line count can make every row taller."""
    cap = _line_cap(style)
    if not cap:
        return tile
    ts = float(style.get("text_size") or 2.5)
    return max(tile, cap * ts * LINE_FACTOR + TEXT_CLEARANCE)


def _anchor(size) -> tuple[float, float, float, float, float, float, bool]:
    """(x0, y0, x1, y1, ax, ay, engine) of a drawing in mm, Nova axes (y up).

    Horizontally the anchor is the insertion point (origin of the symbol) when it
    lies in the middle half of the drawing, otherwise the middle of the drawing
    (lines and some boxes have it at one end). Vertically it is always the middle,
    so the drawing fills its row. Old callers give only
    (width, height, engine): then the drawing is centred on its insertion point.
    """
    if len(size) == 3:
        w, h, engine = size
        return -w / 2, -h / 2, w / 2, h / 2, 0.0, 0.0, bool(engine)
    x0, y0, x1, y1, engine = size
    quarter = (x1 - x0) / 4
    ax = 0.0 if x0 + quarter - 1e-6 <= 0 <= x1 - quarter + 1e-6 else (x0 + x1) / 2
    ay = (y0 + y1) / 2          # vertically the drawing sits on the middle of its row
    return x0, y0, x1, y1, ax, ay, bool(engine)


def _symbol_box(item: dict, size, style: dict, tile: float) -> dict:
    """Fit one drawing into the shared tile. The longer side fills the tile, the other
    side keeps its proportion, and the drawing is centred in the tile."""
    kind = item["kind"]

    def box(left, right, up, down, scale=1.0, ax=0.0, ay=0.0):
        return {"left": left, "right": right, "up": up, "down": down, "scale": scale, "ax": ax, "ay": ay}

    if kind == "symbol":
        rot = int(item.get("rotation") or 0)
        factor = float(item.get("symbol_factor") or 1.0)
        if size:
            x0, y0, x1, y1, _ax, _ay, _engine = _anchor(size)
            span, tall = x1 - x0, y1 - y0
            if rot in (90, 270):
                span, tall = tall, span
            longest = max(span, tall, 1e-6)
            scale = tile / longest * factor
            return box(span * scale / 2, span * scale / 2, tall * scale / 2, tall * scale / 2,
                       round(scale, 4), (x0 + x1) / 2, (y0 + y1) / 2)
        half = tile / 2 * factor
        return box(half, half, half, half, round(factor, 4))
    if kind == "line":
        return box(tile / 2, tile / 2, 0.35, 0.35)
    if kind == "note":
        return box(tile / 2, tile / 2, tile / 2, tile / 2)
    return box(0.0, 0.0, 0.0, 0.0)


def layout(doc: dict, sizes: dict | None = None, general: dict | None = None,
           only_block: str | None = None, include_general: bool = True) -> dict:
    """Place everything. ``sizes`` maps an item id to (x0, y0, x1, y1, engine) of its
    drawing in mm at scale 1 around its insertion point (or the older (width, height, engine)). ``general`` is {"w", "h"} of the locked part in mm (already fitted)."""
    sizes = sizes or {}
    style = doc["style"]
    ts = style["text_size"]
    row = style["row"]
    margin = style["margin"]
    gap = max(0.0, float(style.get("section_gap") or 0.0))
    width = max(80.0, min(style["width"], 210.0))
    inner = width - 2 * margin
    cols = 3 if style["columns"] >= 3 else 2
    prims: list[dict] = []
    y = margin

    if general and include_general and general.get("h"):
        # the general part shrinks with a narrower sheet, keeping its proportions
        fit = min(1.0, inner / general["w"]) if general.get("w") else 1.0
        gw, gh = general["w"] * fit, general["h"] * fit
        prims.append({"t": "rect", "x": margin, "y": y, "w": gw, "h": gh, "fill": None, "stroke": None,
                      "role": "general", "fit": round(fit, 5)})
        prims.append({"t": "hit", "kind": "general", "block": None, "id": "general",
                      "x": margin, "y": y, "w": gw, "h": gh})
        y += gh + row

    title = doc.get("title") or {}
    text = str(title.get("text", "")).strip()
    if text and not only_block:
        own = float(title.get("size_mm") or 0)
        tts = own if own > 0 else ts * float(title.get("scale") or 1.0)
        framed = bool(title.get("border_on"))
        pad = 1.5 if framed else 0.0          # room between the title and its border
        top = y
        y += pad
        for line in wrap(text, tts, inner - 2 * pad, True):
            prims.append({"t": "text", "x": margin + pad, "y": y + tts, "size": tts, "text": line, "bold": True,
                          "color": title.get("color") or "#000000",
                          "font": title.get("font") or style.get("font") or "Arial"})
            y += tts * LINE_FACTOR
        y += pad
        if framed:
            prims.append({"t": "rect", "x": margin, "y": top, "w": inner, "h": y - top, "fill": None,
                          "stroke": title.get("border") or "#000000", "role": "border", "block": "title"})
        prims.append({"t": "hit", "kind": "title", "block": None, "id": "title",
                      "x": margin, "y": top, "w": inner, "h": y - top})
        y += row * 0.5

    first = True
    for block in doc["blocks"]:
        if only_block and block["id"] != only_block:
            continue
        if not first:
            y += gap
        first = False
        y = _block(block, style, sizes, prims, margin, y, inner, cols, ts, row)

    height = max(math.ceil((y + margin) * 10) / 10, 2 * margin + row)
    if style.get("frame_on"):
        # border round the whole legend, in the middle of the margin
        prims.append({"t": "rect", "x": margin / 2, "y": margin / 2, "w": width - margin, "h": height - margin,
                      "fill": None, "stroke": style.get("frame") or "#000000", "role": "border", "block": "frame"})
    return {"width": width, "height": height, "prims": prims}


def _block(block, style, sizes, prims, x0, y, inner, cols, ts, row) -> float:
    st = block["style"]
    pad = st["padding"]
    hts = ts * float(block.get("title_scale") or 1.0)
    head_h = max(hts * LINE_FACTOR + 1.6, hts * 2.0)
    top = y
    body: list[dict] = []
    colw = (inner - 2 * pad) / cols
    items = [it for it in block["items"] if not it.get("hidden")]
    tile = min(symbol_tile(style), colw * 0.46)
    boxes = {it["id"]: _symbol_box(it, sizes.get(it["id"]), style, tile) for it in items}
    cap = _line_cap(style)
    gap_mm = max(0.0, float(style.get("entry_gap") or 0.0))
    fixed = entry_slot(style, tile)
    # one tile centre and one text start for the whole section
    axis = tile / 2 + 0.4
    text_x = axis + tile / 2 + 1.5
    per_col = math.ceil(len(items) / cols) if items else 0
    col_heights = []
    for c in range(cols):
        cx0 = x0 + pad + c * colw
        cy = top + head_h + pad
        chunk = items[c * per_col:(c + 1) * per_col]
        for i, item in enumerate(chunk):
            cy += _entry(item, boxes[item["id"]], body, block, cx0, cy, colw, ts, row, axis, text_x, st,
                         fixed, cap, bool(style.get("strip_fill")))
            if gap_mm and i < len(chunk) - 1:
                cy += gap_mm
        col_heights.append(cy - (top + head_h + pad))
    body_h = max(col_heights or [0.0]) if items else row
    total_h = head_h + pad + body_h + pad
    prims.append({"t": "grid", "block": block["id"], "x": x0 + pad, "y": top + head_h + pad,
                  "w": inner - 2 * pad, "h": body_h, "row": fixed + gap_mm, "cols": cols, "colw": colw,
                  "axis": axis, "text": text_x})
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


def _line_cap(style: dict) -> int:
    """1–3 reserves that many text lines and one row height. 0 keeps the automatic height."""
    try:
        n = int(style.get("text_lines") or 0)
    except (TypeError, ValueError):
        return 0
    return n if n in (1, 2, 3) else 0


def _entry(item, box, out, block, cx0, cy, colw, ts, row, axis, text_x, st,
           fixed_h: float | None = None, lines_n: int = 0, strip_fill: bool = False) -> float:
    """Draw one entry at the top of its slot, return the slot height."""
    kind = item["kind"]
    its = ts * float(item.get("text_scale") or 1.0)
    lh = its * LINE_FACTOR
    tx = cx0 + text_x
    lines = wrap(item["text"], its, cx0 + colw - tx - 0.8)
    reserve = lines_n if lines_n else 1
    lines = lines[:reserve] or [""]
    h = fixed_h if fixed_h is not None else max(row, reserve * lh)
    mid = cy + h / 2
    sx = cx0 + axis
    w = box["left"] + box["right"]
    if kind == "symbol":
        out.append({"t": "symbol", "id": item["id"], "key": item["symbol_key"], "family_key": item["family_key"],
                    "length_mm": item["length_mm"], "width_mm": item["width_mm"],
                    "cx": round(sx, 3), "cy": round(mid, 3), "scale": box["scale"], "rot": item.get("rotation", 0),
                    "ax": round(box["ax"], 4), "ay": round(box["ay"], 4),
                    "x0": round(sx - box["left"], 3), "y0": round(mid - box["up"], 3),
                    "w": round(w, 3), "h": round(box["up"] + box["down"], 3), "layer": block.get("layer") or "",
                    "strip_fill": strip_fill})
    elif kind == "line":
        out.append({"t": "line", "x1": round(sx - box["left"], 3), "x2": round(sx + box["right"], 3),
                    "y1": round(mid, 3), "y2": round(mid, 3), "color": st["symbol"], "style": item["line_style"],
                    "layer": block.get("layer") or ""})
    elif kind == "note":
        out.append({"t": "half", "cx": round(sx, 3), "cy": round(mid, 3), "r": round(w / 2, 3), "color": st["symbol"]})
    # The first line of every entry shares one baseline. Further lines go downward.
    base = mid - (reserve - 1) * lh / 2 + its * 0.32
    for i, line in enumerate(lines):
        out.append({"t": "text", "x": round(tx, 3), "y": round(base + i * lh, 3), "size": round(its, 3),
                    "text": line, "bold": False, "color": st["text"], "item": item["id"]})
    out.append({"t": "hit", "kind": "item", "block": block["id"], "id": item["id"],
                "x": cx0, "y": cy, "w": colw, "h": h})
    return h
