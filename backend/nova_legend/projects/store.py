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


def export_filename(meta: dict) -> str:
    """ZIP name: edeco ag-<Bezeichnung>-projekt.zip."""
    label = (meta.get("name") or "Projekt").strip() or "Projekt"
    return f"{safe_folder_name('edeco ag-' + label + '-projekt')}.zip"


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _match_previous(found, pool: list[dict], used: set[int]) -> int | None:
    """Index of an existing row: catalogue code, then Bezeichnung, then name."""

    def free() -> list[int]:
        return [i for i in range(len(pool)) if i not in used]

    def pick(indices: list[int]) -> int | None:
        if not indices:
            return None
        used.add(indices[0])
        return indices[0]

    if found.item:
        by_code = [i for i in free() if (pool[i].get("item") or "") == found.item]
        if len(by_code) == 1:
            return pick(by_code)
        if len(by_code) > 1:
            if found.graphic_name:
                same = [i for i in by_code if _norm(pool[i].get("graphic_name")) == _norm(found.graphic_name)]
                if len(same) == 1:
                    return pick(same)
                if same and found.name:
                    named = [i for i in same if _norm(pool[i].get("name")) == _norm(found.name)]
                    if named:
                        return pick(named)
            if found.name:
                named = [i for i in by_code if _norm(pool[i].get("name")) == _norm(found.name)]
                if named:
                    return pick(named)
            return pick(by_code)
    if found.graphic_name:
        same = [i for i in free() if _norm(pool[i].get("graphic_name")) == _norm(found.graphic_name)]
        if same:
            return pick(same)
    if found.name:
        named = [i for i in free() if _norm(pool[i].get("name")) == _norm(found.name)]
        if named:
            return pick(named)
    same_key = [i for i in free() if pool[i].get("source_key") == found.source_key]
    return pick(same_key)


def merge_found(previous: list[dict], found_list) -> list[dict]:
    """Keep existing rows. New counts overwrite a match; missing rows stay at 0."""
    used: set[int] = set()
    merged: list[dict] = []
    for found in found_list:
        index = _match_previous(found, previous, used)
        old = previous[index] if index is not None else None
        merged.append({
            "source_key": old["source_key"] if old else found.source_key,
            "name": found.name or (old or {}).get("name") or "",
            "count": found.count,
            "dataset": found.dataset or (old or {}).get("dataset") or "",
            "item": found.item or (old or {}).get("item") or "",
            "sheet": found.sheet or (old or {}).get("sheet") or "",
            "graphic_name": found.graphic_name or (old or {}).get("graphic_name") or "",
            "graphic_id": found.graphic_id or (old or {}).get("graphic_id") or "",
            "layers": found.layers,
            "features": found.features,
        })
    for index, old in enumerate(previous):
        if index in used:
            continue
        merged.append({**old, "count": 0})
    return merged


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

    def _current_version_id(self, plan_id: int) -> int | None:
        with self.tx() as con:
            row = con.execute("SELECT current_version FROM plans WHERE id=?", (plan_id,)).fetchone()
        if not row or not row["current_version"]:
            return None
        return int(row["current_version"])

    def store_import(self, plan_id: int, source: Path, original_name: str, result) -> int:
        """Replace the one plan file of this floor and keep rows that the new file lacks.

        A new version is recorded, but only one file stays in Plaene. Counts of
        elements that disappeared become 0; their source key stays so a later
        import can fill the same row again.
        """
        previous_id = self._current_version_id(plan_id)
        previous = self.elements(previous_id) if previous_id else []
        old_stored = ""
        if previous_id:
            with self.tx() as con:
                row = con.execute("SELECT stored_file FROM plan_versions WHERE id=?",
                                  (previous_id,)).fetchone()
                old_stored = (row["stored_file"] or "") if row else ""
        plans_dir = self.folder / PLANS_DIR
        plans_dir.mkdir(parents=True, exist_ok=True)
        stored = plans_dir / f"{plan_id}_{safe_folder_name(original_name)}"
        shutil.copy2(source, stored)
        if old_stored:
            old_path = self.folder / old_stored
            if old_path.is_file() and old_path.resolve() != stored.resolve():
                old_path.unlink()
        rows = merge_found(previous, result.found)
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
                [(vid, row["source_key"], row["name"], row["count"], row["dataset"], row["item"],
                  row["sheet"], row["graphic_name"], row["graphic_id"],
                  json.dumps(row["layers"], ensure_ascii=False),
                  json.dumps(row["features"])) for row in rows])
            con.execute("UPDATE plans SET current_version=? WHERE id=?", (vid, plan_id))
            for layer in result.layers:
                con.execute("INSERT OR REPLACE INTO layers VALUES (?,?,?,?)",
                            (layer.name, layer.color, layer.linetype, result.format))
        return vid

    def detach_file(self, plan_id: int) -> None:
        """Delete the plan file. Elements, counts and the floor stay."""
        version_id = self._current_version_id(plan_id)
        if not version_id:
            return
        with self.tx() as con:
            row = con.execute("SELECT stored_file FROM plan_versions WHERE id=?", (version_id,)).fetchone()
            stored = (row["stored_file"] or "") if row else ""
            con.execute("UPDATE plan_versions SET file_name='', stored_file='' WHERE id=?", (version_id,))
        if stored:
            path = self.folder / stored
            if path.is_file():
                path.unlink()

    def delete_sources(self, source_keys: list[str]) -> None:
        """Remove rows from the current version of every floor."""
        if not source_keys:
            return
        with self.tx() as con:
            versions = [r["current_version"] for r in con.execute(
                "SELECT current_version FROM plans WHERE current_version IS NOT NULL")]
            for version_id in versions:
                for key in source_keys:
                    con.execute("DELETE FROM plan_elements WHERE version_id=? AND source_key=?",
                                (version_id, key))

    def import_ignored(self) -> dict[str, int]:
        """Non-apparatus counts of the current file of every floor, summed by name."""
        totals: dict[str, int] = {}
        with self.tx() as con:
            rows = con.execute("""
                SELECT v.ignored FROM plans p
                JOIN plan_versions v ON v.id = p.current_version
            """).fetchall()
        for row in rows:
            for name, count in json.loads(row["ignored"] or "{}").items():
                totals[name] = totals.get(name, 0) + int(count)
        return totals

    def version_ignored(self, version_id: int) -> dict[str, int]:
        with self.tx() as con:
            row = con.execute("SELECT ignored FROM plan_versions WHERE id=?", (version_id,)).fetchone()
        if not row:
            return {}
        return {name: int(count) for name, count in json.loads(row["ignored"] or "{}").items()}

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
                        "project_number": meta.get("project_number", ""),
                        "nova_version": meta.get("nova_version", ""),
                        "created_at": meta.get("created_at", ""), "created_by": meta.get("created_by", ""),
                        "template_from": meta.get("template_from", ""),
                        "use_as_template": meta.get("use_as_template", True) is not False,
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

    def create(self, name: str, nova_version: str, template: str | None = None,
               project_number: str = "") -> Project:
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
        project.set_meta(name=name, project_number=(project_number or "").strip(),
                         nova_version=nova_version, created_at=_now(),
                         created_by=current_user(), schema=SCHEMA_VERSION,
                         template_from=template or "", use_as_template=True)
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
