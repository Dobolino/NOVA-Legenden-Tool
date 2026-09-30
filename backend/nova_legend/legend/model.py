"""Legend document of a project: blocks (one per category) with entries.

Coordinates are millimetres on paper, x to the right, y downwards (as in the
editor). Block entries are placed relative to the block origin. The defaults
follow the existing edeco legend (Legende_edeco20.n4d): row spacing 4.55 mm,
text 9.75 mm right of the symbol centre, 103.7 mm per legend column.
"""

from __future__ import annotations

import copy
import json
import math
import uuid
from pathlib import Path

DOC_VERSION = 1
AP_NOTE = "Unterscheidung UP / AP (halbausgefüllt)"

DEFAULT_STYLE = {
    "font": "Arial",
    "title_size": 5.0,        # mm text height
    "heading_size": 3.5,
    "text_size": 2.5,
    "row": 4.55,              # default row spacing (a category may set its own)
    "text_offset": 9.75,      # text start right of the symbol centre
    "column_width": 103.7,    # width of one legend column
    "page_columns": 2,
    "page_height": 220.0,     # blocks flow into the next column below this
    "margin": 10.0,
    "grid": 0.5,              # snap grid in the editor
    "plan_scale": 50,         # scale for parametric symbols (luminaires)
}

ITEM_KINDS = ("symbol", "line", "note")
LINE_STYLES = ("solid", "dashed", "dotted", "dashdot")


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def template_texts() -> list[str]:
    """Texts of the existing edeco legend, offered as descriptions."""
    path = Path(__file__).with_name("template_texts.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))["texts"]
    except (OSError, ValueError, KeyError):
        return []


def empty_doc(title: str = "Legende") -> dict:
    return {"version": DOC_VERSION, "style": dict(DEFAULT_STYLE),
            "title": {"text": title, "x": DEFAULT_STYLE["margin"], "y": DEFAULT_STYLE["margin"],
                      "size": DEFAULT_STYLE["title_size"]},
            "blocks": [], "texts": []}


def _num(value, default: float, lo: float | None = None, hi: float | None = None) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    if lo is not None:
        out = max(lo, out)
    if hi is not None:
        out = min(hi, out)
    return out


def normalize(doc: dict | None) -> dict:
    """Clean a document from the client: known fields, sane numbers, ids."""
    base = empty_doc()
    if not isinstance(doc, dict):
        return base
    style = dict(DEFAULT_STYLE)
    for key, default in DEFAULT_STYLE.items():
        value = (doc.get("style") or {}).get(key, default)
        style[key] = value if isinstance(default, str) else _num(value, default, 0)
    style["page_columns"] = int(_num(style["page_columns"], 2, 1, 8))
    style["grid"] = _num(style["grid"], 0.5, 0, 20)
    style["plan_scale"] = _num(style["plan_scale"], 50, 1, 1000)
    title = doc.get("title") or {}
    out = {"version": DOC_VERSION, "style": style,
           "title": {"text": str(title.get("text", base["title"]["text"]))[:200],
                     "x": _num(title.get("x"), style["margin"]), "y": _num(title.get("y"), style["margin"]),
                     "size": _num(title.get("size"), style["title_size"], 0.5, 50)},
           "blocks": [], "texts": []}
    seen: set[str] = set()

    def uid(value) -> str:
        v = str(value or "")[:40] or new_id()
        while v in seen:
            v = new_id()
        seen.add(v)
        return v

    for b in doc.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        block = {"id": uid(b.get("id")), "category_id": b.get("category_id") or None,
                 "title": str(b.get("title", ""))[:200],
                 "x": _num(b.get("x"), 0), "y": _num(b.get("y"), 0),
                 "columns": int(_num(b.get("columns"), 1, 1, 6)),
                 "spacing": _num(b.get("spacing"), style["row"], 1, 50),
                 "heading_size": _num(b.get("heading_size"), style["heading_size"], 0.5, 50),
                 "collapsed": bool(b.get("collapsed")), "items": []}
        for it in b.get("items") or []:
            if not isinstance(it, dict):
                continue
            kind = it.get("kind") if it.get("kind") in ITEM_KINDS else "symbol"
            item = {"id": uid(it.get("id")), "kind": kind,
                    "family_key": it.get("family_key") or None, "symbol_key": it.get("symbol_key") or None,
                    "text": str(it.get("text", ""))[:300],
                    "x": _num(it.get("x"), 0), "y": _num(it.get("y"), 0),
                    "scale": _num(it.get("scale"), 1, 0.05, 20),
                    "text_size": _num(it.get("text_size"), style["text_size"], 0.5, 50),
                    "length_mm": _num(it.get("length_mm"), 0, 0, 100000) or None,
                    "width_mm": _num(it.get("width_mm"), 0, 0, 100000) or None,
                    "line_style": it.get("line_style") if it.get("line_style") in LINE_STYLES else "solid",
                    "line_length": _num(it.get("line_length"), 8, 1, 200)}
            if kind == "symbol" and not item["symbol_key"]:
                continue
            block["items"].append(item)
        out["blocks"].append(block)
    for t in doc.get("texts") or []:
        if isinstance(t, dict) and str(t.get("text", "")).strip():
            out["texts"].append({"id": uid(t.get("id")), "text": str(t["text"])[:300],
                                 "x": _num(t.get("x"), 0), "y": _num(t.get("y"), 0),
                                 "size": _num(t.get("size"), style["text_size"], 0.5, 50)})
    return out


# -- automatic arrangement -----------------------------------------------------

def block_height(block: dict, style: dict) -> float:
    rows = math.ceil(len(block["items"]) / max(1, block["columns"])) if block["items"] else 0
    return block["heading_size"] * 1.8 + rows * block["spacing"]


def auto_layout(doc: dict) -> dict:
    """Place blocks in legend columns and entries in rows (a proposal to edit freely)."""
    doc = copy.deepcopy(doc)
    style = doc["style"]
    margin = style["margin"]
    colw = style["column_width"]
    top = margin + (doc["title"]["size"] * 2.2 if doc["title"]["text"] else 0)
    doc["title"]["x"], doc["title"]["y"] = margin, margin
    col, y = 0, top
    for block in doc["blocks"]:
        h = block_height(block, style)
        if y > top and y + h > style["page_height"]:
            col, y = col + 1, top
        block["x"] = margin + col * colw
        block["y"] = y
        n = max(1, block["columns"])
        rows = math.ceil(len(block["items"]) / n) if block["items"] else 0
        subw = colw / n
        head = block["heading_size"] * 1.8
        for i, item in enumerate(block["items"]):
            c, r = divmod(i, rows) if rows else (0, 0)
            item["x"] = round(c * subw + style["text_offset"] * 0.35, 3)   # symbol centre
            item["y"] = round(head + r * block["spacing"] + block["spacing"] / 2, 3)
        y += h + block["spacing"]
    return doc


# -- symbol size in the row ---------------------------------------------------

def fit_scale(width_mm: float, height_mm: float, spacing: float, text_offset: float) -> float:
    """Shrink large symbols so they fit their row and leave room for the text. Never enlarge."""
    if width_mm <= 0 or height_mm <= 0:
        return 1.0
    limit = min(1.0, spacing * 1.1 / height_mm, (text_offset - 1.5) * 2 / width_mm)
    return max(0.05, math.floor(limit * 20) / 20)


# -- proposal from the project -------------------------------------------------

def propose(rows: list[dict], categories: list[dict], by_category: bool,
            descriptions: dict[str, str], title: str, size_of=None) -> dict:
    """New legend with every apparatus in use, grouped by the first category."""
    doc = empty_doc(title)
    style = doc["style"]
    cats = {c["id"]: c for c in categories}
    order = {c["id"]: i for i, c in enumerate(categories)}
    blocks: dict[str, dict] = {}

    def block_for(cid: str | None) -> dict:
        key = cid if by_category else "_all"
        if key not in blocks:
            cat = cats.get(cid) if by_category else None
            blocks[key] = {"id": new_id(), "category_id": cid if by_category else None,
                           "title": cat["title"] if cat else ("Ohne Kategorie" if by_category else ""),
                           "x": 0, "y": 0, "columns": int(cat.get("columns") or 1) if cat else 1,
                           "spacing": float(cat.get("spacing") or style["row"]) if cat else style["row"],
                           "heading_size": style["heading_size"], "collapsed": False, "items": []}
        return blocks[key]

    has_ap = False
    for row in rows:
        if int(row.get("total") or 0) <= 0 or not row.get("symbol_key"):
            continue
        visible = [c for c in row.get("categories") or [] if c in cats and not cats[c].get("hidden")]
        if row.get("categories") and not visible:
            continue    # only in hidden categories
        cid = visible[0] if visible else None
        has_ap = has_ap or any(m in ("AP", "NAP") for m in (row.get("mountings") or {}))
        block = block_for(cid)
        size = size_of(row["symbol_key"]) if size_of else None
        scale = fit_scale(size[0], size[1], block["spacing"], style["text_offset"]) if size else 1.0
        block["items"].append({
            "id": new_id(), "kind": "symbol", "family_key": row["family_key"],
            "symbol_key": row["symbol_key"],
            "text": descriptions.get(row["family_key"]) or row.get("title") or "",
            "x": 0, "y": 0, "scale": scale, "text_size": style["text_size"],
            "length_mm": None, "width_mm": None, "line_style": "solid", "line_length": 8.0})
    doc["blocks"] = sorted(blocks.values(), key=lambda b: order.get(b["category_id"], 999))
    for b in doc["blocks"]:
        b["columns"] = max(1, min(b["columns"], math.ceil(len(b["items"]) / 3) or 1))
    if has_ap and doc["blocks"]:
        first = next((b for b in doc["blocks"] if b["category_id"] == "allgemein"), doc["blocks"][0])
        first["items"].append({"id": new_id(), "kind": "note", "family_key": None, "symbol_key": None,
                               "text": AP_NOTE, "x": 0, "y": 0, "scale": 1.0,
                               "text_size": style["text_size"], "length_mm": None, "width_mm": None,
                               "line_style": "solid", "line_length": 8.0})
    return auto_layout(doc)
