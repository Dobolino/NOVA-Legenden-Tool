"""Read-only analysis of a DXF exported from Nova (Phase 0).

Findings on 3_1.OG.dxf (exported by Nova, AC1027 = R2013):

* every Nova element becomes its own block, one block per placement:
  "<element name with ',' replaced by '_'>_<10 character element ID>"
* the INSERT carries hidden attributes. ``TypID`` holds the catalogue code
  (e.g. 90-30) and ``Herkunft`` the dataset ("Elektroinstallationen V2 CH
  2025-09 edeco AG"). ``Bez`` holds the graphic name.
* not every element type exports attributes. Those are recognised by the
  block name (element name) against the dataset names.
* coordinates are world millimetres, block geometry lies on layer 0,
  the INSERT sits on the Nova layer (E_...).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import ezdxf

ID_SUFFIX = re.compile(r"_A0[0-9A-Z]{8}$")


def block_base_name(name: str) -> str:
    """Strip the Nova element ID from a block name."""
    return ID_SUFFIX.sub("", name)


def analyse_dxf(path: str | Path, dataset_names: dict[str, set[str]] | None = None) -> dict:
    """Summarise a Nova DXF export.

    dataset_names maps a lower-case symbol name (',' replaced by '_') to
    catalogue codes. It enables the block name fallback.
    """
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    inserts = list(msp.query("INSERT"))
    by_method: Counter = Counter()
    codes: Counter = Counter()
    origins: Counter = Counter()
    unresolved: Counter = Counter()
    layers: Counter = Counter()
    for ins in inserts:
        attrs = {a.dxf.tag: a.dxf.text for a in ins.attribs}
        base = block_base_name(ins.dxf.name)
        layers[ins.dxf.layer] += 1
        code = attrs.get("TypID", "")
        if code and "-" in code:
            by_method["TypID"] += 1
            codes[code] += 1
            origins[attrs.get("Herkunft", "").strip()] += 1
        elif dataset_names and base.lower() in dataset_names:
            by_method["Blockname"] += 1
            for c in dataset_names[base.lower()]:
                codes[c] += 1
                break
        else:
            by_method["offen"] += 1
            unresolved[base] += 1
    return {
        "datei": Path(path).name,
        "dxf_version": doc.dxfversion,
        "insunits": doc.header.get("$INSUNITS"),
        "dimscale": doc.header.get("$DIMSCALE"),
        "entitaeten": dict(Counter(e.dxftype() for e in msp)),
        "bloecke": len(doc.blocks),
        "inserts": len(inserts),
        "erkennung": dict(by_method),
        "katalogcodes": dict(sorted(codes.items())),
        "herkunft": dict(origins),
        "offen": dict(unresolved.most_common()),
        "ebenen_inserts": dict(layers.most_common()),
        "ebenen": [(l.dxf.name, l.dxf.color, l.dxf.linetype) for l in doc.layers],
        "textstile": [(s.dxf.name, s.dxf.font) for s in doc.styles],
    }
