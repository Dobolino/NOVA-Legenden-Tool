"""Read a Nova user stencil file (Benutzerschablonen.n5q).

The file is Nova's own binary format with the same length-prefixed UTF-16
strings as a plan. It is a tree: stencil set -> tab -> entry. Every node starts
with its name and a description; the bytes right before the name tell the node
type (verified on the edeco file «Benutzerschablonen», sets «edeco» and
«Standard V3.2"):

    ... 10 00 00 00 00 01   stencil set
    ... 0c 00 00 00 00 01   tab (Registerkarte)
    ... 17 00 00 00 02 00 01  entry

An entry is followed by the object it places, in the plan format: the
catalogue reference (dataset, sheet, code, graphic id), the layer, or the path
of a macro (.n4d) for company symbols, plan frames and the like. Only what the
legend needs is read; nothing is written.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..n4d.probe import DATASET_PREFIXES, PICTURE_PATH, _strip_guid, read_cstrings

SET_TAIL = b"\x10\x00\x00\x00\x00\x01"
TAB_TAIL = b"\x0c\x00\x00\x00\x00\x01"
ENTRY_TAIL = b"\x17\x00\x00\x00\x02\x00\x01"
LAYER = re.compile(r"^(E|X)_[\w.\-äöüÄÖÜ ]+$")


@dataclass
class StencilEntry:
    name: str
    description: str = ""
    dataset: str | None = None
    sheet: str | None = None
    item: str | None = None
    graphic_id: str | None = None
    layer: str | None = None
    macro: str | None = None          # path of a macro (.n4d) as stored in the file
    object_name: str = ""             # name of the placed object (Nova shows it when the entry has none)

    @property
    def label(self) -> str:
        return self.name or self.object_name


@dataclass
class StencilTab:
    name: str
    description: str = ""
    entries: list[StencilEntry] = field(default_factory=list)


@dataclass
class StencilSet:
    name: str
    description: str = ""
    tabs: list[StencilTab] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def read_stencils(data: bytes) -> list[StencilSet]:
    strings = read_cstrings(data)
    sets: list[StencilSet] = []
    tab: StencilTab | None = None
    entry: StencilEntry | None = None
    prev_end = 0
    for i, s in enumerate(strings):
        gap = data[prev_end:s.offset]
        prev_end = s.end
        nxt = strings[i + 1].text if i + 1 < len(strings) else ""
        if gap.endswith(SET_TAIL):
            sets.append(StencilSet(s.text, nxt))
            tab = entry = None
            continue
        if gap.endswith(TAB_TAIL):
            if not sets:
                sets.append(StencilSet(""))
            tab = StencilTab(s.text, nxt)
            sets[-1].tabs.append(tab)
            entry = None
            continue
        if gap.endswith(ENTRY_TAIL) and tab is not None:
            entry = StencilEntry(s.text.strip(), nxt.strip())
            tab.entries.append(entry)
            continue
        if entry is None:
            continue
        t = s.text
        if not entry.object_name and PICTURE_PATH.match(nxt):
            entry.object_name = _strip_guid(t).strip()
        if entry.item is None and entry.macro is None and t.startswith(DATASET_PREFIXES) and i + 2 < len(strings):
            entry.dataset, entry.sheet, entry.item = t, strings[i + 1].text, strings[i + 2].text
        elif entry.item and entry.graphic_id is None and t.startswith("2D-") and i >= 1 \
                and strings[i - 1].text == entry.item:
            entry.graphic_id = t
        elif entry.layer is None and LAYER.match(t) and entry.item:
            entry.layer = t
        elif entry.macro is None and entry.item is None and t.lower().endswith(".n4d"):
            entry.macro = t
    # entries without a name and without content are spacers in Nova's palette
    for st in sets:
        for tb in st.tabs:
            tb.entries = [e for e in tb.entries if e.name or e.item or e.macro]
    return sets


def read_stencil_file(path: str | Path) -> list[StencilSet]:
    return read_stencils(Path(path).read_bytes())


def stencil_folder(template: str, nova_version: str, user_home: str | None = None) -> Path:
    """The stencil folder of a Nova version: ``{nova}`` in the template becomes the
    major version (19.2 -> 19, 20 -> 20), ``%USERPROFILE%`` / ``~`` the home folder."""
    import os

    major = re.match(r"\d+", str(nova_version or "").strip())
    text = (template or "").replace("{nova}", major.group(0) if major else "19")
    home = user_home or os.environ.get("USERPROFILE") or str(Path.home())
    text = text.replace("%USERPROFILE%", home)
    if text.startswith("~"):
        text = home + text[1:]
    return Path(text)
