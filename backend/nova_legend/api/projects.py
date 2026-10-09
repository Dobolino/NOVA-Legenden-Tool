"""REST routes for projects, plans, import and element mappings."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import time
import uuid
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
from ..projects import preview
from ..projects.diff import diff_counts, tally
from ..projects.floors import resolve_plan_name
from ..projects.service import ProjectEvaluator
from ..projects.store import ProjectManager, export_filename, merge_found

FORMATS = {".dxf": "dxf", ".dwg": "dwg", ".n4d": "n4d", ".n4m": "n4m"}


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


class CommitIn(BaseModel):
    token: str


STAGE_SECONDS = 30 * 60     # a preview stays valid this long
STAGE_LIMIT = 20            # at most this many previewed files are kept


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def same_content(p, stored: str, src: Path) -> bool:
    """True if the upload is byte for byte the file of the current import."""
    if not stored:
        return False
    try:
        current = p._plan_file(stored)
        return current.is_file() and current.stat().st_size == src.stat().st_size and _sha256(current) == _sha256(src)
    except (ValueError, OSError):
        return False


class MappingIn(BaseModel):
    source_key: str
    symbol_key: str | None = None      # None = forget, "__ignore__" = not a symbol
    name: str = ""


def register(app: FastAPI, st) -> None:
    def manager() -> ProjectManager:
        # A shared folder is whatever the firm typed in. Empty: this computer only.
        folder = (st.settings.projects_folder or "").strip()
        root = Path(folder) if folder else config.local_home() / "Projekte"
        return ProjectManager(root)

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

    def category_colors(p, ev, result: dict | None = None) -> list[dict]:
        """Colour and layer state per category (after ev.evaluate, which fills layer_usage)."""
        if result is None:
            result = ev.evaluate(p)
        layers = p.layers()
        chosen = (p.settings().get("category_layers") or {})
        usage = getattr(ev, "layer_usage", {})
        used = category_usage(result["rows"])
        out = []
        for cat in ev.categories:
            picked = pick_category_layer(cat.get("layer") or "", layers, usage.get(cat["id"], {}),
                                         chosen.get(cat["id"]) or None)
            if cat.get("color"):
                # company colour of the category: the same in every project
                picked = {**picked, "color": cat["color"], "reason": "Firmenfarbe der Kategorie", "fixed": True}
            out.append({"id": cat["id"], "title": cat["title"], "parent": cat.get("parent"),
                        "legend_layer": cat.get("layer") or "", **picked,
                        **category_state(picked, layers, used.get(cat["id"], 0))})
        return out

    def detail(project_id: str) -> dict:
        p = project(project_id)
        ev = evaluator()
        result = ev.evaluate(p)
        layers = p.layers()
        category_colors_ = category_colors(p, ev, result)
        meta = p.meta()
        for plan in result["plans"]:
            plan["change_summary"] = _change_summary(p, plan["id"])
        return {"id": p.id, "meta": meta, "settings": p.settings(), "layers": layers,
                "category_colors": category_colors_, "export_name": export_filename(meta),
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
        return {"folder": str(m.root), "folder_exists": m.root.is_dir(),
                "shared": bool((st.settings.projects_folder or "").strip()), "items": m.list()}

    @app.post("/api/projects")
    def create_project(body: ProjectIn) -> dict:
        try:
            legend = st.company.legend_settings()
            p = manager().create(body.name, body.nova_version, body.template or None, body.project_number,
                                 legend_style={"text_size": legend["legend_text_size"],
                                               "symbol_scale": legend["legend_symbol_scale"], "columns": 2})
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

    def read_plan(src: Path, suffix: str):
        try:
            if suffix == ".dxf":
                return read_dxf(src)
            if suffix in (".n4d", ".n4m"):
                return read_n4d(src, FORMATS[suffix])
            return read_dwg(src, st.settings.oda_path or config.find_oda_converter())
        except ConverterMissing as exc:
            raise HTTPException(400, str(exc)) from None
        except Exception as exc:  # noqa: BLE001 - any unreadable file
            raise HTTPException(400, f"Datei konnte nicht gelesen werden: {exc}") from None

    def receive(file: UploadFile) -> tuple[Path, Path, str]:
        """Copy the upload into a temp folder. Returns (folder, file, suffix)."""
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in FORMATS:
            raise HTTPException(400, "Nur DXF-, DWG-, N4D- oder N4M-Dateien können importiert werden.")
        tmp = Path(tempfile.mkdtemp(prefix="nl_import_"))
        src = tmp / f"plan{suffix}"
        with open(src, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        return tmp, src, suffix

    def store(p, plan_id: int | None, name: str, filename: str, src: Path, suffix: str, result) -> None:
        if plan_id is None:
            name = resolve_plan_name(filename, name)
            if not name.strip():
                raise HTTPException(400, "Name des Plans fehlt (z. B. EG)")
            plan_id = p.add_plan(name.strip())
        elif plan_id not in {pl["id"] for pl in p.plans()}:
            raise HTTPException(404, "Plan nicht gefunden")
        try:
            p.store_import(plan_id, src, filename or f"plan{suffix}", result)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except OSError as exc:
            raise HTTPException(500, f"Plandatei konnte nicht gespeichert werden: {exc}") from None
        st.company.learn_layer_colors({l.name: l.color for l in result.layers})

    @app.post("/api/projects/{project_id}/plans")
    async def import_plan(project_id: str, file: UploadFile = File(...), name: str = Form(""),
                          plan_id: int | None = Form(None)) -> dict:
        p = project(project_id)
        tmp, src, suffix = receive(file)
        try:
            store(p, plan_id, name, file.filename or "", src, suffix, read_plan(src, suffix))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return detail(project_id)

    # -- import preview: read once, show the changes, store on confirmation ------------

    staged: dict[str, dict] = {}

    def drop_staged(token: str) -> None:
        entry = staged.pop(token, None)
        if entry:
            shutil.rmtree(entry["tmp"], ignore_errors=True)

    def expire_staged() -> None:
        now = time.monotonic()
        for token in [t for t, e in staged.items() if now - e["created"] > STAGE_SECONDS]:
            drop_staged(token)
        while len(staged) > STAGE_LIMIT:
            drop_staged(min(staged, key=lambda t: staged[t]["created"]))

    @app.post("/api/projects/{project_id}/plans/preview")
    async def preview_plan(project_id: str, file: UploadFile = File(...), name: str = Form(""),
                           plan_id: int | None = Form(None)) -> dict:
        """Read a plan file and show what it changes on its floor. Nothing is stored yet."""
        p = project(project_id)
        expire_staged()
        tmp, src, suffix = receive(file)
        try:
            result = read_plan(src, suffix)
            plans = {pl["id"]: pl for pl in p.plans()}
            if plan_id is not None and plan_id not in plans:
                raise HTTPException(404, "Plan nicht gefunden")
            plan = plans.get(plan_id) if plan_id is not None else None
            previous: list[dict] = []
            old_format, same_file = "", False
            if plan and plan.get("current_version"):
                previous = p.elements(plan["current_version"])
                current = next((v for v in p.versions(plan["id"]) if v["id"] == plan["current_version"]), {})
                old_format = current.get("format") or ""
                same_file = same_content(p, current.get("stored_file") or "", src)
            ev = evaluator()
            after_rows = merge_found(previous, result.found)
            compared = preview.compare(ev.summarize(previous), ev.summarize(after_rows))
            token = uuid.uuid4().hex
            staged[token] = {"project": p.id, "plan_id": plan_id, "name": name, "filename": file.filename or "",
                             # the floor as it was previewed: a later import makes this preview stale
                             "base_version": plan.get("current_version") if plan else None,
                             "src": src, "suffix": suffix, "result": result, "tmp": tmp,
                             "created": time.monotonic()}
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return {"token": token, "file_name": file.filename or "", "format": result.format,
                "plan": {"id": plan["id"], "name": plan["name"]} if plan else None,
                "floor": plan["name"] if plan else resolve_plan_name(file.filename or "", name),
                "existing": bool(previous), **compared,
                "warnings": preview.warnings(compared, bool(previous), old_format, result.format, same_file)}

    @app.post("/api/projects/{project_id}/plans/commit")
    def commit_plan(project_id: str, body: CommitIn) -> dict:
        """Store a previewed plan file. The token is valid for 30 minutes."""
        p = project(project_id)
        expire_staged()
        entry = staged.get(body.token)
        if not entry or entry["project"] != p.id:
            raise HTTPException(410, "Die Vorschau ist abgelaufen. Bitte die Datei noch einmal prüfen.")
        if entry["plan_id"] is not None:
            now = next((pl for pl in p.plans() if pl["id"] == entry["plan_id"]), None)
            if now is None or now.get("current_version") != entry["base_version"]:
                drop_staged(body.token)
                raise HTTPException(409, "Das Geschoss wurde seit der Vorschau geändert. Bitte die Datei noch einmal "
                                         "prüfen, damit du die aktuellen Änderungen siehst.")
        try:
            store(p, entry["plan_id"], entry["name"], entry["filename"], entry["src"], entry["suffix"],
                  entry["result"])
        finally:
            drop_staged(body.token)
        return detail(project_id)

    @app.delete("/api/projects/{project_id}/plans/preview/{token}")
    def discard_preview(project_id: str, token: str) -> dict:
        if staged.get(token, {}).get("project") == project(project_id).id:
            drop_staged(token)
        return {"ok": True}

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
        try:
            project(project_id).detach_file(plan_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except OSError as exc:
            raise HTTPException(500, f"Plandatei konnte nicht entfernt werden: {exc}") from None
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

    from .legend import register as register_legend
    register_legend(app, st, project, evaluator, category_colors)
