"""Suggest library symbols for an unknown plan element.

Score (0 to 100) from four parts:
    name       60 %   rapidfuzz WRatio of element / graphic name vs symbol name
    geometry   20 %   counts of lines, arcs, areas, texts and the aspect ratio
    code       10 %   same number range as the element's catalogue code
    category   10 %   the element's layer is the layer of the symbol's category
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

from ..importer.model import Found

WEIGHTS = {"name": 0.6, "geometry": 0.2, "code": 0.1, "category": 0.1}
FEATURE_KEYS = ("line", "arc", "polygon", "text")


def geometry_similarity(a: dict, b: dict) -> float:
    """1.0 = same feature profile, 0.0 = nothing in common."""
    if not a or not b:
        return 0.0
    diff = 0.0
    total = 0.0
    for k in FEATURE_KEYS:
        x, y = a.get(k, 0), b.get(k, 0)
        diff += abs(x - y)
        total += max(x, y)
    counts = 1.0 - (diff / total) if total else 0.0
    ra, rb = a.get("aspect"), b.get("aspect")
    if ra and rb:
        aspect = min(ra, rb) / max(ra, rb)
        return 0.7 * counts + 0.3 * aspect
    return counts


def symbol_features(stats: dict[str, int], bbox: list[float] | None) -> dict:
    feats = {
        "line": stats.get("line", 0) + stats.get("polyline", 0),
        "arc": stats.get("arc", 0) + stats.get("ellipse_arc", 0),
        "polygon": stats.get("polygon", 0) + stats.get("hatch", 0),
        "text": stats.get("text", 0),
    }
    if bbox and len(bbox) == 4 and bbox[3] - bbox[1] > 1e-9:
        feats["aspect"] = round((bbox[2] - bbox[0]) / (bbox[3] - bbox[1]), 3)
    return feats


def suggest(found: Found, symbols: list, feature_of, layer_category: dict[str, set[str]],
            category_of, limit: int = 8) -> list[dict]:
    """Rank library symbols for ``found``.

    symbols: LibSymbol list; feature_of(symbol) -> features dict;
    layer_category: layer -> category ids using it; category_of(symbol) -> category ids.
    """
    query = found.graphic_name or found.name
    names = [s.name for s in symbols]
    pre = process.extract(query, names, scorer=fuzz.WRatio, limit=40)
    if found.name and found.graphic_name and found.name != found.graphic_name:
        pre += process.extract(found.name, names, scorer=fuzz.WRatio, limit=20)
    seen: set[int] = set()
    ranked = []
    element_cats: set[str] = set()
    for layer in found.layers:
        element_cats |= layer_category.get(layer, set())
    sheet = found.item.split("-")[0] if "-" in found.item else ""
    for _name, name_score, idx in pre:
        if idx in seen:
            continue
        seen.add(idx)
        sym = symbols[idx]
        name_part = max(fuzz.WRatio(query, sym.name),
                        fuzz.WRatio(found.name, sym.name) if found.name else 0) / 100.0
        geo_part = geometry_similarity(found.features, feature_of(sym)) if found.features else 0.0
        code_part = 1.0 if sheet and sym.sheet == sheet else 0.0
        cat_part = 1.0 if element_cats and (element_cats & set(category_of(sym))) else 0.0
        score = (WEIGHTS["name"] * name_part + WEIGHTS["geometry"] * geo_part
                 + WEIGHTS["code"] * code_part + WEIGHTS["category"] * cat_part)
        ranked.append({
            "symbol_key": sym.key, "name": sym.name, "item": sym.item, "dataset": sym.dataset,
            "mounting": sym.mounting, "svg": sym.svg, "score": round(score * 100),
            "parts": {"Name": round(name_part * 100), "Geometrie": round(geo_part * 100),
                      "Code": round(code_part * 100), "Kategorie": round(cat_part * 100)},
        })
    ranked.sort(key=lambda r: -r["score"])
    unique, keys = [], set()
    for r in ranked:           # same symbol name and code in one dataset only once
        k = (r["name"], r["item"], r["dataset"])
        if k not in keys:
            keys.add(k)
            unique.append(r)
    return unique[:limit]
