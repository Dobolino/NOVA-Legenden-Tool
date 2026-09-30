"""Default legend categories and the automatic assignment rules.

Layer names follow the objects in Legende_edeco20.n4d (sheet -> layer).

Finding from Phase 0: the number range of a catalogue code is the Nova
"Sheet" ID (Data/Sheet@ID) and the folder ID (Folder@ID). It is therefore a
reliable category key. Name patterns are only used as a fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Category:
    id: str
    title: str
    layer: str
    parent: str | None = None
    columns: int = 2
    spacing_mm: float = 4.55     # row pitch measured in Legende_edeco20.n4d
    sheets: list[str] = field(default_factory=list)


DEFAULT_CATEGORIES: list[Category] = [
    Category("allgemein", "Allgemein", "E_Starkstrom", sheets=["9999", "Label_10", "Label_20"]),
    Category("leitungen", "Leitungen", "E_Leitung_Licht", sheets=["410", "Label_30", "Label_40"]),
    Category("verteiler", "Verteiler und Stromquellen", "E_Starkstrom", sheets=["405", "420"]),
    Category("licht", "Licht und Leuchten", "E_Licht",
             sheets=["130", "135", "140", "145", "Dialux", "Relux"]),
    Category("fluchtweg", "Fluchtwegleuchten", "E_Fluchtwegleuchten", sheets=["165"]),
    Category("schalter", "Schalter und Taster", "E_Licht",
             sheets=["10", "20", "30", "40", "50", "60", "70", "80"]),
    Category("steckdosen", "Steckdosen und Dosen", "E_Licht",
             sheets=["90", "100", "390", "400", "50", "60"]),  # Kombinationen Gr.I in both
    Category("kraft", "Kraft und Elektrogeräte", "E_Starkstrom", sheets=["170"]),
    Category("schwachstrom", "Schwachstrom", "E_Schwachstrom", sheets=["330"]),
    Category("telefon", "Telefon", "E_Telefon", parent="schwachstrom", sheets=["250", "260"]),
    Category("edv", "EDV und UKV", "E_EDV", parent="schwachstrom", sheets=["310", "320"]),
    Category("tv", "TV und Video", "E_RadioTV", parent="schwachstrom", sheets=["290"]),
    Category("gsa", "Gegensprechanlage", "E_GSA", parent="schwachstrom", sheets=["345", "346", "347"]),
    Category("uhren", "Uhren", "E_Uhren", parent="schwachstrom", sheets=["270"]),
    Category("pans", "PANS und Krankenruf", "E_Schwachstrom_allgemein", parent="schwachstrom",
             sheets=["370", "380"]),
    Category("knx", "BUS-KNX", "E_BUS-KNX", sheets=["210", "220", "225"]),
    Category("bma", "Brandmeldeanlage", "E_Brandmeldeanlagen", sheets=["230", "240"]),
    Category("sicherheit", "Sicherheit", "E_Sicherheit", sheets=["350", "360"]),
    Category("hlks", "Melder, Fühler, Sensoren (HLKS)", "E_HLKS", sheets=["110", "120"]),
    Category("erdung", "Blitzschutz und Erdung", "E_Starkstrom", sheets=["190", "200"]),
    Category("diverse", "Diverse", "E_Starkstrom", sheets=["101"]),
    Category("schema", "Schema Verteiler (Niederspannung)", "E_Starkstrom"),
]

# Number ranges of the other Nova electrical datasets (added in defaults
# version 2): Niederspannung CH, Schwachstrom CH, Elektro-Trassen.
EXTRA_SHEETS: dict[str, list[str]] = {
    "allgemein": ["E_Label_Z1", "ALLG"],
    "leitungen": ["Beschriftung_6_2", "GZLSym", "LeitungsVerw", "Tra1"],
    "verteiler": ["VT1"],
    "licht": ["T5", "T8", "LB", "DL_EB", "DL_AP", "WL_EB", "WL_AP", "BL_AP", "BL_UP",
              "geoL_AP", "geoL_EB", "geoWL_AP", "geoWL_EB", "geoBL_AP", "geoBL_EB"],
    "fluchtweg": ["RZL0"],
    "schalter": ["S_P0", "S_P1", "S_P2", "S_P3", "S_P8", "S_P9", "S_KombGr1", "S_P10", "S_P11"],
    "steckdosen": ["S_KombGr1", "SD_5P0_UP", "SD_5P0_AP", "SD_3P0_UP", "SD_3P0_AP", "SD_3P0_SZ",
                   "SD_2P0_UP", "SD_2P0_AP", "VT2"],
    "kraft": ["EG_Anschluesse", "Hauswirtschaft", "Warmwasser", "EG_Antriebe", "Wandler"],
    "schwachstrom": ["S_P5", "AKSG", "OPSG"],
    "telefon": ["FMA", "FMVT"],
    "edv": ["EDV"],
    "tv": ["TV"],
    "gsa": ["GSA"],
    "uhren": ["UHR"],
    "pans": ["S_P4", "KHS", "KHS_A", "KHS_B", "KHS_C", "RKS"],
    "knx": ["KNX", "KNX_A", "KNX_B", "BUSKNX"],
    "bma": ["S_P7", "BMA"],
    "sicherheit": ["S_P6", "EMA", "SICHERHEIT"],
    "hlks": ["HLK", "MEFUE"],
    "erdung": ["FE", "BS"],
}
for _cat in DEFAULT_CATEGORIES:
    for _sheet in EXTRA_SHEETS.get(_cat.id, []):
        if _sheet not in _cat.sheets:
            _cat.sheets.append(_sheet)

# Whole datasets that go to one category when the sheet is unknown
DATASET_RULES: list[tuple[str, str]] = [
    ("Niederspannung_E", "schema"),   # distribution board schematics (FI, LS, ...)
]

# Fallback rules on the symbol name (only used when the sheet is unknown)
NAME_RULES: list[tuple[str, str]] = [
    (r"brand|rauch|hitze|bma|handalarm", "bma"),
    (r"leuchte|lampe|downlight|scheinwerfer", "licht"),
    (r"flucht|rzl|notleucht|rettungszeichen", "fluchtweg"),
    (r"steckdose|dose", "steckdosen"),
    (r"schalter|taster|dimmer", "schalter"),
    (r"knx|bus", "knx"),
    (r"telefon", "telefon"),
    (r"edv|rj45|daten|ukv|wlan", "edv"),
    (r"tv|radio|antenne", "tv"),
    (r"sprechstelle|türöffner|gsa", "gsa"),
    (r"uhr", "uhren"),
    (r"leitung|kanal|rohr", "leitungen"),
    (r"verteil|tableau", "verteiler"),
]


def categories_for(sheet: str) -> list[str]:
    """All categories that list this number range (a symbol may appear in several)."""
    return [cat.id for cat in DEFAULT_CATEGORIES if sheet in cat.sheets]


def category_for(sheet: str, name: str = "") -> tuple[str, str]:
    """Return (category_id, reason) for a symbol."""
    for cat in DEFAULT_CATEGORIES:
        if sheet in cat.sheets:
            return cat.id, f"Nummernkreis {sheet}"
    low = name.lower()
    for pattern, cat_id in NAME_RULES:
        if re.search(pattern, low):
            return cat_id, f"Namensmuster «{pattern}»"
    return "diverse", "keine Regel"
