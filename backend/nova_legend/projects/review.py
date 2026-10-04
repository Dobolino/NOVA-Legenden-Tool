"""Release check of a project: what is open before a legend is handed on.

One list of checks, each with a level:

    block   must be fixed: the legend would be wrong or incomplete
    warn    should be looked at: the legend may be fine, a person decides
    ok      nothing to do

Every check names the tab where it is fixed (``target``) and lists up to
``LIMIT`` concerned entries. The checks only read the evaluation, the stored
legend and the library; nothing is changed.
"""

from __future__ import annotations

LIMIT = 30
LEVEL_ORDER = {"block": 0, "warn": 1, "ok": 2}


def _check(cid: str, title: str, target: str, items: list[dict], level_if_any: str,
           detail_any: str, detail_none: str) -> dict:
    return {"id": cid, "title": title, "target": target, "count": len(items),
            "level": level_if_any if items else "ok",
            "detail": detail_any if items else detail_none, "items": items[:LIMIT]}


def build_review(evaluation: dict, category_colors: list[dict], legend: dict | None,
                 covered: set[str], has_drawing) -> dict:
    """``evaluation`` is ProjectEvaluator.evaluate(); ``legend`` the stored legend
    ({doc, updated_at}) or None; ``covered`` the family keys the general part shows;
    ``has_drawing(symbol_key)`` tells whether the library can draw a symbol."""
    rows = [r for r in evaluation["rows"] if r["total"] > 0]
    by_family = {r["family_key"]: r for r in evaluation["rows"]}
    checks: list[dict] = []

    unknown = [{"title": u["name"] or u["source_key"], "detail": f"{u['total']}×"}
               for u in evaluation["unknown"] if u["total"] > 0]
    checks.append(_check("unknown", "Unbekannte Elemente", "unknown", unknown, "block",
                         "Ohne Symbol fehlen sie in der Legende. Zuordnen oder als «kein Apparat» markieren.",
                         "Jedes Element der Pläne hat ein Symbol oder ist bewusst nicht berücksichtigt."))

    name_only = [{"title": r["title"], "detail": f"{r['total']}× · im Plan: {', '.join(r['names'][:2]) or r['title']}"}
                 for r in rows if r["methods"] == ["Name"]]
    checks.append(_check("name_only", "Nur über den Namen erkannt", "list", name_only, "warn",
                         "Ohne Katalogcode im Plan. Prüfe, ob das Symbol stimmt.",
                         "Alle Apparate sind über Katalogcode oder deine Zuordnung erkannt."))

    choose = [{"title": c["title"], "detail": "keine passende Ebene in den Plänen"}
              for c in category_colors if c.get("state") == "waehlen"]
    checks.append(_check("layers", "Ebene wählen", "layers", choose, "warn",
                         "Für diese Kategorien fehlt die Ebene, deren Farbe die Legende übernimmt.",
                         "Jede verwendete Kategorie hat ihre Ebene."))

    if not legend:
        checks.append({"id": "legend", "title": "Legende", "target": "legend", "count": 1, "level": "block",
                       "detail": "Für dieses Projekt gibt es noch keine Legende.", "items": []})
    else:
        doc = legend["doc"]
        items = [(b, it) for b in doc["blocks"] for it in b["items"]]
        visible = [(b, it) for b, it in items if not it.get("hidden")]
        shown = {it["family_key"] for _, it in visible if it.get("family_key")}

        missing = [{"title": r["title"], "detail": f"{r['total']}×"}
                   for r in rows if r["family_key"] not in shown and r["family_key"] not in covered]
        checks.append(_check("missing", "Fehlt in der Legende", "legend", missing, "block",
                             "Diese Apparate kommen in den Plänen vor, die Legende zeigt sie nicht.",
                             "Die Legende zeigt jeden Apparat der Pläne (oder der Allgemeinteil zeigt ihn)."))

        no_drawing = [{"title": it["text"] or it["symbol_key"], "detail": b["title"]}
                      for b, it in visible if it["kind"] == "symbol" and not has_drawing(it["symbol_key"])]
        checks.append(_check("drawing", "Symbol ohne Zeichnung", "legend", no_drawing, "warn",
                             "Die Bibliothek hat für diese Symbole keine Zeichnung: Vorschau und DXF zeigen einen Platzhalter.",
                             "Jedes Symbol der Legende hat eine Zeichnung."))

        seen: set[str] = set()
        doubles = []
        for b, it in visible:
            key = it.get("family_key") or it.get("symbol_key")
            if it["kind"] != "symbol" or not key:
                continue
            if key in seen:
                doubles.append({"title": it["text"], "detail": b["title"]})
            seen.add(key)
        checks.append(_check("duplicates", "Doppelt in der Legende", "legend", doubles, "warn",
                             "Dasselbe Symbol steht mehrmals in der Legende.", "Kein Symbol steht doppelt."))

        stale = [{"title": it["text"], "detail": b["title"]} for b, it in visible
                 if it["kind"] == "symbol" and it.get("family_key")
                 and not (by_family.get(it["family_key"]) or {}).get("total")]
        checks.append(_check("stale", "Nicht mehr in den Plänen", "legend", stale, "warn",
                             "Die Legende zeigt Apparate, die in den aktuellen Plänen nicht vorkommen.",
                             "Jeder Eintrag der Legende kommt in den Plänen vor."))

        imports = [p["imported_at"] for p in evaluation["plans"] if p.get("imported_at")]
        newest = max(imports) if imports else ""
        outdated = [{"title": "Letzter Import", "detail": newest}] if newest and legend.get("updated_at", "") < newest else []
        checks.append(_check("outdated", "Legende älter als der letzte Import", "legend", outdated, "warn",
                             "Nach dem letzten Planimport wurde die Legende nicht mehr bearbeitet. Kurz durchsehen.",
                             "Die Legende ist nach dem letzten Import bearbeitet worden."))

    checks.sort(key=lambda c: LEVEL_ORDER[c["level"]])
    blocks = sum(1 for c in checks if c["level"] == "block")
    warns = sum(1 for c in checks if c["level"] == "warn")
    return {"ready": blocks == 0, "blocks": blocks, "warns": warns, "checks": checks}
