"""Place a legend document on its fixed grid.

One source of truth for the editor view and the DXF export. Output is a list
of drawing primitives in millimetres, x to the right, y downwards, on a sheet
of at most 200 mm width:

    rect      x, y, w, h, fill, stroke, role (header / background / border / general)
    text      x, y (baseline), size, text, bold, color
    symbol    id, key, family_key, length_mm, width_mm, cx, cy, scale, color, background
    line      x1, y1, x2, y2, color, style
    half      cx, cy, r, color            (AP note: half filled circle)
    hit       kind (item / block / general), block, id, x, y, w, h

Rules: sections span the full width with a coloured header bar. Entries fill
2 or 3 columns top to bottom. Text wraps inside its column; a row grows with
its text or symbol, so nothing overlaps the next entry or column.
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
    """Common scale, limited so a symbol fits its row height and symbol cell."""
    s = style["symbol_scale"] * (50.0 / style["plan_scale"] if engine else 1.0)
    if not size or size[0] <= 0 or size[1] <= 0:
        return s
    w, h = size
    max_h = style["row"] * 1.25
    max_w = (style["text_offset"] - 1.2) * 2 if not engine else style["text_offset"] * 4
    return round(min(s, max_h / h, max_w / w), 4)


def layout(doc: dict, sizes: dict | None = None, general: dict | None = None,
           only_block: str | None = None, include_general: bool = True) -> dict:
    """Place everything. ``sizes`` maps an item id to (width, height, engine) of its drawing
    at scale 1. ``general`` is {"w", "h"} of the locked part in mm (already fitted)."""
    sizes = sizes or {}
    style = doc["style"]
    ts = style["text_size"]
    lh = ts * LINE_FACTOR
    row = style["row"]
    off = style["text_offset"]
    margin = style["margin"]
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

    title = (doc.get("title") or {}).get("text", "").strip()
    if title and not only_block:
        for line in wrap(title, ts, inner, True):
            prims.append({"t": "text", "x": margin, "y": y + ts, "size": ts, "text": line, "bold": True,
                          "color": "#000000"})
            y += lh
        y += row * 0.5

    for block in doc["blocks"]:
        if only_block and block["id"] != only_block:
            continue
        y = _block(block, style, sizes, prims, margin, y, inner, cols, ts, lh, row, off)
        y += row * 0.6

    height = math.ceil((y + margin - row * 0.6) * 10) / 10
    return {"width": width, "height": max(height, 2 * margin + row), "prims": prims}


def _block(block, style, sizes, prims, x0, y, inner, cols, ts, lh, row, off) -> float:
    st = block["style"]
    pad = st["padding"]
    head_h = max(lh + 1.6, ts * 2.0)
    top = y
    body: list[dict] = []
    colw = (inner - 2 * pad) / cols
    items = block["items"]
    per_col = math.ceil(len(items) / cols) if items else 0
    col_heights = []
    for c in range(cols):
        cx0 = x0 + pad + c * colw
        cy = top + head_h + pad
        for item in items[c * per_col:(c + 1) * per_col]:
            cy += _entry(item, style, sizes.get(item["id"]), body, block, cx0, cy, colw, ts, lh, row, off, st)
        col_heights.append(cy - (top + head_h + pad))
    body_h = max(col_heights or [0.0])
    if not items:
        body_h = row
    total_h = head_h + pad + body_h + pad
    prims.append({"t": "rect", "x": x0, "y": top, "w": inner, "h": total_h, "fill": st["background"],
                  "stroke": None, "role": "background", "block": block["id"]})
    prims.append({"t": "rect", "x": x0, "y": top, "w": inner, "h": head_h, "fill": st["header"],
                  "stroke": None, "role": "header", "block": block["id"]})
    title_lines = wrap(block["title"] or "", ts, inner - 2 * pad - 1, True)[:1]
    prims.append({"t": "text", "x": x0 + pad + 0.5, "y": top + head_h / 2 + ts * 0.36, "size": ts,
                  "text": title_lines[0], "bold": True, "color": st["header_text"]})
    prims.extend(body)
    if st["border_on"]:
        prims.append({"t": "rect", "x": x0, "y": top, "w": inner, "h": total_h, "fill": None,
                      "stroke": st["border"], "role": "border", "block": block["id"]})
    prims.append({"t": "hit", "kind": "block", "block": block["id"], "id": block["id"],
                  "x": x0, "y": top, "w": inner, "h": head_h})
    return top + total_h


def _entry(item, style, size, out, block, cx0, cy, colw, ts, lh, row, off, st) -> float:
    """Draw one entry at the top of its slot, return the slot height."""
    kind = item["kind"]
    sym_w = sym_h = 0.0
    scale = 1.0
    if kind == "symbol" and size:
        scale = symbol_scale((size[0], size[1]), style, bool(size[2]))
        sym_w, sym_h = size[0] * scale, size[1] * scale
    elif kind == "symbol":
        sym_w = sym_h = 5.0 * style["symbol_scale"]
    elif kind == "line":
        sym_w = min(item["line_length"], off * 2 - 2.4)
        sym_h = 1.0
    elif kind == "note":
        sym_w = sym_h = 3.6
    if kind == "text":
        tx = cx0 + 0.5
    else:
        tx = cx0 + max(off, sym_w + 1.6)
    text_w = cx0 + colw - tx - 0.8
    lines = wrap(item["text"], ts, text_w)
    h = max(row, len(lines) * lh + (row - lh), sym_h + 0.8)
    mid = cy + h / 2
    sx = cx0 + max(off * 0.4, sym_w / 2 + 0.3) if kind != "text" else 0
    if kind == "symbol":
        out.append({"t": "symbol", "id": item["id"], "key": item["symbol_key"], "family_key": item["family_key"],
                    "length_mm": item["length_mm"], "width_mm": item["width_mm"],
                    "cx": round(sx, 3), "cy": round(mid, 3), "scale": scale, "w": round(sym_w, 3),
                    "h": round(sym_h, 3), "color": st["symbol"], "background": st["background"],
                    "layer": block.get("layer") or ""})
    elif kind == "line":
        out.append({"t": "line", "x1": round(sx - sym_w / 2, 3), "x2": round(sx + sym_w / 2, 3),
                    "y1": round(mid, 3), "y2": round(mid, 3), "color": st["symbol"], "style": item["line_style"]})
    elif kind == "note":
        out.append({"t": "half", "cx": round(sx, 3), "cy": round(mid, 3), "r": 1.8, "color": st["symbol"]})
    first = mid - (len(lines) * lh) / 2 + ts * 0.86
    for i, line in enumerate(lines):
        out.append({"t": "text", "x": round(tx, 3), "y": round(first + i * lh, 3), "size": ts, "text": line,
                    "bold": False, "color": st["text"]})
    out.append({"t": "hit", "kind": "item", "block": block["id"], "id": item["id"],
                "x": cx0, "y": cy, "w": colw, "h": h})
    return h
