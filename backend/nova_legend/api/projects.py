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
from ..projects.service import ProjectEvaluator
from ..projects.store import ProjectManager

FORMATS = {".dxf": "dxf", ".dwg": "dwg", ".n4d": "n4d"}


class ProjectIn(BaseModel):
    name: str
    nova_version: str = "19.2"
    template: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    nova_version: str | None = None


class CopyIn(BaseModel):
    name: str = ""


class PlanUpdate(BaseModel):
    name: str | None = None


class ReorderPlans(BaseModel):
    ids: list[int]


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

    def detail(project_id: str) -> dict:
        p = project(project_id)
        result = evaluator().evaluate(p)
        colors = {l["name"]: l for l in p.layers()}
        return {"id": p.id, "meta": p.meta(), "settings": p.settings(), "layers": list(colors.values()),
                "folder": str(p.folder), **result}

    @app.get("/api/projects")
    def list_projects() -> dict:
        m = manager()
        return {"folder": str(m.root), "folder_exists": m.root.is_dir(), "items": m.list()}

    @app.post("/api/projects")
    def create_project(body: ProjectIn) -> dict:
        try:
            p = manager().create(body.name, body.nova_version, body.template or None)
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
            if body.nova_version is not None:
                project(pid).set_meta(nova_version=body.nova_version)
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
        target = tmp / f"{p.folder.name}.zip"
        manager().export_zip(project_id, target)
        return FileResponse(target, filename=target.name, media_type="application/zip",
                            background=BackgroundTask(shutil.rmtree, tmp, ignore_errors=True))

    # -- plans -------------------------------------------------------------------------

    @app.post("/api/projects/{project_id}/plans")
    async def import_plan(project_id: str, name: str = Form(...), file: UploadFile = File(...),
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

    @app.get("/api/projects/{project_id}/plans/{plan_id}/versions")
    def plan_versions(project_id: str, plan_id: int) -> dict:
        return {"items": project(project_id).versions(plan_id)}

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
