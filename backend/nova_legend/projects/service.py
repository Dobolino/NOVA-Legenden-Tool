"""Project evaluation: overall list per floor, unknown elements, layers."""

from __future__ import annotations

from collections import defaultdict

from ..categories.store import auto_categories
from ..importer.model import Found
from ..importer.recognize import LibraryIndex, resolve
from ..matcher.suggest import suggest
from .diff import diff_counts, tally, unchanged_count
from .store import Project


def _found_from_row(row: dict) -> Found:
    return Found(row["source_key"], row["name"] or "", row["count"] or 0, row["dataset"] or "",
                 row["item"] or "", row["sheet"] or "", row["graphic_name"] or "",
                 row["graphic_id"] or "", row["layers"] or {}, row["features"] or {})


def _import_reason(name: str) -> str:
    low = name.lower()
    if "leitung" in low:
        return "Leitung"
    if low.startswith("maß") or low.startswith("mass") or "bemass" in low:
        return "Mass"
    if "beschrift" in low or low in {"text", "bezeichnung", "kurzbezeichnung"}:
        return "Beschriftung"
    if low.startswith("plankopf") or low.startswith("planrahmen"):
        return "Plankopf"
    return "kein Apparat"


class ProjectEvaluator:
    def __init__(self, library, company, family_options):
        self.library = library
        self.company = company
        self.options = family_options
        self.index = LibraryIndex(library.symbols(), library.datasets())
        self.families = library.families(family_options)
        self.family_of: dict[str, str] = {}
        for fam_id, fam in self.families.items():
            for m in fam.members:
                self.family_of[m.key] = fam_id
        self.categories = company.categories()
        self.assignments = company.assignments()
        self.fills = company.fill_settings()
        self.mappings = company.mappings()

    def family_categories(self, fam) -> list[str]:
        manual = self.assignments.get(fam.key)
        if manual:
            return manual
        rep = fam.representative
        return auto_categories(rep.sheet, rep.name, self.categories, rep.dataset)[0]

    def evaluate(self, project: Project) -> dict:
        plans = project.plans()
        per_plan = project.current_elements()
        rows: dict[str, dict] = {}
        unknown: dict[str, dict] = {}
        ignored: dict[str, dict] = {}
        stats = defaultdict(int)
        self.layer_usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for plan in plans:
            pid = plan["id"]
            for el in per_plan.get(pid, []):
                found = _found_from_row(el)
                res = resolve(found, self.index, self.mappings)
                stats[res.status] += found.count
                if res.symbol_key:
                    sym = self.index.by_key[res.symbol_key]
                    fam_id = self.family_of.get(sym.key, sym.key)
                    fam = self.families.get(fam_id)
                    # One row per function: the same family in V1 and V2 is merged
                    row_key = fam.key if fam else sym.key
                    if row_key not in rows:
                        rep = fam.representative if fam else sym
                        show_fill = self.fills.get(fam.key, True) if fam else True
                        rows[row_key] = {
                            "family_id": fam_id,
                            "family_key": row_key,
                            "symbol_key": rep.key,
                            "title": fam.title if fam else sym.name,
                            "item": rep.item,
                            "dataset": rep.dataset,
                            "svg": rep.svg if show_fill or not rep.has_fill else rep.svg_nofill,
                            "kind": rep.kind,
                            "categories": self.family_categories(fam) if fam else [],
                            "counts": defaultdict(int),
                            "mountings": defaultdict(int),
                            "names": set(),
                            "methods": set(),
                            "sources": set(),
                            "total": 0,
                            "datasets": set(),
                        }
                    row = rows[row_key]
                    row["datasets"].add(sym.dataset)
                    row["counts"][pid] = row["counts"].get(pid, 0) + found.count
                    row["total"] += found.count
                    if found.count:
                        row["mountings"][sym.mounting or "-"] += found.count
                        for layer, amount in found.layers.items():
                            for cid in row["categories"]:
                                self.layer_usage[cid][layer] += amount
                    if found.name and found.name.lower() != (row["title"] or "").lower():
                        row["names"].add(found.name)
                    row["methods"].add(res.method)
                    row["sources"].add(found.source_key)
                elif res.status == "unbekannt":
                    u = unknown.setdefault(found.source_key, {
                        "source_key": found.source_key, "name": found.name, "item": found.item,
                        "graphic_name": found.graphic_name, "dataset": found.dataset,
                        "counts": defaultdict(int), "layers": defaultdict(int), "total": 0})
                    u["counts"][pid] += found.count
                    u["total"] += found.count
                    for layer, n in found.layers.items():
                        u["layers"][layer] += n
                else:
                    g = ignored.setdefault(found.source_key, {
                        "source_key": found.source_key, "name": found.name, "reason": res.method,
                        "manual": res.method == "manuell", "total": 0})
                    g["total"] += found.count

        order = {c["id"]: i for i, c in enumerate(self.categories)}
        out_rows = []
        for row in rows.values():
            row["counts"] = dict(row["counts"])
            row["mountings"] = dict(row["mountings"])
            row["names"] = sorted(row["names"])
            row["methods"] = sorted(row["methods"])
            row["sources"] = sorted(row["sources"])
            row["datasets"] = sorted(row["datasets"], key=lambda d: (".V2." not in d, d))
            out_rows.append(row)
        out_rows.sort(key=lambda r: (min((order.get(c, 999) for c in r["categories"]), default=999),
                                     r["title"].lower()))
        out_unknown = []
        for u in unknown.values():
            u["counts"] = dict(u["counts"])
            u["layers"] = dict(u["layers"])
            out_unknown.append(u)
        out_unknown.sort(key=lambda u: -u["total"])
        for name, count in project.import_ignored().items():
            ignored[f"import:{name}"] = {
                "source_key": f"import:{name}", "name": name, "reason": _import_reason(name),
                "manual": False, "total": count}
        return {
            "plans": plans,
            "rows": out_rows,
            "unknown": out_unknown,
            "ignored": sorted(ignored.values(), key=lambda g: -g["total"]),
            "stats": dict(stats),
        }

    # -- suggestions ---------------------------------------------------------------

    def suggestions(self, project: Project, source_key: str, limit: int = 8) -> list[dict]:
        found = None
        for elements in project.current_elements().values():
            for el in elements:
                if el["source_key"] == source_key:
                    found = _found_from_row(el)
                    break
            if found:
                break
        if found is None:
            raise KeyError(source_key)
        layer_category: dict[str, set[str]] = defaultdict(set)
        for c in self.categories:
            if c.get("layer"):
                layer_category[c["layer"]].add(c["id"])
        features = self.library.geometry_features()

        def feature_of(sym):
            return features.get(sym.key) or {}

        def category_of(sym):
            fam = self.families.get(self.family_of.get(sym.key, ""))
            return self.family_categories(fam) if fam else []

        symbols = [s for s in self.library.symbols() if not s.sheet.startswith("Label_")]
        return suggest(found, symbols, feature_of, layer_category, category_of, limit)

    # -- version comparison --------------------------------------------------------

    def describe_element(self, row: dict | None) -> dict:
        """Library title for one stored element, for the changes list."""
        if not row:
            return {"title": "", "name": "", "item": "", "svg": "", "status": ""}
        found = _found_from_row(row)
        res = resolve(found, self.index, self.mappings)
        title = found.name or found.source_key
        item = found.item
        svg = ""
        if res.symbol_key:
            sym = self.index.by_key.get(res.symbol_key)
            if sym is not None:
                fam = self.families.get(self.family_of.get(sym.key, ""))
                if fam is not None:
                    title = fam.title
                    item = item or fam.representative.item
                    show_fill = self.fills.get(fam.key, True)
                    rep = fam.representative
                    svg = rep.svg if show_fill or not rep.has_fill else rep.svg_nofill
                else:
                    title = sym.name
                    item = item or sym.item
                    svg = sym.svg
        return {"title": title, "name": found.name, "item": item, "svg": svg, "status": res.status}

    def compare_plan(self, project: Project, plan: dict, older: int | None, newer: int | None) -> dict:
        """Changes between two versions of one floor. None means there is only one import."""
        versions = project.versions(plan["id"])
        base = {"plan_id": plan["id"], "name": plan["name"], "versions": versions,
                "older": older, "newer": newer, "comparable": older is not None and newer is not None,
                "changes": [], "ignored_changes": [], "unchanged": 0,
                "summary": {"neu": 0, "weg": 0, "geaendert": 0}}
        if older is None or newer is None:
            return base
        before_rows = {row["source_key"]: row for row in project.elements(older)}
        after_rows = {row["source_key"]: row for row in project.elements(newer)}
        before_counts = {key: int(row["count"] or 0) for key, row in before_rows.items()}
        after_counts = {key: int(row["count"] or 0) for key, row in after_rows.items()}
        changes = []
        for row in diff_counts(before_counts, after_counts):
            shown = after_rows.get(row["key"]) or before_rows.get(row["key"])
            changes.append({**self.describe_element(shown), "source_key": row["key"],
                            "kind": row["kind"], "before": row["before"], "after": row["after"],
                            "delta": row["delta"]})
        changes.sort(key=lambda row: (0 if row["kind"] == "neu" else 1 if row["kind"] == "geaendert" else 2,
                                     (row["title"] or "").lower()))
        ignored = []
        for row in diff_counts(project.version_ignored(older), project.version_ignored(newer)):
            ignored.append({"name": row["key"], "reason": _import_reason(row["key"]),
                            "kind": row["kind"], "before": row["before"], "after": row["after"],
                            "delta": row["delta"]})
        ignored.sort(key=lambda row: (0 if row["kind"] == "neu" else 1 if row["kind"] == "geaendert" else 2,
                                     row["name"].lower()))
        base.update(changes=changes, ignored_changes=ignored,
                    unchanged=unchanged_count(before_counts, after_counts),
                    summary=tally(changes))
        return base
