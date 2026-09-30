"""Pick the plan layer whose colour a category shows in the overall list.

The company category keeps the legend layer (E_Licht). A floor plan often
uses a BKP layer (E_232.5_Licht). Exact name first, otherwise the same tail
after the BKP number. E_233_Leuchten does not match E_Licht; the project can
choose that layer itself.
"""

from __future__ import annotations

import re

_BKP = re.compile(r"^E_\d+(?:\.\d+)?_(.+)$")


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
