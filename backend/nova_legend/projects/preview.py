"""Import preview: what a new plan file changes on its floor, before it is stored.

The preview compares the floor as the overall list shows it now with the floor
after the import (rows merged exactly like ``store_import`` does). Warnings
point at changes that often mean a wrong or incomplete file: many apparatus
fewer, kinds that disappear, a kind that loses most of its count, new unknown
elements, another file format, or the very same file again.
"""

from __future__ import annotations

KIND_ORDER = {"weg": 0, "geaendert": 1, "neu": 2}

# thresholds for warnings
TOTAL_DROP_SHARE = 0.10      # 10 % fewer apparatus on the floor ...
TOTAL_DROP_MIN = 5           # ... and at least 5
ROW_DROP_SHARE = 0.5         # a kind loses half of its count ...
ROW_DROP_MIN = 3             # ... and at least 3


def compare(before: dict, after: dict) -> dict:
    """``before`` and ``after`` come from ProjectEvaluator.summarize."""
    changes, unchanged = [], 0
    for key in set(before["rows"]) | set(after["rows"]):
        b = before["rows"].get(key)
        a = after["rows"].get(key)
        old, new = (b or {}).get("count", 0), (a or {}).get("count", 0)
        info = a or b
        if old == new:
            if new:
                unchanged += 1
            continue
        kind = "neu" if old == 0 else "weg" if new == 0 else "geaendert"
        changes.append({"key": key, "title": info["title"], "item": info["item"], "svg": info["svg"],
                        "kind": kind, "before": old, "after": new, "delta": new - old})
    # losses first: they are what needs a look
    changes.sort(key=lambda c: (KIND_ORDER[c["kind"]], c["delta"], c["title"].lower()))
    total_before = sum(r["count"] for r in before["rows"].values())
    total_after = sum(r["count"] for r in after["rows"].values())
    new_unknown = [{"name": u["name"], "count": u["count"]} for k, u in after["unknown"].items()
                   if u["count"] and not before["unknown"].get(k, {}).get("count")]
    return {
        "changes": changes,
        "unchanged": unchanged,
        "summary": {k: sum(1 for c in changes if c["kind"] == k) for k in ("neu", "weg", "geaendert")},
        "total_before": total_before,
        "total_after": total_after,
        "kinds_after": sum(1 for r in after["rows"].values() if r["count"]),
        "unknown_after": sum(u["count"] for u in after["unknown"].values()),
        "new_unknown": sorted(new_unknown, key=lambda u: -u["count"]),
    }


def warnings(result: dict, existing: bool, old_format: str = "", new_format: str = "",
             same_file: bool = False) -> list[dict]:
    """Notes before the import replaces the floor. "warn" (needs a confirmation) only
    for losses on an existing floor; "info" for the rest."""
    out: list[dict] = []
    if same_file:
        out.append({"level": "info", "text": "Gleiche Datei wie der aktuelle Import. Es ändert sich nichts."})
    if existing:
        tb, ta = result["total_before"], result["total_after"]
        drop = tb - ta
        if tb and drop >= TOTAL_DROP_MIN and drop / tb >= TOTAL_DROP_SHARE:
            out.append({"level": "warn",
                        "text": f"{drop} Apparate weniger als bisher ({round(100 * drop / tb)} %)."})
        gone = [c for c in result["changes"] if c["kind"] == "weg"]
        if gone:
            names = ", ".join(f"«{c['title']}»" for c in gone[:3]) + (" …" if len(gone) > 3 else "")
            out.append({"level": "warn",
                        "text": f"{len(gone)} {'Art fällt' if len(gone) == 1 else 'Arten fallen'} ganz weg: {names}. "
                                "Die Zeilen bleiben mit Anzahl 0 stehen."})
        halved = [c for c in result["changes"] if c["kind"] == "geaendert" and -c["delta"] >= ROW_DROP_MIN
                  and -c["delta"] / c["before"] >= ROW_DROP_SHARE]
        if halved:
            names = ", ".join(f"«{c['title']}» {c['before']} → {c['after']}" for c in halved[:3])
            out.append({"level": "warn", "text": f"Stark weniger: {names}{' …' if len(halved) > 3 else ''}."})
        if old_format and new_format and old_format != new_format:
            out.append({"level": "info",
                        "text": f"Bisher {old_format.upper()}, neu {new_format.upper()}. Zeilen werden über den "
                                "Katalogcode zugeordnet, was nicht sicher passt, wird neu."})
    unknown = sum(u["count"] for u in result["new_unknown"])
    if unknown:
        out.append({"level": "info",       # nothing is lost: they are assigned after the import
                    "text": f"{unknown} neue unbekannte Elemente ({len(result['new_unknown'])} Arten). "
                            "Du ordnest sie nach dem Import unter «Unbekannt» zu."})
    return out
