"""Pick the plan layer whose colour a category shows in the overall list.

The company category keeps the legend layer (E_Licht). A floor plan often
uses a BKP layer (E_232.5_Licht). Exact name first, otherwise the same tail
after the BKP number. E_233_Leuchten does not match E_Licht; the project can
choose that layer itself.
"""

from __future__ import annotations

import re

_BKP = re.compile(r"^E_\d+(?:\.\d+)?_(.+)$")


def _legend_color(color: str | None) -> str:
    """A plan colour that can colour a legend section. White and empty do not."""
    text = (color or "").strip()
    if len(text) == 7 and text.startswith("#") and text.lower() != "#ffffff":
        return text
    return ""


def layer_tail(name: str) -> str:
    """Part of a layer name after E_ and an optional BKP number."""
    match = _BKP.match(name or "")
    if match:
        return match.group(1)
    if (name or "").startswith("E_"):
        return name[2:]
    return name or ""


def pick_category_layer(category_layer: str, layers: list[dict], usage: dict[str, int],
                        override: str | None) -> dict:
    """Return color, layer, reason and whether the project chose the layer."""
    by_name = {layer["name"]: layer for layer in layers}

    def from_layer(name: str, manual: bool) -> dict:
        layer = by_name.get(name)
        if layer is None:
            return {"color": "", "layer": name, "reason": f"gewählte Ebene {name} ist im Plan nicht vorhanden",
                    "manual": manual}
        color = layer.get("color") or ""
        reason = "" if color else f"Ebene {name} hat keine Farbe"
        return {"color": color, "layer": name, "reason": reason, "manual": manual}

    if override:
        return from_layer(override, True)
    if category_layer and category_layer in by_name:
        return from_layer(category_layer, False)

    want = layer_tail(category_layer)
    candidates = [layer for layer in layers if want and layer_tail(layer["name"]) == want]
    if not candidates:
        # The category layer is not on the plan. Use the colour the symbols of
        # this category actually use most often, instead of leaving the section grey.
        used = [layer for layer in layers
                if usage.get(layer["name"], 0) > 0 and _legend_color(layer.get("color"))]
        if used:
            best = max(used, key=lambda layer: (usage.get(layer["name"], 0), layer["name"]))
            return {"color": best.get("color") or "", "layer": best["name"],
                    "reason": f"häufigste Farbe im Plan ({best['name']})", "manual": False}
        if category_layer:
            reason = f"keine passende Ebene, {category_layer} ist im Plan nicht vorhanden"
        else:
            reason = "keine Ebene an der Kategorie"
        return {"color": "", "layer": "", "reason": reason, "manual": False}

    def rank(layer: dict) -> tuple:
        return (usage.get(layer["name"], 0), 1 if layer.get("color") else 0, layer["name"])

    best = max(candidates, key=rank)
    color = best.get("color") or ""
    reason = "" if color else f"Ebene {best['name']} hat keine Farbe"
    return {"color": color, "layer": best["name"], "reason": reason, "manual": False}


def category_usage(rows: list[dict]) -> dict[str, int]:
    """Apparatus per category in the current imports (rows of the overall list)."""
    used: dict[str, int] = {}
    for row in rows:
        total = int(row.get("total") or 0)
        if total <= 0:
            continue
        for cid in row.get("categories") or []:
            used[cid] = used.get(cid, 0) + total
    return used


def category_state(picked: dict, layers: list[dict], used: int) -> dict:
    """What the layers tab shows for one category.

    state: "manuell" (the project chose a layer), "unbenutzt" (no apparatus in
    the current imports), "automatisch" (found by name) or "waehlen" (used, but
    no layer found). layer_missing and no_color tell a layer that is not in the
    plans apart from a layer without colour.
    """
    names = {layer["name"] for layer in layers}
    layer = picked.get("layer") or ""
    layer_missing = bool(layer) and layer not in names
    no_color = bool(layer) and not layer_missing and not picked.get("color")
    if picked.get("manual"):
        state = "manuell"
    elif used <= 0:
        state = "unbenutzt"
    elif layer:
        state = "automatisch"
    else:
        state = "waehlen"
    return {"state": state, "used": used, "layer_missing": layer_missing, "no_color": no_color}
