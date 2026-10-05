"""Legend document of a project (version 2).

The document stores content and style, no free coordinates: sections
(blocks) in order, entries in order. ``layout.py`` places everything on a
fixed grid inside a sheet of at most 200 mm width. The locked general part on
top (Allgemeinteil) is not stored here; it is read fresh from the company
template on every opening.
"""

from __future__ import annotations

import json
import math
import re
import uuid
from pathlib import Path

DOC_VERSION = 4
AP_NOTE = "Unterscheidung UP / AP (halbausgefüllt)"
AP_NOTE_KEY = "hinweis:up-ap"      # key of its company text (table descriptions)
SHEET_WIDTH = 200.0          # mm, including the margin (standard)
MAX_SHEET_WIDTH = 210.0      # widest sheet the user may choose
MIN_SHEET_WIDTH = 80.0
MARGIN = 5.0

# Grid presets. "standard" follows the existing edeco legend.
GRIDS = {
    "standard": {"label": "Standard", "row": 4.55, "text_offset": 9.75},
    "kompakt": {"label": "Kompakt", "row": 4.0, "text_offset": 8.5},
    "weit": {"label": "Weit", "row": 5.0, "text_offset": 10.5},
    "gross": {"label": "Gross", "row": 6.0, "text_offset": 12.0},
}
DEFAULT_TEXT_SIZE = 2.5
DEFAULT_SYMBOL_SCALE = 1.0
DEFAULT_TITLE_MM = 5.0      # legend title height, until a legend sets its own

ITEM_KINDS = ("symbol", "line", "note", "text", "gap")   # gap: an empty cell kept free on purpose
ROTATIONS = (0, 45, 90, 135, 180, 225, 270, 315)
ITEM_EXTRA = {"text_scale": 1.0, "symbol_factor": 1.0, "rotation": 0, "hidden": False, "keep": False,
              "mirror": False}
LINE_STYLES = ("solid", "dashed", "dotted", "dashdot")
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def template_texts() -> list[str]:
    """Texts of the existing edeco legend, offered as descriptions."""
    path = Path(__file__).with_name("template_texts.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))["texts"]
    except (OSError, ValueError, KeyError):
        return []


# -- colours --------------------------------------------------------------------

def _hex(value, default: str) -> str:
    return value if isinstance(value, str) and _HEX.match(value) else default


def _rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def tint(color: str, share: float) -> str:
    """Mix a colour with white (share 0 = colour, 1 = white)."""
    r, g, b = _rgb(color)
    return "#%02x%02x%02x" % tuple(round(c + (255 - c) * share) for c in (r, g, b))


def readable_on(color: str) -> str:
    r, g, b = _rgb(color)
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "#ffffff"


def section_style(color: str | None) -> dict:
    """Default look of a section from the plan colour of its legend layer.

    Only the header bar takes the colour. The area behind the entries stays
    white paper (background off), the border is off, texts are black. Symbols
    keep the colours of their Nova drawing; ``symbol`` only colours lines and
    notes of the section.
    """
    own = _hex(color, "")
    c = own or "#6b7280"
    if c.lower() in ("#ffffff", "#000000"):
        c = "#6b7280" if c.lower() == "#ffffff" else c
    # symbols and lines take the plan colour; without a plan colour they stay black
    symbol = c if own and own.lower() != "#ffffff" else "#000000"
    return {"header": c, "header_text": readable_on(c), "background_on": False, "background": tint(c, 0.9),
            "border_on": False, "border": c, "symbol": symbol, "text": "#000000", "padding": 1.5}


def _section_style(value, fallback: dict) -> dict:
    v = value if isinstance(value, dict) else {}
    return {"header": _hex(v.get("header"), fallback["header"]),
            "header_text": _hex(v.get("header_text"), fallback["header_text"]),
            "background_on": bool(v.get("background_on", fallback["background_on"])),
            "background": _hex(v.get("background"), fallback["background"]),
            "border_on": bool(v.get("border_on", fallback["border_on"])),
            "border": _hex(v.get("border"), fallback["border"]),
            "symbol": _hex(v.get("symbol"), fallback["symbol"]),
            "text": _hex(v.get("text"), fallback["text"]),
            "padding": _num(v.get("padding"), fallback["padding"], 0, 10)}


# -- document -------------------------------------------------------------------

def default_style(text_size: float = DEFAULT_TEXT_SIZE, symbol_scale: float = DEFAULT_SYMBOL_SCALE,
                  columns: int = 2) -> dict:
    grid = GRIDS["standard"]
    return {"font": "Arial", "text_size": text_size, "symbol_scale": symbol_scale,
            "grid": "standard", "row": grid["row"], "text_offset": grid["text_offset"],
            "columns": columns, "width": SHEET_WIDTH, "margin": MARGIN, "plan_scale": 50,
            "section_gap": 0.0, "entry_gap": 0.0, "text_lines": 0,
            "hatch_off": False, "fill_off": False,
            "symbol_size": "tile",
            "frame_on": False, "frame": "#000000"}


def empty_doc(title: str = "", style: dict | None = None) -> dict:
    return {"version": DOC_VERSION, "style": style or default_style(),
            "title": {"text": title, "scale": 1.0, "size_mm": DEFAULT_TITLE_MM, "font": "Arial",
                      "color": "#000000", "border_on": False, "border": "#000000"},
            "blocks": []}


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


def normalize_style(value) -> dict:
    v = value if isinstance(value, dict) else {}
    grid = v.get("grid") if v.get("grid") in GRIDS else "standard"
    style = default_style(_num(v.get("text_size"), DEFAULT_TEXT_SIZE, 1.0, 10.0),
                          _num(v.get("symbol_scale"), DEFAULT_SYMBOL_SCALE, 0.2, 5.0),
                          3 if int(_num(v.get("columns"), 2)) >= 3 else 2)
    style["grid"] = grid
    style["row"] = GRIDS[grid]["row"]
    style["text_offset"] = GRIDS[grid]["text_offset"]
    style["plan_scale"] = _num(v.get("plan_scale"), 50, 1, 1000)
    style["font"] = str(v.get("font") or "Arial")[:40]
    style["section_gap"] = _num(v.get("section_gap"), 0.0, 0, 50)
    style["entry_gap"] = _num(v.get("entry_gap"), 0.0, 0, 20)
    try:
        lines = int(v.get("text_lines") or 0)
    except (TypeError, ValueError):
        lines = 0
    style["text_lines"] = lines if lines in (1, 2, 3) else 0
    # symbol fills, for all symbols: soft (hatches, light areas) and solid separately;
    # "strip_fill" of older legends removed both
    old = bool(v.get("strip_fill"))
    style["hatch_off"] = bool(v.get("hatch_off", old))
    style["fill_off"] = bool(v.get("fill_off", old))
    # "tile" (default): every drawing fills 75 % of one tile sized from the text;
    # "real": every symbol at the common scale, on its insertion point, in grid rows
    style["symbol_size"] = "real" if v.get("symbol_size") == "real" else "tile"
    style["width"] = _num(v.get("width"), SHEET_WIDTH, MIN_SHEET_WIDTH, MAX_SHEET_WIDTH)
    style["frame_on"] = bool(v.get("frame_on"))           # border round the whole legend
    style["frame"] = _hex(v.get("frame"), "#000000")
    return style


def _scale(value) -> float:
    """Text factor of one text: 1 = the common text size."""
    return round(_num(value, 1.0, 0.5, 3.0), 3)


def normalize(doc: dict | None) -> dict:
    """Clean a document from the client or an older version (v1 had free coordinates)."""
    if not isinstance(doc, dict):
        return empty_doc()
    old_style = doc.get("style") or {}
    style = normalize_style(old_style)
    title = doc.get("title") or {}
    old = int(_num(doc.get("version"), 1))
    out = {"version": DOC_VERSION, "style": style,
           "title": {"text": str(title.get("text", ""))[:200], "scale": _scale(title.get("scale")),
                     "size_mm": _num(title.get("size_mm", DEFAULT_TITLE_MM), DEFAULT_TITLE_MM, 0, 20),
                     "font": str(title.get("font") or "Arial")[:40],
                     "color": _hex(title.get("color"), "#000000"),
                     "border_on": bool(title.get("border_on")), "border": _hex(title.get("border"), "#000000")},
           "blocks": []}
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
                 "title": str(b.get("title", ""))[:200], "layer": str(b.get("layer") or "")[:80],
                 "collapsed": bool(b.get("collapsed")), "title_scale": _scale(b.get("title_scale")),
                 "style": _section_style(b.get("style"), section_style(None)), "items": []}
        if old < 3:
            # v2 filled the area and drew the border by default
            block["style"].update(background_on=False, border_on=False)
        if old < 4:
            # v3 drew symbols black; now parts without own colour take the section colour
            head = block["style"]["header"]
            block["style"]["symbol"] = head if head.lower() != "#6b7280" else "#000000"
        for it in b.get("items") or []:
            item = _item(it, uid)
            if item:
                block["items"].append(item)
        out["blocks"].append(block)
    # v1: free texts outside the sections become entries of their own section
    free = [t for t in doc.get("texts") or [] if isinstance(t, dict) and str(t.get("text", "")).strip()]
    if free:
        out["blocks"].append({"id": uid(None), "category_id": None, "title": "Zusatztext", "layer": "",
                              "collapsed": False, "title_scale": 1.0, "style": section_style(None),
                              "items": [_item({"kind": "text", "text": t["text"]}, uid) for t in free]})
    return out


def _rotation(value) -> int:
    r = int(_num(value, 0)) % 360
    return r if r in ROTATIONS else 0


def _item(it, uid) -> dict | None:
    if not isinstance(it, dict):
        return None
    kind = it.get("kind") if it.get("kind") in ITEM_KINDS else "symbol"
    item = {"id": uid(it.get("id")), "kind": kind,
            "family_key": it.get("family_key") or None, "symbol_key": it.get("symbol_key") or None,
            "text": str(it.get("text", ""))[:300],
            "length_mm": _num(it.get("length_mm"), 0, 0, 100000) or None,
            "width_mm": _num(it.get("width_mm"), 0, 0, 100000) or None,
            "line_style": it.get("line_style") if it.get("line_style") in LINE_STYLES else "solid",
            "line_length": _num(it.get("line_length"), 8, 1, 60),
            "text_scale": _scale(it.get("text_scale")),
            # size of this one symbol relative to the common symbol scale
            "symbol_factor": round(_num(it.get("symbol_factor"), 1.0, 0.3, 4.0), 3),
            "rotation": _rotation(it.get("rotation")),
            # hidden: the general part already shows it (hidden, not deleted); keep: shown on purpose
            "hidden": bool(it.get("hidden")), "keep": bool(it.get("keep")),
            "mirror": bool(it.get("mirror"))}       # mirrored left-right before turning
    if kind == "symbol" and not item["symbol_key"]:
        return None
    return item


# -- proposal from the project -------------------------------------------------

def propose(rows: list[dict], categories: list[dict], by_category: bool,
            descriptions: dict[str, str], title: str, style: dict | None = None,
            colors: dict[str, str] | None = None, covered: set[str] | None = None,
            ap_covered: bool = False, layer_categories: dict[str, str] | None = None) -> dict:
    """New legend with every apparatus in use, grouped by the first visible category.

    A symbol that sits on plan layers of two or more categories is entered in
    each of those categories, so each copy keeps that category's layer colour.

    ``covered`` holds the family keys the general part already shows; they are
    left out. ``ap_covered`` leaves out the AP note when the general part has it.

    ``colors`` maps a category id to the plan colour of its legend layer; it
    gives each section its default look.
    """
    style = normalize_style(style)
    doc = empty_doc(title, style)
    colors = colors or {}
    cats = {c["id"]: c for c in categories}
    order = {c["id"]: i for i, c in enumerate(categories)}
    blocks: dict[str, dict] = {}

    def block_for(cid: str | None) -> dict:
        key = cid if by_category else "_all"
        if key not in blocks:
            cat = cats.get(cid) if by_category else None
            blocks[key] = {"id": new_id(), "category_id": cid if by_category else None,
                           "title": cat["title"] if cat else ("Ohne Kategorie" if by_category else "Legende"),
                           "layer": (cat.get("layer") or "") if cat else "", "collapsed": False,
                           "title_scale": 1.0,
                           "style": section_style(colors.get(cid) if cat else None), "items": []}
        return blocks[key]

    has_ap = False
    for row in rows:
        if int(row.get("total") or 0) <= 0 or not row.get("symbol_key"):
            continue
        visible = [c for c in row.get("categories") or [] if c in cats and not cats[c].get("hidden")]
        from_layers: list[str] = []
        for name in row.get("layers") or {}:
            cid = (layer_categories or {}).get(name)
            if cid and cid in cats and not cats[cid].get("hidden") and cid not in from_layers:
                from_layers.append(cid)
        if len(from_layers) >= 2:
            targets: list[str | None] = list(from_layers)
        elif row.get("categories") and not visible:
            continue    # only in hidden categories
        else:
            targets = [visible[0] if visible else None]
        if covered and row["family_key"] in covered:
            continue    # the general part already shows it
        has_ap = has_ap or any(m in ("AP", "NAP") for m in (row.get("mountings") or {}))
        for cid in targets:
            block_for(cid)["items"].append({
                "id": new_id(), "kind": "symbol", "family_key": row["family_key"],
                "symbol_key": row["symbol_key"],
                "text": descriptions.get(row["family_key"]) or row.get("title") or "",
                "length_mm": None, "width_mm": None, "line_style": "solid", "line_length": 8.0, **ITEM_EXTRA})
    doc["blocks"] = sorted(blocks.values(), key=lambda b: order.get(b["category_id"], 999))
    if has_ap and doc["blocks"] and not ap_covered:
        first = next((b for b in doc["blocks"] if b["category_id"] == "allgemein"), doc["blocks"][0])
        first["items"].append({"id": new_id(), "kind": "note", "family_key": None, "symbol_key": None,
                               "text": descriptions.get(AP_NOTE_KEY) or AP_NOTE, "length_mm": None, "width_mm": None,
                               "line_style": "solid", "line_length": 8.0, **ITEM_EXTRA})
    return doc
