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
    Category("steckdosen", "Steckdosen und Dosen", "E_Licht", sheets=["90", "100", "390", "400"]),
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
