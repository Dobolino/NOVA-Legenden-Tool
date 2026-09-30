"""Data model shared by all importers (DXF, DWG, N4D)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Found:
    """One kind of element found in a plan, with its count.

    ``source_key`` identifies the element independent of the plan. It is the
    key for remembered decisions (mappings), e.g. ``code:Trimble…V2.CH|90-30|Steckdose T13, UP``
    or ``name:gateway``.
    """

    source_key: str
    name: str                      # element name in the plan (block name, N4D name)
    count: int = 0
    dataset: str = ""              # dataset id if known
    item: str = ""                 # catalogue code if known
    sheet: str = ""                # number range if known (N4D)
    graphic_name: str = ""         # graphic description (DXF "Bez", N4D graphic name)
    graphic_id: str = ""           # N4D gives it directly
    layers: dict[str, int] = field(default_factory=dict)
    features: dict = field(default_factory=dict)   # geometry features for the matcher

    def add(self, layer: str) -> None:
        self.count += 1
        self.layers[layer] = self.layers.get(layer, 0) + 1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Layer:
    name: str
    color: str = ""                # "#rrggbb"
    linetype: str = ""


@dataclass
class ImportResult:
    format: str                    # dxf, dwg, n4d
    found: list[Found] = field(default_factory=list)
    layers: list[Layer] = field(default_factory=list)
    ignored: dict[str, int] = field(default_factory=dict)   # non-symbol elements by name
    info: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
