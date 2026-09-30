"""Load a Nova dataset archive (.nzp) into a flat list of symbols.

A symbol is one 2D GraphicItem that belongs to a catalogue item (Item code
such as ``10-10``). One catalogue item can have several 2D variants
(GraphicItem ID ``2D-10``, ``2D-20`` ...), e.g. "Var. 1" / "Var. 2" or
"(Ohne Text)". Each variant is its own symbol.

Sources inside the archive:
    Set       dataset id, version, date
    Graphic   2D/3D graphics per item (name, geometry, 3D file)
    Data      catalogue sheets (number ranges) and Bauteil records
    Folder    folder tree shown in Nova (sheet -> folder name)
    Package   stencils (Schablonen) with the order used in Nova
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import tree
from .geometry import SymbolGeometry, parse_geometry

MOUNTING_TOKENS = ("NUP", "NAP", "UP", "AP", "EB")
_MOUNT_RE = re.compile(r"(?<![A-Za-z0-9])(NUP|NAP|UP|AP|EB)(?![A-Za-z0-9])")


@dataclass
class DatasetInfo:
    id: str
    version: str
    name: str
    long_name: str
    raw: dict[str, str]


@dataclass
class Symbol:
    dataset: str
    item: str                    # catalogue code, e.g. "10-10"
    graphic_id: str              # e.g. "2D-10"
    sheet: str                   # number range, e.g. "10"
    name: str                    # GraphicItem description
    part_name: str               # Bauteil description from Data
    sheet_name: str              # e.g. "UP Schalter"
    folder: str                  # e.g. "Schalter UP"
    folder_path: list[str]
    stencils: list[str]
    kind: str                    # Geometry, Engine, Symbol
    usage: str
    place_mode: str
    mounting: str | None         # UP, AP, NUP, NAP, EB or None
    geometry: SymbolGeometry | None
    engine: str | None = None    # parametric definition for Engine items
    lib_ref: str | None = None   # "Lib:Content" for Symbol items
    files_3d: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    duplicate_no: int = 0        # >0 when Nova repeats sheet+item+graphic id

    @property
    def key(self) -> str:
        base = f"{self.dataset}|{self.sheet}|{self.item}|{self.graphic_id}"
        return f"{base}~{self.duplicate_no}" if self.duplicate_no else base


def detect_mounting(*texts: str | None) -> str | None:
    """Return the mounting type named in the first text that has one.

    The last token wins inside one text ("Leerdose - Kombi Gr.I, UP").
    """
    for text in texts:
        if not text:
            continue
        hits = _MOUNT_RE.findall(text)
        if hits:
            return hits[-1]
    return None


def _sort_key(code: str) -> tuple:
    parts = re.split(r"[-_]", code)
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in parts)


class Dataset:
    """A parsed .nzp dataset."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        with zipfile.ZipFile(self.path) as zf:
            self._files = {n: zf.read(n) for n in zf.namelist()}
        self.trees = {n: tree.parse(b) for n, b in self._files.items()
                      if not n.startswith("Lib/")}
        self.info = self._read_set()
        self.sheets = self._read_sheets()
        self.folders, self.folder_paths = self._read_folders()
        self.stencils = self._read_stencils()
        self.symbols = self._read_symbols()

    # -- readers -----------------------------------------------------------

    def _read_set(self) -> DatasetInfo:
        node = self.trees["Set"].root
        a = node.attrs
        return DatasetInfo(a.get("ID", ""), a.get("Version", ""), a.get("Name", ""),
                           a.get("LongName", ""), dict(a))

    def _read_sheets(self) -> dict[str, dict]:
        sheets: dict[str, dict] = {}
        for sh in self.trees["Data"].root.find_all("Sheet"):
            defaults: dict[str, str] = {}
            parts: dict[str, dict[str, str]] = {}
            for child in sh.children:
                if child.name == "Defaults":
                    for d in child.children:
                        defaults.update(d.attrs)
                else:
                    parts[child.get("ID", "")] = dict(child.attrs)
            sheets[sh.get("ID", "")] = {
                "description": sh.get("Description", ""),
                "base_class": sh.get("BaseClass", ""),
                "defaults": defaults,
                "parts": parts,
            }
        return sheets

    def _read_folders(self) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Map item code -> folder name, and item code -> folder path."""
        folder_of: dict[str, str] = {}
        path_of: dict[str, list[str]] = {}

        def walk(node: tree.Node, path: list[str]) -> None:
            for child in node.children:
                if child.name == "Folder":
                    walk(child, path + [child.get("Description", "")])
                elif child.name == "Item":
                    code = child.get("ID", "")
                    folder_of.setdefault(code, path[-1] if path else "")
                    path_of.setdefault(code, path)

        root = self.trees["Folder"].root
        for fs in root.children:
            walk(fs, [])
        return folder_of, path_of

    def _read_stencils(self) -> dict[str, list[str]]:
        """Map item code -> stencil labels (Schablonen) that contain it."""
        out: dict[str, list[str]] = {}
        for st in self.trees["Package"].root.find_all("Stencil"):
            label = st.get("Label", "")
            for item in st.find_all("Item"):
                out.setdefault(item.get("ID", ""), [])
                if label not in out[item.get("ID", "")]:
                    out[item.get("ID", "")].append(label)
        return out

    def _read_symbols(self) -> list[Symbol]:
        graphic = self.trees["Graphic"].root
        files_3d: dict[str, list[str]] = {}
        items_2d = []
        for gi in graphic.find_all("GraphicItem"):
            item = gi.get("Item")
            if not item:
                continue
            if gi.get("Usage") == "3D" or gi.get("Type") == "3DGeo":
                if gi.get("GraphicFile"):
                    files_3d.setdefault(item, []).append(gi.get("GraphicFile"))
                continue
            items_2d.append(gi)

        symbols: list[Symbol] = []
        for gi in items_2d:
            item = gi.get("Item", "")
            sheet_id = gi.get("Sheet", "")
            sheet = self.sheets.get(sheet_id, {})
            part = sheet.get("parts", {}).get(item, {})
            attrs = dict(sheet.get("defaults", {}))
            attrs.update(part)
            name = gi.get("Description") or part.get("Description") or item
            kind = gi.get("Type", "")
            geo = None
            if gi.get("Geometry") and kind in ("Geometry", "Symbol"):
                try:
                    geo = parse_geometry(gi.get("Geometry"))
                except (ValueError, IndexError, TypeError):
                    # One broken graphic must not stop the whole dataset
                    geo = None
            elif kind == "Engine":
                # Parametric symbol: simplified preview from its parameters
                from ..render.engine import engine_geometry
                try:
                    geo = engine_geometry(gi.get("Content"), attrs)
                except (ValueError, IndexError, TypeError):
                    geo = None
            symbols.append(Symbol(
                dataset=self.info.id,
                item=item,
                graphic_id=gi.get("ID", ""),
                sheet=sheet_id,
                name=name,
                part_name=part.get("Description", ""),
                sheet_name=sheet.get("description", ""),
                folder=self.folders.get(item, ""),
                folder_path=self.folder_paths.get(item, []),
                stencils=self.stencils.get(item, []),
                kind=kind,
                usage=gi.get("Usage", ""),
                place_mode=gi.get("PlaceMode", ""),
                mounting=detect_mounting(gi.get("Description"), part.get("Description"),
                                         sheet.get("description"), self.folders.get(item)),
                geometry=geo,
                engine=gi.get("Content") if kind == "Engine" else None,
                lib_ref=f"{gi.get('Lib')}:{gi.get('Content')}" if gi.get("Lib") else None,
                files_3d=sorted(set(files_3d.get(item, []))),
                attributes=attrs,
            ))
        symbols.sort(key=lambda s: (_sort_key(s.sheet), _sort_key(s.item), s.graphic_id))
        # The datasets contain a few repeated graphic ids (e.g. 120-130 "Var. 1"
        # and "Var. 2" both as 2D-10). Number them so every symbol keeps a
        # unique key.
        seen: dict[str, int] = {}
        for sym in symbols:
            count = seen.get(sym.key, 0)
            seen[sym.key] = count + 1
            if count:
                sym.duplicate_no = count
        return symbols

    # -- helpers -----------------------------------------------------------

    def lib_file(self, name: str) -> bytes | None:
        """Raw bytes of a bundled .nsb symbol library (Lib/<name>.nsb)."""
        for key in (f"Lib/{name}.nsb", f"Lib/{name}"):
            if key in self._files:
                return self._files[key]
        return None
