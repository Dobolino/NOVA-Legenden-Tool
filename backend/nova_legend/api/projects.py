"""REST routes for projects, plans, import and element mappings."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from .. import config
from ..importer.dwg import ConverterMissing, read_dwg
from ..importer.dxf import read_dxf
from ..importer.n4d import read_n4d
from ..importer.recognize import IGNORE
from ..projects.colors import category_state, category_usage, pick_category_layer
from ..projects.diff import diff_counts, tally
from ..projects.floors import resolve_plan_name
from ..projects.service import ProjectEvaluator
from ..projects.store import ProjectManager, export_filename

FORMATS = {".dxf": "dxf", ".dwg": "dwg", ".n4d": "n4d"}


class ProjectIn(BaseModel):
    name: str
    project_number: str = ""
    nova_version: str = "19.2"
    template: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    project_number: str | None = None
    nova_version: str | None = None
    use_as_template: bool | None = None


class CopyIn(BaseModel):
    name: str = ""


class PlanUpdate(BaseModel):
    name: str | None = None


class ReorderPlans(BaseModel):
    ids: list[int]


class CategoryLayerIn(BaseModel):
    category_id: str
    layer: str | None = None


class SourcesIn(BaseModel):
    source_keys: list[str]


class MappingIn(BaseModel):
    source_key: str
    symbol_key: str | None = None      # None = forget, "__ignore__" = not a symbol
    name: str = ""


def register(app: FastAPI, st) -> None:
    def manager() -> ProjectManager:
        folder = st.settings.projects_folder or config.DEFAULT_PROJECTS_FOLDER
        return ProjectManager(Path(folder))

    def project(project_id: str):
        try:
            return manager().get(project_id)
        except KeyError:
            raise HTTPException(404, "Projekt nicht gefunden") from None

    def evaluator() -> ProjectEvaluator:
        return ProjectEvaluator(st.library, st.company, st.family_options())

    def _change_summary(p, plan_id: int) -> dict | None:
        versions = p.versions(plan_id)
        if len(versions) < 2:
            return None
        before = {row["source_key"]: int(row["count"] or 0) for row in p.elements(versions[1]["id"])}
        after = {row["source_key"]: int(row["count"] or 0) for row in p.elements(versions[0]["id"])}
        return tally(diff_counts(before, after))

    def detail(project_id: str) -> dict:
        p = project(project_id)
        ev = evaluator()
        result = ev.evaluate(p)
        layers = p.layers()
        chosen = (p.settings().get("category_layers") or {})
        usage = getattr(ev, "layer_usage", {})
        used = category_usage(result["rows"])
        category_colors = []
        for cat in ev.categories:
            picked = pick_category_layer(cat.get("layer") or "", layers, usage.get(cat["id"], {}),
                                         chosen.get(cat["id"]) or None)
            category_colors.append({"id": cat["id"], "title": cat["title"], "parent": cat.get("parent"),
                                    "legend_layer": cat.get("layer") or "", **picked,
                                    **category_state(picked, layers, used.get(cat["id"], 0))})
        meta = p.meta()
        for plan in result["plans"]:
            plan["change_summary"] = _change_summary(p, plan["id"])
        return {"id": p.id, "meta": meta, "settings": p.settings(), "layers": layers,
                "category_colors": category_colors, "export_name": export_filename(meta),
                "folder": str(p.folder), **result}


    def version_pair(p, plan_id: int, older: int | None, newer: int | None) -> tuple[int | None, int | None]:
        versions = p.versions(plan_id)
        known = {v["id"] for v in versions}
        if older is None and newer is None:
            if len(versions) < 2:
                return None, None
            return versions[1]["id"], versions[0]["id"]
        if older is None or newer is None or older == newer or older not in known or newer not in known:
            raise HTTPException(400, "Die beiden Importe gehören nicht zu diesem Geschoss.")
        return older, newer

    @app.get("/api/projects")
    def list_projects() -> dict:
        m = manager()
        return {"folder": str(m.root), "folder_exists": m.root.is_dir(), "items": m.list()}

    @app.post("/api/projects")
    def create_project(body: ProjectIn) -> dict:
        try:
            p = manager().create(body.name, body.nova_version, body.template or None, body.project_number)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except KeyError:
            raise HTTPException(400, "Vorlagen-Projekt nicht gefunden") from None
        except OSError as exc:
            raise HTTPException(500, f"Projektordner nicht beschreibbar: {exc}") from None
        return detail(p.id)

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict:
        return detail(project_id)

    @app.put("/api/projects/{project_id}")
    def update_project(project_id: str, body: ProjectUpdate) -> dict:
        pid = project_id
        try:
            if body.name is not None:
                pid = manager().rename(project_id, body.name).id
            if body.project_number is not None:
                project(pid).set_meta(project_number=body.project_number.strip())
            if body.nova_version is not None:
                project(pid).set_meta(nova_version=body.nova_version)
            if body.use_as_template is not None:
                project(pid).set_meta(use_as_template=body.use_as_template)
        except KeyError:
            raise HTTPException(404, "Projekt nicht gefunden") from None
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from None
        return detail(pid)

    @app.post("/api/projects/{project_id}/copy")
    def copy_project(project_id: str, body: CopyIn) -> dict:
        try:
            p = manager().copy(project_id, body.name)
        except KeyError:
            raise HTTPException(404, "Projekt nicht gefunden") from None
        return detail(p.id)

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str) -> dict:
        try:
            target = manager().delete(project_id)
        except KeyError:
            raise HTTPException(404, "Projekt nicht gefunden") from None
        return {"ok": True, "moved_to": str(target)}

    @app.get("/api/projects/{project_id}/export")
    def export_project(project_id: str):
        p = project(project_id)
        tmp = Path(tempfile.mkdtemp(prefix="nl_export_"))
        target = tmp / export_filename(p.meta())
        manager().export_zip(project_id, target)
        return FileResponse(target, filename=target.name, media_type="application/zip",
                            background=BackgroundTask(shutil.rmtree, tmp, ignore_errors=True))

    # -- plans -------------------------------------------------------------------------

    @app.post("/api/projects/{project_id}/plans")
    async def import_plan(project_id: str, file: UploadFile = File(...), name: str = Form(""),
                          plan_id: int | None = Form(None)) -> dict:
        p = project(project_id)
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in FORMATS:
            raise HTTPException(400, "Nur DXF-, DWG- oder N4D-Dateien können importiert werden.")
        tmp = Path(tempfile.mkdtemp(prefix="nl_import_"))
        try:
            src = tmp / f"plan{suffix}"
            with open(src, "wb") as fh:
                shutil.copyfileobj(file.file, fh)
            try:
                if suffix == ".dxf":
                    result = read_dxf(src)
                elif suffix == ".n4d":
                    result = read_n4d(src)
                else:
                    result = read_dwg(src, st.settings.oda_path or config.find_oda_converter())
            except ConverterMissing as exc:
                raise HTTPException(400, str(exc)) from None
            except Exception as exc:  # noqa: BLE001 - any unreadable file
                raise HTTPException(400, f"Datei konnte nicht gelesen werden: {exc}") from None
            if plan_id is None:
                name = resolve_plan_name(file.filename or "", name)
                if not name.strip():
                    raise HTTPException(400, "Name des Plans fehlt (z. B. EG)")
                plan_id = p.add_plan(name.strip())
            elif plan_id not in {pl["id"] for pl in p.plans()}:
                raise HTTPException(404, "Plan nicht gefunden")
            p.store_import(plan_id, src, file.filename or f"plan{suffix}", result)
            st.company.learn_layer_colors({l.name: l.color for l in result.layers})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return detail(project_id)

    @app.put("/api/projects/{project_id}/plans/{plan_id}")
    def update_plan(project_id: str, plan_id: int, body: PlanUpdate) -> dict:
        project(project_id).update_plan(plan_id, name=body.name)
        return detail(project_id)

    @app.post("/api/projects/{project_id}/plans/reorder")
    def reorder_plans(project_id: str, body: ReorderPlans) -> dict:
        project(project_id).reorder_plans(body.ids)
        return detail(project_id)

    @app.delete("/api/projects/{project_id}/plans/{plan_id}")
    def delete_plan(project_id: str, plan_id: int) -> dict:
        project(project_id).delete_plan(plan_id)
        return detail(project_id)

    @app.post("/api/projects/{project_id}/plans/{plan_id}/detach")
    def detach_plan_file(project_id: str, plan_id: int) -> dict:
        project(project_id).detach_file(plan_id)
        return detail(project_id)

    @app.post("/api/projects/{project_id}/rows/delete")
    def delete_rows(project_id: str, body: SourcesIn) -> dict:
        project(project_id).delete_sources(body.source_keys)
        return detail(project_id)

    @app.put("/api/projects/{project_id}/category-layer")
    def category_layer(project_id: str, body: CategoryLayerIn) -> dict:
        p = project(project_id)
        chosen = dict(p.settings().get("category_layers") or {})
        if body.layer:
            chosen[body.category_id] = body.layer
        else:
            chosen.pop(body.category_id, None)
        p.set_settings({"category_layers": chosen})
        return detail(project_id)

    @app.get("/api/projects/{project_id}/plans/{plan_id}/versions")
    def plan_versions(project_id: str, plan_id: int) -> dict:
        return {"items": project(project_id).versions(plan_id)}

    def one_comparison(project_id: str, plan_id: int, older: int | None, newer: int | None) -> dict:
        p = project(project_id)
        plan = next((item for item in p.plans() if item["id"] == plan_id), None)
        if plan is None:
            raise HTTPException(404, "Plan nicht gefunden")
        old_id, new_id = version_pair(p, plan_id, older, newer)
        return evaluator().compare_plan(p, plan, old_id, new_id)

    @app.get("/api/projects/{project_id}/changes")
    def project_changes(project_id: str) -> dict:
        p = project(project_id)
        return {"plans": [one_comparison(project_id, plan["id"], None, None) for plan in p.plans()]}

    @app.get("/api/projects/{project_id}/plans/{plan_id}/changes")
    def plan_changes(project_id: str, plan_id: int, older: int | None = None, newer: int | None = None) -> dict:
        return {"plan": one_comparison(project_id, plan_id, older, newer)}

    # -- unknown elements --------------------------------------------------------------

    @app.get("/api/projects/{project_id}/suggestions")
    def suggestions(project_id: str, source_key: str) -> dict:
        try:
            return {"items": evaluator().suggestions(project(project_id), source_key)}
        except KeyError:
            raise HTTPException(404, "Element nicht gefunden") from None

    @app.put("/api/mappings")
    def set_mapping(body: MappingIn) -> dict:
        if body.symbol_key not in (None, IGNORE) and st.library.symbol(body.symbol_key) is None:
            raise HTTPException(400, "Symbol nicht in der Bibliothek")
        st.company.set_mapping(body.source_key, body.symbol_key, body.name)
        return {"ok": True}

    @app.get("/api/layer-colors")
    def layer_colors() -> dict:
        return st.company.layer_colors()
