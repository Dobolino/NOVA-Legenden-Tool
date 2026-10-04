"""Floor names taken from a plan file name (EG, 1. OG, UG, …)."""

from __future__ import annotations

import re
from pathlib import Path

_NUMBERED = re.compile(r"(?i)(\d+)\s*\.\s*(OG|UG|DG|STOCK)")
_BARE = re.compile(r"(?i)(?:^|[_\s.-])(EG|UG|DG|OG)(?:$|[_\s.-])")


def floor_name_from_filename(filename: str) -> str | None:
    """Return a floor label such as «1. OG» or «EG», or None if the name has none.

    «3_1.OG.dxf» becomes «1. OG». A numbered floor wins over a bare OG/EG.
    """
    stem = Path(filename).stem
    numbered = _NUMBERED.search(stem)
    if numbered:
        kind = numbered.group(2)
        kind = "Stock" if kind.lower() == "stock" else kind.upper()
        return f"{int(numbered.group(1))}. {kind}"
    bare = _BARE.search(stem)
    if bare:
        return bare.group(1).upper()
    return None


def resolve_plan_name(filename: str, given: str) -> str:
    """Use the typed name, unless it is empty or just the file stem and a floor is recognisable."""
    given = (given or "").strip()
    stem = Path(filename).stem
    guess = floor_name_from_filename(filename)
    if guess and given in ("", stem):
        return guess
    return given or guess or stem or "Geschoss"
