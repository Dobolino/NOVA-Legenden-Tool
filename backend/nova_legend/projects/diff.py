"""Compare two imports of the same floor.

Elements are matched by the stored source key. A reimport keeps that key, so a
switch that was there before stays the same row when its count changes.
Counts of 0 and missing rows are the same: the element is gone.
"""

from __future__ import annotations

KIND_ORDER = {"neu": 0, "geaendert": 1, "weg": 2}


def _kind(before: int, after: int) -> str | None:
    if before == after:
        return None
    if before == 0 and after > 0:
        return "neu"
    if after == 0 and before > 0:
        return "weg"
    return "geaendert"


def diff_counts(before: dict[str, int], after: dict[str, int]) -> list[dict]:
    """Rows whose count changed. ``before`` and ``after`` map a key to a count."""
    rows = []
    for key in set(before) | set(after):
        old = int(before.get(key) or 0)
        new = int(after.get(key) or 0)
        kind = _kind(old, new)
        if kind is None:
            continue
        rows.append({"key": key, "kind": kind, "before": old, "after": new, "delta": new - old})
    rows.sort(key=lambda row: (KIND_ORDER[row["kind"]], row["key"].lower()))
    return rows


def unchanged_count(before: dict[str, int], after: dict[str, int]) -> int:
    """Elements present with the same count above zero in both imports."""
    return sum(1 for key, old in before.items() if int(old or 0) > 0 and int(after.get(key) or 0) == int(old or 0))


def tally(rows: list[dict]) -> dict[str, int]:
    counts = {"neu": 0, "weg": 0, "geaendert": 0}
    for row in rows:
        counts[row["kind"]] += 1
    return counts
