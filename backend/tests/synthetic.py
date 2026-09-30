"""Build tiny Nova dataset archives (.nzp) for tests without real Trimble files."""

from __future__ import annotations

import zipfile
from pathlib import Path

from nova_legend.parser.tree import Node, serialize

CIRCLE = ('((1)(("")()(0)((1)(((Arc)((0;0.0025)(0.0025;0.0025)(0.0025;0.0025)(0)))))((0))((0))((0))))'
          '((1)(("NP0")(0;0.0025;0)))((0))(-0.0025;0;0.0025;0.005;1)')


def make_nzp(path: Path, dataset_id: str, items: list[tuple[str, str, str]]) -> Path:
    """items: (sheet, item code, description). One 2D graphic per item."""
    sheets: dict[str, list[tuple[str, str]]] = {}
    for sheet, code, desc in items:
        sheets.setdefault(sheet, []).append((code, desc))

    set_root = Node("DataSet", {"ID": dataset_id, "Name": dataset_id, "Version": "1.0.0",
                                "LongName": f"{dataset_id} Test"})
    graphic = Node("Root", {}, [Node("GraphicSet", {"ID": "Default"}, [Node("Graphic", {}, [
        Node("GraphicItem", {"ID": "2D-10", "Description": desc, "Type": "Geometry", "Usage": "I",
                             "PlaceMode": "W,Y", "Geometry": CIRCLE, "Sheet": sheet, "Item": code})
        for sheet, code, desc in items])])])
    data = Node("Root", {}, [Node("Data", {}, [
        Node("Sheet", {"ID": sheet, "Description": f"Blatt {sheet}", "BaseClass": "Bauteil"},
             [Node("Bauteil", {"ID": code, "Description": desc}) for code, desc in entries])
        for sheet, entries in sheets.items()])])
    folder = Node("Root", {}, [Node("FolderSet", {"ID": "Default"}, [
        Node("Folder", {"ID": sheet, "Description": f"Ordner {sheet}"},
             [Node("Item", {"Sheet": sheet, "ID": code}) for code, _ in entries])
        for sheet, entries in sheets.items()])])
    package = Node("Root", {}, [Node("PackageSet", {"ID": "Default"})])

    with zipfile.ZipFile(path, "w") as zf:
        for name, node in (("Set", set_root), ("Graphic", graphic), ("Data", data),
                           ("Folder", folder), ("Package", package)):
            zf.writestr(name, serialize(node))
    return path
