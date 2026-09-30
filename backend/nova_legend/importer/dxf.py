"""Read a plan exported from Nova as DXF.

Findings (Phase 0, 3_1.OG.dxf, AC1027):

* every Nova element is its own block, one per placement, named
  "<element name, ',' -> '_'>_<10 character element id>"
* Nova parts carry hidden attributes: ``TypID`` = catalogue code,
  ``Bez`` = graphic name, ``Herkunft`` = dataset long name + company
* some element types have no attributes; they are recognised by name later
* lines, dimensions, labels etc. without attributes are not apparatus
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import ezdxf
from ezdxf import colors as ezcolors

from .model import Found, ImportResult, Layer

ID_SUFFIX = re.compile(r"_A0[0-9A-Z]{8}$")

# Nova elements that are never apparatus (compared lower case, block base name)
NON_SYMBOLS = {
    "leitung", "schaltkreis", "bauteilbeschriftung", "kurzbezeichnung", "bezeichnung",
    "maß", "mass", "polygon", "einfuegepunkt", "durchbruch beschriften", "0.0 arc",
    "text", "linie", "bemassung",
}
NON_SYMBOL_PREFIXES = ("plankopf", "planrahmen", "s&a", "a_")


def block_base_name(name: str) -> str:
    return ID_SUFFIX.sub("", name)


def display_name(base: str) -> str:
    """Block names replace ',' by '_': 'Steckdose T13_ UP' -> 'Steckdose T13, UP'."""
    return base.replace("_ ", ", ").replace("_", ",")


def _layer_color(layer) -> str:
    try:
        rgb = layer.rgb or ezcolors.aci2rgb(abs(layer.dxf.color))
    except Exception:  # noqa: BLE001 - odd colour values
        return ""
    return "#{:02x}{:02x}{:02x}".format(*rgb) if rgb else ""


def block_features(doc, block_name: str) -> dict:
    """Simple geometry features of a block for the similarity matcher."""
    counts: Counter = Counter()
    xs: list[float] = []
    ys: list[float] = []
    block = doc.blocks.get(block_name)
    if block is None:
        return {}
    base = block.block.dxf.base_point
    for e in block:
        t = e.dxftype()
        counts[{"LINE": "line", "ARC": "arc", "CIRCLE": "arc", "ELLIPSE": "arc",
                "LWPOLYLINE": "polygon", "POLYLINE": "polygon", "SOLID": "polygon",
                "HATCH": "polygon", "SPLINE": "spline", "TEXT": "text", "MTEXT": "text"}.get(t, "other")] += 1
        try:
            if t == "LINE":
                pts = [e.dxf.start, e.dxf.end]
            elif t in ("CIRCLE", "ARC"):
                c, r = e.dxf.center, e.dxf.radius
                pts = [(c[0] - r, c[1] - r), (c[0] + r, c[1] + r)]
            elif t == "LWPOLYLINE":
                pts = list(e.get_points("xy"))
            else:
                pts = []
        except Exception:  # noqa: BLE001
            pts = []
        for p in pts:
            xs.append(p[0] - base[0])
            ys.append(p[1] - base[1])
    feats = dict(counts)
    if xs:
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        feats["aspect"] = round(w / h, 3) if h > 1e-9 else 0.0
    return feats


def read_dxf(path: str | Path) -> ImportResult:
    doc = ezdxf.readfile(str(path))
    result = ImportResult("dxf", info={"dxf_version": doc.dxfversion,
                                       "insunits": doc.header.get("$INSUNITS"),
                                       "dimscale": doc.header.get("$DIMSCALE")})
    result.layers = [Layer(l.dxf.name, _layer_color(l), l.dxf.linetype) for l in doc.layers]
    found: dict[str, Found] = {}
    features_done: set[str] = set()

    for ins in doc.modelspace().query("INSERT"):
        name = ins.dxf.name
        base = block_base_name(name)
        attrs = {a.dxf.tag: a.dxf.text for a in ins.attribs}
        layer = ins.dxf.layer
        code = (attrs.get("TypID") or "").strip()
        if code:
            origin = (attrs.get("Herkunft") or "").strip()
            graphic = (attrs.get("Bez") or "").strip()
            key = f"code:{origin}|{code}|{graphic}"
            entry = found.setdefault(key, Found(key, display_name(base), item=code,
                                                graphic_name=graphic))
            entry.dataset = origin              # long name, resolved later
        else:
            low = base.lower()
            if (low in NON_SYMBOLS or low.startswith(NON_SYMBOL_PREFIXES)
                    or not ID_SUFFIX.search(name) or not layer.upper().startswith("E_")):
                result.ignored[base] = result.ignored.get(base, 0) + 1
                continue
            key = f"name:{display_name(base).lower()}"
            entry = found.setdefault(key, Found(key, display_name(base)))
        entry.add(layer)
        if key not in features_done:
            entry.features = block_features(doc, name)
            features_done.add(key)

    result.found = sorted(found.values(), key=lambda f: -f.count)
    return result
