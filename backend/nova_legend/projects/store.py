"""Projects: one folder per project in the projects folder (shared drive).

    <projects folder>/<Projektname>/projekt.nlproj   SQLite file with all data
    <projects folder>/<Projektname>/Plaene/          copies of the imported plan files
    <projects folder>/_Geloescht/                    deleted projects (moved, not destroyed)

The project file stores plans (floors), each import as a version, the
elements found per version, the layers with colours and project settings.
A project can be copied, renamed, exported as one ZIP file and used as a
template for a new project (settings and legend layout, no plans).
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from ..config import current_user

PROJECT_FILE = "projekt.nlproj"
PLANS_DIR = "Plaene"
TRASH_DIR = "_Geloescht"
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, sort INTEGER,
    current_version INTEGER, created_at TEXT, created_by TEXT);
CREATE TABLE IF NOT EXISTS plan_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL,
    file_name TEXT, stored_file TEXT, format TEXT, imported_at TEXT, imported_by TEXT,
    info TEXT, ignored TEXT);
CREATE TABLE IF NOT EXISTS plan_elements (
    version_id INTEGER NOT NULL, source_key TEXT NOT NULL, name TEXT, count INTEGER,
    dataset TEXT, item TEXT, sheet TEXT, graphic_name TEXT, graphic_id TEXT,
    layers TEXT, features TEXT, PRIMARY KEY (version_id, source_key));
CREATE TABLE IF NOT EXISTS layers (
    name TEXT PRIMARY KEY, color TEXT, linetype TEXT, source TEXT);
"""

TEMPLATE_SETTINGS_EXCLUDE = {"name"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def safe_folder_name(name: str) -> str:
    """Folder name for a project: no characters Windows forbids."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(".")
    return cleaned or "Projekt"


class Project:
    """Access to one project file."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.file = self.folder / PROJECT_FILE

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.file, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=DELETE")
            con.execute("PRAGMA foreign_keys=ON")
            yield con
            con.commit()
        finally:
            con.close()

    @property
    def id(self) -> str:
        return self.folder.name

    # -- meta / settings ---------------------------------------------------------

    def meta(self) -> dict:
        with self.tx() as con:
            return {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT * FROM meta")}

    def set_meta(self, **values) -> None:
        with self.tx() as con:
            for k, v in values.items():
                con.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, json.dumps(v)))

    def settings(self) -> dict:
        with self.tx() as con:
            return {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT * FROM settings")}

    def set_settings(self, values: dict) -> None:
        with self.tx() as con:
            for k, v in values.items():
                con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, json.dumps(v)))

    # -- plans ---------------------------------------------------------------------

    def plans(self) -> list[dict]:
        with self.tx() as con:
            rows = con.execute("""
                SELECT p.*, v.file_name, v.format, v.imported_at, v.imported_by,
                       (SELECT COUNT(*) FROM plan_versions WHERE plan_id = p.id) AS versions
                FROM plans p LEFT JOIN plan_versions v ON v.id = p.current_version
                ORDER BY p.sort, p.id""").fetchall()
        return [dict(r) for r in rows]

    def add_plan(self, name: str) -> int:
        with self.tx() as con:
            sort = con.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM plans").fetchone()[0]
            cur = con.execute("INSERT INTO plans (name, sort, created_at, created_by) VALUES (?,?,?,?)",
                              (name, sort, _now(), current_user()))
            return int(cur.lastrowid)

    def update_plan(self, plan_id: int, name: str | None = None, sort: int | None = None) -> None:
        with self.tx() as con:
            if name is not None:
                con.execute("UPDATE plans SET name=? WHERE id=?", (name, plan_id))
            if sort is not None:
                con.execute("UPDATE plans SET sort=? WHERE id=?", (sort, plan_id))

    def reorder_plans(self, ids: list[int]) -> None:
        with self.tx() as con:
            for sort, pid in enumerate(ids):
                con.execute("UPDATE plans SET sort=? WHERE id=?", (sort, pid))

    def delete_plan(self, plan_id: int) -> None:
        with self.tx() as con:
            versions = [r["id"] for r in con.execute(
                "SELECT id FROM plan_versions WHERE plan_id=?", (plan_id,))]
            for vid in versions:
                con.execute("DELETE FROM plan_elements WHERE version_id=?", (vid,))
            con.execute("DELETE FROM plan_versions WHERE plan_id=?", (plan_id,))
            con.execute("DELETE FROM plans WHERE id=?", (plan_id,))

    def store_import(self, plan_id: int, source: Path, original_name: str, result) -> int:
        """Save an import as a new version of the plan (the file is copied)."""
        plans_dir = self.folder / PLANS_DIR
        plans_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        stored = plans_dir / f"{stamp}_{safe_folder_name(original_name)}"
        shutil.copy2(source, stored)
        with self.tx() as con:
            cur = con.execute(
                "INSERT INTO plan_versions (plan_id, file_name, stored_file, format, imported_at, "
                "imported_by, info, ignored) VALUES (?,?,?,?,?,?,?,?)",
                (plan_id, original_name, str(stored.relative_to(self.folder)), result.format, _now(),
                 current_user(), json.dumps(result.info, ensure_ascii=False, default=str),
                 json.dumps(result.ignored, ensure_ascii=False)))
            vid = int(cur.lastrowid)
            con.executemany(
                "INSERT INTO plan_elements VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(vid, f.source_key, f.name, f.count, f.dataset, f.item, f.sheet, f.graphic_name,
                  f.graphic_id, json.dumps(f.layers, ensure_ascii=False),
                  json.dumps(f.features)) for f in result.found])
            con.execute("UPDATE plans SET current_version=? WHERE id=?", (vid, plan_id))
            for layer in result.layers:
                con.execute("INSERT OR REPLACE INTO layers VALUES (?,?,?,?)",
                            (layer.name, layer.color, layer.linetype, result.format))
        return vid

    def versions(self, plan_id: int) -> list[dict]:
        with self.tx() as con:
            return [dict(r) for r in con.execute(
                "SELECT id, file_name, format, imported_at, imported_by FROM plan_versions "
                "WHERE plan_id=? ORDER BY id DESC", (plan_id,))]

    def elements(self, version_id: int) -> list[dict]:
        with self.tx() as con:
            rows = con.execute("SELECT * FROM plan_elements WHERE version_id=?", (version_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["layers"] = json.loads(d["layers"] or "{}")
            d["features"] = json.loads(d["features"] or "{}")
            out.append(d)
        return out

    def current_elements(self) -> dict[int, list[dict]]:
        return {p["id"]: self.elements(p["current_version"]) for p in self.plans()
                if p["current_version"]}

    def layers(self) -> list[dict]:
        with self.tx() as con:
            return [dict(r) for r in con.execute("SELECT * FROM layers ORDER BY name")]


class ProjectManager:
    """All projects in the projects folder."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        out = []
        for folder in sorted(self.root.iterdir(), key=lambda p: p.name.lower()):
            if folder.name.startswith("_") or not (folder / PROJECT_FILE).is_file():
                continue
            try:
                p = Project(folder)
                meta = p.meta()
                plans = p.plans()
            except sqlite3.Error:
                continue
            out.append({"id": p.id, "name": meta.get("name", p.id),
                        "nova_version": meta.get("nova_version", ""),
                        "created_at": meta.get("created_at", ""), "created_by": meta.get("created_by", ""),
                        "template_from": meta.get("template_from", ""),
                        "plan_count": len(plans),
                        "modified": datetime.fromtimestamp((folder / PROJECT_FILE).stat().st_mtime)
                        .isoformat(timespec="seconds")})
        return out

    def get(self, project_id: str) -> Project:
        folder = self.root / project_id
        if project_id.startswith("_") or "/" in project_id or "\\" in project_id \
                or not (folder / PROJECT_FILE).is_file():
            raise KeyError(project_id)
        return Project(folder)

    def _unique_folder(self, name: str) -> Path:
        base = safe_folder_name(name)
        folder = self.root / base
        n = 2
        while folder.exists():
            folder = self.root / f"{base} ({n})"
            n += 1
        return folder

    def create(self, name: str, nova_version: str, template: str | None = None) -> Project:
        name = name.strip()
        if not name:
            raise ValueError("Projektname fehlt")
        src = self.get(template) if template else None   # KeyError before anything is created
        self.ensure_root()
        folder = self._unique_folder(name)
        folder.mkdir(parents=True)
        project = Project(folder)
        with project.tx() as con:
            con.executescript(SCHEMA)
        project.set_meta(name=name, nova_version=nova_version, created_at=_now(),
                         created_by=current_user(), schema=SCHEMA_VERSION,
                         template_from=template or "")
        if src is not None:
            project.set_settings({k: v for k, v in src.settings().items()
                                  if k not in TEMPLATE_SETTINGS_EXCLUDE})
            with src.tx() as con:
                layers = con.execute("SELECT * FROM layers").fetchall()
            with project.tx() as con:
                for l in layers:
                    con.execute("INSERT OR REPLACE INTO layers VALUES (?,?,?,?)",
                                (l["name"], l["color"], l["linetype"], "Vorlage"))
        return project

    def rename(self, project_id: str, new_name: str) -> Project:
        project = self.get(project_id)
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Projektname fehlt")
        project.set_meta(name=new_name)
        target = self.root / safe_folder_name(new_name)
        if target != project.folder:
            if target.exists():
                target = self._unique_folder(new_name)
            project.folder.rename(target)
            project = Project(target)
        return project

    def copy(self, project_id: str, new_name: str) -> Project:
        src = self.get(project_id)
        new_name = new_name.strip() or f"{src.meta().get('name', project_id)} Kopie"
        target = self._unique_folder(new_name)
        shutil.copytree(src.folder, target)
        copy = Project(target)
        copy.set_meta(name=new_name, created_at=_now(), created_by=current_user(),
                      template_from=project_id)
        return copy

    def delete(self, project_id: str) -> Path:
        """Move the project to _Geloescht (can be restored by moving it back)."""
        project = self.get(project_id)
        trash = self.root / TRASH_DIR
        trash.mkdir(exist_ok=True)
        target = trash / f"{project.folder.name}_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
        shutil.move(str(project.folder), str(target))
        return target

    def export_zip(self, project_id: str, target: Path) -> Path:
        project = self.get(project_id)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in project.folder.rglob("*"):
                if path.is_file():
                    zf.write(path, Path(project.folder.name) / path.relative_to(project.folder))
        return target
