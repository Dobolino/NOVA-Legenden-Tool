"""FastAPI application: REST API for the UI and static hosting of the UI build."""

from __future__ import annotations

import threading
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config, updater
from ..categories.store import CompanyStore, auto_categories
from ..library.families import FamilyOptions
from ..library.store import Library
from ..render.svg import render_svg
from ..parser.geometry import SymbolGeometry, Primitive


class AppState:
    """Holds settings and the two stores. Rebuilt when settings change."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.settings = config.load_settings()
        self.sync_report: dict = {}
        self._open_stores()

    def _open_stores(self) -> None:
        self.library = Library(config.local_home() / "library.sqlite")
        try:
            self.company = CompanyStore(self.settings.company_db)
            self.company_error = ""
        except Exception as exc:  # noqa: BLE001 - network folder may be unreachable
            self.company_error = f"Firmenordner nicht erreichbar: {exc}. Lokale Kopie wird genutzt."
            self.company = CompanyStore(config.resolve_company_db(config.local_home()))

    def first_start(self) -> None:
        """Search datasets if none are configured, then sync the library."""
        with self.lock:
            if not self.settings.dataset_paths:
                found = config.find_datasets()
                if found:
                    self.settings.dataset_paths = found
                    config.save_settings(self.settings)
            self.sync_report = self.library.sync(self.settings.dataset_paths)

    def apply_settings(self, values: dict) -> None:
        with self.lock:
            data = asdict(self.settings)
            data.update({k: v for k, v in values.items() if k in data and v is not None})
            self.settings = config.Settings(**data)
            config.save_settings(self.settings)
            self._open_stores()
            self.sync_report = self.library.sync(self.settings.dataset_paths)

    def family_options(self) -> FamilyOptions:
        opts = self.company.options()
        return FamilyOptions(bool(opts["merge_labels"]), bool(opts["merge_orientation"]))


# -- request models --------------------------------------------------------------

class SettingsIn(BaseModel):
    dataset_paths: list[str] | None = None
    company_folder: str | None = None
    projects_folder: str | None = None
    nova_version: str | None = None
    oda_path: str | None = None


class CategoryIn(BaseModel):
    title: str | None = None
    parent: str | None = None
    layer: str | None = None
    columns: int | None = None
    spacing: float | None = None
    hidden: bool | None = None
    sheets: list[str] | None = None


class AssignIn(BaseModel):
    categories: list[str] | None = None


class FillIn(BaseModel):
    show_fill: bool | None = None   # None = default (fill shown)


class ReorderIn(BaseModel):
    ids: list[str]


# -- app factory -----------------------------------------------------------------

def create_app(state: AppState | None = None, ui_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="NOVA-Legenden", version=config.APP_VERSION)
    st = state or AppState()
    app.state.nova = st
    if state is None:
        st.first_start()

    def family_categories(fam, categories, assignments) -> tuple[list[str], str]:
        manual = assignments.get(fam.key)
        if manual:
            return manual, "manuell"
        rep = fam.representative
        return auto_categories(rep.sheet, rep.name, categories, rep.dataset)

    def family_entry(fam_id: str, fam, categories, assignments, fills) -> dict:
        cats, source = family_categories(fam, categories, assignments)
        rep = fam.representative
        show_fill = fills.get(fam.key, True)
        return {
            "id": fam_id,
            "key": fam.key,
            "title": fam.title,
            "dataset": rep.dataset,
            "representative": _symbol_brief(rep, show_fill),
            "mountings": fam.mountings,
            "variant_count": len(fam.members),
            "categories": cats,
            "category_source": source,
            "conflicts": fam.conflicts,
            "has_fill": any(m.has_fill for m in fam.members),
            "show_fill": show_fill,
        }

    # -- status & settings -------------------------------------------------------

    @app.get("/api/status")
    def status() -> dict:
        return {
            "version": config.APP_VERSION,
            "version_label": updater.current_label(),
            "user": config.current_user(),
            "settings": asdict(st.settings),
            "company_db": str(st.company.db_path),
            "company_error": st.company_error,
            "datasets": st.library.datasets(),
            "symbol_count": len(st.library.symbols()),
            "sync": st.sync_report,
            "oda": st.settings.oda_path or config.find_oda_converter(),
            "local_home": str(config.local_home()),
        }

    @app.put("/api/settings")
    def put_settings(body: SettingsIn) -> dict:
        st.apply_settings(body.model_dump())
        return status()

    @app.post("/api/settings/search-datasets")
    def search_datasets() -> dict:
        known = {d["id"] for d in st.library.datasets()}
        return {"found": config.find_datasets(skip_ids=known),
                "folders": config.DATASET_SEARCH_ROOTS}

    @app.post("/api/library/sync")
    def sync() -> dict:
        with st.lock:
            st.sync_report = st.library.sync(st.settings.dataset_paths)
        return st.sync_report

    # -- program update ------------------------------------------------------------

    @app.get("/api/update/check")
    def update_check() -> dict:
        return updater.check().to_dict()

    @app.post("/api/update/install")
    def update_install() -> dict:
        info = updater.check()
        if not info.available:
            raise HTTPException(400, info.message or "Kein Update verfügbar")
        if not info.can_install:
            raise HTTPException(400, info.message)
        try:
            setup = updater.download(info)
        except Exception as exc:  # noqa: BLE001 - report download problems
            raise HTTPException(502, f"Download fehlgeschlagen: {exc}") from None
        updater.install(setup, getattr(app.state, "shutdown", lambda: None))
        return {"ok": True, "message": "Update wird installiert. Das Programm startet danach neu."}

    # -- options (company wide) ----------------------------------------------------

    @app.get("/api/options")
    def get_options() -> dict:
        return st.company.options()

    @app.put("/api/options")
    def put_options(body: dict) -> dict:
        return st.company.set_options(body)

    # -- library -------------------------------------------------------------------

    @app.get("/api/library/families")
    def families(q: str = "", category: str = "", dataset: str = "", mounting: str = "",
                 all_variants: bool = False, limit: int = 5000) -> dict:
        categories = st.company.categories()
        assignments = st.company.assignments()
        fills = st.company.fill_settings()
        fams = st.library.families(st.family_options())
        words = [w for w in q.lower().split() if w]
        items = []
        for fam_id, fam in fams.items():
            rep = fam.representative
            if dataset and rep.dataset != dataset:
                continue
            entry = family_entry(fam_id, fam, categories, assignments, fills)
            if category and category not in entry["categories"]:
                continue
            members = fam.members if all_variants else [rep]
            for sym in members:
                if mounting:
                    # Variant list: the symbol itself. Family list: any member.
                    if all_variants and (sym.mounting or "-") != mounting:
                        continue
                    if not all_variants and mounting not in fam.mountings:
                        continue
                if words:
                    # Variant list: search the variant itself. Family list: search
                    # name and catalogue code of every member (e.g. the AP code).
                    searched = [sym] if all_variants else fam.members
                    hay = " ".join([fam.title] + [
                        f"{m.name} {m.item} {m.folder} {m.part_name}" for m in searched]).lower()
                    if not all(w in hay for w in words):
                        continue
                if all_variants:
                    items.append({**entry, "id": f"{fam_id}#{sym.key}",
                                  "title": sym.name,
                                  "representative": _symbol_brief(sym, entry["show_fill"]),
                                  "is_representative": sym is rep})
                else:
                    items.append({**entry, "is_representative": True})
        total = len(items)
        return {"total": total, "items": items[:limit]}

    @app.get("/api/library/family")
    def family(id: str) -> dict:  # noqa: A002 - query name used by the UI
        fams = st.library.families(st.family_options())
        fam = fams.get(id.split("#")[0])
        if not fam:
            raise HTTPException(404, "Familie nicht gefunden")
        entry = family_entry(id.split("#")[0], fam, st.company.categories(),
                             st.company.assignments(), st.company.fill_settings())
        entry["members"] = [{**_symbol_brief(m, entry["show_fill"]),
                             "is_representative": m is fam.representative} for m in fam.members]
        return entry

    @app.get("/api/library/symbol")
    def symbol(key: str, fill: bool = True) -> dict:
        detail = st.library.symbol_detail(key)
        if not detail:
            raise HTTPException(404, "Symbol nicht gefunden")
        geo = detail.pop("geometry")
        detail["svg_points"] = _svg_with_points(geo, fill) if geo else ""
        detail["stats"] = _stats(geo)
        return detail

    @app.put("/api/library/family/categories")
    def assign(id: str, body: AssignIn) -> dict:  # noqa: A002
        fams = st.library.families(st.family_options())
        fam = fams.get(id.split("#")[0])
        if not fam:
            raise HTTPException(404, "Familie nicht gefunden")
        known = {c["id"] for c in st.company.categories()}
        unknown = [c for c in (body.categories or []) if c not in known]
        if unknown:
            raise HTTPException(400, f"Unbekannte Kategorie: {', '.join(unknown)}")
        st.company.assign(fam.key, body.categories)
        return family(id)

    @app.put("/api/library/family/fill")
    def set_fill(id: str, body: FillIn) -> dict:  # noqa: A002
        fams = st.library.families(st.family_options())
        fam = fams.get(id.split("#")[0])
        if not fam:
            raise HTTPException(404, "Familie nicht gefunden")
        st.company.set_fill(fam.key, body.show_fill)
        return family(id)

    # -- categories ----------------------------------------------------------------

    @app.get("/api/categories")
    def categories(dataset: str = "") -> dict:
        """Categories with the number of families. With ``dataset`` only that
        dataset is counted, so the numbers match the visible tiles."""
        cats = st.company.categories()
        assignments = st.company.assignments()
        counts = {c["id"]: 0 for c in cats}
        for fam in st.library.families(st.family_options()).values():
            if dataset and fam.representative.dataset != dataset:
                continue
            for cid in family_categories(fam, cats, assignments)[0]:
                if cid in counts:
                    counts[cid] += 1
        for c in cats:
            c["family_count"] = counts[c["id"]]
        return {"items": cats}

    @app.post("/api/categories")
    def create_category(body: CategoryIn) -> dict:
        if not body.title or not body.title.strip():
            raise HTTPException(400, "Titel fehlt")
        return st.company.create_category(body.title.strip(), body.parent, body.layer or "")

    @app.put("/api/categories/{cat_id}")
    def update_category(cat_id: str, body: CategoryIn) -> dict:
        try:
            # Only fields the client sent. An explicit "parent": null makes the
            # category a main category again; null for other fields is ignored.
            values = {k: v for k, v in body.model_dump(exclude_unset=True).items()
                      if v is not None or k == "parent"}
            if values.get("parent") == cat_id:
                raise HTTPException(400, "Eine Kategorie kann nicht unter sich selbst liegen")
            return st.company.update_category(cat_id, values)
        except KeyError:
            raise HTTPException(404, "Kategorie nicht gefunden") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.delete("/api/categories/{cat_id}")
    def delete_category(cat_id: str) -> dict:
        try:
            st.company.delete_category(cat_id)
        except KeyError:
            raise HTTPException(404, "Kategorie nicht gefunden") from None
        return {"ok": True}

    @app.post("/api/categories/reorder")
    def reorder(body: ReorderIn) -> dict:
        return {"items": st.company.reorder(body.ids)}

    @app.post("/api/categories/reset")
    def reset() -> dict:
        return {"items": st.company.reset_defaults()}

    from .projects import register as register_projects
    register_projects(app, st)

    # -- UI --------------------------------------------------------------------------

    ui = ui_dir or (config.resource_dir() / "ui" / "dist")
    if (ui / "index.html").exists():
        app.mount("/", StaticFiles(directory=ui, html=True), name="ui")
    else:
        @app.get("/", response_class=HTMLResponse)
        def no_ui() -> str:
            return ("<h1>NOVA-Legenden</h1><p>Die Oberfläche ist nicht gebaut. "
                    "Im Ordner ui: <code>npm install</code> und <code>npm run build</code>.</p>")
    return app


def _symbol_brief(sym, show_fill: bool = True) -> dict:
    return {
        "key": sym.key, "name": sym.name, "item": sym.item, "graphic_id": sym.graphic_id,
        "dataset": sym.dataset, "sheet": sym.sheet, "folder": sym.folder,
        "mounting": sym.mounting, "label_variant": sym.label_variant,
        "orientation": sym.orientation, "kind": sym.kind,
        "svg": sym.svg if show_fill or not sym.has_fill else sym.svg_nofill,
        "has_fill": sym.has_fill,
    }


def _geometry_from_dict(geo: dict) -> SymbolGeometry:
    return SymbolGeometry(
        primitives=[Primitive(**p) for p in geo["primitives"]],
        points=geo.get("points") or {}, cpoints=geo.get("cpoints") or {},
        bbox=geo.get("bbox"), groups=geo.get("groups") or [], warnings=geo.get("warnings") or [])


def _svg_with_points(geo: dict, show_fill: bool = True) -> str:
    g = _geometry_from_dict(geo)
    return render_svg(g, None, show_points=True, show_fill=show_fill) if g.primitives else ""


def _stats(geo: dict | None) -> dict:
    if not geo:
        return {}
    out: dict[str, int] = {}
    for p in geo["primitives"]:
        out[p["kind"]] = out.get(p["kind"], 0) + 1
    return out
