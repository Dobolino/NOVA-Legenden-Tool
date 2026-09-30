"""Company-wide categories and symbol assignments (firma.sqlite).

The file lives in the company folder (for example T:\\_CAD\\NOVA-Legenden)
so every user shares the same categories. SQLite on a network share is
safe for this use as long as writes are short and rare:

* journal_mode DELETE (WAL does not work on network shares)
* a new connection per operation, busy timeout 10 s
* every change records user and time
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from ..config import current_user
from .defaults import DEFAULT_CATEGORIES, NAME_RULES

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, parent TEXT, layer TEXT,
    columns INTEGER DEFAULT 2, spacing REAL DEFAULT 4.55, sort INTEGER,
    hidden INTEGER DEFAULT 0, sheets TEXT DEFAULT '[]',
    updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS assignments (
    family_key TEXT PRIMARY KEY, categories TEXT NOT NULL,
    updated_by TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS options (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS log (ts TEXT, user TEXT, action TEXT, detail TEXT);
"""

DEFAULT_OPTIONS = {
    "merge_labels": True,        # "(Ohne Text)" etc. under the UP representative
    "merge_orientation": False,  # liegend / stehend stay separate symbols
    "show_empty_categories": False,
    "legend_by_category": True,
}

CATEGORY_FIELDS = ("title", "parent", "layer", "columns", "spacing", "hidden", "sheets")


def normalize_sheets(values: list[str] | str) -> list[str]:
    """Clean number ranges: split on commas, trim, drop empty and duplicates."""
    parts = values.split(",") if isinstance(values, str) else [
        p for v in values for p in str(v).split(",")]
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CompanyStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as con:
            con.executescript(SCHEMA)
            if not con.execute("SELECT 1 FROM categories LIMIT 1").fetchone():
                self._seed(con)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.db_path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=DELETE")
            yield con
            con.commit()
        finally:
            con.close()

    def _log(self, con: sqlite3.Connection, action: str, detail: str) -> None:
        con.execute("INSERT INTO log VALUES (?,?,?,?)", (_now(), current_user(), action, detail))

    def _seed(self, con: sqlite3.Connection) -> None:
        for sort, cat in enumerate(DEFAULT_CATEGORIES):
            d = asdict(cat)
            con.execute(
                "INSERT INTO categories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (d["id"], d["title"], d["parent"], d["layer"], d["columns"], d["spacing_mm"],
                 sort, 0, json.dumps(d["sheets"]), "system", _now()))
        self._log(con, "seed", "Standardkategorien angelegt")

    # -- options ---------------------------------------------------------------

    def options(self) -> dict:
        with self._tx() as con:
            stored = {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT * FROM options")}
        return {**DEFAULT_OPTIONS, **stored}

    def set_options(self, values: dict) -> dict:
        with self._tx() as con:
            for key, value in values.items():
                if key in DEFAULT_OPTIONS:
                    con.execute("INSERT OR REPLACE INTO options VALUES (?,?)", (key, json.dumps(value)))
            self._log(con, "options", json.dumps(values, ensure_ascii=False))
        return self.options()

    # -- categories ------------------------------------------------------------

    def categories(self) -> list[dict]:
        with self._tx() as con:
            rows = con.execute("SELECT * FROM categories ORDER BY sort, title").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["sheets"] = json.loads(d["sheets"] or "[]")
            d["hidden"] = bool(d["hidden"])
            out.append(d)
        return out

    def create_category(self, title: str, parent: str | None = None, layer: str = "") -> dict:
        base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "kategorie"
        cat_id = f"{base}-{uuid.uuid4().hex[:6]}"
        with self._tx() as con:
            sort = con.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM categories").fetchone()[0]
            con.execute(
                "INSERT INTO categories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (cat_id, title, parent, layer, 2, 4.55, sort, 0, "[]", current_user(), _now()))
            self._log(con, "category.create", f"{cat_id} {title}")
        return next(c for c in self.categories() if c["id"] == cat_id)

    def update_category(self, cat_id: str, values: dict) -> dict:
        sets, args = [], []
        for key in CATEGORY_FIELDS:
            if key in values:
                value = values[key]
                if key == "sheets":
                    value = json.dumps(normalize_sheets(value))
                if key == "hidden":
                    value = int(bool(value))
                sets.append(f"{key}=?")
                args.append(value)
        if not sets:
            raise ValueError("Keine Änderung angegeben")
        with self._tx() as con:
            cur = con.execute(
                f"UPDATE categories SET {', '.join(sets)}, updated_by=?, updated_at=? WHERE id=?",
                (*args, current_user(), _now(), cat_id))
            if cur.rowcount == 0:
                raise KeyError(cat_id)
            self._log(con, "category.update", f"{cat_id} {json.dumps(values, ensure_ascii=False)}")
        return next(c for c in self.categories() if c["id"] == cat_id)

    def delete_category(self, cat_id: str) -> None:
        with self._tx() as con:
            cur = con.execute("DELETE FROM categories WHERE id=?", (cat_id,))
            if cur.rowcount == 0:
                raise KeyError(cat_id)
            con.execute("UPDATE categories SET parent=NULL WHERE parent=?", (cat_id,))
            # Remove the category from manual assignments
            for row in con.execute("SELECT family_key, categories FROM assignments").fetchall():
                cats = [c for c in json.loads(row["categories"]) if c != cat_id]
                if cats:
                    con.execute("UPDATE assignments SET categories=? WHERE family_key=?",
                                (json.dumps(cats), row["family_key"]))
                else:
                    con.execute("DELETE FROM assignments WHERE family_key=?", (row["family_key"],))
            self._log(con, "category.delete", cat_id)

    def reorder(self, ids: list[str]) -> list[dict]:
        with self._tx() as con:
            for sort, cat_id in enumerate(ids):
                con.execute("UPDATE categories SET sort=? WHERE id=?", (sort, cat_id))
            self._log(con, "category.reorder", ",".join(ids))
        return self.categories()

    def reset_defaults(self) -> list[dict]:
        with self._tx() as con:
            con.execute("DELETE FROM categories")
            con.execute("DELETE FROM assignments")
            self._seed(con)
        return self.categories()

    # -- assignments -------------------------------------------------------------

    def assignments(self) -> dict[str, list[str]]:
        with self._tx() as con:
            return {r["family_key"]: json.loads(r["categories"])
                    for r in con.execute("SELECT * FROM assignments")}

    def assign(self, family_key: str, category_ids: list[str] | None) -> None:
        """Set manual categories for a family. None or [] restores the automatic rule."""
        with self._tx() as con:
            if category_ids:
                con.execute("INSERT OR REPLACE INTO assignments VALUES (?,?,?,?)",
                            (family_key, json.dumps(category_ids), current_user(), _now()))
            else:
                con.execute("DELETE FROM assignments WHERE family_key=?", (family_key,))
            self._log(con, "assign", f"{family_key} -> {category_ids}")


def auto_categories(sheet: str, name: str, categories: list[dict]) -> tuple[list[str], str]:
    """Automatic rule: number range first, then name pattern, else Diverse."""
    ids = [c["id"] for c in categories if sheet in c["sheets"]]
    if ids:
        return ids, f"Nummernkreis {sheet}"
    low = name.lower()
    known = {c["id"] for c in categories}
    for pattern, cat_id in NAME_RULES:
        if cat_id in known and re.search(pattern, low):
            return [cat_id], "Namensmuster"
    fallback = "diverse" if "diverse" in known else (categories[-1]["id"] if categories else "")
    return ([fallback] if fallback else []), "keine Regel"
