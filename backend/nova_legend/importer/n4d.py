"""Read a Nova plan (.n4d) or a Nova model drawing (.n4m).

Both are the same OLE container (streams Header, Version, Elements, Bitmap or
BITMAP, OLEClients) with the same object records, so one reader serves both.
Source keys keep the prefix "n4d:" for both, so a floor imported as N4D and
later as N4M matches its rows exactly.

Uses the read-only probe from Phase 0: every Nova object that references a
dataset gives dataset id, catalogue code, graphic id and layer. Objects
without a graphic are labels, cables etc.; they are counted only when their
code is a symbol in the library (checked in recognize.py).

Layer colours: after a layer name the object stores the colour twice as
R, G, B, 0 (verified: 17 of 17 layers match the DXF export of the same plan).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import olefile

from ..n4d.probe import analyse, read_cstrings
from .model import Found, ImportResult, Layer


def n4d_layer_colors(elements: bytes) -> dict[str, str]:
    votes: dict[str, Counter] = defaultdict(Counter)
    for s in read_cstrings(elements):
        if not re.match(r"^(E_|X_)", s.text):
            continue
        tail = elements[s.end:s.end + 8]
        if len(tail) == 8 and tail[:4] == tail[4:8] and tail[3] == 0:
            votes[s.text]["#{:02x}{:02x}{:02x}".format(*tail[:3])] += 1
    return {name: c.most_common(1)[0][0] for name, c in votes.items()}


def read_n4d(path: str | Path, fmt: str = "n4d") -> ImportResult:
    report = analyse(path)
    ole = olefile.OleFileIO(str(path))
    try:
        elements = ole.openstream("Elements").read()
    finally:
        ole.close()
    colors = n4d_layer_colors(elements)
    result = ImportResult(fmt, info={"version_stream": report.version_stream,
                                       "datasets": report.datasets})
    result.layers = [Layer(name, colors.get(name, "")) for name in report.layers]
    found: dict[str, Found] = {}
    for obj in report.objects:
        if not obj.item:
            continue
        if obj.sheet.startswith("Label_"):
            result.ignored[obj.sheet] = result.ignored.get(obj.sheet, 0) + 1
            continue
        key = f"n4d:{obj.dataset}|{obj.sheet}|{obj.item}|{obj.graphic_id or ''}"
        entry = found.setdefault(key, Found(key, obj.name or obj.graphic_name or obj.item,
                                            dataset=obj.dataset, item=obj.item, sheet=obj.sheet,
                                            graphic_id=obj.graphic_id or "",
                                            graphic_name=obj.graphic_name or ""))
        entry.features["has_graphic"] = bool(obj.graphic_id)
        entry.add(obj.layer or "")
    result.found = sorted(found.values(), key=lambda f: -f.count)
    return result
