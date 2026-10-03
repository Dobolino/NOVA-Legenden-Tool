"""Map found plan elements to library symbols.

Order of the rules:
1. a remembered decision (mapping) for the element, company wide
2. catalogue code (+ graphic id or graphic name) in the dataset of the element
3. element name = name of a library symbol
   When the element names its source dataset, rules 2 and 3 only look in that
   dataset. A symbol from another catalogue is never taken as recognised; the
   element stays unknown and the user decides (no guessing).
4. otherwise unknown: the user picks a symbol (suggestions in matcher.suggest)

Labels (number ranges Label_*) are not apparatus and are skipped.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz import fuzz

from .model import Found

IGNORE = "__ignore__"


@dataclass
class Resolution:
    symbol_key: str | None
    status: str          # erkannt, zugeordnet, ignoriert, unbekannt
    method: str          # Katalogcode, Name, manuell, ...


class LibraryIndex:
    """Lookup tables over the library symbols (LibSymbol objects)."""

    def __init__(self, symbols, datasets: list[dict]):
        self.by_key = {s.key: s for s in symbols}
        self.by_code: dict[tuple[str, str], list] = defaultdict(list)
        self.by_name: dict[str, list] = defaultdict(list)
        for s in symbols:
            self.by_code[(s.dataset, s.item)].append(s)
            self.by_name[s.name.lower()].append(s)
            if s.part_name:
                self.by_name[s.part_name.lower()].append(s)
        self.datasets = datasets
        # catalogues that have 2D symbols at all (EloTrassen has none: its objects are trays)
        self.with_symbols = {s.dataset for s in symbols}
        # Newest first: V2 before V1 when the dataset is not known
        self.order = [d["id"] for d in sorted(datasets, key=lambda d: d["id"], reverse=True)]
        self.order.sort(key=lambda i: 0 if ".V2." in i else 1)

    def dataset_id(self, text: str) -> str | None:
        """Dataset id from an id or from DXF 'Herkunft' (long name + company)."""
        if not text:
            return None
        for d in self.datasets:
            if text == d["id"]:
                return d["id"]
        best = None
        for d in self.datasets:
            name = (d.get("long_name") or "").strip()
            if name and text.startswith(name) and (best is None or len(name) > len(best[1])):
                best = (d["id"], name)
        return best[0] if best else None

    def by_code_any(self, item: str, dataset: str | None) -> list:
        if dataset and (dataset, item) in self.by_code:
            return self.by_code[(dataset, item)]
        for ds in self.order:
            if (ds, item) in self.by_code:
                return self.by_code[(ds, item)]
        return []

    def by_name_any(self, name: str) -> list:
        cands = self.by_name.get(name.lower(), [])
        return sorted(cands, key=lambda s: self.order.index(s.dataset) if s.dataset in self.order else 99)


def _pick_graphic(cands: list, graphic_id: str, graphic_name: str):
    if graphic_id:
        for s in cands:
            if s.graphic_id == graphic_id:
                return s
    if graphic_name:
        for s in cands:
            if s.name == graphic_name:
                return s
        scored = sorted(cands, key=lambda s: -fuzz.ratio(s.name.lower(), graphic_name.lower()))
        if scored and fuzz.ratio(scored[0].name.lower(), graphic_name.lower()) >= 60:
            return scored[0]
    return cands[0] if cands else None


def resolve(found: Found, index: LibraryIndex, mappings: dict[str, str]) -> Resolution:
    mapped = mappings.get(found.source_key)
    if mapped == IGNORE:
        return Resolution(None, "ignoriert", "manuell")
    if mapped and mapped in index.by_key:
        return Resolution(mapped, "zugeordnet", "manuell")

    named = bool((found.dataset or "").strip())     # the element says where it comes from
    ds = index.dataset_id(found.dataset)
    if found.item:
        if named:
            cands = list(index.by_code.get((ds, found.item), [])) if ds else []
        else:
            cands = index.by_code_any(found.item, None)
        if found.sheet:
            cands = [c for c in cands if c.sheet == found.sheet] or cands
        sym = _pick_graphic(cands, found.graphic_id, found.graphic_name)
        if sym is not None:
            if sym.sheet.startswith("Label_"):
                return Resolution(None, "ignoriert", "Beschriftung")
            return Resolution(sym.key, "erkannt", "Katalogcode")
        if found.features.get("has_graphic") is False:
            # Only objects of a catalogue without any 2D symbols (cable trays) are left
            # out silently. An apparatus of an electrical catalogue without a drawing
            # is shown under "Unbekannt" so the legend is not incomplete unnoticed.
            if ds and ds in index.with_symbols:
                return Resolution(None, "unbekannt", "ohne Grafik")
            return Resolution(None, "ignoriert", "ohne Grafik")

    cands = index.by_name_any(found.name) or (
        index.by_name_any(found.graphic_name) if found.graphic_name else [])
    if named:
        cands = [c for c in cands if c.dataset == ds]
    if cands:
        if cands[0].sheet.startswith("Label_"):
            return Resolution(None, "ignoriert", "Beschriftung")
        return Resolution(cands[0].key, "erkannt", "Name")
    return Resolution(None, "unbekannt", "")
