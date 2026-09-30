"""Group symbol variants of the same function into families.

Rule (confirmed by the user on 30.09.2026):

1. The family key is the symbol name without the mounting token
   (UP, AP, NUP, NAP, EB). Label variants such as "(Ohne Text)" are merged
   too (setting ``merge_labels``, default on). Orientations such as
   "liegend" / "stehend" stay separate (setting ``merge_orientation``,
   default off).
2. Catalogue sheets come in UP/AP pairs (10/20, 30/40 ...). Item 10-N and
   20-N normally describe the same function. This is used as a cross check
   and reported when it disagrees with the name rule.
3. The representative is the UP variant with the standard label. If no UP
   variant exists: NUP, then EB, then no mounting, then AP, then NAP.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from ..parser.dataset import Symbol

# UP sheet -> AP sheet, taken from Data/Sheet descriptions
SHEET_PAIRS: dict[str, str] = {
    "10": "20", "30": "40", "50": "60", "70": "80", "90": "100",
    "110": "120", "210": "220", "230": "240", "250": "260", "310": "320",
    "346": "347", "350": "360", "370": "380", "390": "400",
}

LABEL_VARIANTS = re.compile(
    r"\(\s*(ohne text|ohen text|kein text|mit text|text horizontal|text stehend|"
    r"text vertikal|text liegend)\s*\)", re.I)
ORIENTATION = re.compile(
    r"(?<![A-Za-zäöü])(liegend|stehend|rechts|links)(\s*-?\d+°)?(?![A-Za-zäöü])", re.I)
MOUNT_TOKEN = re.compile(r"(?<![A-Za-z0-9])(NUP|NAP|UP|AP|EB)(?![A-Za-z0-9])")
REP_ORDER = ["UP", "NUP", "EB", None, "AP", "NAP"]


@dataclass(frozen=True)
class FamilyOptions:
    merge_labels: bool = True
    merge_orientation: bool = False


def label_variant(name: str) -> str:
    """Return the label variant ("" = standard) found in a symbol name."""
    m = LABEL_VARIANTS.search(name)
    return m.group(1).lower().replace("ohen", "ohne").replace("kein text", "ohne text") if m else ""


def orientation(name: str) -> str:
    """Return the orientation named in a symbol name ("" = none)."""
    m = ORIENTATION.search(name)
    return m.group(0).strip().lower() if m else ""


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*(,\s*)*", ", ", text)
    return text.strip(" ,")


def family_title(name: str, options: FamilyOptions = FamilyOptions()) -> str:
    """Readable family name: the symbol name without the merged parts."""
    n = MOUNT_TOKEN.sub("", name)
    if options.merge_labels:
        n = LABEL_VARIANTS.sub("", n)
    if options.merge_orientation:
        n = ORIENTATION.sub("", n)
    return _tidy(n)


def family_key(name: str, options: FamilyOptions = FamilyOptions()) -> str:
    n = family_title(name.replace("Schutz-Deckel", "Schutzdeckel"), options)
    return n.lower()


@dataclass
class Family:
    key: str
    title: str
    representative: Symbol
    members: list[Symbol] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @property
    def mountings(self) -> list[str]:
        order = ["UP", "NUP", "AP", "NAP", "EB", "-"]
        found = {m.mounting or "-" for m in self.members}
        return sorted(found, key=lambda x: order.index(x) if x in order else 99)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "title": self.title,
            "representative": self.representative.key,
            "members": [{"key": m.key, "name": m.name, "mounting": m.mounting,
                         "label_variant": label_variant(m.name)} for m in self.members],
            "mountings": self.mountings,
            "conflicts": self.conflicts,
        }


def _rep_rank(sym: Symbol) -> tuple:
    mount_rank = REP_ORDER.index(sym.mounting) if sym.mounting in REP_ORDER else 9
    return (mount_rank, 0 if not label_variant(sym.name) else 1,
            0 if not orientation(sym.name) else 1, sym.graphic_id, sym.item)


def build_families(symbols: list[Symbol], options: FamilyOptions = FamilyOptions()) -> list[Family]:
    """Group symbols of ONE dataset into families."""
    groups: dict[str, list[Symbol]] = defaultdict(list)
    for s in symbols:
        groups[family_key(s.name, options)].append(s)

    families: list[Family] = []
    by_key: dict[str, Family] = {}
    for key, members in groups.items():
        rep = min(members, key=_rep_rank)
        fam = Family(key, family_title(rep.name, options), rep, sorted(members, key=_rep_rank))
        families.append(fam)
        by_key[key] = fam

    # Cross check with the UP/AP sheet pairs
    index = {(s.item, s.graphic_id): s for s in symbols}
    for s in symbols:
        ap_sheet = SHEET_PAIRS.get(s.sheet)
        if not ap_sheet or "-" not in s.item:
            continue
        twin = index.get((f"{ap_sheet}-{s.item.split('-', 1)[1]}", s.graphic_id))
        if twin and family_key(twin.name, options) != family_key(s.name, options):
            fam = by_key[family_key(s.name, options)]
            fam.conflicts.append(
                f"Code-Paar {s.item} / {twin.item} hat abweichende Namen: "
                f"«{s.name}» / «{twin.name}»")
    families.sort(key=lambda f: (f.representative.sheet.zfill(5), f.representative.item))
    return families
